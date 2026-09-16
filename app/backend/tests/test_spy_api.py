import httpx
import pytest
import pytest_asyncio

from app.db import get_session
from app.engine import spy
from app.main import app
from tests.conftest import NOW

DOC = {
    "brand": {"name": "Pipedrive", "domain": "pipedrive.com", "aliases": []},
    "competitors": [
        {
            "name": "HubSpot",
            "domain": "hubspot.com",
            "aliases": ["HubSpot CRM"],
            "linkedin": "hubspot",
            "google_advertiser_id": "AR123",
        },
        {"name": "Zoho CRM", "domain": "zoho.com", "aliases": ["Zoho"]},
    ],
    "queries": ["best crm for small business", "hubspot alternatives"],
    "country": "US",
    "language": "en",
}
QUERY, OTHER_QUERY = DOC["queries"]
SEPTEMBER = "from=2026-09-01&to=2026-09-30"
D1, D2, D3 = "2026-08-20T00:00:00Z", "2026-09-01T00:00:00Z", "2026-09-02T00:00:00Z"
AD_URL = "https://adstransparency.google.com/advertiser/AR123/creative/CR1"
PREVIEW = "https://tpc.googlesyndication.com/archive/CR1.png"


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
def tracked(monkeypatch):
    definition = spy.parse(DOC)
    monkeypatch.setattr(spy, "definition", lambda: definition)
    return definition


@pytest.fixture
def check(canonical):
    async def _make(engine, query=QUERY, checked_at=D2, answer="An answer", **extra):
        facts = {"engine": engine, "query": query, "checked_at": checked_at, **extra}
        if answer is not None:
            facts["answer"] = answer
        return await canonical("visibility_check", facts)

    return _make


@pytest.fixture
def mention(canonical):
    async def _make(engine, company, rank, query=QUERY, checked_at=D2):
        return await canonical(
            "visibility_mention",
            {
                "engine": engine,
                "query": query,
                "checked_at": checked_at,
                "company": company,
                "role": "competitor",
                "rank": rank,
            },
        )

    return _make


@pytest.fixture
def ad(canonical):
    async def _make(company="HubSpot", last_seen=D2, platform="google", **extra):
        return await canonical(
            "ad",
            {
                "company": company,
                "platform": platform,
                "last_seen": last_seen,
                **extra,
            },
        )

    return _make


@pytest.fixture
def post(canonical):
    async def _make(company="HubSpot", posted_at=D2, likes=0, comments=0, **extra):
        return await canonical(
            "competitor_post",
            {
                "company": company,
                "platform": "linkedin",
                "posted_at": posted_at,
                "likes": likes,
                "comments": comments,
                **extra,
            },
        )

    return _make


def _checks_of(body, query=QUERY):
    return next(q for q in body["queries"] if q["query"] == query)["checks"]


class TestWindowRefusals:
    @pytest.mark.parametrize("route", ["visibility", "ads", "posts"])
    @pytest.mark.parametrize(
        "query,reason",
        [
            ("from=2026-09-01", "together"),
            ("to=2026-09-30", "together"),
            ("from=2026-09-30&to=2026-09-01", "after"),
        ],
        ids=["from_without_to", "to_without_from", "from_after_to"],
    )
    async def test_a_lopsided_or_inverted_window_is_refused(
        self, api, route, query, reason
    ):
        response = await api.get(f"/api/spy/{route}?{query}")
        assert response.status_code == 422, response.text
        assert reason in response.json()["detail"]

    @pytest.mark.parametrize("route", ["visibility", "ads", "posts"])
    async def test_a_date_that_is_not_a_date_is_refused(self, api, route):
        response = await api.get(f"/api/spy/{route}?from=yesterday&to=2026-09-30")
        assert response.status_code == 422


@pytest.mark.usefixtures("tracked")
class TestVisibilityRefusals:
    @pytest.mark.parametrize("engine", ["bing", "", "Google"])
    async def test_an_engine_outside_the_six_is_refused(self, api, engine):
        response = await api.get(f"/api/spy/visibility?engine={engine}")
        assert response.status_code == 422, response.text
        assert "engine" in response.json()["detail"]


