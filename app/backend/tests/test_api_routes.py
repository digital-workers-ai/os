import uuid
from datetime import UTC, datetime

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import func, select

from app.api import entities_api, sources_api
from app.db import get_session
from app.engine import run
from app.main import app
from app.models import EngineRun, Entity, EntityFact, RawEvent

SELF_TRANSACTING = (sources_api, entities_api)

SEEN = datetime(2026, 8, 1, tzinfo=UTC)


@pytest_asyncio.fixture
async def api(session, sessionmaker_for_test, monkeypatch):
    async def override():
        yield session

    app.dependency_overrides[get_session] = override
    for module in SELF_TRANSACTING:
        monkeypatch.setattr(
            module, "async_session", sessionmaker_for_test, raising=False
        )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://backend"
    ) as client:
        yield client
    app.dependency_overrides.clear()


class TestRaw:
    async def test_an_empty_log_is_zero_events(self, api):
        body = (await api.get("/api/raw")).json()
        assert body == {"total": 0, "limit": 50, "offset": 0, "events": []}

    async def test_both_filters_narrow_the_total_as_well_as_the_page(
        self, api, session
    ):
        for n, (source, object_type) in enumerate(
            [
                ("hubspot", "companies"),
                ("hubspot", "deals"),
                ("stripe", "subscriptions"),
            ]
        ):
            session.add(
                RawEvent(
                    id=uuid.uuid4(),
                    seq=n + 1,
                    source=source,
                    object_type=object_type,
                    source_id=str(n),
                    payload_sha=f"sha{n}",
                    raw_payload={"n": n},
                    ingested_at=datetime(2026, 8, 1, tzinfo=UTC),
                )
            )
        await session.flush()
        assert (await api.get("/api/raw?source=hubspot")).json()["total"] == 2
        one = await api.get("/api/raw?source=hubspot&object_type=deals")
        assert one.json()["total"] == 1
        assert one.json()["events"][0]["object_type"] == "deals"


class TestOffsetsThatReachTheDriver:
    async def test_the_largest_legal_offset_is_an_empty_page(self, api):
        response = await api.get(f"/api/raw?offset={2**63 - 1}")
        assert response.status_code == 200
        assert response.json()["events"] == []

    async def test_an_offset_past_the_bigint_range_is_refused(self, api):
        assert (await api.get(f"/api/raw?offset={2**63}")).status_code == 422


class TestSources:
    async def test_syncing_a_source_that_does_not_exist_is_a_404(self, api):
        response = await api.post("/api/sync", json={"sources": ["nope"]})
        assert response.status_code == 404
        assert "nope" in response.json()["detail"]

    async def test_a_named_source_reaches_the_syncer(self, api, monkeypatch):
        seen = {}

        async def fake_run_all(sessionmaker, sources=None):
            seen["sources"] = sources
            return {"ok": 1, "failed": 0, "rows_written": 0, "results": []}

        monkeypatch.setattr(sources_api.sync, "run_all", fake_run_all)
        body = (await api.post("/api/sync", json={"sources": ["hubspot"]})).json()
        assert seen["sources"] == ["hubspot"]
        assert body["failed"] == 0


class TestTheSyncEndpointHandlesItsOwnAdvertisedInputs:
    async def test_an_empty_body_syncs_everything_rather_than_500ing(
        self, api, monkeypatch
    ):
        seen = {}

        async def fake_run_all(sessionmaker, sources=None):
            seen["sources"] = sources
            return {"ok": 0, "failed": 0, "rows_written": 0, "results": []}

        monkeypatch.setattr(sources_api.sync, "run_all", fake_run_all)
        response = await api.post("/api/sync")
        assert response.status_code == 200
        assert seen["sources"] is None

    async def test_an_explicit_empty_list_syncs_nothing(self, api, monkeypatch):
        called = {"n": 0}

        async def fake_run_all(sessionmaker, sources=None):
            called["n"] += 1
            return {"ok": 0, "failed": 0, "rows_written": 0, "results": []}

        monkeypatch.setattr(sources_api.sync, "run_all", fake_run_all)
        body = (await api.post("/api/sync", json={"sources": []})).json()
        assert called["n"] == 0, "an empty list synced the whole estate"
        assert body["results"] == []

    async def test_a_named_source_is_unaffected(self, api, monkeypatch):
        seen = {}

        async def fake_run_all(sessionmaker, sources=None):
            seen["sources"] = sources
            return {"ok": 1, "failed": 0, "rows_written": 0, "results": []}

        monkeypatch.setattr(sources_api.sync, "run_all", fake_run_all)
        await api.post("/api/sync", json={"sources": ["hubspot"]})
        assert seen["sources"] == ["hubspot"]

    @pytest.mark.parametrize("sources", ["hubspot", {"name": "hubspot"}, 7])
    async def test_a_sources_field_that_is_not_a_list_is_refused(self, api, sources):
        response = await api.post("/api/sync", json={"sources": sources})
        assert response.status_code == 422
        assert "must be a list" in response.json()["detail"]


