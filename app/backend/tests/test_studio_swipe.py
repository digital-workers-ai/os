import pytest
from sqlalchemy import select

from app.models import SkillRun
from app.studio import errors, proposals, swipe
from tests.test_studio_factories import (
    enriched,
    raw_event,
    studio_on,
    sync_run,
)

VIDORA = {"name": "Vidora", "domain": "vidora.ai"}


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
        given = {k: v for k, v in {**base, **facts}.items() if v is not None}
        made = await canonical("competitor_ad", given, sources=["meta_ad_library"])
        if owner is not None:
            await link(made, "belongs_to", owner)
        return made

    return _make


async def test_an_ad_becomes_a_swipe_row(session, competitor, ad):
    owner = await competitor()
    made = await ad(owner)
    page = await swipe.file(session)
    assert page["items"] == [
        {
            "id": str(made),
            "competitor": "Vidora",
            "platform": "meta",
            "format": "video",
            "days_running": 84,
            "first_seen": "2026-06-12",
            "last_seen": None,
            "running": True,
            "headline": "",
            "body": "You approve every ad before it runs. Why?",
            "angle": None,
            "hook": None,
            "offer": None,
            "proof": None,
            "url": "https://facebook.com/ads/1",
        }
    ]
    assert page["total"] == 1


async def test_an_ad_nobody_has_read_is_unlabelled_rather_than_missing(
    session, competitor, ad
):
    await ad(await competitor())
    page = await swipe.file(session)
    assert (page["items"][0]["angle"], page["items"][0]["hook"]) == (None, None)


async def test_the_creative_reading_fills_the_labels(session, competitor, ad):
    made = await ad(await competitor())
    await enriched(session, made, attr="angle", value="approval")
    await enriched(session, made, attr="hook", value="contrast", quote="Hiring vs us")
    await enriched(session, made, attr="offer", value="flat-fee", quote="$499/month")
    await enriched(session, made, attr="proof", value="testimonial", quote="I stopped")
    row = (await swipe.file(session))["items"][0]
    assert (row["angle"], row["hook"], row["offer"], row["proof"]) == (
        "approval",
        "contrast",
        "flat-fee",
        "testimonial",
    )


async def test_a_reading_of_something_else_is_not_a_label(session, competitor, ad):
    made = await ad(await competitor())
    await enriched(session, made, attr="angle", value="approval", reading="sales_call")
    assert (await swipe.file(session))["items"][0]["angle"] is None


async def test_an_ad_with_no_competitor_falls_back_to_the_id_it_carries(session, ad):
    await ad(None)
    assert (await swipe.file(session))["items"][0]["competitor"] == "204815000001"


async def test_last_seen_decides_whether_an_ad_is_still_running(
    session, competitor, ad
):
    owner = await competitor()
    await ad(owner, first_seen="2026-05-01", last_seen="2026-06-01")
    await ad(owner, first_seen="2026-06-12", last_seen="2026-09-30")
    await ad(owner, first_seen="2026-07-01")
    rows = {
        r["first_seen"]: (r["running"], r["last_seen"])
        for r in (await swipe.file(session))["items"]
    }
    assert rows == {
        "2026-05-01": (False, "2026-06-01"),
        "2026-06-12": (True, "2026-09-30"),
        "2026-07-01": (True, None),
    }


async def test_an_ad_with_no_dates_at_all_still_reports_a_row(session, competitor, ad):
    await ad(await competitor(), first_seen=None, url=None, category=None)
    row = (await swipe.file(session))["items"][0]
    assert (row["first_seen"], row["days_running"], row["url"], row["format"]) == (
        "",
        0,
        "",
        "",
    )


async def test_a_date_the_source_garbled_is_no_date(session, competitor, ad):
    await ad(await competitor(), first_seen="soon", last_seen="never")
    row = (await swipe.file(session))["items"][0]
    assert (row["days_running"], row["first_seen"], row["running"]) == (0, "", True)