@pytest.mark.usefixtures("tracked")
class TestVisibilityEmpty:
    async def test_an_empty_estate_lists_every_query_with_no_checks(self, api):
        response = await api.get("/api/spy/visibility")
        assert response.status_code == 200, response.text
        body = response.json()
        assert body == {
            "as_of": NOW.isoformat(),
            "engine": None,
            "window_from": None,
            "window_to": None,
            "companies": [
                {"name": "Pipedrive", "domain": "pipedrive.com", "role": "brand"},
                {"name": "HubSpot", "domain": "hubspot.com", "role": "competitor"},
                {"name": "Zoho CRM", "domain": "zoho.com", "role": "competitor"},
            ],
            "checks": 0,
            "queries": [
                {"query": QUERY, "checks": []},
                {"query": OTHER_QUERY, "checks": []},
            ],
            "share": {"Pipedrive": {}, "HubSpot": {}, "Zoho CRM": {}},
        }


class TestVisibilityDefinition:
    async def test_the_shipped_definition_is_the_default(self, api):
        body = (await api.get("/api/spy/visibility")).json()
        shipped = spy.definition()
        assert [c["name"] for c in body["companies"]] == [
            c.name for c in shipped.companies
        ]
        assert [q["query"] for q in body["queries"]] == list(shipped.queries)
        assert set(body["share"]) == {c.name for c in shipped.companies}


@pytest.mark.usefixtures("tracked")
class TestVisibilityChecks:
    async def test_a_check_carries_its_answer_sources_and_id(self, api, check, mention):
        cid = await check("chatgpt", answer="Try HubSpot or Pipedrive.", sources=3)
        await mention("chatgpt", "HubSpot", 1)
        await mention("chatgpt", "Pipedrive", 2)
        [row] = _checks_of((await api.get("/api/spy/visibility")).json())
        assert row == {
            "engine": "chatgpt",
            "checked_at": D2,
            "answer": "Try HubSpot or Pipedrive.",
            "sources": 3,
            "canonical_id": str(cid),
            "mentions": {"HubSpot": 1, "Pipedrive": 2},
        }
        assert isinstance(row["sources"], int | float)
        assert isinstance(row["mentions"]["HubSpot"], int | float)

    async def test_a_check_without_an_answer_reads_null(self, api, check):
        await check("google", answer=None, sources=10)
        [row] = _checks_of((await api.get("/api/spy/visibility")).json())
        assert row["answer"] is None
        assert row["sources"] == 10

    async def test_only_the_latest_check_per_engine_is_listed(self, api, check):
        await check("chatgpt", checked_at=D1)
        newest = await check("chatgpt", checked_at=D3)
        await check("chatgpt", checked_at=D2)
        body = (await api.get("/api/spy/visibility")).json()
        [row] = _checks_of(body)
        assert row["canonical_id"] == str(newest)
        assert row["checked_at"] == D3
        assert body["checks"] == 3

    async def test_a_tie_on_checked_at_goes_to_the_greater_canonical_id(
        self, api, check
    ):
        ids = [await check("chatgpt") for _ in range(3)]
        [row] = _checks_of((await api.get("/api/spy/visibility")).json())
        assert row["canonical_id"] == max(str(cid) for cid in ids)

    async def test_checks_within_a_query_follow_the_engine_order(self, api, check):
        for engine in ("gemini", "google", "claude", "ai_overview"):
            await check(engine)
        rows = _checks_of((await api.get("/api/spy/visibility")).json())
        assert [row["engine"] for row in rows] == [
            "google",
            "ai_overview",
            "claude",
            "gemini",
        ]

    async def test_queries_keep_definition_order_and_empty_ones_stay(self, api, check):
        await check("chatgpt", query=OTHER_QUERY)
        body = (await api.get("/api/spy/visibility")).json()
        assert [q["query"] for q in body["queries"]] == [QUERY, OTHER_QUERY]
        assert _checks_of(body, QUERY) == []
        assert len(_checks_of(body, OTHER_QUERY)) == 1

    async def test_an_untracked_query_counts_but_is_not_listed(self, api, check):
        await check("chatgpt", query="crm with built in calling")
        body = (await api.get("/api/spy/visibility")).json()
        assert [q["query"] for q in body["queries"]] == [QUERY, OTHER_QUERY]
        assert body["checks"] == 1

    async def test_mentions_join_on_engine_query_and_day(self, api, check, mention):
        await check("chatgpt")
        await mention("chatgpt", "HubSpot", 1)
        await mention("perplexity", "Zoho CRM", 1)
        await mention("chatgpt", "Zoho CRM", 2, query=OTHER_QUERY)
        await mention("chatgpt", "Pipedrive", 3, checked_at=D1)
        [row] = _checks_of((await api.get("/api/spy/visibility")).json())
        assert row["mentions"] == {"HubSpot": 1}

    async def test_a_company_outside_the_definition_is_ignored(
        self, api, check, mention
    ):
        await check("chatgpt")
        await mention("chatgpt", "Salesforce", 1)
        await mention("chatgpt", "HubSpot", 2)
        body = (await api.get("/api/spy/visibility")).json()
        [row] = _checks_of(body)
        assert row["mentions"] == {"HubSpot": 2}
        assert "Salesforce" not in body["share"]

    async def test_the_response_echoes_no_engine_when_none_was_asked(self, api, check):
        await check("claude")
        body = (await api.get("/api/spy/visibility")).json()
        assert body["engine"] is None


