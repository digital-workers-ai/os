from collections import Counter
from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import and_, func, select

from app import clock
from app.engine import competitors as company
from app.models import (
    CanonicalLink,
    CanonicalMember,
    EnrichedFact,
    Entity,
    FactCurrent,
    RawEvent,
    SyncRun,
)
from app.sources import catalog
from app.studio import errors, proposals, runs

AD = "competitor_ad"

READING = "competitor_creative"

FACETS = ("competitor", "platform", "angle", "hook", "format")

LONG_RUNNING = 90

NEW_DAYS = 7

WEEKS = 12

RECENT_POSTS = 20

RECENT_CHANGES = 20

COMPETITOR_SOURCES = "Competitors"

LOCATION = ""

TRUE = ("true", "yes", "1")


def _uuid(value):
    try:
        return UUID(value)
    except ValueError as exc:
        raise errors.Missing(f"no swipe item {value!r}") from exc


def _date(value):
    if value is None:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _int(value):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _week_of(day):
    return day - timedelta(days=day.weekday())


def _ordered(values, preferred):
    place = {name: index for index, name in enumerate(preferred)}
    return sorted(values, key=lambda value: (place.get(value, len(place)), value))


async def _facts(session, entity_type, ids=None):
    query = select(FactCurrent.canonical_id, FactCurrent.attr, FactCurrent.value).where(
        FactCurrent.entity_type == entity_type
    )
    if ids is not None:
        query = query.where(FactCurrent.canonical_id.in_(ids))
    found: dict = {}
    for canonical_id, attr, value in (await session.execute(query)).all():
        found.setdefault(canonical_id, {})[attr] = value
    return found


async def _owners(session, ids):
    rows = (
        await session.execute(
            select(CanonicalLink.from_canonical, FactCurrent.attr, FactCurrent.value)
            .join(FactCurrent, FactCurrent.canonical_id == CanonicalLink.to_canonical)
            .where(
                CanonicalLink.rel == "belongs_to",
                CanonicalLink.from_canonical.in_(ids),
            )
        )
    ).all()
    owners: dict = {}
    for canonical_id, attr, value in rows:
        owners.setdefault(canonical_id, {})[attr] = value
    return owners


async def _labels(session, ids):
    rows = (
        (
            await session.execute(
                select(EnrichedFact)
                .where(
                    EnrichedFact.reading == READING,
                    EnrichedFact.canonical_id.in_(ids),
                )
                .order_by(EnrichedFact.attr, EnrichedFact.value)
            )
        )
        .scalars()
        .all()
    )
    labels: dict = {}
    for row in rows:
        labels.setdefault(row.canonical_id, []).append(
            {"field": row.attr, "label": row.value, "quote": row.quote or None}
        )
    return labels


def _named(labels):
    return {label["field"]: label["label"] for label in labels}


def _company(owner, facts):
    return owner.get("name") or owner.get("domain") or facts.get("competitor_ref", "")


def _row(canonical_id, facts, owner, labels, today):
    first = _date(facts.get("first_seen"))
    last = _date(facts.get("last_seen"))
    named = _named(labels)
    return {
        "id": str(canonical_id),
        "competitor": _company(owner, facts),
        "platform": facts.get("platform", ""),
        "format": facts.get("category") or named.get("format", ""),
        "days_running": 0 if first is None else (today - first).days,
        "first_seen": "" if first is None else first.isoformat(),
        "last_seen": None if last is None else last.isoformat(),
        "running": last is None or last >= today,
        "headline": "",
        "body": facts.get("name", ""),
        "angle": named.get("angle"),
        "hook": named.get("hook"),
        "offer": named.get("offer"),
        "proof": named.get("proof"),
        "url": facts.get("url", ""),
    }


async def _rows(session):
    facts = await _facts(session, AD)
    ids = list(facts)
    owners = await _owners(session, ids)
    labels = await _labels(session, ids)
    today = clock.now().date()
    return [
        _row(
            canonical_id,
            facts[canonical_id],
            owners.get(canonical_id, {}),
            labels.get(canonical_id, []),
            today,
        )
        for canonical_id in sorted(ids, key=str)
    ]


