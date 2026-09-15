import json
import types

import httpx
import pytest
import yaml

from app.render import clients, scenes, video

MANIFEST = {
    "name": "demo",
    "medium": "video",
    "ratio": "9:16",
    "scenes": ["hook", "aside"],
    "heygen_template": "tmpl_9f2",
    "voice": "voice_1",
    "voice_confirmed": False,
    "limits_measured": "2026-09-01",
    "build": "2 HeyGen renders",
}

TEMPLATE_PY = '''
from typing import Literal

from pydantic import BaseModel, Field

from app.render.scenes import BaseContentSpec, BaseScene


class HookContent(BaseModel):
    headline: str = Field(..., max_length=12)


class AsideContent(BaseModel):
    note: str = Field(..., max_length=20)


class HookScene(BaseScene):
    type: Literal["hook"]
    content: HookContent


class AsideScene(BaseScene):
    type: Literal["aside"]
    background: Literal["solid"] = "solid"
    content: AsideContent


class ContentSpec(BaseContentSpec):
    scenes: list[HookScene | AsideScene]


PLANNER_PROMPT = "Write a hook and an aside."

SLOTS = [{"id": "s1", "pose": "to camera"}, {"id": "s2", "pose": "seated"}]

WORD_SYNC = {"hook": "headline"}


def shout(value):
    return str(value).upper()


FILTERS = {"shout": shout}
'''

BASE = """{% for scene in scenes %}
<div id="s{{ loop.index0 }}" data-start="{{ starts[loop.index0] }}"
     data-run="{{ durations[loop.index0] }}" data-cues="{{ scene.cues }}"
     data-words="{{ scene.word_timestamps }}">{{ scene.content.headline
     | default(scene.content.note) | shout }}</div>
{% endfor %}
<p data-total="{{ total_duration }}" data-stills="{{ stills }}"
   data-preview="{{ preview | default(false) }}">{{ project.name }}</p>
"""

SAMPLE = {
    "project": {"name": "demo", "resolution": "portrait"},
    "scenes": [
        {
            "type": "hook",
            "duration": 4.0,
            "script": "Ninety percent of it never gets read",
            "content": {"headline": "Hello"},
        },
        {
            "type": "aside",
            "duration": 3.0,
            "script": "And nobody notices",
            "content": {"note": "Nobody notices"},
        },
    ],
}


@pytest.fixture
def looks_dir(tmp_path):
    directory = tmp_path / "looks" / "demo"
    directory.mkdir(parents=True)
    (directory / "look.yaml").write_text(yaml.safe_dump(MANIFEST))
    (directory / "template.py").write_text(TEMPLATE_PY)
    (directory / "base.html.j2").write_text(BASE)
    (directory / "content.yaml").write_text(yaml.safe_dump(SAMPLE))
    return tmp_path / "looks"


@pytest.fixture
def spec(looks_dir):
    from app.engine import looks

    return looks.schema("demo", looks_dir)(**SAMPLE)


class FakeHeyGen:
    def __init__(self, slots=(("s1", "script_1"), ("s2", "script_2")), duration=5.25):
        self._slots = list(slots)
        self.duration = duration
        self.started: list[tuple] = []
        self.spoken: list[tuple] = []
        self.fetched: list[str] = []

    async def slots(self, template_id):
        self.asked = template_id
        return self._slots

    async def start(self, template_id, scene_id, script, variable):
        self.started.append((scene_id, script, variable))
        return f"vid_{scene_id}"

    async def wait(self, video_id):
        return {"video_url": f"https://heygen.test/{video_id}", "duration": self.duration}

    async def speak(self, voice_id, script):
        self.spoken.append((voice_id, script))
        return {
            "audio_url": "https://heygen.test/speech.wav",
            "duration": 2.5,
            "word_timestamps": [
                {"word": "<start>", "start": 0.0, "end": 0.0},
                {"word": "And", "start": 0.1, "end": 0.3},
                {"word": "nobody", "start": 0.3, "end": 0.6},
            ],
        }

    async def fetch(self, url, dest):
        self.fetched.append(url)
        dest.write_bytes(b"mp4")
        return dest


class FakeDeepgram:
    def __init__(self, words=None):
        self.heard: list[int] = []
        self.words = (
            words
            if words is not None
            else [
                {"word": "Ninety", "start": 0.1, "end": 0.4},
                {"word": "percent", "start": 0.4, "end": 0.8},
                {"word": "of", "start": 0.8, "end": 0.9},
                {"word": "it", "start": 0.9, "end": 1.0},
                {"word": "never", "start": 1.0, "end": 1.3},
                {"word": "gets", "start": 1.3, "end": 1.5},
                {"word": "read", "start": 1.5, "end": 1.8},
            ]
        )

    async def listen(self, audio):
        self.heard.append(len(audio))
        return {"words": self.words, "text": " ".join(w["word"] for w in self.words)}


