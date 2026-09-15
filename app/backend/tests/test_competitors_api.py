import httpx
import pytest
import pytest_asyncio

from app import caches
from app.db import get_session
from app.main import app
from tests.conftest import NOW
from tests.test_competition_factories import (
    ad,
    competitor,
    definitions_file,
    mention,
    page,
    post,
    ranking,
    sync_run,
    track,
)

US = "hiredigitalworkers.com"

ADS = "/api/competitors/ads"

ROW_FIELDS = {
    "id",
    "competitor",
    "text",
    "format",
    "first_seen",
    "last_seen",
    "days_running",
    "running",
    "url",
}


def never(connector):
    return {"source": connector, "ok": None, "last_sync": None}


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


@pytest.fixture
def tracked(monkeypatch, tmp_path):
    track(monkeypatch, definitions_file(tmp_path))
    yield
    caches.reset_all()


class TestAds:
    async def test_meta_ads_answer_the_contract_shape(
        self, api, session, canonical, link
    ):
        made = await ad(canonical, link, await competitor(canonical))
        await sync_run(session, "meta_ad_library")
        answer = await api.get(f"{ADS}?platform=meta")
        assert answer.status_code == 200
        body = answer.json()
        assert set(body) == {"source", "total", "running", "rows"}
        assert body["source"] == {
            "source": "meta_ad_library",
            "ok": True,
            "last_sync": NOW.isoformat(),
        }
        assert (body["total"], body["running"]) == (1, 1)
        assert set(body["rows"][0]) == ROW_FIELDS
        assert (body["rows"][0]["id"], body["rows"][0]["competitor"]) == (
            str(made),
            "Vidora",
        )

    async def test_google_ads_name_their_own_connector(
        self, api, session, canonical, link
    ):
        owner = await competitor(canonical)
        await ad(canonical, link, owner)
        made = await ad(canonical, link, owner, platform="google")
        answer = await api.get(f"{ADS}?platform=google")
        assert answer.status_code == 200
        body = answer.json()
        assert body["source"] == never("google_ads_transparency")
        assert [row["id"] for row in body["rows"]] == [str(made)]

    @pytest.mark.parametrize("query", ["", "?platform=", "?platform=tiktok"])
    async def test_a_platform_nobody_watches_is_refused(self, api, query):
        assert (await api.get(f"{ADS}{query}")).status_code == 422


class TestRankings:
    async def test_rankings_answer_the_contract_shape(self, api, canonical, tracked):
        await ranking(canonical)
        await ranking(canonical, domain="vidora.ai", position="2")
        answer = await api.get("/api/competitors/rankings")
        assert answer.status_code == 200
        body = answer.json()
        assert set(body) == {
            "source",
            "engine",
            "checked_on",
            "us",
            "domains",
            "keywords",
        }
        assert body["source"] == never("serp")
        assert (body["engine"], body["checked_on"], body["us"]) == (
            "google",
            "2026-09-01",
            US,
        )
        assert body["domains"] == [
            {"domain": US, "name": "Digital Workers"},
            {"domain": "vidora.ai", "name": "Vidora"},
        ]
        assert body["keywords"] == [
            {"keyword": "ai ugc ads", "positions": {US: 12, "vidora.ai": 2}}
        ]


class TestAnswers:
    async def test_answers_answer_the_contract_shape(self, api, canonical, tracked):
        await mention(canonical)
        await mention(canonical, brand="Vidora", mentioned="no", rank="0")
        answer = await api.get("/api/competitors/answers")
        assert answer.status_code == 200
        body = answer.json()
        assert set(body) == {"source", "checked_on", "engines", "prompts", "brands"}
        assert body["source"] == never("ai_answers")
        assert (body["checked_on"], body["engines"]) == ("2026-09-01", ["chatgpt"])
        assert body["prompts"] == [
            {"prompt": "best ai ugc ad tool", "named": {"chatgpt": ["Digital Workers"]}}
        ]
        assert body["brands"] == [
            {"brand": "Digital Workers", "named": 1, "asked": 1, "rate": 1.0},
            {"brand": "Vidora", "named": 0, "asked": 1, "rate": 0.0},
        ]


class TestPages:
    async def test_pages_answer_the_contract_shape(self, api, canonical, link):
        await page(canonical, link, await competitor(canonical))
        answer = await api.get("/api/competitors/pages")
        assert answer.status_code == 200
        assert answer.json() == {
            "source": never("competitor_pages"),
            "total": 1,
            "rows": [
                {
                    "competitor": "Vidora",
                    "title": "Pricing",
                    "url": "https://vidora.ai/pricing",
                    "words": 420,
                    "sha": "a3f9",
                    "fetched_on": "2026-09-01",
                }
            ],
        }


class TestPosts:
    async def test_posts_answer_the_contract_shape(self, api, canonical, link):
        await post(canonical, link, await competitor(canonical))
        answer = await api.get("/api/competitors/posts")
        assert answer.status_code == 200
        assert answer.json() == {
            "source": never("linkedin_posts"),
            "total": 1,
            "rows": [
                {
                    "competitor": "Vidora",
                    "text": "We shut down our studio",
                    "posted_at": "2026-09-02",
                    "likes": 890,
                    "comments": 12,
                    "shares": 4,
                    "url": "https://linkedin.com/posts/1",
                }
            ],
        }


class TestAnEmptyEstate:
    @pytest.mark.parametrize(
        ("route", "body"),
        [
            (
                f"{ADS}?platform=meta",
                {
                    "source": never("meta_ad_library"),
                    "total": 0,
                    "running": 0,
                    "rows": [],
                },
            ),
            (
                f"{ADS}?platform=google",
                {
                    "source": never("google_ads_transparency"),
                    "total": 0,
                    "running": 0,
                    "rows": [],
                },
            ),
            (
                "/api/competitors/rankings",
                {
                    "source": never("serp"),
                    "engine": "",
                    "checked_on": None,
                    "us": US,
                    "domains": [],
                    "keywords": [],
                },
            ),
            (
                "/api/competitors/answers",
                {
                    "source": never("ai_answers"),
                    "checked_on": None,
                    "engines": [],
                    "prompts": [],
                    "brands": [],
                },
            ),
            (
                "/api/competitors/pages",
                {"source": never("competitor_pages"), "total": 0, "rows": []},
            ),
            (
                "/api/competitors/posts",
                {"source": never("linkedin_posts"), "total": 0, "rows": []},
            ),
        ],
    )
    async def test_every_view_answers_its_empty_shape(self, api, tracked, route, body):
        answer = await api.get(route)
        assert answer.status_code == 200
        assert answer.json() == body
