from collections import Counter
from datetime import date

from fastapi import Depends, HTTPException, Query
from sqlalchemy import select

from app import clock
from app.api.routers import spy as router
from app.db import get_session
from app.engine import metrics, spy
from app.models import FactCurrent

CHECK_ATTRS = ("engine", "query", "checked_at", "answer", "sources")
MENTION_ATTRS = ("engine", "query", "checked_at", "company", "rank")
AD_ATTRS = (
    "company",
    "platform",
    "name",
    "category",
    "first_seen",
    "last_seen",
    "url",
    "preview",
)
POST_ATTRS = (
    "company",
    "platform",
    "name",
    "category",
    "posted_at",
    "likes",
    "comments",
    "url",
)


def _window(attr, from_, to) -> dict | None:
    if (from_ is None) != (to is None):
        raise HTTPException(422, "from and to travel together")
    if from_ is None:
        return None
    if from_ > to:
        raise HTTPException(422, "from must not be after to")
    return {"attr": attr, "from": from_.isoformat(), "to": to.isoformat()}


def _inside(window, value) -> bool:
    return window is not None and window["from"] <= (value or "")[:10] <= window["to"]


async def _rows(session, entity, attrs, filt, window) -> dict:
    ids = await metrics.ids_for(session, entity, filt, window)
    rows = {canonical_id: dict.fromkeys(attrs) for canonical_id in ids}
    for canonical_id, attr, value, value_num in await metrics.in_chunks(
        session,
        ids,
        lambda chunk: select(
            FactCurrent.canonical_id,
            FactCurrent.attr,
            FactCurrent.value,
            FactCurrent.value_num,
        ).where(FactCurrent.canonical_id.in_(chunk), FactCurrent.attr.in_(attrs)),
    ):
        rows[canonical_id][attr] = value if value_num is None else value_num
    return rows


def _newest_first(rows, attr) -> list:
    return sorted(
        rows.items(),
        key=lambda item: (item[1][attr] or "", str(item[0])),
        reverse=True,
    )


def _matching(rows, attr, value) -> list:
    return [
        (cid, facts) for cid, facts in rows if value is None or facts[attr] == value
    ]


def _by_company(rows) -> list:
    order = {company.name: n for n, company in enumerate(spy.definition().companies)}
    groups: dict = {}
    for _, facts in rows:
        groups.setdefault(facts["company"], []).append(facts)
    return sorted(
        groups.items(), key=lambda item: (order.get(item[0], len(order)), str(item[0]))
    )


def _total(group, attr) -> float:
    return sum(facts[attr] or 0 for facts in group)


def _row(canonical_id, facts, attrs) -> dict:
    return {"canonical_id": str(canonical_id), **{attr: facts[attr] for attr in attrs}}


def _at(facts) -> tuple:
    return (facts["engine"], facts["query"], facts["checked_at"])


def _mentioned(mentions, companies) -> dict:
    names = {company.name for company in companies}
    mentioned: dict = {}
    for facts in mentions.values():
        if facts["company"] in names:
            mentioned.setdefault(_at(facts), {})[facts["company"]] = facts["rank"]
    return mentioned


def _latest(checks) -> dict:
    latest: dict = {}
    for canonical_id, facts in _newest_first(checks, "checked_at"):
        latest.setdefault(facts["query"], {}).setdefault(
            facts["engine"], (canonical_id, facts)
        )
    return latest


def _check(engine, canonical_id, facts, mentioned) -> dict:
    return {
        "engine": engine,
        "checked_at": facts["checked_at"],
        "answer": facts["answer"],
        "sources": facts["sources"],
        "canonical_id": str(canonical_id),
        "mentions": mentioned.get(_at(facts), {}),
    }


def _query_checks(by_engine, mentioned) -> list:
    return [
        _check(engine, *by_engine[engine], mentioned)
        for engine in spy.ENGINES
        if engine in by_engine
    ]


def _share(companies, checks, mentioned) -> dict:
    per_engine = Counter(facts["engine"] for facts in checks)
    hits: Counter = Counter()
    for facts in checks:
        for name in mentioned.get(_at(facts), {}):
            hits[(name, facts["engine"])] += 1
    engines = [engine for engine in spy.ENGINES if engine in per_engine]
    return {
        company.name: {
            engine: hits[(company.name, engine)] / per_engine[engine]
            for engine in engines
        }
        for company in companies
    }


@router.get("/visibility")
async def visibility(
    engine: str | None = None,
    from_: date | None = Query(None, alias="from"),
    to: date | None = Query(None),
    session=Depends(get_session),
):
    if engine is not None and engine not in spy.ENGINES:
        raise HTTPException(422, f"engine must be one of {', '.join(spy.ENGINES)}")
    window = _window("checked_at", from_, to)
    filt = {} if engine is None else {"engine": engine}
    checks = await _rows(session, "visibility_check", CHECK_ATTRS, filt, window)
    mentions = await _rows(session, "visibility_mention", MENTION_ATTRS, filt, window)
    tracked = spy.definition()
    mentioned = _mentioned(mentions, tracked.companies)
    latest = _latest(checks)
    return {
        "as_of": clock.now().isoformat(),
        "engine": engine,
        "window_from": None if window is None else window["from"],
        "window_to": None if window is None else window["to"],
        "companies": [
            {"name": company.name, "domain": company.domain, "role": company.role}
            for company in tracked.companies
        ],
        "checks": len(checks),
        "queries": [
            {
                "query": query,
                "checks": _query_checks(latest.get(query, {}), mentioned),
            }
            for query in tracked.queries
        ],
        "share": _share(tracked.companies, checks.values(), mentioned),
    }


@router.get("/ads")
async def ads(
    platform: str | None = None,
    from_: date | None = Query(None, alias="from"),
    to: date | None = Query(None),
    session=Depends(get_session),
):
    window = _window("last_seen", from_, to)
    rows = await _rows(session, "ad", AD_ATTRS, {}, window)
    matching = _matching(_newest_first(rows, "last_seen"), "platform", platform)
    return {
        "as_of": clock.now().isoformat(),
        "companies": [
            {
                "name": name,
                "ads": len(group),
                "new": sum(
                    1 for facts in group if _inside(window, facts["first_seen"])
                ),
            }
            for name, group in _by_company(matching)
        ],
        "ads": [
            _row(canonical_id, facts, AD_ATTRS) for canonical_id, facts in matching
        ],
    }


@router.get("/posts")
async def posts(
    company: str | None = None,
    from_: date | None = Query(None, alias="from"),
    to: date | None = Query(None),
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session=Depends(get_session),
):
    window = _window("posted_at", from_, to)
    rows = _newest_first(
        await _rows(session, "competitor_post", POST_ATTRS, {}, window), "posted_at"
    )
    matching = _matching(rows, "company", company)
    return {
        "as_of": clock.now().isoformat(),
        "companies": [
            {
                "name": name,
                "posts": len(group),
                "likes": _total(group, "likes"),
                "comments": _total(group, "comments"),
            }
            for name, group in _by_company(rows)
        ],
        "total": len(matching),
        "limit": limit,
        "offset": offset,
        "posts": [
            _row(canonical_id, facts, POST_ATTRS)
            for canonical_id, facts in matching[offset : offset + limit]
        ],
    }