class FakeFrames:
    def __init__(self, fail=False):
        self.fail = fail
        self.exported: list[tuple] = []

    def export(self, project_dir, name):
        self.exported.append((project_dir, name))
        if self.fail:
            raise clients.RenderError("exporter fell over")
        dest = project_dir / video.RENDERS / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"mp4")
        return dest


class FakeModel:
    def __init__(self, *answers, stop_reason="end_turn"):
        self.answers = list(answers)
        self.asked: list[dict] = []
        self.messages = types.SimpleNamespace(create=self._create)
        self.stop_reason = stop_reason

    async def _create(self, **kw):
        self.asked.append(kw)
        text = self.answers.pop(0)
        return types.SimpleNamespace(
            stop_reason=self.stop_reason,
            content=[types.SimpleNamespace(type="text", text=text)],
        )


def _plan_json(headline="Hello", note="Nobody notices"):
    return json.dumps(
        {
            "project": {"name": "demo", "resolution": "portrait"},
            "scenes": [
                {
                    "type": "hook",
                    "duration": 4.0,
                    "script": "one",
                    "content": {"headline": headline},
                },
                {
                    "type": "aside",
                    "duration": 3.0,
                    "script": "two",
                    "content": {"note": note},
                },
            ],
        }
    )


class TestTheSceneModels:
    def test_a_scene_over_video_shows_the_avatar(self):
        scene = scenes.BaseScene(type="hook", duration=1, script="hi")
        assert scenes.shows_avatar(scene) is True

    def test_a_scene_over_a_solid_page_hides_it(self):
        scene = scenes.BaseScene(
            type="hook", duration=1, script="hi", background="solid"
        )
        assert scenes.shows_avatar(scene) is False

    def test_a_state_entry_is_made_once_and_then_found(self):
        state = scenes.PipelineState()
        first = state.for_scene(2)
        assert state.for_scene(2) is first
        assert len(state.scenes) == 1


class TestPlanning:
    async def test_a_plan_is_validated_and_written_as_yaml(
        self, looks_dir, tmp_path, monkeypatch
    ):
        model = FakeModel(_plan_json())
        out = tmp_path / "out"
        spec = await video.plan(
            "demo", "an idea", out, looks_dir=looks_dir, client_override=model
        )
        assert spec.scenes[0].content.headline == "Hello"
        written = yaml.safe_load((out / video.SPEC).read_text())
        assert written["scenes"][1]["content"]["note"] == "Nobody notices"

    async def test_a_fenced_answer_is_unwrapped_rather_than_refused(
        self, looks_dir, tmp_path
    ):
        model = FakeModel(f"```json\n{_plan_json()}\n```")
        spec = await video.plan(
            "demo", "an idea", tmp_path / "out", looks_dir=looks_dir,
            client_override=model,
        )
        assert spec.scenes[0].content.headline == "Hello"

    async def test_copy_over_its_limit_is_handed_back_for_repair(
        self, looks_dir, tmp_path
    ):
        model = FakeModel(_plan_json(headline="far too long"), _plan_json())
        spec = await video.plan(
            "demo", "an idea", tmp_path / "out", looks_dir=looks_dir,
            client_override=model,
        )
        assert spec.scenes[0].content.headline == "Hello"
        assert len(model.asked) == 2
        assert "far too long" in model.asked[1]["messages"][0]["content"]

    async def test_a_plan_that_never_validates_is_one_render_error(
        self, looks_dir, tmp_path
    ):
        model = FakeModel(*[_plan_json(headline="far too long")] * video.MAX_ATTEMPTS)
        with pytest.raises(clients.RenderError) as caught:
            await video.plan(
                "demo", "an idea", tmp_path / "out", looks_dir=looks_dir,
                client_override=model,
            )
        assert "demo" in str(caught.value)
        assert len(model.asked) == video.MAX_ATTEMPTS

    async def test_an_answer_that_is_not_json_is_repaired_too(
        self, looks_dir, tmp_path
    ):
        model = FakeModel("not json at all", _plan_json())
        spec = await video.plan(
            "demo", "an idea", tmp_path / "out", looks_dir=looks_dir,
            client_override=model,
        )
        assert spec.scenes[0].content.headline == "Hello"

    async def test_a_supplied_script_must_survive_verbatim(self, looks_dir, tmp_path):
        model = FakeModel(_plan_json())
        await video.plan(
            "demo", "an idea", tmp_path / "out", script="say this exactly",
            looks_dir=looks_dir, client_override=model,
        )
        assert "verbatim" in model.asked[0]["system"]
        assert "say this exactly" in model.asked[0]["messages"][0]["content"]

    async def test_with_no_script_the_model_writes_the_dialogue(
        self, looks_dir, tmp_path
    ):
        model = FakeModel(_plan_json())
        await video.plan(
            "demo", "an idea", tmp_path / "out", looks_dir=looks_dir,
            client_override=model,
        )
        assert "spoken dialogue" in model.asked[0]["system"]

    async def test_a_measured_overflow_is_handed_back_like_any_other_refusal(
        self, looks_dir, tmp_path
    ):
        seen: list = []

        def measure(spec):
            seen.append(spec)
            if len(seen) == 1:
                raise clients.RenderError("headline overflows by 40px")

        model = FakeModel(_plan_json(), _plan_json())
        await video.plan(
            "demo", "an idea", tmp_path / "out", looks_dir=looks_dir,
            client_override=model, validate=measure,
        )
        assert len(model.asked) == 2
        assert "overflows" in model.asked[1]["messages"][0]["content"]

    async def test_the_stage_is_reported(self, looks_dir, tmp_path):
        seen: list[str] = []
        await video.plan(
            "demo", "an idea", tmp_path / "out", looks_dir=looks_dir,
            client_override=FakeModel(_plan_json()), progress=seen.append,
        )
        assert seen == ["plan"]


