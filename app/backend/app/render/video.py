import asyncio
import json
import re
import shutil
from pathlib import Path

import yaml
from jinja2 import ChoiceLoader, Environment, FileSystemLoader
from pydantic import ValidationError

from app import llm
from app.config import settings
from app.engine import looks
from app.render.clients import Deepgram, Frames, HeyGen, RenderError
from app.render.scenes import PipelineState, SceneStatus, shows_avatar

SPEC = "content.yaml"

INDEX = "index.html"

PREVIEW = "preview.html"

ASSETS = "assets"

RENDERS = "renders"

MP4 = "video.mp4"

TRANSCRIPTS = "transcripts.json"

STAGES = (
    "plan",
    "render_scenes",
    "sync_durations",
    "transcribe",
    "compose",
    "export",
)

MAX_ATTEMPTS = 3

MAX_CONCURRENT = 5

PLAN_MAX_TOKENS = 16000

FRAME_OVERLAP = 0.01

MAX_FORWARD_GAP = 1.8

FALLBACK_STEP = 0.18

MIN_MATCHED = 0.5

FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)

IMAGE_EXT = re.compile(r"\.(png|jpe?g|webp|gif|svg)$", re.I)

NUMBER_WORDS = {
    "zero": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
    "eleven": "11",
    "twelve": "12",
    "thirteen": "13",
    "fourteen": "14",
    "fifteen": "15",
    "sixteen": "16",
    "seventeen": "17",
    "eighteen": "18",
    "nineteen": "19",
    "twenty": "20",
    "thirty": "30",
    "forty": "40",
    "fifty": "50",
    "sixty": "60",
    "seventy": "70",
    "eighty": "80",
    "ninety": "90",
    "hundred": "100",
    "thousand": "1000",
}

NO_SCRIPT = (
    '\n\nEach scene needs a "script" field with natural spoken dialogue, '
    "conversational and in the brand's voice."
)

WITH_SCRIPT = (
    '\n\nThe script below is the one to use verbatim as the "script" fields. '
    "Split it across the scenes so each scene's script is a consecutive chunk "
    "of it. Do not rewrite, rephrase or summarise it, and design each scene's "
    "overlay copy to match the chunk it carries."
)

SHAPE = (
    "\n\nReturn ONLY a JSON object matching this JSON Schema. No prose, no "
    "markdown fences.\n\n"
)

REPAIR = (
    "\n\nThat failed validation:\n\n{problem}\n\nHere is what you returned:\n\n"
    "{answer}\n\nFix only the offending fields and return the corrected JSON "
    "object in full. No prose, no markdown fences."
)


def scene_file(index: int) -> str:
    return f"scene_{index + 1:02d}.mp4"


def _report(progress, stage):
    if progress:
        progress(stage)


def _write_spec(spec, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.dump(
            spec.model_dump(exclude_none=True),
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
        )
    )


async def plan(
    look: str,
    prompt: str,
    out_dir,
    *,
    script=None,
    looks_dir=None,
    validate=None,
    progress=None,
    client_override=None,
) -> object:
    _report(progress, STAGES[0])
    spec_model = looks.schema(look, looks_dir)
    system = (
        looks.prompt(look, looks_dir)
        + (WITH_SCRIPT if script else NO_SCRIPT)
        + SHAPE
        + json.dumps(spec_model.model_json_schema(), indent=2)
    )
    user = f"Topic: {prompt}\n\nSpoken script:\n{script}" if script else prompt

    refused = 0
    while True:
        answer = await llm.complete(
            system,
            user,
            model=settings.SKILL_MODEL,
            max_tokens=PLAN_MAX_TOKENS,
            client_override=client_override,
        )
        raw = FENCE.sub("", answer.strip())
        try:
            spec = spec_model(**json.loads(raw))
            if validate:
                validate(spec)
            break
        except (ValidationError, json.JSONDecodeError, RenderError) as problem:
            refused += 1
            if refused == MAX_ATTEMPTS:
                raise RenderError(
                    f"look {look!r} refused {MAX_ATTEMPTS} plans in a row: {problem}"
                ) from problem
            user = user + REPAIR.format(problem=problem, answer=raw)

    _write_spec(spec, Path(out_dir) / SPEC)
    return spec


