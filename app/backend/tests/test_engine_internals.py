from datetime import UTC, datetime

import pytest

from app.engine import mappings, ontology, pipeline
from app.engine.report import SyncReport
from app.sources import hooks

INGESTED = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)


def _onto():
    return ontology.load()


def _line_index():
    return mappings.by_object(mappings.load())


class TestObservationTimeFallback:
    MODULE = type(
        "M", (), {"SOURCE": "hubspot", "OBSERVED_AT": {"companies": "updated_at"}}
    )

    def test_the_providers_own_timestamp_wins_when_it_is_usable(self):
        observed, which = pipeline.observed_at_for(
            self.MODULE, "companies", {"updated_at": "2026-07-01T00:00:00Z"}, INGESTED
        )
        assert which == "provider"
        assert observed != INGESTED

    def test_a_date_the_provider_spelled_wrong_falls_back_to_ingestion(self):
        observed, which = pipeline.observed_at_for(
            self.MODULE, "companies", {"updated_at": "yesterday-ish"}, INGESTED
        )
        assert (observed, which) == (INGESTED, "ingested")

    @pytest.mark.parametrize("payload", [{}, {"updated_at": None}, {"updated_at": ""}])
    def test_an_absent_timestamp_falls_back_to_ingestion(self, payload):
        assert (
            pipeline.observed_at_for(self.MODULE, "companies", payload, INGESTED)[1]
            == "ingested"
        )

    def test_a_source_that_declares_none_always_falls_back(self):
        module = type("M", (), {"SOURCE": "salesforce", "OBSERVED_AT": {}})
        assert (
            pipeline.observed_at_for(
                module, "accounts", {"updated_at": "2026-07-01T00:00:00Z"}, INGESTED
            )[1]
            == "ingested"
        )


class TestExtractFailuresCostOneRecord:
    def test_a_hook_that_throws_is_counted_rather_than_stopping_the_rebuild(
        self, monkeypatch
    ):
        def explode(source, object_type, payload):
            raise hooks.ExtractError("properties block unreadable")

        monkeypatch.setattr(pipeline.hooks, "reshape", explode)
        report = SyncReport()
        out = pipeline.project_payload(
            source="hubspot",
            object_type="contacts",
            source_id="c1",
            payload={"id": "c1"},
            raw_event_id=None,
            ingested_at=INGESTED,
            seq=1,
            onto=_onto(),
            line_index=_line_index(),
            transform_map={},
            report=report,
        )
        assert out == []
        assert report.totals()["records_skipped"] == 1