class TestRenderingTheScenes:
    async def test_an_acted_scene_goes_through_the_template(
        self, looks_dir, tmp_path, spec
    ):
        agent, state = FakeHeyGen(), scenes.PipelineState()
        out = tmp_path / "out"
        await video.render_scenes(
            "demo", spec, out, state, looks_dir=looks_dir, client=agent
        )
        assert agent.started == [("s1", spec.scenes[0].script, "script_1")]
        first = state.for_scene(0)
        assert first.status == scenes.SceneStatus.rendered
        assert first.source == "avatar"
        assert first.actual_duration == 5.25

    async def test_a_scene_that_hides_the_avatar_is_spoken_not_acted(
        self, looks_dir, tmp_path, spec
    ):
        agent, state = FakeHeyGen(), scenes.PipelineState()
        await video.render_scenes(
            "demo", spec, tmp_path / "out", state, looks_dir=looks_dir, client=agent
        )
        assert agent.spoken == [("voice_1", spec.scenes[1].script)]
        second = state.for_scene(1)
        assert second.source == "voice"
        assert [w["word"] for w in second.transcript["words"]] == ["And", "nobody"]

    async def test_a_scene_already_on_disk_is_adopted_rather_than_paid_for(
        self, looks_dir, tmp_path, spec
    ):
        out = tmp_path / "out"
        (out / video.ASSETS).mkdir(parents=True)
        for index in range(2):
            (out / video.ASSETS / video.scene_file(index)).write_bytes(b"mp4")
        agent, state = FakeHeyGen(), scenes.PipelineState()
        await video.render_scenes(
            "demo", spec, out, state, looks_dir=looks_dir, client=agent
        )
        assert agent.started == []
        assert agent.spoken == []
        assert state.for_scene(0).status == scenes.SceneStatus.rendered

    async def test_a_scene_may_name_the_shot_it_wants(self, looks_dir, tmp_path, spec):
        spec.scenes[0].slot = 2
        agent = FakeHeyGen()
        await video.render_scenes(
            "demo", spec, tmp_path / "out", scenes.PipelineState(),
            looks_dir=looks_dir, client=agent,
        )
        assert agent.started[0][0] == "s2"

    async def test_more_scenes_than_shots_reuse_the_last_one(
        self, looks_dir, tmp_path, spec
    ):
        spec.scenes[1].background = "video"
        agent = FakeHeyGen(slots=(("s1", "script_1"),))
        await video.render_scenes(
            "demo", spec, tmp_path / "out", scenes.PipelineState(),
            looks_dir=looks_dir, client=agent,
        )
        assert [started[0] for started in agent.started] == ["s1", "s1"]

    async def test_a_template_with_no_text_variable_is_refused(
        self, looks_dir, tmp_path, spec
    ):
        with pytest.raises(clients.RenderError) as caught:
            await video.render_scenes(
                "demo", spec, tmp_path / "out", scenes.PipelineState(),
                looks_dir=looks_dir, client=FakeHeyGen(slots=()),
            )
        assert "text variable" in str(caught.value)

    async def test_shots_recut_under_the_look_are_refused(
        self, looks_dir, tmp_path, spec
    ):
        agent = FakeHeyGen(slots=(("moved", "script_1"), ("s2", "script_2")))
        with pytest.raises(clients.RenderError) as caught:
            await video.render_scenes(
                "demo", spec, tmp_path / "out", scenes.PipelineState(),
                looks_dir=looks_dir, client=agent,
            )
        assert "moved" in str(caught.value)

    async def test_a_look_with_no_heygen_template_cannot_act_a_scene(
        self, looks_dir, tmp_path, spec
    ):
        manifest = {**MANIFEST, "heygen_template": None}
        (looks_dir / "demo" / "look.yaml").write_text(yaml.safe_dump(manifest))
        with pytest.raises(clients.RenderError) as caught:
            await video.render_scenes(
                "demo", spec, tmp_path / "out", scenes.PipelineState(),
                looks_dir=looks_dir, client=FakeHeyGen(),
            )
        assert "heygen_template" in str(caught.value)

    async def test_a_silent_look_needs_no_heygen_template_at_all(
        self, looks_dir, tmp_path, spec
    ):
        manifest = {**MANIFEST, "heygen_template": None}
        (looks_dir / "demo" / "look.yaml").write_text(yaml.safe_dump(manifest))
        for scene in spec.scenes:
            scene.background = "solid"
        agent, state = FakeHeyGen(), scenes.PipelineState()
        await video.render_scenes(
            "demo", spec, tmp_path / "out", state, looks_dir=looks_dir, client=agent
        )
        assert agent.started == []
        assert len(agent.spoken) == 2

    async def test_a_looks_voice_is_overridden_by_the_spec(
        self, looks_dir, tmp_path, spec
    ):
        spec.voice = "voice_2"
        agent = FakeHeyGen()
        await video.render_scenes(
            "demo", spec, tmp_path / "out", scenes.PipelineState(),
            looks_dir=looks_dir, client=agent,
        )
        assert agent.spoken[0][0] == "voice_2"

    async def test_a_look_with_no_voice_acts_every_scene(
        self, looks_dir, tmp_path, spec
    ):
        manifest = {**MANIFEST, "voice": None}
        (looks_dir / "demo" / "look.yaml").write_text(yaml.safe_dump(manifest))
        agent = FakeHeyGen()
        await video.render_scenes(
            "demo", spec, tmp_path / "out", scenes.PipelineState(),
            looks_dir=looks_dir, client=agent,
        )
        assert len(agent.started) == 2
        assert agent.spoken == []

    async def test_speech_with_no_audio_is_one_render_error(
        self, looks_dir, tmp_path, spec
    ):
        agent = FakeHeyGen()

        async def silent(voice_id, script):
            return {"duration": 0}

        agent.speak = silent
        with pytest.raises(clients.RenderError) as caught:
            await video.render_scenes(
                "demo", spec, tmp_path / "out", scenes.PipelineState(),
                looks_dir=looks_dir, client=agent,
            )
        assert "audio" in str(caught.value)

    async def test_speech_with_no_timings_leaves_the_transcript_to_deepgram(
        self, looks_dir, tmp_path, spec
    ):
        agent = FakeHeyGen()

        async def untimed(voice_id, script):
            return {"audio_url": "https://heygen.test/s.wav", "duration": 2.0}

        agent.speak = untimed
        state = scenes.PipelineState()
        await video.render_scenes(
            "demo", spec, tmp_path / "out", state, looks_dir=looks_dir, client=agent
        )
        assert state.for_scene(1).transcript is None

    async def test_every_scene_is_reported_as_it_moves(self, looks_dir, tmp_path, spec):
        seen: list[tuple] = []
        await video.render_scenes(
            "demo", spec, tmp_path / "out", scenes.PipelineState(),
            looks_dir=looks_dir, client=FakeHeyGen(),
            progress=lambda stage: seen.append(stage),
        )
        assert seen[0] == "render_scenes"