async def _act(client, template_id, slots, index, scene, assets, state):
    entry = state.for_scene(index)
    entry.status = SceneStatus.rendering
    entry.source = "avatar"
    position = (scene.slot - 1) if scene.slot else index
    scene_id, variable = slots[position] if position < len(slots) else slots[-1]
    entry.video_id = await client.start(template_id, scene_id, scene.script, variable)
    finished = await client.wait(entry.video_id)
    url = finished.get("video_url") or finished.get("download_url")
    if not url:
        raise RenderError(f"scene {index + 1} finished with no video to download")
    dest = assets / scene_file(index)
    await client.fetch(url, dest)
    entry.status = SceneStatus.rendered
    entry.video_path = str(dest)
    entry.actual_duration = float(finished.get("duration", 0))


def _speech_transcript(index, script, timings) -> dict | None:
    words = [
        {
            "word": word["word"],
            "start": round(word["start"], 3),
            "end": round(word["end"], 3),
        }
        for word in timings or []
        if not (word["word"].startswith("<") and word["word"].endswith(">"))
    ]
    if not words:
        return None
    return {"scene": index + 1, "words": words, "text": script.strip()}


async def _speak(client, voice_id, index, scene, assets, state):
    entry = state.for_scene(index)
    entry.status = SceneStatus.rendering
    entry.source = "voice"
    spoken = await client.speak(voice_id, scene.script)
    if not spoken.get("audio_url"):
        raise RenderError(f"scene {index + 1} came back with no audio to speak")
    dest = assets / scene_file(index)
    await client.fetch(spoken["audio_url"], dest)
    entry.status = SceneStatus.rendered
    entry.video_path = str(dest)
    entry.actual_duration = float(spoken.get("duration", 0))
    entry.transcript = _speech_transcript(
        index, scene.script, spoken.get("word_timestamps")
    )


async def render_scenes(
    look: str,
    spec,
    out_dir,
    state: PipelineState,
    *,
    looks_dir=None,
    client=None,
    progress=None,
) -> None:
    _report(progress, STAGES[1])
    manifest = looks.load(look, looks_dir)
    assets = Path(out_dir) / ASSETS
    assets.mkdir(parents=True, exist_ok=True)

    todo = []
    for index in range(len(spec.scenes)):
        path = assets / scene_file(index)
        if path.exists():
            entry = state.for_scene(index)
            entry.status = SceneStatus.rendered
            entry.video_path = str(path)
            continue
        todo.append(index)
    if not todo:
        return

    voice_id = spec.voice or manifest.get("voice")
    voiced = {i for i in todo if voice_id and not shows_avatar(spec.scenes[i])}
    acted = [i for i in todo if i not in voiced]
    template_id = manifest.get("heygen_template")
    if acted and not template_id:
        raise RenderError(
            f"look {look!r} names no heygen_template and scene "
            f"{acted[0] + 1} shows the avatar, so there is nothing to act it with"
        )

    client = client or HeyGen()
    slots = await client.slots(template_id) if acted else []
    if acted and not slots:
        raise RenderError(
            f"HeyGen template {template_id} exposes no text variable, so there "
            "is nowhere to put the script"
        )
    declared = [
        shot["id"] for shot in getattr(looks.module(look, looks_dir), "SLOTS", [])
    ]
    if acted and declared and declared != [scene_id for scene_id, _ in slots]:
        raise RenderError(
            f"look {look!r} declares shots {declared} and HeyGen now reports "
            f"{[scene_id for scene_id, _ in slots]} — the template was re-cut"
        )

    gate = asyncio.Semaphore(MAX_CONCURRENT)

    async def one(index):
        async with gate:
            if index in voiced:
                await _speak(client, voice_id, index, spec.scenes[index], assets, state)
                return
            await _act(
                client, template_id, slots, index, spec.scenes[index], assets, state
            )

    await asyncio.gather(*[one(index) for index in todo])