async def test_the_format_falls_back_to_what_the_reading_called_it(
    session, competitor, ad
):
    made = await ad(await competitor(), category=None)
    await enriched(session, made, attr="format", value="ugc-avatar", quote="")
    assert (await swipe.file(session))["items"][0]["format"] == "ugc-avatar"


@pytest.mark.parametrize(
    ("filters", "kept"),
    [
        ({"competitor": "Vidora"}, 1),
        ({"competitor": "Clipwise"}, 0),
        ({"platform": "meta"}, 1),
        ({"platform": "google"}, 0),
        ({"angle": "approval"}, 1),
        ({"angle": "number"}, 0),
        ({"hook": "contrast"}, 1),
        ({"hook": "story"}, 0),
        ({"fmt": "video"}, 1),
        ({"fmt": "image"}, 0),
    ],
)
async def test_the_file_filters_on_every_facet(session, competitor, ad, filters, kept):
    made = await ad(await competitor())
    await enriched(session, made, attr="angle", value="approval")
    await enriched(session, made, attr="hook", value="contrast")
    page = await swipe.file(session, **filters)
    assert len(page["items"]) == kept
    assert page["total"] == kept


async def test_the_facets_list_every_value_whatever_is_filtered(
    session, competitor, ad
):
    owner = await competitor()
    first = await ad(owner)
    await ad(owner, platform="google", category="image")
    await enriched(session, first, attr="angle", value="approval")
    page = await swipe.file(session, platform="google")
    assert page["facets"] == {
        "competitor": ["Vidora"],
        "platform": ["google", "meta"],
        "angle": ["approval"],
        "hook": [],
        "format": ["image", "video"],
    }


async def test_the_file_sorts_by_days_running_then_by_newest(session, competitor, ad):
    owner = await competitor()
    await ad(owner, first_seen="2026-08-01")
    await ad(owner, first_seen="2026-05-01")
    assert [r["days_running"] for r in (await swipe.file(session))["items"]] == [
        126,
        34,
    ]
    newest = await swipe.file(session, sort="first_seen")
    assert [r["first_seen"] for r in newest["items"]] == ["2026-08-01", "2026-05-01"]


async def test_a_sort_nobody_declared_falls_back_to_days_running(
    session, competitor, ad
):
    owner = await competitor()
    await ad(owner, first_seen="2026-08-01")
    await ad(owner, first_seen="2026-05-01")
    page = await swipe.file(session, sort="; drop table")
    assert [r["days_running"] for r in page["items"]] == [126, 34]


async def test_the_file_pages_and_still_counts_the_whole(session, competitor, ad):
    owner = await competitor()
    await ad(owner, first_seen="2026-08-01")
    await ad(owner, first_seen="2026-05-01")
    page = await swipe.file(session, limit=1, offset=1)
    assert [r["days_running"] for r in page["items"]] == [34]
    assert page["total"] == 2


async def test_an_empty_swipe_file_is_empty_rather_than_absent(session):
    assert await swipe.file(session) == {
        "items": [],
        "total": 0,
        "facets": {
            "competitor": [],
            "platform": [],
            "angle": [],
            "hook": [],
            "format": [],
        },
    }


async def test_an_item_carries_its_labels_with_the_quotes_behind_them(
    session, competitor, ad
):
    made = await ad(await competitor())
    await enriched(
        session, made, attr="angle", value="approval", quote="You approve every ad"
    )
    await enriched(session, made, attr="counter", value="proof = receipts", quote="")
    found = await swipe.item(session, str(made))
    assert found["labels"] == [
        {"field": "angle", "label": "approval", "quote": "You approve every ad"},
        {"field": "counter", "label": "proof = receipts", "quote": None},
    ]
    assert found["counter"] == "proof = receipts"
    assert found["competitor"] == "Vidora"


async def test_an_item_counts_the_raw_rows_behind_it(session, competitor, ad):
    made = await ad(await competitor())
    await raw_event(session, "meta_ad_library", "competitor_ads", "competitor_ad_2")
    await raw_event(session, "meta_ad_library", "competitor_ads", "competitor_ad_2")
    await raw_event(session, "meta_ad_library", "competitor_ads", "someone_else")
    found = await swipe.item(session, str(made))
    assert found["raw_events"] == 2
    assert found["landing_url"] is None


