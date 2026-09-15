import httpx
import pytest
import pytest_asyncio

from app.db import get_session
from app.main import app
from app.skills import runner
from tests.test_studio_factories import enriched, studio_on, sync_run

VIDORA = {"name": "Vidora", "domain": "vidora.ai"}


@pytest_asyncio.fixture
async def api(session, monkeypatch):
    started: list = []

    async def detached(seq, ask, **kwargs):
        started.append((seq, ask))

    async def override():
        yield session

    monkeypatch.setattr(runner, "execute_detached", detached)
    studio_on(monkeypatch)
    app.dependency_overrides[get_session] = override
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://backend"
    ) as client:
        client.started = started
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def competitor(canonical):
    async def _make(**facts):
        return await canonical(
            "competitor", {**VIDORA, **facts}, sources=["meta_ad_library"]
        )

    return _make


@pytest.fixture
def ad(canonical, link):
    async def _make(owner=None, **facts):
        base = {
            "name": "You approve every ad before it runs. Why?",
            "platform": "meta",
            "category": "video",
            "competitor_ref": "204815000001",
            "first_seen": "2026-06-12",
            "url": "https://facebook.com/ads/1",
        }
        made = await canonical(
            "competitor_ad",
            {k: v for k, v in {**base, **facts}.items() if v is not None},
            sources=["meta_ad_library"],
        )
        if owner is not None:
            await link(made, "belongs_to", owner)
        return made

    return _make


async def test_the_companies_answer_us_and_the_tracked(api, session):
    await sync_run(session, "meta_ad_library")
    body = (await api.get("/api/competitors")).json()
    assert body["us"]["domain"] == "hiredigitalworkers.com"
    assert [row["slug"] for row in body["competitors"]] == [
        "avatarly",
        "clipwise",
        "vidora",
    ]
    sources = {row["source"]: row for row in body["competitors"][0]["sources"]}
    assert sources["meta_ad_library"]["ok"] is True


async def test_the_swipe_file_answers_items_facets_and_a_total(
    api, session, competitor, ad
):
    made = await ad(await competitor())
    await enriched(session, made, attr="angle", value="approval")
    body = (await api.get("/api/competitors/swipe")).json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == str(made)
    assert body["items"][0]["angle"] == "approval"
    assert body["facets"]["competitor"] == ["Vidora"]


async def test_the_swipe_file_narrows_sorts_and_pages(api, session, competitor, ad):
    owner = await competitor()
    await ad(owner, first_seen="2026-08-01")
    await ad(owner, first_seen="2026-05-01", platform="google")
    body = (await api.get("/api/competitors/swipe?platform=google")).json()
    assert body["total"] == 1
    newest = (await api.get("/api/competitors/swipe?sort=first_seen&limit=1")).json()
    assert newest["items"][0]["first_seen"] == "2026-08-01"
    later = (
        await api.get("/api/competitors/swipe?sort=first_seen&limit=1&offset=1")
    ).json()
    assert later["items"][0]["first_seen"] == "2026-05-01"
    assert (await api.get("/api/competitors/swipe?format=video")).json()["total"] == 2


async def test_a_swipe_item_answers_its_labels_and_raw_count(
    api, session, competitor, ad
):
    made = await ad(await competitor())
    await enriched(session, made, attr="hook", value="contrast", quote="Hiring vs us")
    body = (await api.get(f"/api/competitors/swipe/{made}")).json()
    assert body["labels"] == [
        {"field": "hook", "label": "contrast", "quote": "Hiring vs us"}
    ]
    assert body["raw_events"] == 0
    assert body["landing_url"] is None


async def test_a_swipe_item_nobody_has_is_not_found(api):
    assert (await api.get("/api/competitors/swipe/nonsense")).status_code == 404


async def test_a_remix_answers_the_proposal_it_opened(api, session, competitor, ad):
    made = await ad(await competitor())
    answer = await api.post(
        f"/api/competitors/swipe/{made}/remix",
        json={"kind": "ad", "look": "aios", "slot": "counter_ad", "keep": ["hook"]},
    )
    assert answer.json()["proposal"] > 0
    assert api.started[0][1].skill == "dw-remix"
    detail = (
        await api.get(f"/api/studio/proposals/{answer.json()['proposal']}")
    ).json()
    assert detail["skill"] == "dw-remix"