@pytest.mark.usefixtures("tracked")
class TestVisibilityShare:
    async def test_share_is_mentioning_checks_over_checks_per_engine(
        self, api, check, mention
    ):
        await check("chatgpt", checked_at=D1)
        await check("chatgpt", checked_at=D2)
        await check("chatgpt", query=OTHER_QUERY)
        await check("claude")
        await mention("chatgpt", "HubSpot", 1, checked_at=D1)
        await mention("chatgpt", "HubSpot", 1, query=OTHER_QUERY)
        await mention("chatgpt", "Pipedrive", 2, checked_at=D1)
        await mention("claude", "Zoho CRM", 1)
        body = (await api.get("/api/spy/visibility")).json()
        assert body["share"] == {
            "Pipedrive": {"chatgpt": 1 / 3, "claude": 0.0},
            "HubSpot": {"chatgpt": 2 / 3, "claude": 0.0},
            "Zoho CRM": {"chatgpt": 0.0, "claude": 1.0},
        }
        assert body["checks"] == 4

    async def test_share_counts_every_check_not_only_the_latest(
        self, api, check, mention
    ):
        await check("chatgpt", checked_at=D1)
        await check("chatgpt", checked_at=D2)
        await mention("chatgpt", "HubSpot", 1, checked_at=D1)
        body = (await api.get("/api/spy/visibility")).json()
        assert body["share"]["HubSpot"] == {"chatgpt": 0.5}
        assert _checks_of(body)[0]["mentions"] == {}

    async def test_engines_without_a_check_are_absent_from_share(self, api, check):
        await check("gemini")
        body = (await api.get("/api/spy/visibility")).json()
        assert body["share"]["Pipedrive"] == {"gemini": 0.0}

    async def test_share_engines_follow_the_engine_order(self, api, check):
        for engine in ("gemini", "google", "chatgpt"):
            await check(engine)
        body = (await api.get("/api/spy/visibility")).json()
        assert list(body["share"]["HubSpot"]) == ["google", "chatgpt", "gemini"]


