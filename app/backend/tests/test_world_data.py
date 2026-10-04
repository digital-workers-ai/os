import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from app.engine import spy
from app.sources.google_ads_transparency import connector
from tests import ground_truth

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


def in_the_world(env: dict[str, str], code: str, *args: str) -> str:
    clean = {k: v for k, v in os.environ.items() if k != "WORLD_DATA"}
    run = subprocess.run(
        [sys.executable, "-c", code, *args],
        capture_output=True,
        text=True,
        env={**clean, **env, "PYTHONPATH": ground_truth.ADVERSARIAL_ROOT},
    )
    assert run.returncode == 0, run.stderr
    return run.stdout.strip()


def world_brand(env: dict[str, str]) -> str:
    code = "import seeds.world as world; print(world.SPY_BRAND['name'])"
    return in_the_world(env, code)


def test_the_world_loads_the_file_named_by_world_data(tmp_path):
    data = load_data()
    data["spy"]["brand"]["name"] = "Example Brand"
    other = tmp_path / "world.yaml"
    other.write_text(yaml.safe_dump(data))
    assert world_brand({"WORLD_DATA": str(other)}) == "Example Brand"


def test_the_world_loads_the_bundled_data_without_world_data():
    assert world_brand({}) == load_data()["spy"]["brand"]["name"]


ASK = """
import json, sys
from fastapi.testclient import TestClient
from seeds.server import app
client = TestClient(app, headers={"Authorization": "Bearer mock_key"})
print(json.dumps([client.request(**call).json() for call in json.loads(sys.argv[1])]))
"""


def ask(env: dict[str, str], *calls: dict) -> list[dict]:
    return json.loads(in_the_world(env, ASK, json.dumps(calls)))


def serpapi(**params) -> dict:
    return {
        "method": "GET",
        "url": "/serpapi/search.json",
        "params": {"api_key": "mock_key", **params},
    }


def searchapi(**params) -> dict:
    return {"method": "GET", "url": "/searchapi/api/v1/search", "params": params}


class TestAWorldWhoseCompetitorsCarryNoHandles:
    @pytest.fixture
    def names(self) -> list[str]:
        return [c["name"] for c in load_data()["spy"]["competitors"]]

    @pytest.fixture
    def bare(self, tmp_path) -> dict[str, str]:
        data = load_data()
        data["spy"]["competitors"] = [
            {key: competitor[key] for key in spy.BRAND_KEYS}
            for competitor in data["spy"]["competitors"]
        ]
        other = tmp_path / "world.yaml"
        other.write_text(yaml.safe_dump(data))
        return {"WORLD_DATA": str(other)}

    def test_the_mock_serves(self, bare):
        [health] = ask(bare, {"method": "GET", "url": "/health"})
        assert health["status"] == "ok"

    def test_the_ads_transparency_center_finds_no_advertiser(self, bare, names):
        calls = [
            serpapi(engine="google_ads_transparency_center", advertiser_id="AR0"),
            *(serpapi(engine="google_ads_transparency_center", text=n) for n in names),
        ]
        answers = ask(bare, *calls)
        assert {a["error"] for a in answers} == {
            "Google hasn't returned any results for this query."
        }

    def test_the_ad_reader_still_reads_an_image(self, bare):
        image = "https://tpc.googlesyndication.com/archive/simgad/1"
        call = {
            "method": "POST",
            "url": "/openrouter/api/v1/chat/completions",
            "json": connector._read_request(image),
        }
        [answer] = ask(bare, call)
        assert answer["choices"][0]["message"]["content"]

    def test_the_linkedin_ad_library_finds_no_ads(self, bare, names):
        calls = [
            searchapi(engine="linkedin_ad_library_ad_details", ad_id="1"),
            *(searchapi(engine="linkedin_ad_library", advertiser=n) for n in names),
        ]
        answers = ask(bare, *calls)
        assert {a["error"] for a in answers} == {
            "LinkedIn Ad Library didn't return any results."
        }

    def test_the_meta_page_search_finds_no_page(self, bare, names):
        calls = [searchapi(engine="meta_ad_library_page_search", q=n) for n in names]
        answers = ask(bare, *calls)
        assert {a["error"] for a in answers} == {
            "Meta Ad Library page search didn't return any results."
        }
