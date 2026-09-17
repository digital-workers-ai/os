import httpx
import pytest
import pytest_asyncio
import yaml

from app.db import get_session
from app.engine import looks
from app.main import app

STAT = {
    "name": "stat-card",
    "medium": "image",
    "ratios": ["1:1", "4:5", "9:16", "16:9"],
    "slots": [
        {"name": "stat", "max": 6},
        {"name": "label", "max": 28},
        {"name": "support", "max": 96},
    ],
}
STAT_CONTENT = {
    "stat": "27",
    "label": "tools, one connector each",
    "support": "Every record kept as it arrived.",
}
CAROUSEL = {
    "name": "carousel",
    "medium": "carousel",
    "ratios": ["1:1", "4:5"],
    "slides": {"min": 3, "max": 10},
    "slots": {
        "cover": [{"name": "title", "max": 60}, {"name": "kicker", "max": 40}],
        "slide": [{"name": "title", "max": 40}, {"name": "body", "max": 160}],
        "closing": [{"name": "title", "max": 40}, {"name": "cta", "max": 40}],
    },
}
CAROUSEL_CONTENT = {
    "cover": {"title": "Where a number comes from", "kicker": "Three facts"},
    "slides": [{"title": f"Fact {n}", "body": "A body."} for n in (1, 2, 3)],
    "closing": {"title": "Open source", "cta": "Read the code"},
}
LAYOUTS = "┌┐\n"


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


def _write_look(root, manifest, content):
    folder = root / manifest["name"]
    folder.mkdir()
    (folder / "look.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False))
    (folder / "content.yaml").write_text(yaml.safe_dump(content, sort_keys=False))
    (folder / "layouts.md").write_text(LAYOUTS)


@pytest.fixture
def root(tmp_path, monkeypatch):
    _write_look(tmp_path, STAT, STAT_CONTENT)
    _write_look(tmp_path, CAROUSEL, CAROUSEL_CONTENT)
    monkeypatch.setattr(looks, "DEFAULT_LOOKS", tmp_path)
    return tmp_path


class TestLooks:
    async def test_every_look_is_a_row_and_only_the_carousel_carries_slides(
        self, api, root
    ):
        assert (await api.get("/api/looks")).json() == {
            "looks": [
                {
                    "name": "carousel",
                    "medium": "carousel",
                    "ratios": ["1:1", "4:5"],
                    "slots": CAROUSEL["slots"],
                    "slides": {"min": 3, "max": 10},
                },
                {
                    "name": "stat-card",
                    "medium": "image",
                    "ratios": ["1:1", "4:5", "9:16", "16:9"],
                    "slots": STAT["slots"],
                },
            ]
        }

    async def test_the_detail_adds_the_sample_and_the_layouts(self, api, root):
        assert (await api.get("/api/looks/stat-card")).json() == {
            **STAT,
            "sample": STAT_CONTENT,
            "layouts": LAYOUTS,
        }

    async def test_a_carousel_detail_keeps_its_slides(self, api, root):
        body = (await api.get("/api/looks/carousel")).json()
        assert body["slides"] == {"min": 3, "max": 10}
        assert body["sample"] == CAROUSEL_CONTENT

    async def test_an_unknown_look_is_a_404(self, api, root):
        response = await api.get("/api/looks/nope")
        assert response.status_code == 404
        assert "nope" in response.json()["detail"]