async def test_an_item_nobody_has_is_refused(session, competitor, ad):
    await ad(await competitor())
    with pytest.raises(errors.Missing):
        await swipe.item(session, "0b3c2f4e-0000-0000-0000-000000000000")


async def test_an_item_id_that_is_not_an_id_is_refused(session):
    with pytest.raises(errors.Missing):
        await swipe.item(session, "../../etc/passwd")


async def test_the_ads_view_counts_active_new_and_long_running(session, competitor, ad):
    owner = await competitor()
    await ad(owner, first_seen="2026-05-01")
    await ad(owner, first_seen="2026-09-01")
    await ad(owner, first_seen="2026-01-02", last_seen="2026-02-02")
    found = await swipe.ads(session)
    assert (found["active"], found["new_7d"], found["long_running"]) == (2, 1, 1)


async def test_the_ads_view_splits_by_competitor_and_platform(
    session, canonical, ad, link
):
    vidora = await canonical("competitor", VIDORA)
    clipwise = await canonical(
        "competitor", {"name": "Clipwise", "domain": "clipwise.io"}
    )
    await ad(vidora, first_seen="2026-05-01")
    await ad(vidora, platform="google")
    await ad(clipwise, first_seen="2026-01-02", last_seen="2026-02-02")
    found = await swipe.ads(session)
    assert found["by_competitor"] == [
        {
            "competitor": "Clipwise",
            "active": 0,
            "long_running": 0,
            "platforms": {"meta": 1},
        },
        {
            "competitor": "Vidora",
            "active": 2,
            "long_running": 1,
            "platforms": {"google": 1, "meta": 1},
        },
    ]


async def test_the_ads_view_mixes_the_angles_it_has_been_told(session, competitor, ad):
    owner = await competitor()
    first = await ad(owner)
    second = await ad(owner)
    await enriched(session, first, attr="angle", value="approval")
    await enriched(session, second, attr="angle", value="approval")
    await enriched(session, second, attr="hook", value="contrast")
    assert (await swipe.ads(session))["angle_mix"] == {"approval": 2}


async def test_the_ads_view_counts_what_was_new_each_week(session, competitor, ad):
    owner = await competitor()
    await ad(owner, first_seen="2026-08-31")
    await ad(owner, first_seen="2026-09-01")
    await ad(owner, first_seen="2025-01-01")
    weeks = (await swipe.ads(session))["new_per_week"]
    assert len(weeks) == 12
    assert weeks[-1] == {"week": "2026-08-31", "count": 2}
    assert sum(w["count"] for w in weeks) == 2


async def test_the_ads_view_narrows_to_one_competitor_and_platform(
    session, canonical, ad
):
    vidora = await canonical("competitor", VIDORA)
    clipwise = await canonical(
        "competitor", {"name": "Clipwise", "domain": "clipwise.io"}
    )
    await ad(vidora)
    await ad(clipwise, platform="google")
    found = await swipe.ads(session, competitor="Vidora")
    assert [r["competitor"] for r in found["by_competitor"]] == ["Vidora"]
    assert (await swipe.ads(session, platform="google"))["active"] == 1


async def test_an_empty_ads_view_counts_nothing(session):
    found = await swipe.ads(session)
    assert found["active"] == 0
    assert found["by_competitor"] == []
    assert found["angle_mix"] == {}
    assert len(found["new_per_week"]) == 12


@pytest.fixture
def ranking(canonical):
    async def _make(**facts):
        base = {
            "keyword": "ai ugc ads",
            "engine": "google",
            "domain": "hiredigitalworkers.com",
            "position": "12",
            "url": "https://hiredigitalworkers.com/ai-ugc-ads",
            "checked_on": "2026-09-01",
        }
        return await canonical("ranking", {**base, **facts}, sources=["serp"])

    return _make


