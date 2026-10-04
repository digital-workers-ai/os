import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

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
