import httpx
import pytest
import pytest_asyncio
from sqlalchemy import func, select

from app import sync
from app.api import entities_api, sources_api
from app.db import get_session
from app.engine import run
from app.main import app
from app.models import (
    CanonicalAlias,
    CanonicalLink,
    CanonicalMember,
    EngineRun,
    Entity,
    EntityCanonical,
    FactCurrent,
)

pytestmark = pytest.mark.e2e

SOURCES = ["hubspot", "stripe"]


async def _rebuilt(session, sessionmaker_for_test):
    synced = await sync.run_all(sessionmaker_for_test, SOURCES)
    assert synced["failed"] == 0, synced
    return await run.rebuild(session)


@pytest_asyncio.fixture
async def api(session, sessionmaker_for_test, monkeypatch):
    async def override():
        yield session

    app.dependency_overrides[get_session] = override
    for module in (sources_api, entities_api):
        monkeypatch.setattr(
            module, "async_session", sessionmaker_for_test, raising=False
        )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://backend"
    ) as client:
        yield client
    app.dependency_overrides.clear()


async def _count(session, model):
    return (await session.execute(select(func.count()).select_from(model))).scalar_one()


async def test_the_sync_stores_the_whole_two_source_estate(
    session, sessionmaker_for_test
):
    result = await sync.run_all(sessionmaker_for_test, SOURCES)
    assert result["failed"] == 0, result
    assert result["rows_written"] == 62


async def test_the_rebuild_resolves_the_estate_into_canonicals(
    session, sessionmaker_for_test
):
    result = await _rebuilt(session, sessionmaker_for_test)
    assert result["ok"] is True

    entities_by_type = dict(
        (
            await session.execute(
                select(Entity.entity_type, func.count()).group_by(Entity.entity_type)
            )
        ).all()
    )
    assert entities_by_type == {
        "company": 20,
        "person": 32,
        "deal": 10,
        "subscription": 10,
    }

    canonical_by_type = dict(
        (
            await session.execute(
                select(EntityCanonical.entity_type, func.count()).group_by(
                    EntityCanonical.entity_type
                )
            )
        ).all()
    )
    assert canonical_by_type == {
        "company": 10,
        "person": 22,
        "deal": 10,
        "subscription": 10,
    }
    assert sum(canonical_by_type.values()) == 52

    assert await _count(session, CanonicalMember) == 72
    member_count_sum = (
        await session.execute(select(func.sum(EntityCanonical.member_count)))
    ).scalar_one()
    assert member_count_sum == 72

    assert await _count(session, FactCurrent) == 173

    newest = (
        await session.execute(select(EngineRun).order_by(EngineRun.seq.desc()).limit(1))
    ).scalar_one()
    assert newest.canonical_written == 52
    assert newest.links_written == 10


async def test_every_subscription_links_to_its_company(session, sessionmaker_for_test):
    result = await _rebuilt(session, sessionmaker_for_test)

    links = (await session.execute(select(CanonicalLink))).scalars().all()
    assert len(links) == 10
    assert all(link.rel == "belongs_to" for link in links)
    assert all(link.grounding == "via:customer_ref" for link in links)

    rates = result["report"]["match_rates"]
    assert rates
    assert all(rate["match_rate"] == 1.0 for rate in rates.values())


async def test_the_two_renamed_companies_surface_as_disagreements(
    session, sessionmaker_for_test
):
    result = await _rebuilt(session, sessionmaker_for_test)
    assert result["report"]["disagreements"] == {"company.name": 2}

    contested = (
        (
            await session.execute(
                select(FactCurrent).where(
                    FactCurrent.entity_type == "company",
                    FactCurrent.attr == "name",
                    FactCurrent.disagreements > 0,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(contested) == 2
    assert all(fact.disagreements == 1 for fact in contested)


async def test_a_clean_estate_reports_no_skips_dead_paths_or_fallbacks(
    session, sessionmaker_for_test
):
    report = (await _rebuilt(session, sessionmaker_for_test))["report"]
    assert report["skips"] == {}
    assert report["dead_paths"] == []
    assert "observed_at_fallback/stripe" not in report["counts"]


async def test_the_entities_api_serves_the_canonical_layer(
    api, session, sessionmaker_for_test
):
    await _rebuilt(session, sessionmaker_for_test)
    body = (await api.get("/api/entities?entity_type=company")).json()
    assert body["total"] == 10
    assert all(row["members"] == 2 for row in body["entities"])
    assert body["entities"][0]["facts"] == {
        "domain": "acme.io",
        "industry": "Software",
        "name": "Acme Corp",
    }


async def test_the_detail_route_serves_members_and_edges_for_acme(
    api, session, sessionmaker_for_test
):
    await _rebuilt(session, sessionmaker_for_test)
    listing = (await api.get("/api/entities?entity_type=company")).json()
    acme_id = listing["entities"][0]["canonical_id"]
    body = (await api.get(f"/api/entities/{acme_id}")).json()
    assert {(m["source"], m["evidence"]) for m in body["members"]} == {
        ("hubspot", "domain=acme.io"),
        ("stripe", "domain=acme.io"),
    }
    incoming = body["links"]["in"]
    assert len(incoming) == 1
    assert incoming[0]["rel"] == "belongs_to"


async def test_a_second_rebuild_mints_byte_identical_canonical_ids(
    session, sessionmaker_for_test
):
    await _rebuilt(session, sessionmaker_for_test)
    before = sorted(
        (await session.execute(select(EntityCanonical.canonical_id))).scalars().all()
    )

    async with sessionmaker_for_test() as second:
        await run.rebuild(second)
    after = sorted(
        (await session.execute(select(EntityCanonical.canonical_id))).scalars().all()
    )

    assert len(before) == 52
    assert before == after
    assert await _count(session, CanonicalAlias) == 0
