import httpx
import pytest
import pytest_asyncio
import yaml

from app.db import get_session
from app.engine import checks, looks
from app.main import app
from app.models import Asset, AssetFile

VIDEO_MANIFEST = {
    "name": "demo",
    "medium": "video",
    "ratio": "9:16",
    "scenes": ["hook"],
    "heygen_template": None,
    "voice": None,
    "voice_confirmed": False,
    "limits_measured": "2026-09-01",
    "build": "composed locally, no renders",
}

IMAGE_MANIFEST = {
    "name": "card",
    "medium": "image",
    "ratio": "1:1",
    "slots": [{"name": "stat", "max": 6}, {"name": "label", "max": 10}],
    "limits_measured": "2026-09-01",
    "build": "one background call",
}

TEMPLATE_PY = """
from typing import Literal

from pydantic import BaseModel, Field

from app.render.scenes import BaseContentSpec, BaseScene


class HookContent(BaseModel):
    headline: str = Field(..., max_length=12)


class HookScene(BaseScene):
    type: Literal["hook"]
    background: Literal["solid"] = "solid"
    script: str = ""
    content: HookContent


class ContentSpec(BaseContentSpec):
    scenes: list[HookScene]


PLANNER_PROMPT = "Write one hook."
"""

VIDEO_SAMPLE = {
    "project": {"name": "demo", "resolution": "portrait"},
    "scenes": [{"type": "hook", "duration": 4.0, "content": {"headline": "Hello"}}],
}

IMAGE_SAMPLE = {"stat": "29", "label": "ads live"}


def _video_look(root, name="demo", manifest=None, sample=None, omit=()):
    directory = root / "looks" / name
    directory.mkdir(parents=True, exist_ok=True)
    body = dict(VIDEO_MANIFEST if manifest is None else manifest)
    if "look.yaml" not in omit:
        (directory / "look.yaml").write_text(yaml.safe_dump(body))
    if "base.html.j2" not in omit:
        (directory / "base.html.j2").write_text("<p>{{ scenes | length }}</p>")
    if "template.py" not in omit:
        (directory / "template.py").write_text(TEMPLATE_PY)
    if "content.yaml" not in omit:
        (directory / "content.yaml").write_text(
            yaml.safe_dump(VIDEO_SAMPLE if sample is None else sample)
        )
    return root / "looks"


def _image_look(root, name="card", manifest=None, sample=None, omit=()):
    directory = root / "looks" / name
    directory.mkdir(parents=True, exist_ok=True)
    body = dict(IMAGE_MANIFEST if manifest is None else manifest)
    if "look.yaml" not in omit:
        (directory / "look.yaml").write_text(yaml.safe_dump(body))
    if "card.html.j2" not in omit:
        (directory / "card.html.j2").write_text("<p>{{ slots.stat }}</p>")
    if "content.yaml" not in omit:
        (directory / "content.yaml").write_text(
            yaml.safe_dump(IMAGE_SAMPLE if sample is None else sample)
        )
    return root / "looks"


class TestTheShippedLooks:
    def test_the_shipped_directory_has_no_problems(self):
        assert looks.check() == []

    def test_every_shipped_look_is_named(self):
        assert looks.names() == ["aios", "soda", "square-stat"]

    def test_the_shared_partials_are_not_a_look(self):
        assert "_shared" not in looks.names()

    @pytest.mark.parametrize("name", ["aios", "soda"])
    def test_a_video_look_carries_its_scene_vocabulary(self, name):
        manifest = looks.load(name)
        assert manifest["medium"] == "video"
        assert manifest["scenes"]

    def test_the_video_schema_comes_from_the_looks_own_template(self):
        spec = looks.schema("aios")
        assert "scenes" in spec.model_fields

    def test_the_image_look_declares_slots_rather_than_scenes(self):
        manifest = looks.load("square-stat")
        assert manifest["medium"] == "image"
        assert [slot["name"] for slot in manifest["slots"]] == [
            "stat",
            "label",
            "support",
            "mark",
        ]

    def test_the_calendars_video_look_is_one_we_ship(self):
        assert "aios" in looks.names()

    @pytest.mark.parametrize("name", ["aios", "soda", "square-stat"])
    def test_every_ratio_is_one_the_renderer_knows_the_frame_for(self, name):
        assert looks.frame(name) in looks.FRAMES.values()


