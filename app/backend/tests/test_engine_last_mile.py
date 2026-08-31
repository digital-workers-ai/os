from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select

from app.engine import mappings, ontology, pipeline, run
from app.engine.report import SyncReport

INGESTED = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)


class TestAccountCurrencyFallback:
    def test_a_connector_declaring_a_nonsense_currency_is_refused_and_counted(self):
        module = type(
            "M", (), {"SOURCE": "hubspot", "ACCOUNT_CURRENCY": "not a currency code"}
        )
        report = SyncReport()
        pipeline.project_payload(
            source="hubspot",
            object_type="deals",
            source_id="d1",
            payload={"properties": {"dealname": "Acme deal", "amount": "100"}},
            raw_event_id=None,
            ingested_at=INGESTED,
            seq=1,
            onto=ontology.load(),
            line_index=mappings.by_object(mappings.load()),
            transform_map={"amount": "normalize_money"},
            report=report,
            connector_module=module,
        )
        skips = str(report.as_dict())
        assert "account_level" in skips


class TestTwoRebuildsCannotCollide:
    async def test_a_second_rebuild_is_refused_while_one_holds_the_lock(
        self, session, sessionmaker_for_test
    ):
        async with sessionmaker_for_test() as holder:
            await holder.execute(
                select(func.pg_try_advisory_xact_lock(run._REBUILD_LOCK_ID))
            )
            with pytest.raises(run.RebuildInProgress):
                await run.rebuild(session)

    async def test_an_uncontended_rebuild_runs(self, session):
        assert (await run.rebuild(session))["ok"] is True

    async def test_the_lock_is_released_for_the_next_rebuild(self, session):
        await run.rebuild(session)
        assert (await run.rebuild(session))["ok"] is True
