from datetime import date

import pytest

from app.engine import calendar as spec
from app.studio import calendar
from tests.test_studio_factories import (
    TODAY,
    agent_run,
    evidence,
    fake_marketer,
    proposal,
    slot_skip,
)

WEEK_FROM = date(2026, 9, 7)
WEEK_TO = date(2026, 9, 13)


@pytest.fixture
def declared(monkeypatch):
    def _set(**slots):
        monkeypatch.setattr(spec, "definitions", lambda: {"slots": slots})

    return _set


def weekly(**extra):
    return {
        "kind": "post",
        "when": "weekly",
        "days": ["tue", "fri"],
        "time": "06:00",
        "theme": "brand",
        **extra,
    }


async def test_a_weekly_slot_lands_on_each_of_its_days(session, declared):
    declared(linkedin_post=weekly())
    rows = await calendar.slots(session, WEEK_FROM, WEEK_TO)
    assert [r["date"] for r in rows] == ["2026-09-08", "2026-09-11"]
    assert {r["name"] for r in rows} == {"linkedin_post"}


async def test_a_weekly_slot_may_name_one_day(session, declared):
    declared(
        newsletter_weekly={
            "kind": "newsletter",
            "when": "weekly",
            "day": "mon",
            "time": "06:00",
            "theme": "brand",
        }
    )
    rows = await calendar.slots(session, WEEK_FROM, WEEK_TO)
    assert [r["date"] for r in rows] == ["2026-09-07"]


async def test_a_fortnightly_slot_skips_every_other_week(session, declared):
    declared(
        blog_biweekly={
            "kind": "blog",
            "when": "fortnightly",
            "day": "thu",
            "time": "06:00",
            "theme": "brand",
        }
    )
    rows = await calendar.slots(session, date(2026, 9, 1), date(2026, 9, 30))
    assert [r["date"] for r in rows] == ["2026-09-03", "2026-09-17"]


async def test_a_monthly_slot_lands_on_its_day_in_every_month(session, declared):
    declared(
        video_monthly={
            "kind": "video",
            "when": "monthly",
            "day": 1,
            "look": "aios",
            "time": "06:00",
            "theme": "brand",
        }
    )
    rows = await calendar.slots(session, date(2026, 8, 15), date(2026, 11, 2))
    assert [r["date"] for r in rows] == ["2026-09-01", "2026-10-01", "2026-11-01"]
    assert rows[0]["look"] == "aios"


async def test_a_reactive_slot_appears_on_the_date_of_its_proposal(session, declared):
    declared(
        counter_ad={
            "kind": "ad",
            "when": "reactive",
            "cap_per_week": 2,
            "look": "aios",
            "theme": "competitor",
        }
    )
    made = await proposal(
        session, kind="ad", slot_name="counter_ad", reactive=True, skill="dw-counter-ad"
    )
    await evidence(
        session,
        made.seq,
        kind="competitor_ad",
        ref="swipe/8821",
        detail="five ads on one angle",
    )
    rows = await calendar.slots(session, date(2026, 9, 1), date(2026, 9, 30))
    assert [(r["date"], r["state"], r["proposal_seq"]) for r in rows] == [
        (TODAY.isoformat(), "proposed", made.seq)
    ]
    assert rows[0]["reactive"] is True
    assert rows[0]["reason"] == "five ads on one angle"


async def test_a_reactive_slot_with_no_proposal_shows_no_date_of_its_own(
    session, declared
):
    declared(
        counter_ad={
            "kind": "ad",
            "when": "reactive",
            "cap_per_week": 2,
            "theme": "competitor",
        }
    )
    assert await calendar.slots(session, date(2026, 9, 1), date(2026, 9, 30)) == []


async def test_a_reactive_proposal_with_no_evidence_records_no_reason(
    session, declared
):
    declared(
        counter_ad={
            "kind": "ad",
            "when": "reactive",
            "cap_per_week": 2,
            "theme": "competitor",
        }
    )
    await proposal(session, kind="ad", slot_name="counter_ad", reactive=True)
    rows = await calendar.slots(session, date(2026, 9, 1), date(2026, 9, 30))
    assert rows[0]["reason"] is None


async def test_a_reactive_proposal_outside_the_range_is_not_shown(session, declared):
    declared(
        counter_ad={
            "kind": "ad",
            "when": "reactive",
            "cap_per_week": 2,
            "theme": "competitor",
        }
    )
    await proposal(session, kind="ad", slot_name="counter_ad", reactive=True)
    assert await calendar.slots(session, date(2026, 10, 1), date(2026, 10, 31)) == []


async def test_a_slot_with_no_proposal_is_empty(session, declared):
    declared(linkedin_post=weekly())
    rows = await calendar.slots(session, WEEK_FROM, WEEK_TO)
    assert [(r["state"], r["proposal_seq"], r["reason"]) for r in rows] == [
        ("empty", None, None),
        ("empty", None, None),
    ]


@pytest.mark.parametrize(
    ("status", "state"),
    [("open", "proposed"), ("approved", "approved"), ("built", "built")],
)
async def test_the_proposal_carrying_a_slot_gives_it_its_state(
    session, declared, status, state
):
    declared(linkedin_post=weekly())
    made = await proposal(
        session, slot_date=date(2026, 9, 8), slot_name="linkedin_post", status=status
    )
    rows = await calendar.slots(session, WEEK_FROM, WEEK_TO)
    assert rows[0]["state"] == state
    assert rows[0]["proposal_seq"] == made.seq