class TestLoadingOneLook:
    def test_the_manifest_comes_back_as_written(self, tmp_path):
        directory = _video_look(tmp_path)
        assert looks.load("demo", directory)["name"] == "demo"

    def test_a_look_nobody_has_is_refused_by_name(self, tmp_path):
        directory = _video_look(tmp_path)
        with pytest.raises(looks.LookError) as caught:
            looks.load("ghost", directory)
        assert "ghost" in str(caught.value)

    def test_names_is_empty_when_there_is_no_looks_directory(self, tmp_path):
        assert looks.names(tmp_path / "nothing") == []

    def test_the_sample_spec_validates_against_the_looks_own_schema(self, tmp_path):
        directory = _video_look(tmp_path)
        spec = looks.schema("demo", directory)(**looks.sample("demo", directory))
        assert spec.scenes[0].content.headline == "Hello"

    def test_an_image_look_has_no_python_schema_to_import(self, tmp_path):
        directory = _image_look(tmp_path)
        with pytest.raises(looks.LookError):
            looks.schema("card", directory)

    def test_the_frame_is_the_pixels_the_ratio_names(self, tmp_path):
        directory = _image_look(tmp_path)
        assert looks.frame("card", directory) == (1080, 1080)

    def test_the_limits_are_read_off_an_image_looks_slots(self, tmp_path):
        directory = _image_look(tmp_path)
        assert looks.limits("card", directory) == {"stat": 6, "label": 10}


class TestTheDirectoryIsChecked:
    def test_a_complete_pair_of_looks_has_no_problems(self, tmp_path):
        _video_look(tmp_path)
        assert looks.check(_image_look(tmp_path)) == []

    def test_a_missing_looks_directory_is_one_problem(self, tmp_path):
        problems = looks.check(tmp_path / "looks")
        assert len(problems) == 1, problems
        assert "looks" in problems[0]

    def test_a_directory_with_no_manifest_is_named(self, tmp_path):
        directory = _video_look(tmp_path, omit=("look.yaml",))
        problems = looks.check(directory)
        assert any("look.yaml" in p and "demo" in p for p in problems), problems

    def test_a_manifest_that_is_not_a_mapping_is_named(self, tmp_path):
        directory = _video_look(tmp_path)
        (directory / "demo" / "look.yaml").write_text("- not a mapping\n")
        problems = looks.check(directory)
        assert any("demo" in p for p in problems), problems

    def test_a_medium_nothing_renders_is_named(self, tmp_path):
        directory = _video_look(tmp_path, manifest={**VIDEO_MANIFEST, "medium": "gif"})
        problems = looks.check(directory)
        assert any("gif" in p for p in problems), problems

    def test_a_ratio_no_feed_shows_is_named(self, tmp_path):
        directory = _video_look(tmp_path, manifest={**VIDEO_MANIFEST, "ratio": "3:2"})
        problems = looks.check(directory)
        assert any("3:2" in p for p in problems), problems

    def test_a_video_look_with_no_markup_is_named(self, tmp_path):
        directory = _video_look(tmp_path, omit=("base.html.j2",))
        problems = looks.check(directory)
        assert any("base.html.j2" in p for p in problems), problems

    def test_a_video_look_with_no_schema_is_named(self, tmp_path):
        directory = _video_look(tmp_path, omit=("template.py",))
        problems = looks.check(directory)
        assert any("template.py" in p for p in problems), problems

    def test_a_schema_missing_the_expected_symbols_is_named(self, tmp_path):
        directory = _video_look(tmp_path)
        (directory / "demo" / "template.py").write_text("ContentSpec = None\n")
        problems = looks.check(directory)
        assert any("PLANNER_PROMPT" in p for p in problems), problems

    def test_a_schema_that_will_not_import_is_named(self, tmp_path):
        directory = _video_look(tmp_path)
        (directory / "demo" / "template.py").write_text("import nothing_at_all\n")
        problems = looks.check(directory)
        assert any("demo" in p for p in problems), problems

    def test_an_image_look_with_no_template_file_is_named(self, tmp_path):
        directory = _image_look(tmp_path, omit=("card.html.j2",))
        problems = looks.check(directory)
        assert any("card.html.j2" in p for p in problems), problems

    def test_an_image_look_whose_slots_are_not_a_list_is_named(self, tmp_path):
        directory = _image_look(tmp_path, manifest={**IMAGE_MANIFEST, "slots": "stat"})
        problems = looks.check(directory)
        assert any("slots" in p for p in problems), problems

    def test_an_image_slot_with_no_limit_is_named(self, tmp_path):
        manifest = {**IMAGE_MANIFEST, "slots": [{"name": "stat"}]}
        problems = looks.check(_image_look(tmp_path, manifest=manifest))
        assert any("stat" in p for p in problems), problems

    def test_a_sample_missing_from_a_look_is_named(self, tmp_path):
        directory = _video_look(tmp_path, omit=("content.yaml",))
        problems = looks.check(directory)
        assert any("content.yaml" in p for p in problems), problems

    def test_a_sample_that_fails_its_own_schema_is_named(self, tmp_path):
        sample = {
            "project": {"name": "demo"},
            "scenes": [
                {
                    "type": "hook",
                    "duration": 4.0,
                    "content": {"headline": "far too long to fit"},
                }
            ],
        }
        problems = looks.check(_video_look(tmp_path, sample=sample))
        assert any("content.yaml" in p and "demo" in p for p in problems), problems

    def test_an_image_sample_missing_a_slot_is_named(self, tmp_path):
        directory = _image_look(tmp_path, sample={"stat": "29"})
        problems = looks.check(directory)
        assert any("label" in p for p in problems), problems

    def test_an_image_sample_over_its_limit_is_named(self, tmp_path):
        directory = _image_look(
            tmp_path, sample={"stat": "29", "label": "far too long"}
        )
        problems = looks.check(directory)
        assert any("label" in p for p in problems), problems

    def test_a_confirmed_voice_with_no_voice_id_is_named(self, tmp_path):
        manifest = {**VIDEO_MANIFEST, "voice_confirmed": True}
        problems = looks.check(_video_look(tmp_path, manifest=manifest))
        assert any("voice" in p for p in problems), problems

    def test_a_confirmed_voice_that_names_one_is_fine(self, tmp_path):
        manifest = {**VIDEO_MANIFEST, "voice": "v1", "voice_confirmed": True}
        assert looks.check(_video_look(tmp_path, manifest=manifest)) == []

    def test_the_boot_check_reads_the_looks_directory(self, tmp_path):
        problems = checks.run(looks_dir=tmp_path / "looks")
        assert any("looks" in p for p in problems), problems