def sync_durations(spec, state: PipelineState, yaml_path, *, progress=None) -> list:
    _report(progress, STAGES[2])
    updates = []
    for entry in state.scenes:
        if not entry.actual_duration:
            continue
        scene = spec.scenes[entry.index]
        was = scene.duration
        now = round(max(entry.actual_duration, scene.hold or 0), 2)
        if abs(was - now) > 0.001:
            scene.duration = now
            updates.append((entry.index + 1, was, now))
    if updates:
        _write_spec(spec, Path(yaml_path))
    return updates


async def transcribe(out_dir, state: PipelineState, *, client=None, progress=None):
    _report(progress, STAGES[3])
    assets = Path(out_dir) / ASSETS
    cache = assets / TRANSCRIPTS
    if cache.exists():
        for heard in json.loads(cache.read_text()):
            entry = state.for_scene(heard["scene"] - 1)
            entry.transcript = heard
            entry.status = SceneStatus.transcribed
        return

    heard_all = []
    for entry in sorted(state.scenes, key=lambda scene: scene.index):
        if entry.transcript:
            entry.status = SceneStatus.transcribed
            heard_all.append(entry.transcript)
            continue
        if not entry.video_path or not Path(entry.video_path).exists():
            continue
        client = client or Deepgram()
        heard = await client.listen(Path(entry.video_path).read_bytes())
        heard["scene"] = entry.index + 1
        entry.transcript = heard
        entry.status = SceneStatus.transcribed
        heard_all.append(heard)
    assets.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(heard_all, indent=2))


def _norm(word: str) -> str:
    plain = re.sub(r"[^a-z0-9]", "", word.lower())
    return NUMBER_WORDS.get(plain, plain)


def _spoken(transcript) -> list[tuple[str, float]]:
    if not transcript or not transcript.get("words"):
        return []
    return [
        (_norm(word["word"]), round(word["start"], 3)) for word in transcript["words"]
    ]


def match_word_timestamps(display_text: str, transcript) -> list[dict] | None:
    spoken = _spoken(transcript)
    if not spoken:
        return None

    found: list[dict] = []
    cursor = 0
    last = 0.0
    matched = 0
    for line_index, line in enumerate(display_text.split("\n")):
        for word in line.split():
            wanted = _norm(word)
            start = None
            for position in range(cursor, len(spoken)):
                near = matched == 0 or spoken[position][1] - last <= MAX_FORWARD_GAP
                if spoken[position][0] == wanted and near:
                    start = spoken[position][1]
                    cursor = position + 1
                    matched += 1
                    break
            if start is None:
                start = round(last + FALLBACK_STEP, 3)
            last = start
            found.append({"word": word, "start": start, "line": line_index})

    if not found or matched / len(found) < MIN_MATCHED:
        return None
    return found


def _locate(text: str, spoken, from_index: int = 0) -> tuple[float | None, int]:
    wanted = [word for word in (_norm(part) for part in text.split()) if word]
    if not wanted or not spoken:
        return None, from_index

    def best(lower: int):
        position, score = None, 0
        for start in range(lower, len(spoken)):
            hits = sum(
                1
                for offset, word in enumerate(wanted)
                if start + offset < len(spoken) and spoken[start + offset][0] == word
            )
            if hits > score:
                position, score = start, hits
        return position, score

    position, score = best(from_index)
    if not score and from_index:
        position, score = best(0)
    if not score:
        return None, from_index
    return spoken[position][1], position + 1


def _searchable(text: str) -> str:
    if IMAGE_EXT.search(text):
        text = re.sub(r"[-_]+", " ", IMAGE_EXT.sub("", text))
    return text


def content_cues(content, transcript) -> dict:
    spoken = _spoken(transcript)
    cues: dict = {}
    cursor = 0
    for name in getattr(content, "model_fields", {}):
        value = getattr(content, name, None)
        if isinstance(value, str):
            if not spoken:
                continue
            at, cursor = _locate(value, spoken, cursor)
            if at is not None:
                cues[name] = at
        elif isinstance(value, list) and all(isinstance(v, str) for v in value):
            times = []
            for entry in value:
                at = None
                if spoken:
                    at, cursor = _locate(_searchable(entry), spoken, cursor)
                times.append(at)
            cues[name] = times
    return cues