def _kept(rows, wanted):
    return [
        row
        for row in rows
        if all(row[field] == value for field, value in wanted.items() if value)
    ]


def _sorted(rows, sort):
    if sort == "first_seen":
        return sorted(
            rows, key=lambda row: (row["first_seen"], row["id"]), reverse=True
        )
    return sorted(rows, key=lambda row: (-row["days_running"], row["id"]))


async def file(
    session,
    competitor=None,
    platform=None,
    angle=None,
    hook=None,
    fmt=None,
    sort="days_running",
    limit=50,
    offset=0,
):
    rows = await _rows(session)
    kept = _sorted(
        _kept(
            rows,
            {
                "competitor": competitor,
                "platform": platform,
                "angle": angle,
                "hook": hook,
                "format": fmt,
            },
        ),
        sort,
    )
    return {
        "items": kept[offset : offset + limit],
        "total": len(kept),
        "facets": {
            field: sorted({row[field] for row in rows if row[field]})
            for field in FACETS
        },
    }


async def _raw_events(session, canonical_id):
    return (
        await session.execute(
            select(func.count())
            .select_from(RawEvent)
            .join(
                Entity,
                and_(
                    Entity.source == RawEvent.source,
                    Entity.object_type == RawEvent.object_type,
                    Entity.source_id == RawEvent.source_id,
                ),
            )
            .join(CanonicalMember, CanonicalMember.entity_id == Entity.id)
            .where(CanonicalMember.canonical_id == canonical_id)
        )
    ).scalar_one()


async def item(session, swipe_id):
    canonical_id = _uuid(swipe_id)
    facts = (await _facts(session, AD, [canonical_id])).get(canonical_id)
    if facts is None:
        raise errors.Missing(f"no swipe item {swipe_id!r}")
    owners = await _owners(session, [canonical_id])
    labels = (await _labels(session, [canonical_id])).get(canonical_id, [])
    return {
        **_row(
            canonical_id,
            facts,
            owners.get(canonical_id, {}),
            labels,
            clock.now().date(),
        ),
        "labels": labels,
        "raw_events": await _raw_events(session, canonical_id),
        "landing_url": None,
        "counter": _named(labels).get("counter"),
    }


def _by_competitor(rows):
    grouped: dict = {}
    for row in rows:
        entry = grouped.setdefault(
            row["competitor"],
            {
                "competitor": row["competitor"],
                "active": 0,
                "long_running": 0,
                "platforms": {},
            },
        )
        entry["active"] += row["running"]
        entry["long_running"] += row["running"] and row["days_running"] >= LONG_RUNNING
        entry["platforms"][row["platform"]] = (
            entry["platforms"].get(row["platform"], 0) + 1
        )
    return sorted(grouped.values(), key=lambda entry: entry["competitor"])


def _new_per_week(rows, today):
    first_week = _week_of(today) - timedelta(weeks=WEEKS - 1)
    weeks = [first_week + timedelta(weeks=index) for index in range(WEEKS)]
    counted = dict.fromkeys(weeks, 0)
    for row in rows:
        first = _date(row["first_seen"])
        week = None if first is None else _week_of(first)
        if week in counted:
            counted[week] += 1
    return [{"week": week.isoformat(), "count": counted[week]} for week in weeks]


async def ads(session, competitor=None, platform=None):
    today = clock.now().date()
    rows = _kept(await _rows(session), {"competitor": competitor, "platform": platform})
    fresh = today - timedelta(days=NEW_DAYS)
    first_seen = [_date(row["first_seen"]) for row in rows]
    return {
        "active": sum(1 for row in rows if row["running"]),
        "new_7d": sum(
            1 for first in first_seen if first is not None and first >= fresh
        ),
        "long_running": sum(
            1 for row in rows if row["running"] and row["days_running"] >= LONG_RUNNING
        ),
        "by_competitor": _by_competitor(rows),
        "angle_mix": dict(
            sorted(Counter(row["angle"] for row in rows if row["angle"]).items())
        ),
        "new_per_week": _new_per_week(rows, today),
    }


def _latest(rows, key, on):
    newest: dict = {}
    for facts in rows:
        stamp = _date(facts.get(on)) or date.min
        if key(facts) not in newest or newest[key(facts)][0] <= stamp:
            newest[key(facts)] = (stamp, facts)
    return {name: facts for name, (_stamp, facts) in newest.items()}