@pytest_asyncio.fixture
async def api(session):
    async def override():
        yield session

    app.dependency_overrides[get_session] = override
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://backend"
    ) as client:
        yield client
    app.dependency_overrides.clear()


async def _asset(session, look, *, files=0):
    asset = Asset(name="a post", kind="video", look=look, origin="proposal")
    session.add(asset)
    await session.flush()
    for version in range(1, files + 1):
        session.add(
            AssetFile(
                asset_seq=asset.seq,
                version=version,
                path=f"assets/{asset.seq}/v{version}.mp4",
                media_type="video/mp4",
                bytes=12,
            )
        )
    await session.flush()
    return asset


class TestTheLooksApi:
    async def test_every_look_is_listed_with_what_the_console_shows(self, api):
        body = (await api.get("/api/looks")).json()
        names = [row["name"] for row in body["looks"]]
        assert names == ["aios", "soda", "square-stat"]
        row = body["looks"][0]
        assert set(row) == {
            "name",
            "medium",
            "ratio",
            "voice_confirmed",
            "scenes",
            "limits_measured",
            "used_by",
            "built",
            "build_cost",
        }

    async def test_an_image_look_reports_its_slots_as_its_scenes(self, api):
        body = (await api.get("/api/looks")).json()
        row = next(r for r in body["looks"] if r["name"] == "square-stat")
        assert row["scenes"] == ["stat", "label", "support", "mark"]
        assert row["voice_confirmed"] is None

    async def test_a_look_counts_the_assets_that_carry_it(self, api, session):
        await _asset(session, "aios", files=2)
        await _asset(session, "aios")
        await _asset(session, "soda", files=1)
        body = (await api.get("/api/looks")).json()
        rows = {row["name"]: row for row in body["looks"]}
        assert (rows["aios"]["used_by"], rows["aios"]["built"]) == (2, 1)
        assert (rows["soda"]["used_by"], rows["soda"]["built"]) == (1, 1)
        assert rows["square-stat"]["used_by"] == 0

    async def test_one_look_carries_its_own_frames_and_preview(self, api):
        body = (await api.get("/api/looks/aios")).json()
        assert body["name"] == "aios"
        assert "hook" in body["layouts"]
        assert isinstance(body["preview"], str)

    async def test_a_look_with_no_preview_file_says_so_with_an_empty_string(self, api):
        body = (await api.get("/api/looks/soda")).json()
        assert body["preview"] == ""

    async def test_a_look_nobody_has_is_a_404(self, api):
        response = await api.get("/api/looks/ghost")
        assert response.status_code == 404
        assert "ghost" in response.json()["detail"]
