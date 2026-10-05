import importlib
import os
import re
import subprocess
import sys
from pathlib import Path

import httpx
import pytest
import yaml
from fastapi import FastAPI

from app.engine import spy
from tests import ground_truth
from tools import instance_check

MOCK = Path(ground_truth.ADVERSARIAL_ROOT) / "seeds"
DATA = MOCK / "world" / "data.yaml"
SCANNED = sorted(
    [
        *(MOCK / "providers").glob("*.py"),
        MOCK / "adversarial.py",
    ]
)

pytestmark = pytest.mark.skipif(
    not (MOCK / "adversarial.py").is_file(),
    reason="the mock is not mounted at ADVERSARIAL_ROOT",
)


def load_data() -> dict:
    return yaml.safe_load(DATA.read_text())


def brand_terms(data: dict) -> list[str]:
    spy = data["spy"]
    terms = [spy["brand"]["name"], spy["brand"]["domain"], *spy["brand"]["aliases"]]
    for competitor in spy["competitors"]:
        terms += [competitor["name"], competitor["domain"], *competitor["aliases"]]
    terms += sorted(
        {call["host_email"].partition("@")[2] for call in data["sales_calls"]}
    )
    vendors = {path.stem for path in (MOCK / "providers").glob("*.py")}
    return [term for term in terms if re.split(r"[ .]", term.lower())[0] not in vendors]


@pytest.fixture(scope="module")
def terms() -> list[str]:
    return brand_terms(load_data())


@pytest.mark.parametrize("path", SCANNED, ids=lambda path: str(path.relative_to(MOCK)))
def test_the_mock_names_no_brand_from_the_world(path, terms):
    text = path.read_text().lower()
    found = sorted({term for term in terms if term.lower() in text})
    assert not found, f"{path.relative_to(MOCK)} names {found}"


def world_brand(env: dict[str, str]) -> str:
    code = "import seeds.world as world; print(world.SPY_BRAND['name'])"
    clean = {k: v for k, v in os.environ.items() if k != "WORLD_DATA"}
    run = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
        env={**clean, **env, "PYTHONPATH": ground_truth.ADVERSARIAL_ROOT},
    )
    return run.stdout.strip()


def test_the_world_loads_the_file_named_by_world_data(tmp_path):
    data = load_data()
    data["spy"]["brand"]["name"] = "Example Brand"
    other = tmp_path / "world.yaml"
    other.write_text(yaml.safe_dump(data))
    assert world_brand({"WORLD_DATA": str(other)}) == "Example Brand"


def test_the_world_loads_the_bundled_data_without_world_data():
    assert world_brand({}) == load_data()["spy"]["brand"]["name"]


HANDLES = ("linkedin", "x", "instagram", "google_advertiser_id", "meta_page_id")
ASKED = {
    "linkedin": lambda world, company: [
        *world.spy_posts(company["linkedin"]),
        *world.spy_linkedin_ads(company["name"]),
    ],
    "x": lambda world, company: world.spy_x_posts(company["x"]),
    "instagram": lambda world, company: world.spy_instagram_posts(company["instagram"]),
    "google_advertiser_id": lambda world, company: world.spy_ads(
        company["google_advertiser_id"]
    ),
    "meta_page_id": lambda world, company: [
        *world.spy_meta_ads(company["meta_page_id"]),
        *world.spy_meta_pages(company["name"]),
    ],
}


@pytest.fixture
def fresh_mock():
    saved = {
        name: m for name, m in sys.modules.items() if name.split(".")[0] == "seeds"
    }
    for name in saved:
        del sys.modules[name]
    yield
    for name in [name for name in sys.modules if name.split(".")[0] == "seeds"]:
        del sys.modules[name]
    sys.modules.update(saved)


def without(field: str, tmp_path, monkeypatch) -> tuple[dict, dict]:
    data = load_data()
    bare, full = data["spy"]["competitors"][:2]
    asked = dict(bare)
    del bare[field]
    world = tmp_path / "world.yaml"
    world.write_text(yaml.safe_dump(data))
    monkeypatch.setenv("WORLD_DATA", str(world))
    named = yaml.safe_load(spy.DEFAULT_SPY.read_text())
    del named["competitors"][0][field]
    definitions = tmp_path / "spy.yaml"
    definitions.write_text(yaml.safe_dump(named))
    monkeypatch.setattr(spy, "DEFAULT_SPY", definitions)
    return asked, full


@pytest.mark.parametrize("field", HANDLES)
def test_a_competitor_without_a_handle_loads_and_that_stand_in_has_nothing_for_it(
    field, tmp_path, monkeypatch, fresh_mock
):
    bare, full = without(field, tmp_path, monkeypatch)
    world = ground_truth.world()
    assert instance_check.check_world() == []
    assert ASKED[field](world, bare) == []
    assert ASKED[field](world, full) != []


async def test_without_an_advertiser_id_the_ad_stand_ins_answer_no_results(
    tmp_path, monkeypatch, fresh_mock
):
    bare, full = without("google_advertiser_id", tmp_path, monkeypatch)
    world = ground_truth.world()
    serpapi = importlib.import_module("seeds.providers.serpapi")
    openrouter = importlib.import_module("seeds.providers.openrouter")
    app = FastAPI()
    app.include_router(serpapi.router, prefix="/serpapi")
    app.include_router(openrouter.router, prefix="/openrouter")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://mock") as client:
        for asked in (
            {"text": bare["domain"]},
            {"advertiser_id": bare["google_advertiser_id"]},
        ):
            found = await client.get(
                "/serpapi/search.json",
                params={
                    "api_key": "mock_serpapi_key",
                    "engine": "google_ads_transparency_center",
                    **asked,
                },
            )
            assert found.json()["error"] == serpapi.NO_RESULTS
        ad = next(
            a for a in world.spy_ads(full["google_advertiser_id"]) if "image" in a
        )
        image = {"type": "image_url", "image_url": {"url": ad["image"]}}
        read = await client.post(
            "/openrouter/api/v1/chat/completions",
            headers={"Authorization": "Bearer mock_openrouter_key"},
            json={
                "model": "openai/gpt-5.6-luna",
                "messages": [{"role": "user", "content": [image]}],
            },
        )
    message = read.json()["choices"][0]["message"]
    assert message["content"] == world.spy_ad_text(ad["ad_creative_id"])