async def rankings(session, keyword=None):
    rows = [
        facts
        for facts in (await _facts(session, "ranking")).values()
        if not keyword or facts.get("keyword") == keyword
    ]
    newest = _latest(
        rows, lambda facts: (facts.get("keyword"), facts.get("domain")), "checked_on"
    )
    ours = company.definitions().get("us", {}).get("domain")
    tracked = [spec["domain"] for spec in company.tracked().values()]
    domains = _ordered(
        {facts["domain"] for facts in rows if facts.get("domain")}, [ours, *tracked]
    )
    keywords = sorted({facts["keyword"] for facts in rows if facts.get("keyword")})
    tally = Counter(facts["engine"] for facts in rows if facts.get("engine"))
    return {
        "engine": max(sorted(tally), key=lambda name: tally[name], default=""),
        "location": LOCATION,
        "us": ours or "",
        "keywords": [
            {
                "keyword": name,
                "positions": {
                    domain: _position(newest.get((name, domain))) for domain in domains
                },
                "history": _history(
                    [
                        facts
                        for facts in rows
                        if facts.get("keyword") == name and facts.get("domain") == ours
                    ],
                    clock.now().date(),
                ),
            }
            for name in keywords
        ],
        "domains": domains,
    }


def _position(facts):
    if facts is None:
        return None
    return _int(facts.get("position"))


def _history(rows, today):
    first_week = _week_of(today) - timedelta(weeks=WEEKS - 1)
    weeks = [first_week + timedelta(weeks=index) for index in range(WEEKS)]
    seen = _latest(
        rows,
        lambda facts: _week_of(_date(facts.get("checked_on")) or today),
        "checked_on",
    )
    return [
        {"date": week.isoformat(), "position": _position(seen.get(week))}
        for week in weeks
    ]


def _mentioned(value):
    return str(value).strip().lower() in TRUE


async def answers(session, prompt=None):
    rows = [
        facts
        for facts in (await _facts(session, "ai_mention")).values()
        if not prompt or facts.get("prompt") == prompt
    ]
    newest = _latest(
        rows,
        lambda facts: (facts.get("prompt"), facts.get("engine"), facts.get("brand")),
        "checked_on",
    )
    engines = _ordered(
        {facts["engine"] for facts in rows if facts.get("engine")},
        company.definitions().get("engines", []),
    )
    prompts = sorted({facts["prompt"] for facts in rows if facts.get("prompt")})
    named: dict = {}
    rate: dict = {}
    for (asked, engine, brand), facts in newest.items():
        named.setdefault(asked, {}).setdefault(engine, {})[brand] = _mentioned(
            facts.get("mentioned")
        )
        seen, total = rate.get(brand, (0, 0))
        rate[brand] = (seen + _mentioned(facts.get("mentioned")), total + 1)
    ours = company.definitions().get("us", {}).get("domain", "")
    cited = Counter(
        facts["cited_url"]
        for facts in rows
        if facts.get("cited_url") and ours in facts["cited_url"]
    )
    return {
        "us": ours,
        "engines": engines,
        "prompts": [
            {"prompt": asked, "named": named.get(asked, {})} for asked in prompts
        ],
        "mention_rate": {
            brand: seen / total for brand, (seen, total) in sorted(rate.items())
        },
        "cited": [
            {"url": url, "count": count}
            for url, count in sorted(
                cited.items(), key=lambda entry: (-entry[1], entry[0])
            )
        ],
    }


def _changes(pages, owners, today):
    by_url: dict = {}
    for canonical_id, facts in pages.items():
        by_url.setdefault(facts.get("url"), []).append((canonical_id, facts))
    found = []
    for url, reads in by_url.items():
        reads.sort(key=lambda entry: _date(entry[1].get("fetched_on")) or today)
        for (_before_id, before), (after_id, after) in zip(
            reads, reads[1:], strict=False
        ):
            if before.get("body_sha") == after.get("body_sha"):
                continue
            found.append(
                {
                    "competitor": _company(owners.get(after_id, {}), after),
                    "url": url,
                    "on": after.get("fetched_on", ""),
                    "before": before.get("body_sha", ""),
                    "after": after.get("body_sha", ""),
                }
            )
    return sorted(found, key=lambda change: change["on"], reverse=True)[:RECENT_CHANGES]


