import shutil
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
import yaml

from app import caches
from app.api import entities_api, metrics_api, sources_api
from app.db import get_session
from app.engine import checks
from app.main import app

pytestmark = pytest.mark.e2e

KNOWLEDGE = Path(caches.BACKEND_DIR)
ALL_FILES = (
    "mappings.yaml",
    "ontology.yaml",
    "transforms.yaml",
    "metrics.yaml",
    "rules.yaml",
    "goals.yaml",
)


@pytest_asyncio.fixture
async def api(session, sessionmaker_for_test, monkeypatch):
    async def override():
        yield session

    app.dependency_overrides[get_session] = override
    for module in (sources_api, entities_api, metrics_api):
        monkeypatch.setattr(
            module, "async_session", sessionmaker_for_test, raising=False
        )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://backend"
    ) as client:
        yield client
    app.dependency_overrides.clear()


def _broken_estate(tmp_path):
    for name in ALL_FILES:
        shutil.copy(KNOWLEDGE / name, tmp_path / name)
    path = tmp_path / "metrics.yaml"
    doc = yaml.safe_load(path.read_text())
    doc["quarterly_unicorns"] = {"entity": "unicorn", "expression": "COUNT(entity)"}
    path.write_text(yaml.safe_dump(doc, sort_keys=False))
    return checks.run(
        mapping_paths=[tmp_path / "mappings.yaml"],
        ontology_path=tmp_path / "ontology.yaml",
        transforms_path=tmp_path / "transforms.yaml",
        metrics_path=tmp_path / "metrics.yaml",
        rules_path=tmp_path / "rules.yaml",
        goals_path=tmp_path / "goals.yaml",
    )


class TestBuildChecks:
    def test_the_shipped_estate_passes_every_check(self):
        problems = checks.run()
        assert problems == [], "\n".join(problems)

    def test_one_broken_file_is_named_while_the_shipped_files_stay_clean(
        self, tmp_path
    ):
        problems = _broken_estate(tmp_path)
        assert any("quarterly_unicorns" in p for p in problems)
        assert checks.run() == []

    def test_the_error_a_boot_would_raise_carries_the_name(self, tmp_path):
        problems = _broken_estate(tmp_path)
        error = checks.BuildCheckError(problems)
        assert str(error).startswith("build checks failed:")
        assert "quarterly_unicorns" in str(error)


class TestSources:
    async def test_every_source_reports_its_validation_level(self, api):
        body = (await api.get("/api/sources")).json()
        by_source = {s["source"]: s for s in body["sources"]}
        assert len(by_source) == 27
        assert {s["validation"] for s in body["sources"]} == {"mock-validated"}
        assert by_source["stripe"]["entities"] == [
            "company",
            "person",
            "subscription",
        ]

    async def test_nothing_mock_validated_is_on_by_default(self, api):
        body = (await api.get("/api/sources")).json()
        assert body["enabled_by_default"] == []
        assert all(not s["enabled_by_default"] for s in body["sources"])

    async def test_the_validation_gap_is_stated_as_a_number_not_implied(self, api):
        coverage = (await api.get("/api/sources")).json()["validation_coverage"]
        assert coverage["total"] == 27
        assert coverage["provider_validated"] == 0
        assert coverage["by_status"] == {"mock-validated": 27}
        assert "mock-validated only" in coverage["detail"]

    async def test_the_summary_agrees_with_the_per_source_labels(self, api):
        body = (await api.get("/api/sources")).json()
        coverage = body["validation_coverage"]
        counted = sum(
            1 for s in body["sources"] if s["validation"] == "provider-validated"
        )
        assert coverage["provider_validated"] == counted
        assert coverage["total"] == len(body["sources"])
