import httpx
import pytest
import pytest_asyncio
import yaml

from app.db import get_session
from app.engine import brand
from app.main import app

TOKENS = {
    "logo": "assets/logo.svg",
    "colors": {
        "ink": "#1A1A1A",
        "paper": "#FFFFFF",
        "wash": "#F5F3EB",
        "line": "#E0DCC1",
        "muted": "#807F74",
        "accent": "#FD4E00",
    },
    "fonts": {
        "sans": "assets/space-grotesk.woff2",
        "display": "assets/science-gothic-500.woff2",
    },
}
SVG = "<svg xmlns='http://www.w3.org/2000/svg'/>"


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


@pytest.fixture
def folder(tmp_path, monkeypatch):
    for name in brand.REQUIRED:
        stem = name.removesuffix(".md")
        text = f"---\ntitle: {stem.title()}\nupdated: 2026-09-15\n---\n# {stem}\n"
        (tmp_path / name).write_text(text)
    (tmp_path / "tokens.yaml").write_text(yaml.safe_dump(TOKENS))
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "logo.svg").write_text(SVG)
    monkeypatch.setattr(brand, "DEFAULT_BRAND", tmp_path)
    return tmp_path


class TestBrand:
    async def test_the_list_carries_the_names_the_tokens_and_the_assets(
        self, api, folder
    ):
        assert (await api.get("/api/brand")).json() == {
            "files": [
                "brand-brain",
                "voice",
                "pillars",
                "audiences",
                "objections",
                "language",
                "proof",
            ],
            "tokens": TOKENS,
            "assets": [
                {
                    "name": "logo.svg",
                    "path": "assets/logo.svg",
                    "media_type": "image/svg+xml",
                    "bytes": len(SVG),
                }
            ],
        }

    async def test_a_file_is_served_with_its_front_matter_and_its_body(
        self, api, folder
    ):
        assert (await api.get("/api/brand/voice")).json() == {
            "file": "voice.md",
            "front": {"title": "Voice", "updated": "2026-09-15"},
            "body": "# voice\n",
        }

    @pytest.mark.parametrize("name", ["nope", "voice.md", "tokens"])
    async def test_a_name_outside_the_brand_files_is_a_404(self, api, folder, name):
        response = await api.get(f"/api/brand/{name}")
        assert response.status_code == 404
        assert name in response.json()["detail"]