class TestSyncingDurations:
    def test_a_real_clip_length_replaces_the_planned_one(self, spec, tmp_path):
        state = scenes.PipelineState()
        state.for_scene(0).actual_duration = 5.25
        path = tmp_path / video.SPEC
        assert video.sync_durations(spec, state, path) == [(1, 4.0, 5.25)]
        assert spec.scenes[0].duration == 5.25
        assert yaml.safe_load(path.read_text())["scenes"][0]["duration"] == 5.25

    def test_a_hold_is_the_floor_however_short_the_audio(self, spec, tmp_path):
        spec.scenes[0].hold = 7.0
        state = scenes.PipelineState()
        state.for_scene(0).actual_duration = 5.25
        video.sync_durations(spec, state, tmp_path / video.SPEC)
        assert spec.scenes[0].duration == 7.0

    def test_nothing_measured_rewrites_nothing(self, spec, tmp_path):
        path = tmp_path / video.SPEC
        assert video.sync_durations(spec, scenes.PipelineState(), path) == []
        assert not path.exists()

    def test_a_length_that_already_agrees_rewrites_nothing(self, spec, tmp_path):
        state = scenes.PipelineState()
        state.for_scene(0).actual_duration = 4.0
        path = tmp_path / video.SPEC
        assert video.sync_durations(spec, state, path) == []
        assert not path.exists()