@pytest.mark.usefixtures("tracked")
class TestVisibilityNarrowing:
    async def test_an_engine_narrows_checks_share_and_count(self, api, check, mention):
        await check("chatgpt")
        await check("claude")
        await mention("claude", "HubSpot", 1)
        body = (await api.get("/api/spy/visibility?engine=claude")).json()
        assert body["engine"] == "claude"
        assert body["checks"] == 1
        assert [row["engine"] for row in _checks_of(body)] == ["claude"]
        assert body["share"]["HubSpot"] == {"claude": 1.0}

    async def test_a_window_narrows_on_checked_at_and_is_stamped(
        self, api, check, mention
    ):
        await check("chatgpt", checked_at=D1)
        inside = await check("chatgpt", checked_at=D2)
        await mention("chatgpt", "HubSpot", 1, checked_at=D1)
        body = (await api.get(f"/api/spy/visibility?{SEPTEMBER}")).json()
        assert body["window_from"] == "2026-09-01"
        assert body["window_to"] == "2026-09-30"
        assert body["checks"] == 1
        assert _checks_of(body)[0]["canonical_id"] == str(inside)
        assert body["share"]["HubSpot"] == {"chatgpt": 0.0}

    async def test_a_window_with_nothing_inside_is_empty_not_an_error(self, api, check):
        await check("chatgpt", checked_at=D1)
        response = await api.get(f"/api/spy/visibility?{SEPTEMBER}&engine=chatgpt")
        assert response.status_code == 200, response.text
        assert response.json()["checks"] == 0
        assert response.json()["share"]["HubSpot"] == {}

    async def test_the_queries_cost_the_same_at_any_check_count(
        self, api, check, mention, count_queries
    ):
        await check("chatgpt")
        await mention("chatgpt", "HubSpot", 1)
        with count_queries() as few:
            await api.get(f"/api/spy/visibility?{SEPTEMBER}")
        for n in range(20):
            await check("claude", checked_at=f"2026-09-{n + 3:02d}T00:00:00Z")
            await mention("claude", "Zoho CRM", 1, checked_at=D2)
        with count_queries() as many:
            body = (await api.get(f"/api/spy/visibility?{SEPTEMBER}")).json()
        assert body["checks"] == 21
        assert many.total == few.total


