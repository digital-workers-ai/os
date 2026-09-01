import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.engine import checks, mappings, ontology, pipeline, transforms
from app.engine.report import SyncReport
from app.sources import registry

FIXTURES = checks.REAL_FIXTURES.parent
CAPTURED_AT = datetime(2026, 8, 2, tzinfo=UTC)


def fixture_dirs(fixture_class: str):
    root = FIXTURES / fixture_class
    if not root.is_dir():
        return []
    return sorted(
        d for d in root.iterdir() if d.is_dir() and (d / "expected.json").exists()
    )


def replay(source: str, directory: Path):
    lines = mappings.load()
    line_index = mappings.by_object(lines)
    transform_map = transforms.load_map()
    onto = ontology.load()
    module = registry.discover().get(source)
    report = SyncReport()
    for line in lines:
        if line.source == source:
            report.declare_path(line.entity, line.key)

    extracted: dict = {}
    for path in sorted(directory.glob("*.json")):
        if path.name == "expected.json":
            continue
        object_type = path.stem
        for record in json.loads(path.read_text()):
            for entity in pipeline.project_payload(
                source=source,
                object_type=object_type,
                source_id=record["source_id"],
                payload=record["payload"],
                raw_event_id=None,
                ingested_at=CAPTURED_AT,
                seq=1,
                onto=onto,
                line_index=line_index,
                transform_map=transform_map,
                report=report,
                connector_module=module,
            ):
                extracted.setdefault(object_type, {}).setdefault(
                    entity.entity_type, {}
                )[entity.source_id] = {
                    attr: fact.value for attr, fact in sorted(entity.facts.items())
                }
    return extracted, report


MOCK_DIRS = fixture_dirs("mock")
REAL_DIRS = fixture_dirs("real")


def real_params():
    if REAL_DIRS:
        return [pytest.param(d, id=d.name) for d in REAL_DIRS]
    return [
        pytest.param(
            None,
            id="none-captured",
            marks=pytest.mark.skip(
                reason="NO REAL PROVIDER PAYLOADS: no source has fixtures under "
                "fixtures/real/. Every source is mock-validated, which proves "
                "the knowledge files agree with mocks we wrote, not with a "
                "provider. Nothing ships enabled until this is non-empty."
            ),
        )
    ]


@pytest.mark.parametrize("directory", MOCK_DIRS, ids=lambda d: d.name)
class TestMockFixtures:
    def test_extracted_values_match_what_was_verified_by_hand(self, directory):
        expected = json.loads((directory / "expected.json").read_text())
        extracted, _report = replay(directory.name, directory)
        assert extracted == expected["extracted"]

    def test_the_recorded_skips_are_the_only_skips(self, directory):
        expected = json.loads((directory / "expected.json").read_text())
        _extracted, report = replay(directory.name, directory)
        assert dict(report.skips) == expected["skips"]

    def test_the_recorded_clears_are_the_only_clears(self, directory):
        expected = json.loads((directory / "expected.json").read_text())
        _extracted, report = replay(directory.name, directory)
        assert dict(report.clears) == expected["clears"]

    def test_no_mapping_line_for_this_source_is_dead(self, directory):
        _extracted, report = replay(directory.name, directory)
        assert report.dead_paths() == []


@pytest.mark.parametrize("directory", real_params())
class TestRealFixtures:
    def test_extracted_values_match(self, directory):
        expected = json.loads((directory / "expected.json").read_text())
        extracted, _report = replay(directory.name, directory)
        assert extracted == expected["extracted"]

    def test_zero_dead_paths(self, directory):
        _extracted, report = replay(directory.name, directory)
        assert report.dead_paths() == []

    def test_zero_unexplained_skips(self, directory):
        expected = json.loads((directory / "expected.json").read_text())
        _extracted, report = replay(directory.name, directory)
        assert dict(report.skips) == expected["skips"]


class TestTheLabelIsLoadBearing:
    def test_every_mapped_source_has_at_least_mock_fixtures(self):
        mapped = {ln.source for ln in mappings.load()}
        captured = {d.name for d in MOCK_DIRS}
        assert mapped <= captured, (
            f"no captured payloads for {sorted(mapped - captured)}"
        )

    def test_provider_validated_requires_a_replayable_capture(self):
        replayable = {d.name for d in REAL_DIRS}
        claiming = {
            s
            for s, e in checks.source_status().items()
            if e["status"] == "provider-validated"
        }
        assert claiming <= replayable, (
            f"{sorted(claiming - replayable)} derive provider-validated from a "
            "fixtures/real/ dir that holds no replayable capture"
        )

    def test_a_source_is_only_enabled_if_a_provider_payload_replays(self):
        replayable = {d.name for d in REAL_DIRS}
        for source in checks.enabled_sources():
            assert source in replayable, (
                f"{source} is enabled with no replayable real fixtures"
            )

    def test_the_real_fixture_gap_is_counted_rather_than_implied(self):
        real = {d.name for d in REAL_DIRS}
        mapped = {ln.source for ln in mappings.load()}
        print(
            f"\nreal-payload coverage: {len(real & mapped)}/{len(mapped)} "
            "mapped sources have provider fixtures"
        )
        if not real:
            print("  every number this project produces is mock-validated only")
