from datetime import timedelta

import pytest

from app import caches
from tests.conftest import NOW
from tests.test_competition_factories import (
    CLIPWISE,
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

YESTERDAY = NOW - timedelta(days=1)

CONNECTORS = {
    "rankings": "serp",
    "answers": "ai_answers",
    "pages": "competitor_pages",
    "posts": "linkedin_posts",
}


def never(connector):
    return {"source": connector, "ok": None, "last_sync": None}


def synced(connector, ok=True, at=NOW):
    return {"source": connector, "ok": ok, "last_sync": at.isoformat()}


@pytest.fixture
def competition():
    from app import competition

    return competition


@pytest.fixture
def tracked(monkeypatch, tmp_path):
    track(monkeypatch, definitions_file(tmp_path))
    yield
    caches.reset_all()


class TestTheSourceBlock:
    async def test_a_connector_that_never_ran_has_no_status(self, session, competition):
        found = await competition.ads(session, "meta")
        assert found["source"] == never("meta_ad_library")

    async def test_google_ads_name_their_own_connector(self, session, competition):
        found = await competition.ads(session, "google")
        assert found["source"] == never("google_ads_transparency")

    async def test_the_newest_run_is_the_status(self, session, competition):
        await sync_run(session, "meta_ad_library", ok=True, started_at=NOW)
        await sync_run(session, "meta_ad_library", ok=False, started_at=YESTERDAY)
        found = await competition.ads(session, "meta")
        assert found["source"] == synced("meta_ad_library")

    async def test_a_failed_newest_run_is_the_status_too(self, session, competition):
        await sync_run(session, "meta_ad_library", ok=True, started_at=YESTERDAY)
        await sync_run(session, "meta_ad_library", ok=False, started_at=NOW)
        found = await competition.ads(session, "meta")
        assert found["source"] == synced("meta_ad_library", ok=False)

    async def test_another_connectors_run_is_not_this_ones(self, session, competition):
        await sync_run(session, "google_ads_transparency")
        found = await competition.ads(session, "meta")
        assert found["source"] == never("meta_ad_library")

    @pytest.mark.parametrize(("view", "connector"), sorted(CONNECTORS.items()))
    async def test_each_view_names_its_connector(
        self, session, competition, tracked, view, connector
    ):
        assert (await getattr(competition, view)(session))["source"] == never(connector)
        await sync_run(session, connector)
        found = await getattr(competition, view)(session)
        assert found["source"] == synced(connector)


class TestAds:
    async def test_an_ad_becomes_a_row(self, session, competition, canonical, link):
        made = await ad(canonical, link, await competitor(canonical))
        found = await competition.ads(session, "meta")
        assert found["rows"] == [
            {
                "id": str(made),
                "competitor": "Vidora",
                "text": "You approve every ad before it runs. Why?",
                "format": "video",
                "first_seen": "2026-06-12",
                "last_seen": None,
                "days_running": 84,
                "running": True,
                "url": "https://facebook.com/ads/1",
            }
        ]
        assert (found["total"], found["running"]) == (1, 1)

    async def test_only_ads_on_the_asked_platform_are_listed(
        self, session, competition, canonical, link
    ):
        owner = await competitor(canonical)
        meta = await ad(canonical, link, owner)
        google = await ad(canonical, link, owner, platform="google")
        await ad(canonical, link, owner, platform=None)
        assert [r["id"] for r in (await competition.ads(session, "meta"))["rows"]] == [
            str(meta)
        ]
        found = await competition.ads(session, "google")
        assert [r["id"] for r in found["rows"]] == [str(google)]
        assert (found["total"], found["running"]) == (1, 1)

    async def test_an_ad_with_no_owner_falls_back_to_the_reference_it_carries(
        self, session, competition, canonical, link
    ):
        await ad(canonical, link, None)
        found = await competition.ads(session, "meta")
        assert found["rows"][0]["competitor"] == "204815000001"

    async def test_an_ad_with_neither_owner_nor_reference_names_nobody(
        self, session, competition, canonical, link
    ):
        await ad(canonical, link, None, competitor_ref=None)
        found = await competition.ads(session, "meta")
        assert found["rows"][0]["competitor"] == ""

    async def test_last_seen_decides_whether_an_ad_is_still_running(
        self, session, competition, canonical, link
    ):
        owner = await competitor(canonical)
        await ad(
            canonical, link, owner, first_seen="2026-05-01", last_seen="2026-06-01"
        )
        await ad(
            canonical, link, owner, first_seen="2026-06-12", last_seen="2026-09-30"
        )
        await ad(canonical, link, owner, first_seen="2026-07-01")
        rows = {
            r["first_seen"]: (r["running"], r["last_seen"], r["days_running"])
            for r in (await competition.ads(session, "meta"))["rows"]
        }
        assert rows == {
            "2026-05-01": (False, "2026-06-01", 31),
            "2026-06-12": (False, "2026-09-30", 110),
            "2026-07-01": (True, None, 65),
        }

    async def test_a_running_ad_counts_its_days_up_to_today(
        self, session, competition, canonical, link
    ):
        owner = await competitor(canonical)
        await ad(canonical, link, owner, first_seen="2026-09-01")
        await ad(canonical, link, owner, first_seen="2026-09-04")
        found = await competition.ads(session, "meta")
        assert [r["days_running"] for r in found["rows"]] == [3, 0]

    async def test_an_ad_never_dated_has_no_days(
        self, session, competition, canonical, link
    ):
        owner = await competitor(canonical)
        await ad(canonical, link, owner, first_seen=None)
        await ad(canonical, link, owner, first_seen=None, last_seen="2026-06-01")
        rows = {
            r["last_seen"]: (r["first_seen"], r["days_running"], r["running"])
            for r in (await competition.ads(session, "meta"))["rows"]
        }
        assert rows == {
            None: (None, None, True),
            "2026-06-01": (None, None, False),
        }

    async def test_a_timestamp_is_shown_as_its_day(
        self, session, competition, canonical, link
    ):
        await ad(
            canonical,
            link,
            await competitor(canonical),
            first_seen="2026-06-15T09:30:00Z",
            last_seen="2026-09-01T14:00:00Z",
        )
        row = (await competition.ads(session, "meta"))["rows"][0]
        assert (row["first_seen"], row["last_seen"], row["days_running"]) == (
            "2026-06-15",
            "2026-09-01",
            78,
        )

    async def test_a_day_nothing_can_read_is_no_day(
        self, session, competition, canonical, link
    ):
        await ad(canonical, link, await competitor(canonical), first_seen="soon")
        row = (await competition.ads(session, "meta"))["rows"][0]
        assert (row["first_seen"], row["days_running"], row["running"]) == (
            None,
            None,
            True,
        )

    async def test_the_format_is_the_category_or_nothing(
        self, session, competition, canonical, link
    ):
        await ad(canonical, link, await competitor(canonical), category=None)
        assert (await competition.ads(session, "meta"))["rows"][0]["format"] is None

    async def test_text_and_url_are_empty_when_the_library_gave_none(
        self, session, competition, canonical, link
    ):
        await ad(canonical, link, await competitor(canonical), name=None, url=None)
        row = (await competition.ads(session, "meta"))["rows"][0]
        assert (row["text"], row["url"]) == ("", "")

    async def test_rows_sort_by_days_running_with_undated_ads_last(
        self, session, competition, canonical, link
    ):
        owner = await competitor(canonical)
        await ad(canonical, link, owner, first_seen=None)
        await ad(canonical, link, owner, first_seen="2026-08-01")
        await ad(canonical, link, owner, first_seen="2026-05-01")
        found = await competition.ads(session, "meta")
        assert [r["days_running"] for r in found["rows"]] == [126, 34, None]

    async def test_equal_days_put_the_newer_ad_first(
        self, session, competition, canonical, link
    ):
        owner = await competitor(canonical)
        await ad(
            canonical, link, owner, first_seen="2026-05-01", last_seen="2026-06-01"
        )
        await ad(
            canonical, link, owner, first_seen="2026-07-01", last_seen="2026-08-01"
        )
        found = await competition.ads(session, "meta")
        assert [(r["days_running"], r["first_seen"]) for r in found["rows"]] == [
            (31, "2026-07-01"),
            (31, "2026-05-01"),
        ]

    async def test_equal_days_and_dates_fall_back_to_the_id(
        self, session, competition, canonical, link
    ):
        owner = await competitor(canonical)
        made = [str(await ad(canonical, link, owner)) for _ in range(3)]
        found = await competition.ads(session, "meta")
        assert [r["id"] for r in found["rows"]] == sorted(made)

    async def test_undated_ads_fall_back_to_the_id(
        self, session, competition, canonical, link
    ):
        owner = await competitor(canonical)
        made = [
            str(await ad(canonical, link, owner, first_seen=None)) for _ in range(3)
        ]
        found = await competition.ads(session, "meta")
        assert [r["id"] for r in found["rows"]] == sorted(made)

    async def test_running_counts_the_ads_still_showing(
        self, session, competition, canonical, link
    ):
        owner = await competitor(canonical)
        await ad(canonical, link, owner)
        await ad(canonical, link, owner, first_seen=None)
        await ad(canonical, link, owner, last_seen="2026-07-01")
        found = await competition.ads(session, "meta")
        assert (found["total"], found["running"]) == (3, 2)

    async def test_ads_of_nothing_are_an_empty_list(self, session, competition):
        assert await competition.ads(session, "meta") == {
            "source": never("meta_ad_library"),
            "total": 0,
            "running": 0,
            "rows": [],
        }


class TestRankings:
    async def test_rankings_pivot_keyword_against_domain(
        self, session, competition, canonical, tracked
    ):
        await ranking(canonical)
        await ranking(canonical, domain="vidora.ai", position="2")
        assert await competition.rankings(session) == {
            "source": never("serp"),
            "engine": "google",
            "checked_on": "2026-09-01",
            "us": US,
            "domains": [
                {"domain": US, "name": "Digital Workers"},
                {"domain": "vidora.ai", "name": "Vidora"},
            ],
            "keywords": [
                {"keyword": "ai ugc ads", "positions": {US: 12, "vidora.ai": 2}}
            ],
        }

    async def test_domains_come_us_first_then_tracked_in_file_order_then_the_rest(
        self, session, competition, canonical, tracked
    ):
        for domain in ("zeta.example", "clipwise.io", "alpha.example", "vidora.ai", US):
            await ranking(canonical, domain=domain)
        found = await competition.rankings(session)
        assert found["domains"] == [
            {"domain": US, "name": "Digital Workers"},
            {"domain": "vidora.ai", "name": "Vidora"},
            {"domain": "clipwise.io", "name": "Clipwise"},
            {"domain": "alpha.example", "name": "alpha.example"},
            {"domain": "zeta.example", "name": "zeta.example"},
        ]

    async def test_a_domain_that_never_ranked_is_not_a_column(
        self, session, competition, canonical, tracked
    ):
        await ranking(canonical, domain="vidora.ai")
        found = await competition.rankings(session)
        assert found["domains"] == [{"domain": "vidora.ai", "name": "Vidora"}]

    async def test_a_domain_never_ranked_for_a_keyword_has_no_position(
        self, session, competition, canonical, tracked
    ):
        await ranking(canonical)
        await ranking(
            canonical, keyword="ugc video tool", domain="vidora.ai", position="1"
        )
        positions = {
            row["keyword"]: row["positions"]
            for row in (await competition.rankings(session))["keywords"]
        }
        assert positions == {
            "ai ugc ads": {US: 12, "vidora.ai": None},
            "ugc video tool": {US: None, "vidora.ai": 1},
        }

    @pytest.mark.parametrize("newest_first", [False, True])
    async def test_the_newest_reading_is_the_position_shown(
        self, session, competition, canonical, tracked, newest_first
    ):
        readings = [("12", "2026-08-01"), ("6", "2026-09-01")]
        for position, checked_on in reversed(readings) if newest_first else readings:
            await ranking(canonical, position=position, checked_on=checked_on)
        found = await competition.rankings(session)
        assert found["keywords"][0]["positions"][US] == 6
        assert found["checked_on"] == "2026-09-01"

    async def test_a_reading_with_no_day_never_beats_a_dated_one(
        self, session, competition, canonical, tracked
    ):
        await ranking(canonical, position="6", checked_on="2026-09-01")
        await ranking(canonical, position="3", checked_on=None)
        found = await competition.rankings(session)
        assert found["keywords"][0]["positions"][US] == 6

    async def test_a_reading_with_no_day_still_counts_alone(
        self, session, competition, canonical, tracked
    ):
        await ranking(canonical, position="3", checked_on=None)
        found = await competition.rankings(session)
        assert found["keywords"][0]["positions"][US] == 3
        assert found["checked_on"] is None

    async def test_a_timestamp_is_shown_as_its_day(
        self, session, competition, canonical, tracked
    ):
        await ranking(canonical, checked_on="2026-09-14T05:42:11Z")
        assert (await competition.rankings(session))["checked_on"] == "2026-09-14"

    async def test_keywords_are_sorted(self, session, competition, canonical, tracked):
        for keyword in ("ugc video tool", "ai ugc ads", "ai ads without a studio"):
            await ranking(canonical, keyword=keyword)
        found = await competition.rankings(session)
        assert [row["keyword"] for row in found["keywords"]] == [
            "ai ads without a studio",
            "ai ugc ads",
            "ugc video tool",
        ]

    async def test_the_engine_is_the_one_most_readings_came_from(
        self, session, competition, canonical, tracked
    ):
        await ranking(canonical, engine="bing")
        await ranking(canonical, keyword="ugc video tool", engine="google")
        await ranking(canonical, keyword="ai video ads", engine="google")
        assert (await competition.rankings(session))["engine"] == "google"

    async def test_readings_with_no_engine_name_none(
        self, session, competition, canonical, tracked
    ):
        await ranking(canonical, engine=None)
        assert (await competition.rankings(session))["engine"] == ""

    async def test_rankings_of_nothing_name_no_engine_and_no_day(
        self, session, competition, tracked
    ):
        assert await competition.rankings(session) == {
            "source": never("serp"),
            "engine": "",
            "checked_on": None,
            "us": US,
            "domains": [],
            "keywords": [],
        }


class TestAnswers:
    async def test_answers_pivot_prompt_against_engine_and_brand(
        self, session, competition, canonical, tracked
    ):
        await mention(canonical)
        await mention(canonical, brand="Vidora", rank="2")
        await mention(canonical, brand="Clipwise", mentioned="false", rank="0")
        await mention(canonical, engine="perplexity", brand="Vidora")
        assert await competition.answers(session) == {
            "source": never("ai_answers"),
            "checked_on": "2026-09-01",
            "engines": ["chatgpt", "perplexity"],
            "prompts": [
                {
                    "prompt": "best ai ugc ad tool",
                    "named": {
                        "chatgpt": ["Digital Workers", "Vidora"],
                        "perplexity": ["Vidora"],
                    },
                }
            ],
            "brands": [
                {"brand": "Digital Workers", "named": 1, "asked": 1, "rate": 1.0},
                {"brand": "Vidora", "named": 2, "asked": 2, "rate": 1.0},
                {"brand": "Clipwise", "named": 0, "asked": 1, "rate": 0.0},
            ],
        }

    async def test_an_engine_that_named_nobody_is_an_empty_list(
        self, session, competition, canonical, tracked
    ):
        await mention(canonical, engine="perplexity", mentioned="false")
        found = await competition.answers(session)
        assert found["prompts"][0]["named"] == {"perplexity": []}

    async def test_an_engine_never_asked_a_prompt_is_absent_from_it(
        self, session, competition, canonical, tracked
    ):
        await mention(canonical)
        await mention(canonical, engine="perplexity")
        await mention(canonical, prompt="ugc ads without creators")
        found = await competition.answers(session)
        assert [set(row["named"]) for row in found["prompts"]] == [
            {"chatgpt", "perplexity"},
            {"chatgpt"},
        ]

    async def test_named_brands_are_listed_by_rank_as_a_number(
        self, session, competition, canonical, tracked
    ):
        await mention(canonical, brand="Avatarly", rank="10")
        await mention(canonical, brand="Vidora", rank="2")
        await mention(canonical, brand="Clipwise", rank="1")
        found = await competition.answers(session)
        assert found["prompts"][0]["named"]["chatgpt"] == [
            "Clipwise",
            "Vidora",
            "Avatarly",
        ]

    async def test_engines_come_in_file_order_then_the_rest_alphabetically(
        self, session, competition, canonical, tracked
    ):
        for engine in ("gemini", "bing", "chatgpt", "aio"):
            await mention(canonical, engine=engine)
        found = await competition.answers(session)
        assert found["engines"] == ["chatgpt", "gemini", "aio", "bing"]

    @pytest.mark.parametrize("newest_first", [False, True])
    async def test_the_newest_reading_decides_whether_a_brand_was_named(
        self, session, competition, canonical, tracked, newest_first
    ):
        readings = [("true", "2026-08-01"), ("false", "2026-09-01")]
        for mentioned, checked_on in reversed(readings) if newest_first else readings:
            await mention(canonical, mentioned=mentioned, checked_on=checked_on)
        found = await competition.answers(session)
        assert found["prompts"][0]["named"] == {"chatgpt": []}
        assert found["brands"] == [
            {"brand": "Digital Workers", "named": 0, "asked": 1, "rate": 0.0}
        ]

    @pytest.mark.parametrize(
        ("value", "named"),
        [
            ("true", True),
            ("TRUE", True),
            ("yes", True),
            ("Yes", True),
            ("1", True),
            ("false", False),
            ("no", False),
            ("0", False),
            ("", False),
            (None, False),
        ],
    )
    async def test_mentioned_is_read_leniently(
        self, session, competition, canonical, tracked, value, named
    ):
        await mention(canonical, mentioned=value)
        found = await competition.answers(session)
        assert found["prompts"][0]["named"]["chatgpt"] == (
            ["Digital Workers"] if named else []
        )
        assert found["brands"][0]["named"] == int(named)

    async def test_the_rate_is_named_over_asked(
        self, session, competition, canonical, tracked
    ):
        await mention(canonical)
        await mention(canonical, engine="perplexity", mentioned="false")
        await mention(canonical, prompt="ugc ads without creators")
        found = await competition.answers(session)
        assert found["brands"] == [
            {"brand": "Digital Workers", "named": 2, "asked": 3, "rate": 2 / 3}
        ]

    async def test_brands_sort_by_rate_then_by_name(
        self, session, competition, canonical, tracked
    ):
        await mention(canonical, brand="Vidora")
        await mention(canonical, engine="perplexity", brand="Vidora", mentioned="no")
        await mention(canonical, brand="Clipwise")
        await mention(canonical, brand="Avatarly")
        found = await competition.answers(session)
        assert [(b["brand"], b["rate"]) for b in found["brands"]] == [
            ("Avatarly", 1.0),
            ("Clipwise", 1.0),
            ("Vidora", 0.5),
        ]

    async def test_prompts_are_sorted(self, session, competition, canonical, tracked):
        await mention(canonical, prompt="ugc ads without creators")
        await mention(canonical, prompt="best ai ugc ad tool")
        found = await competition.answers(session)
        assert [row["prompt"] for row in found["prompts"]] == [
            "best ai ugc ad tool",
            "ugc ads without creators",
        ]

    async def test_checked_on_is_the_latest_day_any_answer_was_read(
        self, session, competition, canonical, tracked
    ):
        await mention(canonical, checked_on="2026-09-01")
        await mention(canonical, engine="perplexity", checked_on="2026-08-01")
        assert (await competition.answers(session))["checked_on"] == "2026-09-01"

    async def test_readings_with_no_day_leave_checked_on_empty(
        self, session, competition, canonical, tracked
    ):
        await mention(canonical, checked_on=None)
        assert (await competition.answers(session))["checked_on"] is None

    async def test_answers_of_nothing_name_no_engines(
        self, session, competition, tracked
    ):
        assert await competition.answers(session) == {
            "source": never("ai_answers"),
            "checked_on": None,
            "engines": [],
            "prompts": [],
            "brands": [],
        }


class TestPages:
    async def test_a_page_becomes_a_row(self, session, competition, canonical, link):
        await page(canonical, link, await competitor(canonical))
        assert await competition.pages(session) == {
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

    async def test_a_page_with_no_owner_is_named_from_the_file_by_its_domain(
        self, session, competition, canonical, link, tracked
    ):
        await page(canonical, link, None)
        found = await competition.pages(session)
        assert found["rows"][0]["competitor"] == "Vidora"

    async def test_a_page_with_no_owner_and_a_domain_nobody_tracks_shows_the_domain(
        self, session, competition, canonical, link, tracked
    ):
        await page(canonical, link, None, competitor_ref="nobody.example")
        found = await competition.pages(session)
        assert found["rows"][0]["competitor"] == "nobody.example"

    async def test_a_page_missing_its_measurements_has_nulls(
        self, session, competition, canonical, link
    ):
        await page(
            canonical,
            link,
            await competitor(canonical),
            word_count=None,
            body_sha=None,
            fetched_on=None,
        )
        row = (await competition.pages(session))["rows"][0]
        assert (row["words"], row["sha"], row["fetched_on"]) == (None, None, None)

    async def test_a_page_with_no_title_has_an_empty_one(
        self, session, competition, canonical, link
    ):
        await page(canonical, link, await competitor(canonical), name=None)
        assert (await competition.pages(session))["rows"][0]["title"] == ""

    async def test_a_timestamp_is_shown_as_its_day(
        self, session, competition, canonical, link
    ):
        await page(
            canonical,
            link,
            await competitor(canonical),
            fetched_on="2026-09-14T05:50:00Z",
        )
        found = await competition.pages(session)
        assert found["rows"][0]["fetched_on"] == "2026-09-14"

    async def test_rows_sort_by_newest_fetch_then_competitor_then_url(
        self, session, competition, canonical, link
    ):
        vidora = await competitor(canonical)
        clipwise = await competitor(canonical, CLIPWISE)
        await page(canonical, link, vidora, fetched_on="2026-09-01")
        await page(
            canonical, link, vidora, url="https://vidora.ai/", fetched_on="2026-09-11"
        )
        await page(canonical, link, vidora, fetched_on="2026-09-11")
        await page(
            canonical,
            link,
            clipwise,
            url="https://clipwise.io/pricing",
            fetched_on="2026-09-11",
        )
        found = await competition.pages(session)
        assert [
            (r["fetched_on"], r["competitor"], r["url"]) for r in found["rows"]
        ] == [
            ("2026-09-11", "Clipwise", "https://clipwise.io/pricing"),
            ("2026-09-11", "Vidora", "https://vidora.ai/"),
            ("2026-09-11", "Vidora", "https://vidora.ai/pricing"),
            ("2026-09-01", "Vidora", "https://vidora.ai/pricing"),
        ]
        assert found["total"] == 4

    async def test_a_page_never_dated_sorts_last(
        self, session, competition, canonical, link
    ):
        owner = await competitor(canonical)
        await page(canonical, link, owner, url="https://vidora.ai/", fetched_on=None)
        await page(canonical, link, owner, fetched_on="2026-09-01")
        found = await competition.pages(session)
        assert [r["fetched_on"] for r in found["rows"]] == ["2026-09-01", None]

    async def test_pages_of_nothing_are_an_empty_list(self, session, competition):
        assert await competition.pages(session) == {
            "source": never("competitor_pages"),
            "total": 0,
            "rows": [],
        }


class TestPosts:
    async def test_a_post_becomes_a_row(self, session, competition, canonical, link):
        await post(canonical, link, await competitor(canonical))
        assert await competition.posts(session) == {
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

    async def test_a_post_with_no_owner_whose_domain_is_ours_shows_our_name(
        self, session, competition, canonical, link, tracked
    ):
        await post(canonical, link, None, competitor_ref=US)
        found = await competition.posts(session)
        assert found["rows"][0]["competitor"] == "Digital Workers"

    async def test_a_post_with_no_owner_and_a_domain_nobody_tracks_shows_the_domain(
        self, session, competition, canonical, link, tracked
    ):
        await post(canonical, link, None, competitor_ref="nobody.example")
        found = await competition.posts(session)
        assert found["rows"][0]["competitor"] == "nobody.example"

    async def test_a_post_with_no_engagement_has_nulls(
        self, session, competition, canonical, link
    ):
        await post(
            canonical,
            link,
            await competitor(canonical),
            likes=None,
            comments=None,
            shares=None,
        )
        row = (await competition.posts(session))["rows"][0]
        assert (row["likes"], row["comments"], row["shares"]) == (None, None, None)

    async def test_a_post_never_dated_has_no_day(
        self, session, competition, canonical, link
    ):
        await post(canonical, link, await competitor(canonical), posted_at=None)
        assert (await competition.posts(session))["rows"][0]["posted_at"] is None

    async def test_a_timestamp_is_shown_as_its_day(
        self, session, competition, canonical, link
    ):
        await post(
            canonical,
            link,
            await competitor(canonical),
            posted_at="2026-09-11T13:25:00Z",
        )
        assert (await competition.posts(session))["rows"][0]["posted_at"] == (
            "2026-09-11"
        )

    async def test_a_post_with_no_text_has_an_empty_one(
        self, session, competition, canonical, link
    ):
        await post(canonical, link, await competitor(canonical), name=None)
        assert (await competition.posts(session))["rows"][0]["text"] == ""

    async def test_rows_sort_by_likes_with_unliked_last_then_newest(
        self, session, competition, canonical, link
    ):
        owner = await competitor(canonical)
        await post(canonical, link, owner, likes="12", posted_at="2026-09-03")
        await post(canonical, link, owner, likes="890", posted_at="2026-09-01")
        await post(canonical, link, owner, likes=None, posted_at="2026-09-02")
        await post(canonical, link, owner, likes="890", posted_at="2026-09-04")
        found = await competition.posts(session)
        assert [(r["likes"], r["posted_at"]) for r in found["rows"]] == [
            (890, "2026-09-04"),
            (890, "2026-09-01"),
            (12, "2026-09-03"),
            (None, "2026-09-02"),
        ]
        assert found["total"] == 4

    async def test_posts_of_nothing_are_an_empty_list(self, session, competition):
        assert await competition.posts(session) == {
            "source": never("linkedin_posts"),
            "total": 0,
            "rows": [],
        }