class TestTranscribing:
    async def test_every_rendered_scene_is_listened_to_once(self, tmp_path):
        out = tmp_path / "out"
        (out / video.ASSETS).mkdir(parents=True)
        state = scenes.PipelineState()
        path = out / video.ASSETS / video.scene_file(0)
        path.write_bytes(b"mp4-bytes")
        entry = state.for_scene(0)
        entry.video_path = str(path)
        entry.status = scenes.SceneStatus.rendered
        agent = FakeDeepgram()
        await video.transcribe(out, state, client=agent)
        assert agent.heard == [9]
        assert state.for_scene(0).status == scenes.SceneStatus.transcribed
        assert (out / video.ASSETS / video.TRANSCRIPTS).exists()

    async def test_a_second_run_reads_the_cache_rather_than_paying_again(
        self, tmp_path
    ):
        out = tmp_path / "out"
        (out / video.ASSETS).mkdir(parents=True)
        (out / video.ASSETS / video.TRANSCRIPTS).write_text(
            json.dumps([{"scene": 1, "words": [], "text": "hi"}])
        )
        state = scenes.PipelineState()
        agent = FakeDeepgram()
        await video.transcribe(out, state, client=agent)
        assert agent.heard == []
        assert state.for_scene(0).transcript["text"] == "hi"

    async def test_a_spoken_scene_keeps_the_timings_it_arrived_with(self, tmp_path):
        out = tmp_path / "out"
        (out / video.ASSETS).mkdir(parents=True)
        state = scenes.PipelineState()
        entry = state.for_scene(0)
        entry.transcript = {"scene": 1, "words": [{"word": "hi"}], "text": "hi"}
        entry.video_path = str(out / video.ASSETS / video.scene_file(0))
        agent = FakeDeepgram()
        await video.transcribe(out, state, client=agent)
        assert agent.heard == []
        assert state.for_scene(0).status == scenes.SceneStatus.transcribed

    async def test_a_scene_with_no_file_is_skipped(self, tmp_path):
        out = tmp_path / "out"
        (out / video.ASSETS).mkdir(parents=True)
        state = scenes.PipelineState()
        state.for_scene(0).video_path = str(out / video.ASSETS / "missing.mp4")
        agent = FakeDeepgram()
        await video.transcribe(out, state, client=agent)
        assert agent.heard == []

    async def test_a_scene_that_never_rendered_is_skipped(self, tmp_path):
        out = tmp_path / "out"
        (out / video.ASSETS).mkdir(parents=True)
        state = scenes.PipelineState()
        state.for_scene(0)
        await video.transcribe(out, state, client=FakeDeepgram())
        assert state.for_scene(0).transcript is None


