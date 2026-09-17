import base64
import json
from types import SimpleNamespace

import pytest
import pytest_asyncio
from sqlalchemy import select

from app import media
from app.config import settings
from app.engine import brand, calendar
from app.models import Asset, AssetVersion, SkillRun, SkillRunToolCall
from app.render.client import Painter, Render, RenderError
from app.skills import toolbelt

PNG = b"\x89PNG\r\n\x1a\nfake"
SHA = "a" * 64
STAT = {
    "stat": "27",
    "label": "tools, one connector each",
    "support": "Every record kept as it arrived.",
}
CAROUSEL = {
    "cover": {"title": "Where a number comes from", "kicker": "Three facts"},
    "slides": [{"title": f"Fact {n}", "body": "A body."} for n in (1, 2, 3)],
    "closing": {"title": "Open source", "cta": "Read the code"},
}
WIRE = [
    "brand_list",
    "brand_read",
    "brand_assets",
    "calendar_read",
    "looks_read",
    "assets_read",
    "transcript_read",
    "image_paint",
    "image_render",
    "carousel_render",
    "files_write",
]


class FakeShot:
    def __init__(self, raises=None):
        self.raises = raises
        self.posts = []

    async def post(self, url, json):
        self.posts.append((url, json))
        if self.raises:
            raise self.raises
        return SimpleNamespace(status_code=200, content=PNG, text="")


class FakePaint:
    def __init__(self, raises=None):
        self.raises = raises
        self.calls = []
        self.images = self

    async def generate(self, **kwargs):
        self.calls.append(kwargs)
        if self.raises:
            raise self.raises
        return SimpleNamespace(
            data=[SimpleNamespace(b64_json=base64.b64encode(PNG).decode())]
        )


async def _asset(session, version=1, **overrides):
    fields = {"name": "A card", "kind": "image", "skill": "dw-image", "origin": "chat"}
    asset = Asset(**{**fields, **overrides})
    session.add(asset)
    await session.flush()
    for number in range(1, version + 1):
        session.add(AssetVersion(asset_seq=asset.seq, version=number, note="ask"))
    await session.flush()
    return asset


async def _run(session, asset, version=1):
    run = SkillRun(
        skill=asset.skill,
        skill_sha=SHA,
        caller="chat",
        asset_seq=asset.seq,
        version=version,
        status="running",
    )
    session.add(run)
    await session.flush()
    return run


