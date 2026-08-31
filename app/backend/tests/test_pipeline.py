from datetime import UTC, datetime
from types import ModuleType, SimpleNamespace

import pytest

from app.engine import mappings, ontology, pipeline, transforms
from app.engine.report import SyncReport
from app.sources import registry

INGESTED = datetime(2026, 8, 2, 12, 0, tzinfo=UTC)


@pytest.fixture(scope="module")
def kit():
    lines = mappings.load()
    return SimpleNamespace(
        onto=ontology.load(),
        line_index=mappings.by_object(lines),
        transform_map=transforms.load_map(),
        connectors=registry.discover(),
    )


def project(kit, source, object_type, payload, source_id="x1", seq=1, report=None):
    report = report or SyncReport()
    entities = pipeline.project_payload(
        source=source,
        object_type=object_type,
        source_id=source_id,
        payload=payload,
        raw_event_id="raw-1",
        ingested_at=INGESTED,
        seq=seq,
        onto=kit.onto,
        line_index=kit.line_index,
        transform_map=kit.transform_map,
        report=report,
        connector_module=kit.connectors.get(source),
    )
    return {e.entity_type: e for e in entities}, report


class TestThreeStates:
    def test_an_absent_path_is_no_observation(self, kit):
        out, report = project(
            kit, "hubspot", "companies", {"properties": {"domain": "acme.io"}}
        )
        assert "industry" not in out["company"].facts
        assert report.totals()["clears"] == 0
        assert report.totals()["skips"] == 0

    def test_a_present_null_is_an_observed_clear(self, kit):
        out, report = project(
            kit,
            "hubspot",
            "companies",
            {"properties": {"domain": "acme.io", "industry": None}},
        )
        fact = out["company"].facts["industry"]
        assert fact.value is None
        assert report.clears["industry/hubspot"] == 1

    def test_an_empty_string_is_how_hubspot_spells_cleared(self, kit):
        out, report = project(
            kit,
            "hubspot",
            "companies",
            {"properties": {"domain": "acme.io", "industry": "  "}},
        )
        assert out["company"].facts["industry"].value is None
        assert report.clears["industry/hubspot"] == 1
        assert report.totals()["skips"] == 0

    def test_a_refused_value_is_a_counted_skip_with_a_reason(self, kit):
        out, report = project(
            kit,
            "hubspot",
            "companies",
            {"properties": {"domain": "not a domain", "name": "Acme"}},
        )
        assert "domain" not in out["company"].facts
        assert report.skips["domain/hubspot/not_a_domain"] == 1

    def test_a_skip_does_not_take_the_records_other_facts_with_it(self, kit):
        out, _ = project(
            kit,
            "hubspot",
            "companies",
            {"properties": {"domain": "@@@", "name": "Acme", "industry": "Software"}},
        )
        assert out["company"].facts["name"].value == "Acme"
        assert out["company"].facts["industry"].value == "Software"

    def test_a_skip_never_becomes_a_null_in_the_canonical_layer(self, kit):
        out, _ = project(
            kit,
            "hubspot",
            "companies",
            {"properties": {"domain": "@@@", "name": "Acme"}},
        )
        assert "domain" not in out["company"].facts


class TestHookIntegration:
    def test_the_composite_name_reaches_the_person_entity(self, kit):
        out, _ = project(
            kit,
            "hubspot",
            "contacts",
            {
                "properties": {
                    "firstname": "Jane",
                    "lastname": "Smith",
                    "email": "jane@acme.io",
                }
            },
        )
        assert out["person"].facts["name"].value == "Jane Smith"


class TestObservationTime:
    def test_the_provider_timestamp_wins_when_declared_and_present(self, kit):
        out, _ = project(
            kit,
            "hubspot",
            "companies",
            {
                "properties": {
                    "domain": "acme.io",
                    "hs_lastmodifieddate": "2026-07-01T10:00:00.000Z",
                }
            },
        )
        fact = out["company"].facts["domain"]
        assert fact.observed_at_source == "provider"
        assert fact.observed_at.isoformat().startswith("2026-07-01T10:00:00")

    def test_falls_back_to_ingestion_when_the_source_declares_none(
        self, kit, monkeypatch
    ):
        module = ModuleType("app.sources.synthetic")
        module.SOURCE = "hubspot"
        monkeypatch.setitem(kit.connectors, "hubspot", module)
        out, report = project(
            kit,
            "hubspot",
            "companies",
            {
                "properties": {
                    "domain": "acme.io",
                    "name": "Acme",
                    "hs_lastmodifieddate": "2026-07-01T10:00:00.000Z",
                }
            },
        )
        assert out["company"].facts["domain"].observed_at == INGESTED
        assert out["company"].facts["domain"].observed_at_source == "ingested"
        assert report.counts["observed_at_fallback/hubspot"] == 1

    def test_falls_back_when_the_declared_field_is_missing_from_the_payload(self, kit):
        out, _ = project(
            kit, "hubspot", "companies", {"properties": {"domain": "acme.io"}}
        )
        assert out["company"].facts["domain"].observed_at_source == "ingested"