async def content(session):
    today = clock.now().date()
    pages = await _facts(session, "competitor_page")
    posts = await _facts(session, "competitor_post")
    owners = await _owners(session, list(pages) + list(posts))
    recent = sorted(
        posts.items(),
        key=lambda entry: (entry[1].get("posted_at", ""), str(entry[0])),
        reverse=True,
    )
    return {
        "pages": len(pages),
        "posts": len(posts),
        "changes": _changes(pages, owners, today),
        "recent_posts": [
            {
                "competitor": _company(owners.get(canonical_id, {}), facts),
                "text": facts.get("name", ""),
                "posted_at": facts.get("posted_at", ""),
                "likes": _int(facts.get("likes")),
                "url": facts.get("url", ""),
            }
            for canonical_id, facts in recent[:RECENT_POSTS]
        ],
    }


async def _sync_status(session):
    rows = (
        await session.execute(
            select(SyncRun.source, SyncRun.ok, SyncRun.started_at)
            .distinct(SyncRun.source)
            .order_by(SyncRun.source, SyncRun.started_at.desc())
        )
    ).all()
    return {row.source: (row.ok, row.started_at.isoformat()) for row in rows}


async def _rows_by_competitor(session):
    rows = (
        await session.execute(
            select(
                FactCurrent.value, Entity.source, func.count(CanonicalMember.entity_id)
            )
            .select_from(CanonicalLink)
            .join(
                CanonicalMember,
                CanonicalMember.canonical_id == CanonicalLink.from_canonical,
            )
            .join(Entity, Entity.id == CanonicalMember.entity_id)
            .join(
                FactCurrent,
                and_(
                    FactCurrent.canonical_id == CanonicalLink.to_canonical,
                    FactCurrent.attr == "domain",
                ),
            )
            .where(CanonicalLink.rel == "belongs_to")
            .group_by(FactCurrent.value, Entity.source)
        )
    ).all()
    return {(domain, source): count for domain, source, count in rows}


def competitor_sources():
    return [
        entry["source"]
        for entry in catalog.catalog()
        if entry["category"] == COMPETITOR_SOURCES
    ]


async def companies(session):
    doc = company.definitions()
    us = doc.get("us", {})
    status = await _sync_status(session)
    counted = await _rows_by_competitor(session)
    sources = competitor_sources()
    return {
        "us": {"name": us.get("name", ""), "domain": us.get("domain", "")},
        "competitors": [
            {
                "slug": slug,
                "name": spec.get("name", slug),
                "domain": spec.get("domain", ""),
                "sources": [
                    {
                        "source": source,
                        "ok": status.get(source, (False, None))[0],
                        "last_sync": status.get(source, (False, None))[1],
                        "rows": counted.get((spec.get("domain"), source), 0),
                    }
                    for source in sources
                ],
            }
            for slug, spec in sorted(company.tracked().items())
        ],
    }


REMIX = "dw-remix"


async def remix(session, swipe_id, kind, look, slot, keep):
    canonical_id = _uuid(swipe_id)
    facts = (await _facts(session, AD, [canonical_id])).get(canonical_id)
    if facts is None:
        raise errors.Missing(f"no swipe item {swipe_id!r}")
    owner = (await _owners(session, [canonical_id])).get(canonical_id, {})
    ref = f"swipe/{canonical_id}"
    ask = f"remix {ref} as {kind}, keep: {', '.join(keep) or 'nothing'}"
    made = await proposals.create(
        session,
        kind=kind,
        title=f"counter to {_company(owner, facts) or ref}",
        skill=REMIX,
        skill_sha=runs.sha(REMIX),
        slot_name=slot,
        reactive=True,
        evidence=[
            {"kind": "competitor_ad", "ref": ref, "detail": "the ad this remix answers"}
        ],
    )
    started = await runs.start(
        session,
        skill=REMIX,
        mode="draft",
        input=ask,
        look=look,
        slot=slot,
        proposal_seq=made.seq,
    )
    return made.seq, started
