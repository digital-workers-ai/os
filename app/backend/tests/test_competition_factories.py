import yaml

from app import caches
from app.models import SyncRun
from tests.conftest import NOW

VIDORA = {"name": "Vidora", "domain": "vidora.ai"}
CLIPWISE = {"name": "Clipwise", "domain": "clipwise.io"}

DEFINITIONS = {
    "us": {"name": "Digital Workers", "domain": "hiredigitalworkers.com"},
    "competitors": {
        "vidora": {
            **VIDORA,
            "meta_page_id": "204815000001",
            "google_advertiser_id": "AR11111111111111111111",
        },
        "clipwise": {
            **CLIPWISE,
            "meta_page_id": "204815000002",
            "google_advertiser_id": "AR22222222222222222222",
        },
    },
    "keywords": ["ai ugc ads", "ugc video tool"],
    "prompts": ["best ai ugc ad tool"],
    "engines": ["chatgpt", "perplexity", "gemini"],
}

AD = {
    "name": "You approve every ad before it runs. Why?",
    "platform": "meta",
    "category": "video",
    "competitor_ref": "204815000001",
    "first_seen": "2026-06-12",
    "url": "https://facebook.com/ads/1",
}

RANKING = {
    "keyword": "ai ugc ads",
    "engine": "google",
    "domain": "hiredigitalworkers.com",
    "position": "12",
    "url": "https://hiredigitalworkers.com/ai-ugc-ads",
    "checked_on": "2026-09-01",
}

MENTION = {
    "prompt": "best ai ugc ad tool",
    "engine": "chatgpt",
    "brand": "Digital Workers",
    "mentioned": "true",
    "rank": "1",
    "checked_on": "2026-09-01",
}

PAGE = {
    "url": "https://vidora.ai/pricing",
    "name": "Pricing",
    "competitor_ref": "vidora.ai",
    "body_sha": "a3f9",
    "word_count": "420",
    "fetched_on": "2026-09-01",
}

POST = {
    "name": "We shut down our studio",
    "platform": "linkedin",
    "competitor_ref": "vidora.ai",
    "posted_at": "2026-09-02",
    "likes": "890",
    "comments": "12",
    "shares": "4",
    "url": "https://linkedin.com/posts/1",
}


async def add(session, row):
    session.add(row)
    await session.flush()
    return row


async def sync_run(session, source, ok=True, started_at=NOW):
    return await add(session, SyncRun(source=source, ok=ok, started_at=started_at))


def definitions_file(root, doc=DEFINITIONS):
    path = root / "competitors.yaml"
    path.write_text(yaml.safe_dump(doc, sort_keys=False))
    return path


def track(monkeypatch, path):
    from app.engine import competitors

    monkeypatch.setattr(competitors, "DEFAULT_COMPETITORS", path)
    caches.reset_all()


def _facts(base, given):
    return {k: v for k, v in {**base, **given}.items() if v is not None}


async def _owned(canonical, link, entity_type, source, base, owner, facts):
    made = await canonical(entity_type, _facts(base, facts), sources=[source])
    if owner is not None:
        await link(made, "belongs_to", owner)
    return made


async def competitor(canonical, spec=VIDORA):
    return await canonical("competitor", {**spec}, sources=["meta_ad_library"])


async def ad(canonical, link, owner=None, **facts):
    return await _owned(
        canonical, link, "competitor_ad", "meta_ad_library", AD, owner, facts
    )


async def page(canonical, link, owner=None, **facts):
    return await _owned(
        canonical, link, "competitor_page", "competitor_pages", PAGE, owner, facts
    )


async def post(canonical, link, owner=None, **facts):
    return await _owned(
        canonical, link, "competitor_post", "linkedin_posts", POST, owner, facts
    )


async def ranking(canonical, **facts):
    return await canonical("ranking", _facts(RANKING, facts), sources=["serp"])


async def mention(canonical, **facts):
    return await canonical("ai_mention", _facts(MENTION, facts), sources=["ai_answers"])