class TestDeadPaths:
    def test_a_line_that_never_hits_is_reported(self, kit):
        report = SyncReport()
        project(
            kit,
            "hubspot",
            "companies",
            {"properties": {"domain": "acme.io"}},
            report=report,
        )
        dead = report.dead_paths()
        assert "company:hubspot.companies.properties.industry" in dead
        assert "company:hubspot.companies.properties.domain" not in dead


class TestTypeValidation:
    def test_a_value_of_the_wrong_type_is_skipped_not_stored(self, kit, monkeypatch):
        monkeypatch.setitem(kit.transform_map, "amount", None)
        out, report = project(
            kit,
            "hubspot",
            "deals",
            {"properties": {"dealname": "Big Deal", "amount": "89.0"}},
        )
        assert "amount" not in out["deal"].facts
        assert report.skips["amount/hubspot/not_number"] == 1
        monkeypatch.setitem(kit.transform_map, "amount", "normalize_money")


class TestEmptyRecords:
    def test_a_payload_with_no_mapped_paths_produces_nothing(self, kit):
        out, _report = project(kit, "hubspot", "companies", {"properties": {}})
        assert out == {}

    def test_a_record_whose_every_value_was_refused_is_counted(self, kit):
        out, report = project(
            kit,
            "hubspot",
            "deals",
            {"properties": {"amount": "n/a", "closedate": "never"}},
        )
        assert out == {}
        assert report.records_skipped["hubspot/deals/no_facts/deal"] == 1
        assert report.skips["amount/hubspot/not_a_number"] == 1

    def test_an_unmapped_object_type_produces_nothing(self, kit):
        out, _ = project(kit, "hubspot", "tickets", {"amount_due": 4900})
        assert out == {}


class TestOneBadRowDoesNotStopTheRebuild:
    def rows(self, payloads):
        return [
            SimpleNamespace(
                source="hubspot",
                object_type="companies",
                source_id=f"c{i}",
                raw_payload=p,
                id=f"raw-{i}",
                ingested_at=INGESTED,
                seq=i,
            )
            for i, p in enumerate(payloads, start=1)
        ]

    def project_rows(self, kit, rows, report=None):
        report = report or SyncReport()
        return pipeline.project_rows(
            rows,
            onto=kit.onto,
            line_index=kit.line_index,
            transform_map=kit.transform_map,
            report=report,
            connectors=kit.connectors,
        ), report

    def test_an_unexpected_error_on_one_row_spares_the_others(self, kit, monkeypatch):
        real = pipeline.project_payload
        poison = {"properties": {"domain": "poison.io", "name": "Poison"}}

        def explode(**kwargs):
            if kwargs["payload"] == poison:
                raise RuntimeError("something no one predicted")
            return real(**kwargs)

        monkeypatch.setattr(pipeline, "project_payload", explode)
        rows = self.rows(
            [
                {"properties": {"domain": "good-one.io", "name": "Good One"}},
                poison,
                {"properties": {"domain": "good-two.io", "name": "Good Two"}},
            ]
        )
        projected, _report = self.project_rows(kit, rows)
        domains = sorted(
            e.facts["domain"].value for e in projected.values() if "domain" in e.facts
        )
        assert domains == ["good-one.io", "good-two.io"]

    def test_the_failed_row_is_counted_not_swallowed(self, kit, monkeypatch):
        def explode(**kwargs):
            raise RuntimeError("boom")

        monkeypatch.setattr(pipeline, "project_payload", explode)
        rows = self.rows([{"properties": {"domain": "a.io", "name": "A"}}])
        _projected, report = self.project_rows(kit, rows)
        assert any("row_failed" in key for key in report.records_skipped), (
            report.records_skipped
        )

    def test_the_reason_survives_into_the_report(self, kit, monkeypatch):
        def explode(**kwargs):
            raise RuntimeError("boom")

        monkeypatch.setattr(pipeline, "project_payload", explode)
        rows = self.rows([{"properties": {"domain": "a.io", "name": "A"}}])
        _projected, report = self.project_rows(kit, rows)
        blob = " ".join(report.records_skipped)
        assert "hubspot" in blob and "RuntimeError" in blob

    def test_a_keyboard_interrupt_is_not_a_bad_row(self, kit, monkeypatch):
        def interrupt(**kwargs):
            raise KeyboardInterrupt

        monkeypatch.setattr(pipeline, "project_payload", interrupt)
        rows = self.rows([{"properties": {"domain": "a.io", "name": "A"}}])
        with pytest.raises(KeyboardInterrupt):
            self.project_rows(kit, rows)

    def test_a_healthy_run_reports_no_failures(self, kit):
        rows = self.rows([{"properties": {"domain": "fine.io", "name": "Fine"}}])
        projected, report = self.project_rows(kit, rows)
        assert projected
        assert not [k for k in report.records_skipped if "row_failed" in k]