async def test_a_remix_of_nothing_is_not_found(api):
    answer = await api.post(
        "/api/competitors/swipe/nonsense/remix", json={"kind": "ad", "keep": []}
    )
    assert answer.status_code == 404


async def test_a_remix_while_studio_is_off_is_refused(
    api, session, competitor, ad, monkeypatch
):
    made = await ad(await competitor())
    monkeypatch.setattr("app.config.settings.STUDIO_ENABLED", False)
    answer = await api.post(
        f"/api/competitors/swipe/{made}/remix", json={"kind": "ad", "keep": []}
    )
    assert answer.status_code == 409


async def test_the_ads_view_answers_counts_and_a_split(api, session, competitor, ad):
    await ad(await competitor(), first_seen="2026-05-01")
    body = (await api.get("/api/competitors/ads")).json()
    assert (body["active"], body["long_running"]) == (1, 1)
    assert body["by_competitor"][0]["competitor"] == "Vidora"
    assert len(body["new_per_week"]) == 12
    narrowed = (
        await api.get("/api/competitors/ads?competitor=Vidora&platform=meta")
    ).json()
    assert narrowed["active"] == 1


async def test_the_rankings_answer_keywords_domains_and_us(api, canonical):
    await canonical(
        "ranking",
        {
            "keyword": "ai ugc ads",
            "engine": "google",
            "domain": "hiredigitalworkers.com",
            "position": "12",
            "checked_on": "2026-09-01",
        },
        sources=["serp"],
    )
    body = (await api.get("/api/competitors/rankings")).json()
    assert body["us"] == "hiredigitalworkers.com"
    assert body["keywords"][0]["positions"] == {"hiredigitalworkers.com": 12}
    assert len(body["keywords"][0]["history"]) == 12
    assert (await api.get("/api/competitors/rankings?keyword=nothing")).json()[
        "keywords"
    ] == []


async def test_the_answers_view_pivots_prompts_engines_and_brands(api, canonical):
    await canonical(
        "ai_mention",
        {
            "prompt": "best ai ugc ad tool",
            "engine": "chatgpt",
            "brand": "Digital Workers",
            "mentioned": "true",
            "cited_url": "https://hiredigitalworkers.com/a",
            "checked_on": "2026-09-01",
        },
        sources=["ai_answers"],
    )
    body = (await api.get("/api/competitors/answers")).json()
    assert body["us"] == "hiredigitalworkers.com"
    assert body["prompts"][0]["named"]["chatgpt"] == {"Digital Workers": True}
    assert body["mention_rate"] == {"Digital Workers": 1.0}
    assert body["cited"] == [{"url": "https://hiredigitalworkers.com/a", "count": 1}]
    narrowed = await api.get("/api/competitors/answers?prompt=nothing")
    assert narrowed.json()["prompts"] == []


async def test_the_content_view_answers_pages_posts_and_changes(
    api, canonical, link, competitor
):
    owner = await competitor()
    for sha, on in (("a3f9", "2026-09-01"), ("0c7a", "2026-09-11")):
        page = await canonical(
            "competitor_page",
            {
                "url": "https://vidora.ai/pricing",
                "name": "Pricing",
                "body_sha": sha,
                "fetched_on": on,
            },
            sources=["competitor_pages"],
        )
        await link(page, "belongs_to", owner)
    post = await canonical(
        "competitor_post",
        {
            "name": "We shut down our studio",
            "platform": "linkedin",
            "posted_at": "2026-09-02",
            "likes": "890",
            "url": "https://linkedin.com/posts/1",
        },
        sources=["linkedin_posts"],
    )
    await link(post, "belongs_to", owner)
    body = (await api.get("/api/competitors/content")).json()
    assert (body["pages"], body["posts"]) == (2, 1)
    assert body["changes"] == [
        {
            "competitor": "Vidora",
            "url": "https://vidora.ai/pricing",
            "on": "2026-09-11",
            "before": "a3f9",
            "after": "0c7a",
        }
    ]
    assert body["recent_posts"][0]["likes"] == 890


async def test_an_empty_estate_answers_empty_views(api):
    assert (await api.get("/api/competitors/swipe")).json()["items"] == []
    assert (await api.get("/api/competitors/ads")).json()["by_competitor"] == []
    assert (await api.get("/api/competitors/rankings")).json()["keywords"] == []
    assert (await api.get("/api/competitors/answers")).json()["prompts"] == []
    assert (await api.get("/api/competitors/content")).json()["pages"] == 0
