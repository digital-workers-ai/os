import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import update

from app import store
from app.db import get_session
from app.engine import run
from app.main import app
from app.models import FactCurrent

SEEN = datetime(2026, 8, 1, tzinfo=UTC)
KEYS = {
    "observed_at",
    "canonical_id",
    "entity_type",
    "label",
    "source",
    "attr",
    "value",
}


@pytest_asyncio.fixture
async def api(session):
    async def override():
        yield session

    app.dependency_overrides[get_session] = override
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://backend"
    ) as client:
        yield client
    app.dependency_overrides.clear()


async def _stamp(session, canonical_id, attr, observed_at):
    await session.execute(
        update(FactCurrent)
        .where(FactCurrent.canonical_id == canonical_id, FactCurrent.attr == attr)
        .values(observed_at=observed_at)
    )
    await session.flush()


class TestActivity:
    async def test_an_empty_estate_is_zero_events_not_an_error(self, api):
        body = (await api.get("/api/activity")).json()
        assert body == {"events": []}

    async def test_every_event_carries_exactly_the_contract_keys(self, api, canonical):
        await canonical("company", {"name": "Acme", "domain": "acme.io"})
        events = (await api.get("/api/activity")).json()["events"]
        assert len(events) == 2
        for event in events:
            assert set(event) == KEYS

    async def test_events_come_newest_first_then_by_entity_then_attr(
        self, api, session, canonical
    ):
        acme = await canonical("company", {"name": "Acme", "domain": "acme.io"})
        globex = await canonical("company", {"name": "Globex"})
        jane = await canonical("person", {"email": "jane@acme.io"})
        await _stamp(session, jane, "email", SEEN + timedelta(days=1))
        events = (await api.get("/api/activity")).json()["events"]
        assert [(e["canonical_id"], e["attr"]) for e in events] == [
            (str(jane), "email"),
            *sorted(
                [(str(acme), "domain"), (str(acme), "name"), (str(globex), "name")]
            ),
        ]
        assert events[0]["observed_at"] == (SEEN + timedelta(days=1)).isoformat()
        assert events[1]["observed_at"] == SEEN.isoformat()

    async def test_each_event_carries_the_label_the_entity_list_serves(
        self, api, canonical
    ):
        await canonical("company", {"domain": "acme.io", "name": "Acme"})
        await canonical("person", {"email": "jane@acme.io", "phone": "555"})
        await canonical("deal", {"amount": "100"})
        listed = {
            e["canonical_id"]: e["label"]
            for e in (await api.get("/api/entities")).json()["entities"]
        }
        events = (await api.get("/api/activity")).json()["events"]
        assert len(events) == 5
        for event in events:
            assert event["label"] == listed[event["canonical_id"]]
        assert {e["label"] for e in events} == {"Acme", "jane@acme.io", "test|deal|3"}

    async def test_each_event_agrees_with_the_entity_detail(self, api, canonical):
        await canonical("company", {"name": "Acme"}, sources=["stripe", "hubspot"])
        await canonical("person", {"email": "jane@acme.io"})
        events = (await api.get("/api/activity")).json()["events"]
        assert len(events) == 2
        for event in events:
            detail = (await api.get(f"/api/entities/{event['canonical_id']}")).json()
            fact = next(f for f in detail["facts"] if f["attr"] == event["attr"])
            assert event["entity_type"] == detail["entity_type"]
            assert event["source"] == fact["source"]
            assert event["value"] == fact["value"]
            assert event["observed_at"] == fact["observed_at"]
        assert {e["source"] for e in events} == {"stripe", "hubspot"}

    async def test_the_limit_keeps_only_the_newest_events(
        self, api, session, canonical
    ):
        acme = await canonical("company", {"name": "Acme", "domain": "acme.io"})
        await _stamp(session, acme, "domain", SEEN + timedelta(hours=1))
        events = (await api.get("/api/activity?limit=1")).json()["events"]
        assert [(e["canonical_id"], e["attr"]) for e in events] == [
            (str(acme), "domain")
        ]

    async def test_the_default_limit_is_two_hundred(self, api, canonical):
        await canonical("company", {f"attr_{n:03}": n for n in range(201)})
        events = (await api.get("/api/activity")).json()["events"]
        assert len(events) == 200

    @pytest.mark.parametrize("query", ["limit=0", "limit=501"])
    async def test_out_of_range_limits_are_refused_not_clamped(self, api, query):
        assert (await api.get(f"/api/activity?{query}")).status_code == 422

    async def test_an_entity_with_no_labeling_fact_is_labeled_by_its_anchor(
        self, api, canonical
    ):
        await canonical("event", {"kind": "click"})
        events = (await api.get("/api/activity")).json()["events"]
        assert [(e["label"], e["attr"], e["value"]) for e in events] == [
            ("test|event|1", "kind", "click")
        ]

    async def test_a_derived_fact_is_a_computation_not_an_observation(
        self, api, session, canonical
    ):
        acme = await canonical("company", {"name": "Acme"})
        session.add(
            FactCurrent(
                id=uuid.uuid4(),
                canonical_id=acme,
                entity_type="company",
                attr="mrr",
                value="1500.0",
                value_num=1500.0,
                entity_id=None,
                raw_event_id=None,
                observed_at=SEEN,
                disagreements=0,
            )
        )
        await session.flush()
        events = (await api.get("/api/activity")).json()["events"]
        assert [(e["attr"], e["source"]) for e in events] == [("name", "hubspot")]

    async def test_a_rebuild_feeds_the_activity_from_raw_events(self, api, session):
        await store.save_raw(
            session,
            source="hubspot",
            object_type="companies",
            source_id="c1",
            raw_payload={"properties": {"domain": "acme.io", "name": "Acme"}},
        )
        await run.rebuild(session)
        events = (await api.get("/api/activity")).json()["events"]
        assert [
            (e["label"], e["source"], e["entity_type"], e["attr"], e["value"])
            for e in events
        ] == [
            ("Acme", "hubspot", "company", "domain", "acme.io"),
            ("Acme", "hubspot", "company", "name", "Acme"),
        ]