@pytest.mark.usefixtures("tracked")
class TestAds:
    async def test_an_empty_estate_is_no_companies_and_no_ads(self, api):
        response = await api.get("/api/spy/ads")
        assert response.status_code == 200, response.text
        assert response.json() == {"as_of": NOW.isoformat(), "companies": [], "ads": []}

    async def test_a_row_carries_every_field_with_nulls_for_absent_facts(self, api, ad):
        cid = await ad(
            name="Grow better",
            category="image",
            first_seen=D1,
            url=AD_URL,
            preview=PREVIEW,
        )
        bare = await ad(company="Zoho CRM", last_seen=D1)
        body = (await api.get("/api/spy/ads")).json()
        assert body["ads"] == [
            {
                "canonical_id": str(cid),
                "company": "HubSpot",
                "platform": "google",
                "name": "Grow better",
                "category": "image",
                "first_seen": D1,
                "last_seen": D2,
                "url": AD_URL,
                "preview": PREVIEW,
            },
            {
                "canonical_id": str(bare),
                "company": "Zoho CRM",
                "platform": "google",
                "name": None,
                "category": None,
                "first_seen": None,
                "last_seen": D1,
                "url": None,
                "preview": None,
            },
        ]

    async def test_ads_come_newest_last_seen_first_then_by_canonical_id(self, api, ad):
        old = await ad(last_seen=D1)
        tied = [await ad(last_seen=D3) for _ in range(3)]
        mid = await ad(last_seen=D2)
        body = (await api.get("/api/spy/ads")).json()
        assert [row["canonical_id"] for row in body["ads"]] == [
            *sorted((str(cid) for cid in tied), reverse=True),
            str(mid),
            str(old),
        ]

    async def test_companies_are_counted_in_definition_order(self, api, ad):
        await ad(company="Zoho CRM")
        await ad(company="HubSpot")
        await ad(company="Zoho CRM")
        await ad(company="Salesforce")
        body = (await api.get("/api/spy/ads")).json()
        assert body["companies"] == [
            {"name": "HubSpot", "ads": 1, "new": 0},
            {"name": "Zoho CRM", "ads": 2, "new": 0},
            {"name": "Salesforce", "ads": 1, "new": 0},
        ]

    async def test_new_counts_first_seen_inside_the_window(self, api, ad):
        await ad(first_seen=D2)
        await ad(first_seen=D1)
        await ad()
        body = (await api.get(f"/api/spy/ads?{SEPTEMBER}")).json()
        assert body["companies"] == [{"name": "HubSpot", "ads": 3, "new": 1}]

    async def test_new_is_zero_without_a_window(self, api, ad):
        await ad(first_seen=D2)
        body = (await api.get("/api/spy/ads")).json()
        assert body["companies"] == [{"name": "HubSpot", "ads": 1, "new": 0}]

    async def test_a_window_narrows_on_last_seen(self, api, ad):
        await ad(last_seen=D1, first_seen=D2)
        inside = await ad(last_seen=D2)
        body = (await api.get(f"/api/spy/ads?{SEPTEMBER}")).json()
        assert [row["canonical_id"] for row in body["ads"]] == [str(inside)]
        assert body["companies"] == [{"name": "HubSpot", "ads": 1, "new": 0}]

    async def test_a_platform_narrows_rows_and_companies_exactly(self, api, ad):
        google = await ad(platform="google")
        await ad(platform="meta", company="Zoho CRM")
        await ad(platform="Google", company="Zoho CRM")
        body = (await api.get("/api/spy/ads?platform=google")).json()
        assert [row["canonical_id"] for row in body["ads"]] == [str(google)]
        assert body["companies"] == [{"name": "HubSpot", "ads": 1, "new": 0}]

    async def test_a_platform_nobody_uses_is_empty(self, api, ad):
        await ad()
        body = (await api.get("/api/spy/ads?platform=tiktok")).json()
        assert body["companies"] == []
        assert body["ads"] == []

    async def test_the_queries_cost_the_same_at_any_ad_count(
        self, api, ad, count_queries
    ):
        await ad()
        with count_queries() as few:
            await api.get(f"/api/spy/ads?{SEPTEMBER}")
        for _ in range(20):
            await ad(company="Zoho CRM")
        with count_queries() as many:
            body = (await api.get(f"/api/spy/ads?{SEPTEMBER}")).json()
        assert len(body["ads"]) == 21
        assert many.total == few.total