async def test_rankings_pivot_keyword_against_domain(session, ranking):
    await ranking()
    await ranking(domain="vidora.ai", position="2")
    found = await swipe.rankings(session)
    assert found["domains"] == ["hiredigitalworkers.com", "vidora.ai"]
    assert found["keywords"][0]["keyword"] == "ai ugc ads"
    assert found["keywords"][0]["positions"] == {
        "hiredigitalworkers.com": 12,
        "vidora.ai": 2,
    }
    assert (found["engine"], found["location"], found["us"]) == (
        "google",
        "",
        "hiredigitalworkers.com",
    )


async def test_a_domain_never_ranked_for_a_keyword_has_no_position(session, ranking):
    await ranking()
    await ranking(keyword="ugc video tool", domain="vidora.ai", position="1")
    found = await swipe.rankings(session)
    positions = {row["keyword"]: row["positions"] for row in found["keywords"]}
    assert positions["ugc video tool"] == {
        "hiredigitalworkers.com": None,
        "vidora.ai": 1,
    }


async def test_the_newest_reading_is_the_position_shown(session, ranking):
    await ranking(position="12", checked_on="2026-08-01")
    await ranking(position="6", checked_on="2026-09-01")
    found = await swipe.rankings(session)
    assert found["keywords"][0]["positions"]["hiredigitalworkers.com"] == 6


async def test_a_keyword_carries_twelve_weeks_of_our_own_position(session, ranking):
    await ranking(position="12", checked_on="2026-09-01")
    await ranking(position="9", checked_on="2026-08-25")
    history = (await swipe.rankings(session))["keywords"][0]["history"]
    assert len(history) == 12
    assert history[-1] == {"date": "2026-08-31", "position": 12}
    assert history[-2] == {"date": "2026-08-24", "position": 9}
    assert history[0]["position"] is None


async def test_rankings_narrow_to_one_keyword(session, ranking):
    await ranking()
    await ranking(keyword="ugc video tool")
    found = await swipe.rankings(session, keyword="ugc video tool")
    assert [row["keyword"] for row in found["keywords"]] == ["ugc video tool"]


async def test_rankings_of_nothing_name_no_engine(session):
    assert await swipe.rankings(session) == {
        "engine": "",
        "location": "",
        "us": "hiredigitalworkers.com",
        "keywords": [],
        "domains": [],
    }


@pytest.fixture
def mention(canonical):
    async def _make(**facts):
        base = {
            "prompt": "best ai ugc ad tool",
            "engine": "chatgpt",
            "brand": "Digital Workers",
            "mentioned": "true",
            "rank": "1",
            "checked_on": "2026-09-01",
        }
        given = {k: v for k, v in {**base, **facts}.items() if v is not None}
        return await canonical("ai_mention", given, sources=["ai_answers"])

    return _make


async def test_answers_pivot_prompt_against_engine_and_brand(session, mention):
    await mention()
    await mention(brand="Vidora", mentioned="false")
    await mention(engine="perplexity", brand="Vidora")
    found = await swipe.answers(session)
    assert found["us"] == "hiredigitalworkers.com"
    assert found["engines"] == ["chatgpt", "perplexity"]
    assert found["prompts"] == [
        {
            "prompt": "best ai ugc ad tool",
            "named": {
                "chatgpt": {"Digital Workers": True, "Vidora": False},
                "perplexity": {"Vidora": True},
            },
        }
    ]


async def test_the_mention_rate_is_a_share_of_the_readings_for_that_brand(
    session, mention
):
    await mention()
    await mention(engine="perplexity", mentioned="false")
    await mention(brand="Vidora")
    found = await swipe.answers(session)
    assert found["mention_rate"] == {"Digital Workers": 0.5, "Vidora": 1.0}


async def test_only_our_own_cited_urls_are_counted(session, mention):
    await mention(cited_url="https://hiredigitalworkers.com/a")
    await mention(engine="perplexity", cited_url="https://hiredigitalworkers.com/a")
    await mention(engine="gemini", cited_url="https://hiredigitalworkers.com/b")
    await mention(brand="Vidora", cited_url="https://vidora.ai/x")
    found = await swipe.answers(session)
    assert found["cited"] == [
        {"url": "https://hiredigitalworkers.com/a", "count": 2},
        {"url": "https://hiredigitalworkers.com/b", "count": 1},
    ]