def _entity(entity_type="company", source="hubspot", source_id="c1", first_seq=1):
    return Entity(
        id=uuid.uuid4(),
        source=source,
        entity_type=entity_type,
        source_id=source_id,
        object_type="companies",
        first_seq=first_seq,
    )


def _fact(entity, attr, value, is_null=False):
    return EntityFact(
        id=uuid.uuid4(),
        entity_id=entity.id,
        attr=attr,
        value=value,
        is_null=is_null,
        source=entity.source,
        observed_at=SEEN,
    )


class TestEntitiesList:
    async def test_an_empty_estate_is_zero_rows_not_an_error(self, api):
        body = (await api.get("/api/entities")).json()
        assert body == {
            "total": 0,
            "limit": 50,
            "offset": 0,
            "by_type": {},
            "entities": [],
        }

    async def test_facts_are_folded_onto_each_entity(self, api, session):
        entity = _entity()
        session.add(entity)
        session.add(_fact(entity, "name", "Acme"))
        session.add(_fact(entity, "domain", "acme.io"))
        await session.flush()
        body = (await api.get("/api/entities")).json()
        assert body["total"] == 1
        assert body["by_type"] == {"company": 1}
        assert body["entities"][0]["facts"] == {"name": "Acme", "domain": "acme.io"}

    async def test_the_type_filter_narrows_rows_and_the_count_together(
        self, api, session
    ):
        session.add(_entity())
        session.add(_entity(entity_type="person", source_id="p1", first_seq=2))
        await session.flush()
        body = (await api.get("/api/entities?entity_type=person")).json()
        assert body["total"] == 1
        assert [e["entity_type"] for e in body["entities"]] == ["person"]
        assert body["by_type"] == {"company": 1, "person": 1}

    async def test_paging_walks_without_repeating(self, api, session):
        for n in range(3):
            session.add(_entity(source_id=f"c{n}", first_seq=n + 1))
        await session.flush()
        first = (await api.get("/api/entities?limit=2&offset=0")).json()
        second = (await api.get("/api/entities?limit=2&offset=2")).json()
        assert len(first["entities"]) == 2 and len(second["entities"]) == 1
        ids = {e["source_id"] for e in first["entities"] + second["entities"]}
        assert len(ids) == 3

    async def test_an_offset_past_the_bigint_range_is_refused(self, api):
        assert (await api.get(f"/api/entities?offset={2**63}")).status_code == 422

    async def test_a_cleared_value_reads_as_null_not_as_missing(self, api, session):
        entity = _entity()
        session.add(entity)
        session.add(_fact(entity, "phone", None, is_null=True))
        await session.flush()
        body = (await api.get("/api/entities")).json()
        assert body["entities"][0]["facts"] == {"phone": None}


class TestReport:
    async def test_no_rebuild_yet_says_so_rather_than_reporting_zeroes(self, api):
        body = (await api.get("/api/report")).json()
        assert body == {"ran": False, "detail": "no rebuild has run yet"}

    async def test_the_newest_run_wins(self, api, session):
        for seq, events in ((1, 10), (2, 99)):
            session.add(
                EngineRun(
                    seq=seq,
                    ok=True,
                    duration_ms=5,
                    raw_events_read=events,
                    entities_written=1,
                    facts_written=1,
                    report={"totals": {}},
                    created_at=datetime(2026, 8, seq, tzinfo=UTC),
                )
            )
        await session.flush()
        body = (await api.get("/api/report")).json()
        assert body["ran"] is True and body["raw_events_read"] == 99

    async def test_rebuilding_an_empty_estate_is_a_run_not_a_failure(self, api):
        body = (await api.post("/api/rebuild")).json()
        assert body["ok"] is True
        assert body["entities"] == 0

    async def test_a_rebuild_while_one_is_running_is_a_409_not_a_500(
        self, api, sessionmaker_for_test
    ):
        async with sessionmaker_for_test() as holder:
            await holder.execute(
                select(func.pg_try_advisory_xact_lock(run._REBUILD_LOCK_ID))
            )
            response = await api.post("/api/rebuild")
        assert response.status_code == 409
        assert "already in progress" in response.json()["detail"]