@pytest.mark.usefixtures("tracked")
class TestPosts:
    async def test_an_empty_estate_is_an_empty_page(self, api):
        response = await api.get("/api/spy/posts")
        assert response.status_code == 200, response.text
        assert response.json() == {
            "as_of": NOW.isoformat(),
            "companies": [],
            "total": 0,
            "limit": 20,
            "offset": 0,
            "posts": [],
        }

    async def test_a_row_carries_every_field_with_nulls_for_absent_facts(
        self, api, post, canonical
    ):
        cid = await post(
            name="We shipped a thing",
            category="article",
            likes=12,
            comments=3,
            url="https://www.linkedin.com/posts/hubspot_1",
        )
        bare = await canonical("competitor_post", {"posted_at": D1})
        body = (await api.get("/api/spy/posts")).json()
        assert body["posts"] == [
            {
                "canonical_id": str(cid),
                "company": "HubSpot",
                "platform": "linkedin",
                "name": "We shipped a thing",
                "category": "article",
                "posted_at": D2,
                "likes": 12,
                "comments": 3,
                "url": "https://www.linkedin.com/posts/hubspot_1",
            },
            {
                "canonical_id": str(bare),
                "company": None,
                "platform": None,
                "name": None,
                "category": None,
                "posted_at": D1,
                "likes": None,
                "comments": None,
                "url": None,
            },
        ]
        assert isinstance(body["posts"][0]["likes"], int | float)

    async def test_posts_come_newest_first_then_by_canonical_id(self, api, post):
        old = await post(posted_at=D1)
        tied = [await post(posted_at=D3) for _ in range(3)]
        mid = await post(posted_at=D2)
        body = (await api.get("/api/spy/posts")).json()
        assert [row["canonical_id"] for row in body["posts"]] == [
            *sorted((str(cid) for cid in tied), reverse=True),
            str(mid),
            str(old),
        ]

    async def test_companies_sum_engagement_in_definition_order(self, api, post):
        await post(company="Zoho CRM", likes=5, comments=1)
        await post(company="HubSpot", likes=10, comments=2)
        await post(company="Zoho CRM", likes=7, comments=0)
        await post(company="Salesforce", likes=1, comments=1)
        body = (await api.get("/api/spy/posts")).json()
        assert body["companies"] == [
            {"name": "HubSpot", "posts": 1, "likes": 10, "comments": 2},
            {"name": "Zoho CRM", "posts": 2, "likes": 12, "comments": 1},
            {"name": "Salesforce", "posts": 1, "likes": 1, "comments": 1},
        ]

    async def test_a_post_without_engagement_sums_as_zero(self, api, canonical):
        await canonical("competitor_post", {"company": "HubSpot", "posted_at": D2})
        body = (await api.get("/api/spy/posts")).json()
        assert body["companies"] == [
            {"name": "HubSpot", "posts": 1, "likes": 0, "comments": 0}
        ]

    async def test_a_company_filter_narrows_the_page_but_not_the_summary(
        self, api, post
    ):
        zoho = await post(company="Zoho CRM", likes=5)
        await post(company="HubSpot", likes=10)
        await post(company="zoho crm", likes=1)
        body = (await api.get("/api/spy/posts?company=Zoho%20CRM")).json()
        assert body["total"] == 1
        assert [row["canonical_id"] for row in body["posts"]] == [str(zoho)]
        assert [c["name"] for c in body["companies"]] == [
            "HubSpot",
            "Zoho CRM",
            "zoho crm",
        ]

    async def test_a_window_narrows_on_posted_at_for_page_and_summary(self, api, post):
        await post(posted_at=D1, likes=100)
        inside = await post(posted_at=D2, likes=1)
        body = (await api.get(f"/api/spy/posts?{SEPTEMBER}")).json()
        assert [row["canonical_id"] for row in body["posts"]] == [str(inside)]
        assert body["companies"] == [
            {"name": "HubSpot", "posts": 1, "likes": 1, "comments": 0}
        ]

    async def test_limit_and_offset_page_through_every_match(self, api, post):
        ids = [
            await post(posted_at=f"2026-09-{day:02d}T00:00:00Z") for day in range(1, 6)
        ]
        body = (await api.get("/api/spy/posts?limit=2&offset=1")).json()
        assert body["total"] == 5
        assert body["limit"] == 2
        assert body["offset"] == 1
        assert [row["canonical_id"] for row in body["posts"]] == [
            str(ids[3]),
            str(ids[2]),
        ]

    async def test_an_offset_past_the_end_is_an_empty_page(self, api, post):
        await post()
        body = (await api.get("/api/spy/posts?offset=5")).json()
        assert body["total"] == 1
        assert body["posts"] == []

    async def test_limit_defaults_to_twenty(self, api, post):
        for day in range(1, 26):
            await post(posted_at=f"2026-09-{day:02d}T00:00:00Z")
        body = (await api.get("/api/spy/posts")).json()
        assert body["total"] == 25
        assert len(body["posts"]) == 20

    @pytest.mark.parametrize(
        "query", ["limit=0", "limit=201", "offset=-1", "limit=ten"]
    )
    async def test_out_of_range_paging_is_refused(self, api, query):
        assert (await api.get(f"/api/spy/posts?{query}")).status_code == 422

    async def test_the_queries_cost_the_same_at_any_post_count(
        self, api, post, count_queries
    ):
        await post()
        with count_queries() as few:
            await api.get(f"/api/spy/posts?{SEPTEMBER}&company=HubSpot")
        for _ in range(20):
            await post(company="Zoho CRM")
        with count_queries() as many:
            body = (await api.get(f"/api/spy/posts?{SEPTEMBER}&company=HubSpot")).json()
        assert body["total"] == 1
        assert len(body["companies"]) == 2
        assert many.total == few.total