async def test_a_rejected_proposal_leaves_its_slot_empty(session, declared):
    declared(linkedin_post=weekly())
    await proposal(
        session,
        slot_date=date(2026, 9, 8),
        slot_name="linkedin_post",
        status="rejected",
        reason="off voice",
    )
    rows = await calendar.slots(session, WEEK_FROM, WEEK_TO)
    assert (rows[0]["state"], rows[0]["proposal_seq"]) == ("empty", None)


async def test_the_furthest_proposal_wins_a_slot_two_of_them_claim(session, declared):
    declared(linkedin_post=weekly())
    await proposal(
        session, slot_date=date(2026, 9, 8), slot_name="linkedin_post", status="open"
    )
    built = await proposal(
        session, slot_date=date(2026, 9, 8), slot_name="linkedin_post", status="built"
    )
    rows = await calendar.slots(session, WEEK_FROM, WEEK_TO)
    assert (rows[0]["state"], rows[0]["proposal_seq"]) == ("built", built.seq)


async def test_a_later_proposal_does_not_take_a_slot_already_built(session, declared):
    declared(linkedin_post=weekly())
    built = await proposal(
        session, slot_date=date(2026, 9, 8), slot_name="linkedin_post", status="built"
    )
    await proposal(session, slot_date=date(2026, 9, 8), slot_name="linkedin_post")
    rows = await calendar.slots(session, WEEK_FROM, WEEK_TO)
    assert (rows[0]["state"], rows[0]["proposal_seq"]) == ("built", built.seq)


async def test_the_later_proposal_wins_when_two_share_a_status(session, declared):
    declared(linkedin_post=weekly())
    await proposal(session, slot_date=date(2026, 9, 8), slot_name="linkedin_post")
    second = await proposal(
        session, slot_date=date(2026, 9, 8), slot_name="linkedin_post"
    )
    rows = await calendar.slots(session, WEEK_FROM, WEEK_TO)
    assert rows[0]["proposal_seq"] == second.seq


async def test_a_skip_beats_the_proposal_on_that_day(session, declared):
    declared(linkedin_post=weekly())
    await proposal(session, slot_date=date(2026, 9, 8), slot_name="linkedin_post")
    await slot_skip(session, date(2026, 9, 8), "linkedin_post")
    rows = await calendar.slots(session, WEEK_FROM, WEEK_TO)
    assert [r["state"] for r in rows] == ["skipped", "empty"]


async def test_a_skip_on_another_day_leaves_the_slot_alone(session, declared):
    declared(linkedin_post=weekly())
    await slot_skip(session, date(2026, 9, 11), "linkedin_post")
    rows = await calendar.slots(session, WEEK_FROM, WEEK_TO)
    assert [r["state"] for r in rows] == ["empty", "skipped"]


async def test_a_slot_carries_the_lines_that_declare_it(session, declared):
    declared(linkedin_post=weekly(look="aios"))
    rows = await calendar.slots(session, WEEK_FROM, WEEK_TO)
    assert rows[0]["spec"] == [
        "kind: post",
        "when: weekly",
        "days: tue, fri",
        "time: 06:00",
        "theme: brand",
        "look: aios",
    ]
    assert rows[0]["time"] == "06:00"
    assert rows[0]["theme"] == "brand"
    assert rows[0]["kind"] == "post"


async def test_a_slot_that_names_no_time_reports_none(session, declared):
    declared(
        linkedin_post={"kind": "post", "when": "weekly", "day": "tue", "theme": "brand"}
    )
    rows = await calendar.slots(session, WEEK_FROM, WEEK_TO)
    assert rows[0]["time"] is None
    assert rows[0]["look"] is None


async def test_slots_come_back_in_date_then_name_order(session, declared):
    declared(
        linkedin_post=weekly(),
        newsletter_weekly={
            "kind": "newsletter",
            "when": "weekly",
            "day": "tue",
            "theme": "brand",
        },
    )
    rows = await calendar.slots(session, WEEK_FROM, WEEK_TO)
    assert [(r["date"], r["name"]) for r in rows] == [
        ("2026-09-08", "linkedin_post"),
        ("2026-09-08", "newsletter_weekly"),
        ("2026-09-11", "linkedin_post"),
    ]


async def test_a_range_that_ends_before_it_starts_has_no_slots(session, declared):
    declared(linkedin_post=weekly())
    assert await calendar.slots(session, WEEK_TO, WEEK_FROM) == []


async def test_cadence_counts_what_is_built_against_what_is_planned(session, declared):
    declared(
        linkedin_post=weekly(),
        video_monthly={"kind": "video", "when": "monthly", "day": 9, "theme": "brand"},
    )
    await proposal(
        session, slot_date=date(2026, 9, 8), slot_name="linkedin_post", status="built"
    )
    rows = await calendar.slots(session, WEEK_FROM, WEEK_TO)
    assert calendar.cadence(rows) == [
        {"kind": "post", "done": 1, "planned": 2},
        {"kind": "video", "done": 0, "planned": 1},
    ]


async def test_a_skipped_slot_is_not_planned(session, declared):
    declared(linkedin_post=weekly())
    await slot_skip(session, date(2026, 9, 8), "linkedin_post")
    rows = await calendar.slots(session, WEEK_FROM, WEEK_TO)
    assert calendar.cadence(rows) == [{"kind": "post", "done": 0, "planned": 1}]


async def test_cadence_of_nothing_is_nothing():
    assert calendar.cadence([]) == []


async def test_filling_the_range_hands_the_days_to_the_marketer(session, monkeypatch):
    marketer = fake_marketer(monkeypatch)
    await agent_run(session)
    run = await calendar.fill(session, 14)
    assert marketer.calls == [14]
    assert run.seq == 9
