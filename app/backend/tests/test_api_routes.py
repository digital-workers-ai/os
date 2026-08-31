import uuid
from datetime import UTC, datetime

import httpx
import pytest
import pytest_asyncio

from app.api import sources_api
from app.db import get_session
from app.main import app
from app.models import RawEvent


@pytest_asyncio.fixture
async def api(session, sessionmaker_for_test, monkeypatch):
    async def override():
        yield session

    app.dependency_overrides[get_session] = override
    monkeypatch.setattr(
        sources_api, "async_session", sessionmaker_for_test, raising=False
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

    async def test_manifests_are_empty_before_any_pull(self, api):
        assert (await api.get("/api/raw/manifests")).json() == {"manifests": []}


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
