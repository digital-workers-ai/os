from collections import Counter
from datetime import date

from sqlalchemy import select

from app import clock
from app.engine import competitors
from app.models import CanonicalLink, FactCurrent, SyncRun

AD_LIBRARIES = {"meta": "meta_ad_library", "google": "google_ads_transparency"}

TRUE = ("true", "yes", "1")


def _date(value):
    if value is None:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _shown(day):
    return None if day is None else day.isoformat()


def _day(value):
    return _shown(_date(value))


def _int(value):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _mentioned(value):
    return str(value).strip().lower() in TRUE


def _ordered(values, preferred):
    place = {name: index for index, name in enumerate(preferred)}
    return sorted(values, key=lambda value: (place.get(value, len(place)), value))


def _newest_first(value):
    day = _date(value)
    return (day is None, 0 if day is None else -day.toordinal())


def _latest(rows, key, on):
    newest: dict = {}
    for facts in rows:
        stamp = _date(facts.get(on)) or date.min
        if key(facts) not in newest or newest[key(facts)][0] <= stamp:
            newest[key(facts)] = (stamp, facts)
    return {name: facts for name, (_stamp, facts) in newest.items()}


def _latest_day(rows, on):
    days = [day for day in (_date(facts.get(on)) for facts in rows) if day is not None]
    return max(days).isoformat() if days else None


def _names():
    us = competitors.definitions()["us"]
    names = {us["domain"]: us["name"]}
    for spec in competitors.tracked().values():
        names[spec["domain"]] = spec.get("name", spec["domain"])
    return names


def _company(owner, facts, names):
    ref = facts.get("competitor_ref", "")
    return owner.get("name") or owner.get("domain") or names.get(ref, ref)


async def _facts(session, entity_type):
    query = select(FactCurrent.canonical_id, FactCurrent.attr, FactCurrent.value).where(
        FactCurrent.entity_type == entity_type
    )
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


async def _owned(session, entity_type):
    facts = await _facts(session, entity_type)
    owners = await _owners(session, list(facts))
    return [
        (canonical_id, facts[canonical_id], owners.get(canonical_id, {}))
        for canonical_id in sorted(facts, key=str)
    ]


async def _sync_status(session, source):
    row = (
        await session.execute(
            select(SyncRun.ok, SyncRun.started_at)
            .where(SyncRun.source == source)
            .order_by(SyncRun.started_at.desc())
            .limit(1)
        )
    ).first()
    if row is None:
        return {"source": source, "ok": None, "last_sync": None}
    return {"source": source, "ok": row.ok, "last_sync": row.started_at.isoformat()}


def _ad(canonical_id, facts, owner, names, today):
    first = _date(facts.get("first_seen"))
    last = _date(facts.get("last_seen"))
    return {
        "id": str(canonical_id),
        "competitor": _company(owner, facts, names),
        "text": facts.get("name", ""),
        "format": facts.get("category"),
        "first_seen": _shown(first),
        "last_seen": _shown(last),
        "days_running": None if first is None else ((last or today) - first).days,
        "running": last is None,
        "url": facts.get("url", ""),
    }


def _ads_order(row):
    days = row["days_running"]
    return (days is None, -(days or 0), *_newest_first(row["first_seen"]), row["id"])


async def ads(session, platform):
    today = clock.now().date()
    names = _names()
    owned = await _owned(session, "competitor_ad")
    rows = sorted(
        (
            _ad(canonical_id, facts, owner, names, today)
            for canonical_id, facts, owner in owned
            if facts.get("platform") == platform
        ),
        key=_ads_order,
    )
    return {
        "source": await _sync_status(session, AD_LIBRARIES[platform]),
        "total": len(rows),
        "running": sum(row["running"] for row in rows),
        "rows": rows,
    }


def _position(facts):
    return None if facts is None else _int(facts.get("position"))