async def test_the_newest_reading_decides_whether_a_brand_was_named(session, mention):
    await mention(mentioned="false", checked_on="2026-08-01")
    await mention(mentioned="true", checked_on="2026-09-01")
    found = await swipe.answers(session)
    assert found["prompts"][0]["named"]["chatgpt"] == {"Digital Workers": True}


async def test_answers_narrow_to_one_prompt(session, mention):
    await mention()
    await mention(prompt="ugc ads without creators")
    found = await swipe.answers(session, prompt="ugc ads without creators")
    assert [row["prompt"] for row in found["prompts"]] == ["ugc ads without creators"]


async def test_answers_of_nothing_name_no_engines(session):
    assert await swipe.answers(session) == {
        "us": "hiredigitalworkers.com",
        "engines": [],
        "prompts": [],
        "mention_rate": {},
        "cited": [],
    }


@pytest.fixture
def page(canonical, link):
    async def _make(owner=None, **facts):
        base = {
            "url": "https://vidora.ai/pricing",
            "name": "Pricing",
            "competitor_ref": "vidora.ai",
            "body_sha": "a3f9",
            "word_count": "420",
            "fetched_on": "2026-09-01",
        }
        made = await canonical(
            "competitor_page", {**base, **facts}, sources=["competitor_pages"]
        )
        if owner is not None:
            await link(made, "belongs_to", owner)
        return made

    return _make


@pytest.fixture
def post(canonical, link):
    async def _make(owner=None, **facts):
        base = {
            "name": "We shut down our studio",
            "platform": "linkedin",
            "competitor_ref": "vidora.ai",
            "posted_at": "2026-09-02",
            "likes": "890",
            "comments": "12",
            "shares": "4",
            "url": "https://linkedin.com/posts/1",
        }
        made = await canonical(
            "competitor_post", {**base, **facts}, sources=["linkedin_posts"]
        )
        if owner is not None:
            await link(made, "belongs_to", owner)
        return made

    return _make


async def test_content_counts_the_pages_and_the_posts(session, competitor, page, post):
    owner = await competitor()
    await page(owner)
    await post(owner)
    found = await swipe.content(session)
    assert (found["pages"], found["posts"]) == (1, 1)


async def test_a_page_read_again_with_another_body_is_a_change(
    session, competitor, page
):
    owner = await competitor()
    await page(owner, body_sha="a3f9", fetched_on="2026-09-01")
    await page(owner, body_sha="0c7a", fetched_on="2026-09-11")
    found = await swipe.content(session)
    assert found["changes"] == [
        {
            "competitor": "Vidora",
            "url": "https://vidora.ai/pricing",
            "on": "2026-09-11",
            "before": "a3f9",
            "after": "0c7a",
        }
    ]


async def test_a_page_read_again_unchanged_is_no_change(session, competitor, page):
    owner = await competitor()
    await page(owner, fetched_on="2026-09-01")
    await page(owner, fetched_on="2026-09-11")
    assert (await swipe.content(session))["changes"] == []


async def test_the_recent_posts_carry_their_engagement(session, competitor, post):
    owner = await competitor()
    await post(owner, posted_at="2026-09-01")
    await post(owner, posted_at="2026-09-03", name="Nine hooks", likes="12")
    found = await swipe.content(session)
    assert found["recent_posts"] == [
        {
            "competitor": "Vidora",
            "text": "Nine hooks",
            "posted_at": "2026-09-03",
            "likes": 12,
            "url": "https://linkedin.com/posts/1",
        },
        {
            "competitor": "Vidora",
            "text": "We shut down our studio",
            "posted_at": "2026-09-01",
            "likes": 890,
            "url": "https://linkedin.com/posts/1",
        },
    ]