@pytest.fixture
def media_root(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "MEDIA_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture
def shot():
    return FakeShot()


@pytest.fixture
def paint():
    return FakePaint()


@pytest_asyncio.fixture
async def bench(session, media_root, shot, paint):
    asset = await _asset(session)
    run = await _run(session, asset)
    return toolbelt.Bench(
        session,
        run.seq,
        asset.seq,
        1,
        painter=Painter(paint),
        renderer=Render(shot),
    )


async def _rows(session, run_seq):
    query = select(SkillRunToolCall).where(SkillRunToolCall.skill_run_seq == run_seq)
    return (await session.execute(query)).scalars().all()


class TestTheBench:
    def test_a_bench_starts_empty_with_real_clients(self):
        bench = toolbelt.Bench(None, 1, 1, 1)
        assert isinstance(bench.painter, Painter)
        assert isinstance(bench.renderer, Render)
        assert (bench.written, bench.renders, bench.pictures, bench.read) == (
            [],
            {},
            {},
            [],
        )
        assert bench.stage is None

    def test_the_fence_is_the_studio_data_tag(self):
        assert toolbelt.FENCE_OPEN == "<studio_data>"
        assert toolbelt.FENCE_CLOSE == "</studio_data>"

    def test_a_refusal_is_a_runtime_error(self):
        assert issubclass(toolbelt.ToolRefused, RuntimeError)


class TestSchemas:
    def test_every_tool_goes_on_the_wire_with_an_underscore(self):
        schemas = toolbelt.schemas()
        assert [schema["name"] for schema in schemas] == WIRE
        for schema in schemas:
            assert schema["description"]
            assert schema["input_schema"]["type"] == "object"
            assert isinstance(schema["input_schema"]["properties"], dict)

    def test_the_tools_are_the_fixed_eleven(self):
        assert [name for name, _, _ in toolbelt.TOOLS] == [
            wire.replace("_", ".") for wire in WIRE
        ]

    def test_dotted_maps_a_wire_name_back(self):
        assert toolbelt.dotted("brand_read") == "brand.read"
        assert toolbelt.dotted("carousel_render") == "carousel.render"

    def test_an_unknown_wire_name_comes_back_unchanged(self):
        assert toolbelt.dotted("drop_everything") == "drop_everything"

    def test_every_tool_has_one_of_the_four_stages(self):
        assert set(toolbelt.STAGES) == {name for name, _, _ in toolbelt.TOOLS}
        assert set(toolbelt.STAGES.values()) == {
            "reading",
            "painting",
            "rendering",
            "writing",
        }


class TestCall:
    async def test_a_tool_the_model_invented_says_the_toolbelt_is_fixed(
        self, session, bench
    ):
        payload = await toolbelt.call(bench, "drop_everything", {})
        assert "fixed" in payload["error"]
        assert "drop_everything" in payload["error"]
        [row] = await _rows(session, bench.run_seq)
        assert (row.tool, row.ok) == ("drop_everything", False)
        assert row.detail == payload["error"]
        assert bench.stage is None

    async def test_a_call_writes_a_row_with_its_arguments_and_stage(
        self, session, bench
    ):
        payload = await toolbelt.call(bench, "brand_read", {"name": "voice"})
        assert payload["file"] == "voice.md"
        [row] = await _rows(session, bench.run_seq)
        assert (row.tool, row.ok) == ("brand_read", True)
        assert row.detail == json.dumps({"name": "voice"})
        assert row.duration_ms >= 0
        assert bench.stage == "reading"

    async def test_the_detail_is_cut_at_200_characters(self, session, bench):
        await toolbelt.call(bench, "files_write", {"path": "a.md", "text": "x" * 500})
        [row] = await _rows(session, bench.run_seq)
        assert len(row.detail) == 200

    async def test_a_dotted_name_is_accepted_too(self, bench):
        payload = await toolbelt.call(bench, "brand.list", None)
        assert payload["files"] == brand.files()

    async def test_bad_arguments_are_an_error_the_model_can_read(self, session, bench):
        payload = await toolbelt.call(bench, "brand_list", {"name": "voice"})
        assert "bad arguments" in payload["error"]
        [row] = await _rows(session, bench.run_seq)
        assert row.ok is False

    async def test_a_refusal_is_the_row_detail(self, session, bench):
        payload = await toolbelt.call(bench, "brand_read", {"name": "secrets"})
        assert "secrets" in payload["error"]
        [row] = await _rows(session, bench.run_seq)
        assert row.ok is False and row.detail == payload["error"]

    async def test_a_long_invented_name_fits_the_row(self, session, bench):
        await toolbelt.call(bench, "x" * 80, {})
        [row] = await _rows(session, bench.run_seq)
        assert row.tool == "x" * 64


class TestBrand:
    async def test_list_names_the_files_and_the_assets(self, bench):
        payload = await toolbelt.call(bench, "brand_list", {})
        assert payload == {
            "files": brand.files(),
            "assets": [asset["name"] for asset in brand.assets()],
        }
        assert bench.read == []

    @pytest.mark.parametrize("name", ["voice", "voice.md"])
    async def test_read_takes_the_name_with_or_without_the_suffix(self, bench, name):
        payload = await toolbelt.call(bench, "brand_read", {"name": name})
        assert payload["file"] == "voice.md"
        assert payload["front"]["title"]
        assert payload["body"].strip()

    async def test_a_read_is_evidence_once_per_file(self, bench):
        await toolbelt.call(bench, "brand_read", {"name": "voice"})
        await toolbelt.call(bench, "brand_read", {"name": "voice.md"})
        await toolbelt.call(bench, "brand_read", {"name": "proof"})
        assert [(item["kind"], item["ref"]) for item in bench.read] == [
            ("brand", "voice.md"),
            ("brand", "proof.md"),
        ]
        assert bench.read[0]["detail"] == brand.read("voice.md")[0]["title"]

    async def test_assets_carry_name_type_and_size(self, bench):
        payload = await toolbelt.call(bench, "brand_assets", {})
        assert payload["assets"] == [
            {"name": a["name"], "media_type": a["media_type"], "bytes": a["bytes"]}
            for a in brand.assets()
        ]


class TestCalendar:
    async def test_no_slot_reads_every_slot(self, bench):
        payload = await toolbelt.call(bench, "calendar_read", {})
        assert payload == {"slots": calendar.slots()}

    async def test_one_slot_is_read_by_name(self, bench):
        payload = await toolbelt.call(bench, "calendar_read", {"slot": "linkedin_post"})
        assert payload["slot"] == "linkedin_post"
        assert payload["kind"] == "post"
        assert payload["theme"]

    async def test_an_unknown_slot_is_refused_with_the_names(self, bench):
        payload = await toolbelt.call(bench, "calendar_read", {"slot": "tiktok"})
        assert "tiktok" in payload["error"]
        assert "linkedin_post" in payload["error"]


class TestLooks:
    async def test_a_look_reads_its_manifest_sample_and_layouts(self, bench):
        payload = await toolbelt.call(bench, "looks_read", {"name": "stat-card"})
        assert payload["name"] == "stat-card"
        assert payload["medium"] == "image"
        assert payload["sample"]["stat"]
        assert payload["layouts"].startswith("# stat-card")

    async def test_an_unknown_look_is_refused(self, bench):
        payload = await toolbelt.call(bench, "looks_read", {"name": "poster"})
        assert "poster" in payload["error"]


class TestAssets:
    async def test_the_latest_version_lists_files_and_reads_the_text_ones(
        self, session, bench
    ):
        earlier = await _asset(session, version=2, name="An earlier card")
        media.write(earlier.seq, 1, "post.md", "old words")
        media.write(earlier.seq, 2, "post.md", "new words")
        media.write(earlier.seq, 2, "image.png", PNG)
        payload = await toolbelt.call(bench, "assets_read", {"seq": earlier.seq})
        assert payload["seq"] == earlier.seq
        assert payload["name"] == "An earlier card"
        assert payload["version"] == 2
        assert payload["files"] == [
            {"path": "image.png", "media_type": "image/png", "bytes": len(PNG)},
            {
                "path": "post.md",
                "media_type": "text/markdown",
                "bytes": 9,
                "text": "new words",
            },
        ]
        assert bench.read == [
            {
                "kind": "asset",
                "ref": str(earlier.seq),
                "detail": "An earlier card, version 2",
            }
        ]

    async def test_the_version_being_built_is_never_the_one_read(
        self, session, media_root, shot, paint
    ):
        asset = await _asset(session, version=2)
        run = await _run(session, asset, version=2)
        media.write(asset.seq, 1, "content.yaml", "stat: '27'")
        bench = toolbelt.Bench(
            session,
            run.seq,
            asset.seq,
            2,
            painter=Painter(paint),
            renderer=Render(shot),
        )
        payload = await toolbelt.call(bench, "assets_read", {"seq": asset.seq})
        assert payload["version"] == 1
        assert payload["files"][0]["text"] == "stat: '27'"

    async def test_an_asset_with_no_earlier_version_is_refused(self, bench):
        payload = await toolbelt.call(bench, "assets_read", {"seq": bench.asset_seq})
        assert "earlier version" in payload["error"]

    async def test_an_unknown_seq_is_refused(self, bench):
        payload = await toolbelt.call(bench, "assets_read", {"seq": 999})
        assert "999" in payload["error"]

    @pytest.mark.parametrize("seq", ["latest", None])
    async def test_a_seq_that_is_not_a_number_is_refused(self, bench, seq):
        payload = await toolbelt.call(bench, "assets_read", {"seq": seq})
        assert "seq" in payload["error"]


class TestTranscript:
    async def test_no_ref_lists_the_meetings_by_name(self, bench, canonical):
        second = await canonical(
            "meeting", {"name": "Zed renewal", "transcript": "later"}
        )
        first = await canonical("meeting", {"name": "Acme kickoff", "transcript": "x"})
        await canonical("company", {"name": "Acme"})
        payload = await toolbelt.call(bench, "transcript_read", {})
        assert payload == {
            "meetings": [
                {"ref": str(first), "name": "Acme kickoff"},
                {"ref": str(second), "name": "Zed renewal"},
            ]
        }
        assert bench.read == []

    async def test_a_transcript_is_read_by_canonical_id(self, bench, canonical):
        cid = await canonical(
            "meeting", {"name": "Acme kickoff", "transcript": "We agreed on Monday."}
        )
        payload = await toolbelt.call(bench, "transcript_read", {"ref": str(cid)})
        assert payload == {
            "ref": str(cid),
            "name": "Acme kickoff",
            "transcript": "We agreed on Monday.",
        }
        assert bench.read == [
            {"kind": "transcript", "ref": str(cid), "detail": "Acme kickoff"}
        ]

    async def test_a_transcript_is_read_by_its_exact_name(self, bench, canonical):
        cid = await canonical("meeting", {"name": "Acme kickoff", "transcript": "x"})
        payload = await toolbelt.call(bench, "transcript_read", {"ref": "Acme kickoff"})
        assert payload["ref"] == str(cid)
        await toolbelt.call(bench, "transcript_read", {"ref": str(cid)})
        assert len(bench.read) == 1

    @pytest.mark.parametrize("ref", ["acme", "00000000-0000-0000-0000-000000000000"])
    async def test_an_unknown_meeting_is_refused(self, bench, canonical, ref):
        await canonical("meeting", {"name": "Acme kickoff", "transcript": "x"})
        payload = await toolbelt.call(bench, "transcript_read", {"ref": ref})
        assert ref in payload["error"]

    async def test_a_meeting_without_a_transcript_says_so(self, bench, canonical):
        await canonical("meeting", {"name": "Acme kickoff"})
        payload = await toolbelt.call(bench, "transcript_read", {"ref": "Acme kickoff"})
        assert "no transcript" in payload["error"]
        assert bench.read == []


class TestPaint:
    async def test_a_picture_is_kept_under_a_numbered_handle(self, bench, paint):
        first = await toolbelt.call(
            bench, "image_paint", {"prompt": "a harbour", "ratio": "4:5"}
        )
        second = await toolbelt.call(
            bench, "image_paint", {"prompt": "a field", "ratio": "1:1"}
        )
        assert first == {"picture": "picture-1"}
        assert second == {"picture": "picture-2"}
        assert bench.pictures == {"picture-1": PNG, "picture-2": PNG}
        assert [call["size"] for call in paint.calls] == ["1024x1280", "1024x1024"]
        assert bench.stage == "painting"

    async def test_an_empty_prompt_is_refused(self, bench, paint):
        payload = await toolbelt.call(
            bench, "image_paint", {"prompt": " ", "ratio": "1:1"}
        )
        assert "prompt" in payload["error"]
        assert paint.calls == []

    async def test_a_painter_failure_is_an_error_not_a_crash(
        self, session, media_root, shot
    ):
        asset = await _asset(session)
        run = await _run(session, asset)
        bench = toolbelt.Bench(
            session,
            run.seq,
            asset.seq,
            1,
            painter=Painter(FakePaint(raises=RenderError("quota"))),
            renderer=Render(shot),
        )
        payload = await toolbelt.call(
            bench, "image_paint", {"prompt": "a harbour", "ratio": "1:1"}
        )
        assert payload["error"] == "quota"
        assert bench.pictures == {}


class TestImageRender:
    async def test_a_card_is_rendered_over_the_picture(self, bench, shot):
        await toolbelt.call(
            bench, "image_paint", {"prompt": "a harbour", "ratio": "1:1"}
        )
        payload = await toolbelt.call(
            bench,
            "image_render",
            {
                "look": "stat-card",
                "fields": STAT,
                "ratio": "1:1",
                "picture": "picture-1",
            },
        )
        assert payload == {"render": "render-1"}
        assert bench.renders == {"render-1": PNG}
        [(_url, body)] = shot.posts
        assert "data:image/png;base64," in body["html"]
        assert (body["width"], body["height"]) == (1080, 1080)
        assert bench.stage == "rendering"

    async def test_a_card_renders_without_a_picture(self, bench, shot):
        payload = await toolbelt.call(
            bench,
            "image_render",
            {"look": "stat-card", "fields": STAT, "ratio": "9:16"},
        )
        assert payload == {"render": "render-1"}
        assert "data:image/png" not in shot.posts[0][1]["html"]

    async def test_an_unknown_picture_handle_is_refused(self, bench, shot):
        payload = await toolbelt.call(
            bench,
            "image_render",
            {
                "look": "stat-card",
                "fields": STAT,
                "ratio": "1:1",
                "picture": "picture-9",
            },
        )
        assert "picture-9" in payload["error"]
        assert shot.posts == []

    async def test_a_slot_over_its_max_is_refused_by_name(self, bench, shot):
        payload = await toolbelt.call(
            bench,
            "image_render",
            {
                "look": "stat-card",
                "fields": {**STAT, "label": "x" * 40},
                "ratio": "1:1",
            },
        )
        assert "'label'" in payload["error"] and "40" in payload["error"]
        assert bench.renders == {}


class TestCarouselRender:
    async def test_every_page_is_a_render_handle_in_order(self, bench, shot):
        await toolbelt.call(
            bench, "image_render", {"look": "stat-card", "fields": STAT, "ratio": "1:1"}
        )
        payload = await toolbelt.call(
            bench,
            "carousel_render",
            {"look": "carousel", "content": CAROUSEL, "ratio": "4:5"},
        )
        assert payload == {"renders": [f"render-{n}" for n in range(2, 7)]}
        assert len(bench.renders) == 6
        assert len(shot.posts) == 6
        assert bench.stage == "rendering"

    async def test_a_refused_slot_names_the_part(self, bench):
        content = {**CAROUSEL, "cover": {"title": "x" * 61, "kicker": "k"}}
        payload = await toolbelt.call(
            bench,
            "carousel_render",
            {"look": "carousel", "content": content, "ratio": "4:5"},
        )
        assert "cover" in payload["error"] and "'title'" in payload["error"]


class TestFilesWrite:
    async def test_text_is_written_under_the_asset_version(self, bench, media_root):
        payload = await toolbelt.call(
            bench, "files_write", {"path": "post.md", "text": "hello"}
        )
        assert payload == {"path": "post.md", "media_type": "text/markdown", "bytes": 5}
        stored = media_root / "assets" / str(bench.asset_seq) / "1" / "post.md"
        assert stored.read_text() == "hello"
        assert bench.written == [payload]
        assert bench.stage == "writing"

    async def test_a_render_handle_is_written_as_its_bytes(self, bench):
        await toolbelt.call(
            bench, "image_render", {"look": "stat-card", "fields": STAT, "ratio": "1:1"}
        )
        payload = await toolbelt.call(
            bench, "files_write", {"path": "image.png", "render": "render-1"}
        )
        assert payload == {
            "path": "image.png",
            "media_type": "image/png",
            "bytes": len(PNG),
        }
        assert media.read(bench.asset_seq, 1, "image.png") == PNG

    @pytest.mark.parametrize(
        "arguments",
        [
            {"path": "a.md"},
            {"path": "a.md", "text": "x", "render": "render-1"},
        ],
    )
    async def test_exactly_one_of_text_or_render(self, bench, arguments):
        payload = await toolbelt.call(bench, "files_write", arguments)
        assert "one of" in payload["error"]
        assert bench.written == []

    async def test_an_unknown_render_handle_is_refused(self, bench):
        payload = await toolbelt.call(
            bench, "files_write", {"path": "image.png", "render": "render-7"}
        )
        assert "render-7" in payload["error"]

    async def test_a_climbing_path_is_refused(self, bench, media_root):
        payload = await toolbelt.call(
            bench, "files_write", {"path": "../post.md", "text": "x"}
        )
        assert "climbs" in payload["error"]
        assert not (media_root / "post.md").exists()

    async def test_writing_a_path_again_keeps_one_entry_with_the_last_size(self, bench):
        await toolbelt.call(bench, "files_write", {"path": "post.md", "text": "one"})
        await toolbelt.call(bench, "files_write", {"path": "build.md", "text": "made"})
        await toolbelt.call(bench, "files_write", {"path": "post.md", "text": "three!"})
        assert [(item["path"], item["bytes"]) for item in bench.written] == [
            ("post.md", 6),
            ("build.md", 4),
        ]