def _copy_frames(look_dir: Path, out_dir: Path) -> None:
    stills = look_dir / looks.FRAMES_DIR
    if not stills.is_dir():
        return
    dest = out_dir / looks.FRAMES_DIR
    dest.mkdir(parents=True, exist_ok=True)
    for still in stills.iterdir():
        if still.is_file() and not (dest / still.name).exists():
            shutil.copy2(still, dest / still.name)


def compose(
    look: str,
    spec,
    out_dir,
    state: PipelineState,
    *,
    looks_dir=None,
    stills: bool = False,
    progress=None,
) -> Path:
    _report(progress, STAGES[4])
    look_dir = looks.directory(look, looks_dir)
    imported = looks.module(look, looks_dir)
    transcripts = {
        entry.index + 1: entry.transcript for entry in state.scenes if entry.transcript
    }
    word_sync = getattr(imported, "WORD_SYNC", {})

    starts: list[float] = []
    running = 0.0
    for scene in spec.scenes:
        starts.append(round(running, 2))
        running += scene.duration
    durations = [
        round(scene.duration - FRAME_OVERLAP, 2)
        if position < len(spec.scenes) - 1
        else scene.duration
        for position, scene in enumerate(spec.scenes)
    ]

    drawn = []
    for position, scene in enumerate(spec.scenes):
        body = scene.model_dump()
        field = word_sync.get(scene.type)
        if field:
            body["word_timestamps"] = match_word_timestamps(
                getattr(scene.content, field), transcripts.get(position + 1)
            )
        body["cues"] = content_cues(scene.content, transcripts.get(position + 1))
        drawn.append(body)

    environment = Environment(
        loader=ChoiceLoader(
            [
                FileSystemLoader(look_dir),
                FileSystemLoader(looks.root(looks_dir) / looks.SHARED),
            ]
        ),
        keep_trailing_newline=True,
    )
    environment.filters.update(getattr(imported, "FILTERS", {}))
    markup = environment.get_template(looks.VIDEO_TEMPLATE)

    context = {
        **spec.model_dump(),
        "scenes": drawn,
        "starts": starts,
        "durations": durations,
        "total_duration": round(running, 2),
        "scene_types": {scene.type for scene in spec.scenes},
        "stills": stills,
    }

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    _copy_frames(look_dir, out_dir)
    preview = out_dir / PREVIEW
    preview.write_text(markup.render(**context, preview=True))
    if stills:
        return preview
    index = out_dir / INDEX
    index.write_text(markup.render(**context))
    return index


def storyboard(look: str, spec, out_dir, *, looks_dir=None, progress=None) -> Path:
    _report(progress, "storyboard")
    return compose(
        look, spec, out_dir, PipelineState(), looks_dir=looks_dir, stills=True
    )


def export(out_dir, *, name=MP4, client=None, progress=None) -> Path:
    _report(progress, STAGES[5])
    return (client or Frames()).export(Path(out_dir), name)


async def run(
    look: str,
    prompt: str,
    out_dir,
    *,
    draft: bool,
    script=None,
    looks_dir=None,
    progress=None,
    client_override=None,
    heygen=None,
    deepgram=None,
    frames=None,
) -> Path:
    out_dir = Path(out_dir)
    spec = await plan(
        look,
        prompt,
        out_dir,
        script=script,
        looks_dir=looks_dir,
        progress=progress,
        client_override=client_override,
    )
    if draft:
        return storyboard(look, spec, out_dir, looks_dir=looks_dir, progress=progress)

    state = PipelineState()
    await render_scenes(
        look,
        spec,
        out_dir,
        state,
        looks_dir=looks_dir,
        client=heygen,
        progress=progress,
    )
    sync_durations(spec, state, out_dir / SPEC, progress=progress)
    await transcribe(out_dir, state, client=deepgram, progress=progress)
    compose(look, spec, out_dir, state, looks_dir=looks_dir, progress=progress)
    return export(out_dir, client=frames, progress=progress)