async def rankings(session):
    rows = list((await _facts(session, "ranking")).values())
    newest = _latest(
        rows, lambda facts: (facts.get("keyword"), facts.get("domain")), "checked_on"
    )
    names = _names()
    seen = {facts["domain"] for facts in rows if facts.get("domain")}
    domains = _ordered(seen, names)
    tally = Counter(facts["engine"] for facts in rows if facts.get("engine"))
    return {
        "source": await _sync_status(session, "serp"),
        "engine": max(sorted(tally), key=lambda name: tally[name], default=""),
        "checked_on": _latest_day(rows, "checked_on"),
        "us": competitors.definitions()["us"]["domain"],
        "domains": [
            {"domain": domain, "name": names.get(domain, domain)} for domain in domains
        ],
        "keywords": [
            {
                "keyword": keyword,
                "positions": {
                    domain: _position(newest.get((keyword, domain)))
                    for domain in domains
                },
            }
            for keyword in sorted(
                {facts["keyword"] for facts in rows if facts.get("keyword")}
            )
        ],
    }


def _by_rank(entry):
    rank, brand = entry
    return (rank is None, rank or 0, brand)


async def answers(session):
    rows = list((await _facts(session, "ai_mention")).values())
    newest = _latest(
        rows,
        lambda facts: (facts.get("prompt"), facts.get("engine"), facts.get("brand")),
        "checked_on",
    )
    engines = _ordered(
        {facts["engine"] for facts in rows if facts.get("engine")},
        competitors.definitions()["engines"],
    )
    named: dict = {}
    tally: dict = {}
    for (prompt, engine, brand), facts in newest.items():
        seen = _mentioned(facts.get("mentioned"))
        found = named.setdefault(prompt, {}).setdefault(engine, [])
        if seen:
            found.append((_int(facts.get("rank")), brand))
        counted = tally.setdefault(brand, [0, 0])
        counted[0] += seen
        counted[1] += 1
    return {
        "source": await _sync_status(session, "ai_answers"),
        "checked_on": _latest_day(rows, "checked_on"),
        "engines": engines,
        "prompts": [
            {
                "prompt": prompt,
                "named": {
                    engine: [brand for _rank, brand in sorted(found, key=_by_rank)]
                    for engine, found in named[prompt].items()
                },
            }
            for prompt in sorted(
                {facts["prompt"] for facts in rows if facts.get("prompt")}
            )
        ],
        "brands": sorted(
            (
                {"brand": brand, "named": seen, "asked": asked, "rate": seen / asked}
                for brand, (seen, asked) in tally.items()
            ),
            key=lambda row: (-row["rate"], row["brand"]),
        ),
    }


def _page(facts, owner, names):
    return {
        "competitor": _company(owner, facts, names),
        "title": facts.get("name", ""),
        "url": facts.get("url", ""),
        "words": _int(facts.get("word_count")),
        "sha": facts.get("body_sha"),
        "fetched_on": _day(facts.get("fetched_on")),
    }


def _pages_order(row):
    return (*_newest_first(row["fetched_on"]), row["competitor"], row["url"])


async def pages(session):
    names = _names()
    owned = await _owned(session, "competitor_page")
    rows = sorted(
        (_page(facts, owner, names) for _canonical_id, facts, owner in owned),
        key=_pages_order,
    )
    return {
        "source": await _sync_status(session, "competitor_pages"),
        "total": len(rows),
        "rows": rows,
    }


def _post(facts, owner, names):
    return {
        "competitor": _company(owner, facts, names),
        "text": facts.get("name", ""),
        "posted_at": _day(facts.get("posted_at")),
        "likes": _int(facts.get("likes")),
        "comments": _int(facts.get("comments")),
        "shares": _int(facts.get("shares")),
        "url": facts.get("url", ""),
    }


def _posts_order(row):
    likes = row["likes"]
    return (likes is None, -(likes or 0), *_newest_first(row["posted_at"]))


async def posts(session):
    names = _names()
    owned = await _owned(session, "competitor_post")
    rows = sorted(
        (_post(facts, owner, names) for _canonical_id, facts, owner in owned),
        key=_posts_order,
    )
    return {
        "source": await _sync_status(session, "linkedin_posts"),
        "total": len(rows),
        "rows": rows,
    }