class TestComposing:
    def _state(self, transcript=None):
        state = scenes.PipelineState()
        entry = state.for_scene(0)
        entry.transcript = transcript
        return state

    def test_both_files_are_written(self, looks_dir, tmp_path, spec):
        out = tmp_path / "out"
        index = video.compose("demo", spec, out, self._state(), looks_dir=looks_dir)
        assert index == out / video.INDEX
        assert (out / video.PREVIEW).exists()

    def test_scene_starts_accumulate_and_the_last_keeps_its_length(
        self, looks_dir, tmp_path, spec
    ):
        out = tmp_path / "out"
        video.compose("demo", spec, out, self._state(), looks_dir=looks_dir)
        markup = (out / video.INDEX).read_text()
        assert 'data-start="0.0"' in markup
        assert 'data-start="4.0"' in markup
        assert 'data-run="3.99"' in markup
        assert 'data-run="3.0"' in markup
        assert 'data-total="7.0"' in markup

    def test_the_looks_own_filters_are_available_to_its_markup(
        self, looks_dir, tmp_path, spec
    ):
        out = tmp_path / "out"
        video.compose("demo", spec, out, self._state(), looks_dir=looks_dir)
        assert "HELLO" in (out / video.INDEX).read_text()

    def test_a_word_synced_field_carries_the_transcripts_timings(
        self, looks_dir, tmp_path, spec
    ):
        spec.scenes[0].content.headline = "Ninety"
        transcript = {
            "words": [
                {"word": "Ninety", "start": 0.4, "end": 0.7},
                {"word": "percent", "start": 0.7, "end": 1.0},
            ]
        }
        out = tmp_path / "out"
        video.compose(
            "demo", spec, out, self._state(transcript), looks_dir=looks_dir
        )
        assert "0.4" in (out / video.INDEX).read_text()

    def test_stills_mode_writes_only_the_preview(self, looks_dir, tmp_path, spec):
        out = tmp_path / "out"
        preview = video.compose(
            "demo", spec, out, self._state(), looks_dir=looks_dir, stills=True
        )
        assert preview == out / video.PREVIEW
        assert not (out / video.INDEX).exists()
        assert 'data-stills="True"' in preview.read_text()

    def test_the_stage_is_reported(self, looks_dir, tmp_path, spec):
        seen: list[str] = []
        video.compose(
            "demo", spec, tmp_path / "out", self._state(), looks_dir=looks_dir,
            progress=seen.append,
        )
        assert seen == ["compose"]


class TestWordTimings:
    def test_displayed_words_are_matched_in_the_order_they_are_spoken(self):
        transcript = {
            "words": [
                {"word": "ninety", "start": 0.1, "end": 0.3},
                {"word": "percent", "start": 0.4, "end": 0.7},
            ]
        }
        found = video.match_word_timestamps("90 percent", transcript)
        assert [entry["start"] for entry in found] == [0.1, 0.4]

    def test_a_line_break_is_carried_through(self):
        transcript = {
            "words": [
                {"word": "one", "start": 0.1, "end": 0.2},
                {"word": "two", "start": 0.3, "end": 0.4},
            ]
        }
        found = video.match_word_timestamps("one\ntwo", transcript)
        assert [entry["line"] for entry in found] == [0, 1]

    def test_no_transcript_means_no_timings(self):
        assert video.match_word_timestamps("one two", None) is None
        assert video.match_word_timestamps("one two", {"words": []}) is None

    def test_mostly_paraphrased_copy_gives_the_look_its_own_stagger_back(self):
        transcript = {"words": [{"word": "one", "start": 0.1, "end": 0.2}]}
        assert video.match_word_timestamps("alpha beta gamma one", transcript) is None

    def test_an_unmatched_word_rides_just_behind_the_last_matched_one(self):
        transcript = {
            "words": [
                {"word": "one", "start": 0.1, "end": 0.2},
                {"word": "three", "start": 0.5, "end": 0.7},
            ]
        }
        found = video.match_word_timestamps("one two three", transcript)
        assert found[1]["start"] == pytest.approx(0.28)

    def test_a_word_spoken_much_later_is_not_latched_onto(self):
        transcript = {
            "words": [
                {"word": "one", "start": 0.1, "end": 0.2},
                {"word": "two", "start": 9.0, "end": 9.2},
            ]
        }
        found = video.match_word_timestamps("one two", transcript)
        assert found[1]["start"] < 1.0

    def test_a_field_is_cued_to_when_it_starts_being_spoken(self, spec):
        transcript = {
            "words": [
                {"word": "nobody", "start": 1.1, "end": 1.3},
                {"word": "notices", "start": 1.3, "end": 1.6},
            ]
        }
        cues = video.content_cues(spec.scenes[1].content, transcript)
        assert cues["note"] == 1.1

    def test_with_no_transcript_nothing_is_cued(self, spec):
        assert video.content_cues(spec.scenes[1].content, None) == {}

    def test_a_list_field_cues_every_entry_even_the_ones_it_cannot_place(self):
        class Listy:
            model_fields = {"items": None}
            items = ["carrot.png", "never said"]

        transcript = {"words": [{"word": "carrot", "start": 2.0, "end": 2.3}]}
        cues = video.content_cues(Listy(), transcript)
        assert cues["items"] == [2.0, None]

    def test_copy_nobody_said_is_left_out_of_the_cues(self, spec):
        transcript = {"words": [{"word": "unrelated", "start": 0.1, "end": 0.2}]}
        assert video.content_cues(spec.scenes[1].content, transcript) == {}