async def test_content_with_nothing_read_is_empty(session):
    assert await swipe.content(session) == {
        "pages": 0,
        "posts": 0,
        "changes": [],
        "recent_posts": [],
    }


async def test_the_companies_view_names_us_and_everyone_tracked(session):
    found = await swipe.companies(session)
    assert found["us"] == {
        "name": "Digital Workers",
        "domain": "hiredigitalworkers.com",
    }
    assert [c["slug"] for c in found["competitors"]] == [
        "avatarly",
        "clipwise",
        "vidora",
    ]
    assert found["competitors"][2]["name"] == "Vidora"


async def test_a_connector_that_never_ran_has_never_synced(session):
    found = await swipe.companies(session)
    sources = {s["source"]: s for s in found["competitors"][0]["sources"]}
    assert sources["meta_ad_library"] == {
        "source": "meta_ad_library",
        "ok": False,
        "last_sync": None,
        "rows": 0,
    }


async def test_a_competitor_counts_the_rows_each_connector_holds_for_it(
    session, canonical, ad, link
):
    vidora = await canonical("competitor", VIDORA)
    await ad(vidora)
    await ad(vidora)
    await sync_run(session, "meta_ad_library", ok=True)
    found = await swipe.companies(session)
    sources = {s["source"]: s for s in found["competitors"][2]["sources"]}
    assert sources["meta_ad_library"]["rows"] == 2
    assert sources["meta_ad_library"]["ok"] is True
    assert sources["meta_ad_library"]["last_sync"] is not None


async def test_a_failed_sync_is_the_status_of_that_connector(session, competitor):
    await competitor()
    await sync_run(session, "meta_ad_library", ok=False, detail="rate-limited")
    found = await swipe.companies(session)
    sources = {s["source"]: s for s in found["competitors"][0]["sources"]}
    assert sources["meta_ad_library"]["ok"] is False


async def test_a_remix_opens_a_proposal_and_a_draft_run(
    session, competitor, ad, monkeypatch
):
    studio_on(monkeypatch)
    made = await ad(await competitor())
    seq, started = await swipe.remix(
        session, str(made), "ad", "aios", "counter_ad", ["hook"]
    )
    run = (await session.execute(select(SkillRun))).scalars().one()
    assert (run.skill, run.mode, run.caller, run.proposal_seq) == (
        "dw-remix",
        "draft",
        "studio",
        seq,
    )
    assert started.skill_run == run.seq
    assert started.ask.input == f"remix swipe/{made} as ad, keep: hook"
    assert (started.ask.look, started.ask.slot) == ("aios", "counter_ad")
    detail = await proposals.detail(session, seq)
    assert detail["title"] == "counter to Vidora"
    assert detail["ancestor_ref"] == f"swipe/{made}"
    assert detail["reactive"] is True


async def test_a_remix_keeping_nothing_says_so(session, competitor, ad, monkeypatch):
    studio_on(monkeypatch)
    made = await ad(await competitor())
    _seq, started = await swipe.remix(session, str(made), "ad", None, None, [])
    assert started.ask.input.endswith("keep: nothing")


async def test_a_remix_of_an_ad_nobody_owns_is_titled_by_its_reference(
    session, ad, monkeypatch
):
    studio_on(monkeypatch)
    made = await ad(None, competitor_ref=None)
    seq, _started = await swipe.remix(session, str(made), "ad", None, None, [])
    assert (await proposals.detail(session, seq))["title"] == f"counter to swipe/{made}"


async def test_a_remix_of_nothing_is_refused(session, monkeypatch):
    studio_on(monkeypatch)
    with pytest.raises(errors.Missing):
        await swipe.remix(
            session, "0b3c2f4e-0000-0000-0000-000000000000", "ad", None, None, []
        )


async def test_a_remix_while_studio_is_off_is_refused(
    session, competitor, ad, monkeypatch
):
    monkeypatch.setattr("app.config.settings.STUDIO_ENABLED", False)
    made = await ad(await competitor())
    with pytest.raises(errors.Refused):
        await swipe.remix(session, str(made), "ad", None, None, [])