class TestExporting:
    def test_the_timeline_is_stepped_into_an_mp4(self, tmp_path):
        agent = FakeFrames()
        out = tmp_path / "out"
        out.mkdir()
        mp4 = video.export(out, client=agent)
        assert mp4.name == video.MP4
        assert agent.exported == [(out, video.MP4)]

    def test_an_exporter_that_falls_over_is_one_render_error(self, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        with pytest.raises(clients.RenderError):
            video.export(out, client=FakeFrames(fail=True))

    def test_the_stage_is_reported(self, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        seen: list[str] = []
        video.export(out, client=FakeFrames(), progress=seen.append)
        assert seen == ["export"]


class TestTheStoryboard:
    def test_a_draft_assembles_the_looks_own_frames_and_pays_nothing(
        self, looks_dir, tmp_path, spec
    ):
        out = tmp_path / "out"
        preview = video.storyboard("demo", spec, out, looks_dir=looks_dir)
        assert preview == out / video.PREVIEW
        assert not (out / video.INDEX).exists()

    async def test_a_draft_run_plans_and_storyboards_and_stops(
        self, looks_dir, tmp_path
    ):
        out = tmp_path / "out"
        seen: list[str] = []
        result = await video.run(
            "demo", "an idea", out, draft=True, looks_dir=looks_dir,
            client_override=FakeModel(_plan_json()), progress=seen.append,
        )
        assert result == out / video.PREVIEW
        assert seen == ["plan", "storyboard"]

    async def test_a_build_run_walks_every_stage_to_the_mp4(self, looks_dir, tmp_path):
        out = tmp_path / "out"
        seen: list[str] = []
        result = await video.run(
            "demo", "an idea", out, draft=False, looks_dir=looks_dir,
            client_override=FakeModel(_plan_json()), heygen=FakeHeyGen(),
            deepgram=FakeDeepgram(), frames=FakeFrames(), progress=seen.append,
        )
        assert result.name == video.MP4
        assert seen == list(video.STAGES)


def _heygen(handler):
    return clients.HeyGen(key="k", transport=httpx.MockTransport(handler))


class TestTheHeyGenSeam:
    async def test_the_slots_come_back_paired_with_their_text_variable(self):
        def handler(request):
            return httpx.Response(
                200,
                json={
                    "data": {
                        "name": "demo",
                        "scenes": [
                            {
                                "scene_id": "s1",
                                "variables": [
                                    {"name": "other", "variable_type": "text"},
                                    {"name": "script_1", "variable_type": "text"},
                                ],
                            },
                            {"scene_id": "s2", "variables": []},
                            {
                                "scene_id": "s3",
                                "variables": [
                                    {"name": "caption", "variable_type": "text"}
                                ],
                            },
                        ],
                    }
                },
            )

        found = await _heygen(handler).slots("tmpl_9f2")
        assert found == [("s1", "script_1"), ("s3", "caption")]

    async def test_a_render_returns_the_job_it_started(self):
        def handler(request):
            assert json.loads(request.content)["scene_ids"] == ["s1"]
            return httpx.Response(200, json={"data": {"id": "vid_1"}})

        assert await _heygen(handler).start("t", "s1", "hello", "script_1") == "vid_1"

    async def test_a_refused_render_is_one_render_error(self):
        def handler(request):
            return httpx.Response(429, text="slow down")

        with pytest.raises(clients.RenderError) as caught:
            await _heygen(handler).start("t", "s1", "hello", "script_1")
        assert "429" in str(caught.value)

    async def test_polling_stops_when_the_video_is_done(self):
        seen = {"n": 0}

        def handler(request):
            seen["n"] += 1
            status = "processing" if seen["n"] == 1 else "completed"
            return httpx.Response(
                200, json={"data": {"status": status, "video_url": "u", "duration": 3}}
            )

        result = await _heygen(handler).wait("vid_1", interval=0)
        assert result["video_url"] == "u"
        assert seen["n"] == 2

    async def test_a_failed_render_is_one_render_error(self):
        def handler(request):
            return httpx.Response(
                200, json={"data": {"status": "failed", "error": "bad script"}}
            )

        with pytest.raises(clients.RenderError) as caught:
            await _heygen(handler).wait("vid_1", interval=0)
        assert "bad script" in str(caught.value)

    async def test_a_render_that_never_finishes_is_one_render_error(self):
        def handler(request):
            return httpx.Response(200, json={"data": {"status": "processing"}})

        with pytest.raises(clients.RenderError) as caught:
            await _heygen(handler).wait("vid_1", interval=0, timeout=0)
        assert "timed out" in str(caught.value)

    async def test_speech_comes_back_with_its_own_timings(self):
        def handler(request):
            return httpx.Response(
                200, json={"data": {"audio_url": "u", "duration": 2.0}}
            )

        assert (await _heygen(handler).speak("v1", "hello"))["audio_url"] == "u"

    async def test_refused_speech_is_one_render_error(self):
        def handler(request):
            return httpx.Response(400, text="no such voice")

        with pytest.raises(clients.RenderError):
            await _heygen(handler).speak("v1", "hello")

    async def test_a_finished_asset_is_streamed_to_disk(self, tmp_path):
        def handler(request):
            return httpx.Response(200, content=b"mp4-bytes")

        dest = tmp_path / "scene.mp4"
        assert await _heygen(handler).fetch("https://heygen.test/a", dest) == dest
        assert dest.read_bytes() == b"mp4-bytes"

    async def test_an_asset_that_will_not_download_is_one_render_error(self, tmp_path):
        def handler(request):
            return httpx.Response(404)

        with pytest.raises(clients.RenderError):
            await _heygen(handler).fetch("https://heygen.test/a", tmp_path / "s.mp4")

    def test_no_key_is_a_refusal_rather_than_a_silent_skip(self, monkeypatch):
        monkeypatch.delenv(clients.HEYGEN_CREDENTIAL_ENV, raising=False)
        with pytest.raises(clients.RenderError) as caught:
            clients.HeyGen()
        assert clients.HEYGEN_CREDENTIAL_ENV in str(caught.value)

    def test_a_key_in_the_environment_is_picked_up(self, monkeypatch):
        monkeypatch.setenv(clients.HEYGEN_CREDENTIAL_ENV, "k")
        assert clients.HeyGen().key == "k"


class TestTheDeepgramSeam:
    async def test_word_level_timings_come_back(self):
        def handler(request):
            return httpx.Response(
                200,
                json={
                    "results": {
                        "channels": [
                            {
                                "alternatives": [
                                    {
                                        "transcript": "hello there",
                                        "words": [
                                            {
                                                "word": "hello",
                                                "start": 0.1234,
                                                "end": 0.4,
                                            }
                                        ],
                                    }
                                ]
                            }
                        ]
                    }
                },
            )

        agent = clients.Deepgram(key="k", transport=httpx.MockTransport(handler))
        heard = await agent.listen(b"audio")
        assert heard["text"] == "hello there"
        assert heard["words"][0]["start"] == 0.123

    async def test_a_refusal_is_one_render_error(self):
        def handler(request):
            return httpx.Response(401, text="bad key")

        agent = clients.Deepgram(key="k", transport=httpx.MockTransport(handler))
        with pytest.raises(clients.RenderError):
            await agent.listen(b"audio")

    def test_no_key_is_a_refusal_rather_than_a_silent_skip(self, monkeypatch):
        monkeypatch.delenv(clients.DEEPGRAM_CREDENTIAL_ENV, raising=False)
        with pytest.raises(clients.RenderError) as caught:
            clients.Deepgram()
        assert clients.DEEPGRAM_CREDENTIAL_ENV in str(caught.value)


class TestTheFrameExporterSeam:
    def test_the_exporter_is_run_in_the_project_and_writes_the_mp4(self, tmp_path):
        calls: list = []

        def runner(command, **kw):
            calls.append((command, kw))
            dest = tmp_path / video.RENDERS / video.MP4
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b"mp4")
            return types.SimpleNamespace(returncode=0, stderr="")

        mp4 = clients.Frames(runner=runner).export(tmp_path, video.MP4)
        assert mp4.read_bytes() == b"mp4"
        assert calls[0][1]["cwd"] == tmp_path
        assert (tmp_path / clients.FRAMES_CONFIG).exists()

    def test_a_non_zero_exit_is_one_render_error(self, tmp_path):
        def runner(command, **kw):
            return types.SimpleNamespace(returncode=1, stderr="no such block")

        with pytest.raises(clients.RenderError) as caught:
            clients.Frames(runner=runner).export(tmp_path, video.MP4)
        assert "no such block" in str(caught.value)

    def test_an_exit_of_zero_with_no_file_is_one_render_error(self, tmp_path):
        def runner(command, **kw):
            return types.SimpleNamespace(returncode=0, stderr="")

        with pytest.raises(clients.RenderError):
            clients.Frames(runner=runner).export(tmp_path, video.MP4)

    def test_an_existing_config_is_left_alone(self, tmp_path):
        (tmp_path / clients.FRAMES_CONFIG).write_text("{}")

        def runner(command, **kw):
            dest = tmp_path / video.RENDERS / video.MP4
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b"mp4")
            return types.SimpleNamespace(returncode=0, stderr="")

        clients.Frames(runner=runner).export(tmp_path, video.MP4)
        assert (tmp_path / clients.FRAMES_CONFIG).read_text() == "{}"
