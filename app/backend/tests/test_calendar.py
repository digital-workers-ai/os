from datetime import date, timedelta
from pathlib import Path

import pytest
import yaml
from hypothesis import given, settings
from hypothesis import strategies as st

from app import caches
from app.engine import calendar

SHIPPED = Path(caches.DEFINITIONS_DIR) / "calendar.yaml"

NEWSLETTER = {
    "kind": "newsletter",
    "skill": "dw-newsletter",
    "when": "weekly",
    "day": "mon",
    "time": "06:00",
    "theme": "What changed this week.",
}
POST = {
    "kind": "post",
    "skill": "dw-linkedin-post",
    "when": "weekly",
    "days": ["tue", "fri"],
    "time": "06:00",
    "look": "stat-card",
    "ratio": "1:1",
    "theme": "One thing a spreadsheet cannot do.",
}
BLOG = {
    "kind": "blog",
    "skill": "dw-blog",
    "when": "fortnightly",
    "day": "thu",
    "time": "06:00",
    "theme": "One pillar, explained.",
}
CAROUSEL = {
    "kind": "carousel",
    "skill": "dw-carousel",
    "when": "monthly",
    "day": 1,
    "time": "06:00",
    "look": "carousel",
    "ratio": "4:5",
    "theme": "One objection, answered.",
}
SLOTS = {
    "newsletter_weekly": NEWSLETTER,
    "linkedin_post": POST,
    "blog_fortnightly": BLOG,
    "carousel_monthly": CAROUSEL,
}

SEPTEMBER = (date(2026, 9, 1), date(2026, 9, 30))
MONDAYS = [date(2026, 9, d) for d in (7, 14, 21, 28)]
TUESDAYS_AND_FRIDAYS = [date(2026, 9, d) for d in (1, 4, 8, 11, 15, 18, 22, 25, 29)]
EVEN_WEEK_THURSDAYS = [date(2026, 9, 3), date(2026, 9, 17)]


def _write(folder, doc):
    path = folder / "calendar.yaml"
    path.write_text(yaml.safe_dump(doc, sort_keys=False))
    return path


def _slot(base=POST, **overrides):
    return {**base, **overrides}


def _without(base, *keys):
    return {k: v for k, v in base.items() if k not in keys}


def _problems(folder, spec, skills=None):
    return calendar.check(_write(folder, {"slots": {"linkedin_post": spec}}), skills)


def _span(frm, to):
    return [frm + timedelta(days=n) for n in range((to - frm).days + 1)]


class TestSlotsRead:
    def test_slots_keeps_file_order(self, tmp_path, monkeypatch):
        path = _write(tmp_path, {"slots": SLOTS})
        monkeypatch.setattr(calendar, "DEFAULT_CALENDAR", path)
        assert calendar.slots() == SLOTS
        assert list(calendar.slots()) == list(SLOTS)

    def test_a_calendar_without_a_slots_mapping_is_refused(self, tmp_path, monkeypatch):
        path = _write(tmp_path, {"slots": ["a"]})
        monkeypatch.setattr(calendar, "DEFAULT_CALENDAR", path)
        with pytest.raises(calendar.CalendarError, match="slots"):
            calendar.slots()

    def test_the_constants_match_the_contract(self):
        assert calendar.KINDS == ("post", "newsletter", "blog", "image", "carousel")
        assert calendar.CADENCES == ("weekly", "fortnightly", "monthly")
        assert calendar.DAYS == ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


class TestDatesFollowTheCadence:
    def test_weekly_on_one_day(self):
        assert calendar.dates(NEWSLETTER, *SEPTEMBER) == MONDAYS

    def test_weekly_on_several_days(self):
        assert calendar.dates(POST, *SEPTEMBER) == TUESDAYS_AND_FRIDAYS

    def test_fortnightly_keeps_even_iso_weeks_only(self):
        found = calendar.dates(BLOG, date(2026, 9, 1), date(2026, 10, 8))
        assert found == [date(2026, 9, 3), date(2026, 9, 17), date(2026, 10, 1)]

    def test_fortnightly_on_several_days(self):
        slot = _slot(_without(BLOG, "day"), days=["mon", "thu"])
        found = calendar.dates(slot, date(2026, 9, 1), date(2026, 9, 14))
        assert found == [date(2026, 9, 3), date(2026, 9, 14)]

    def test_monthly_on_its_day(self):
        found = calendar.dates(CAROUSEL, date(2026, 9, 1), date(2026, 11, 30))
        assert found == [date(2026, 9, 1), date(2026, 10, 1), date(2026, 11, 1)]

    def test_monthly_late_in_the_month(self):
        slot = _slot(CAROUSEL, day=28)
        found = calendar.dates(slot, date(2026, 2, 1), date(2026, 3, 31))
        assert found == [date(2026, 2, 28), date(2026, 3, 28)]

    def test_both_ends_are_inclusive(self):
        found = calendar.dates(NEWSLETTER, date(2026, 9, 7), date(2026, 9, 14))
        assert found == [date(2026, 9, 7), date(2026, 9, 14)]

    def test_a_window_that_ends_before_it_starts_is_empty(self):
        assert calendar.dates(NEWSLETTER, date(2026, 9, 14), date(2026, 9, 7)) == []

    def test_a_single_day_window(self):
        friday = date(2026, 9, 4)
        assert calendar.dates(POST, friday, friday) == [friday]
        saturday = date(2026, 9, 5)
        assert calendar.dates(POST, saturday, saturday) == []


START = st.dates(min_value=date(2026, 1, 1), max_value=date(2027, 12, 1))
SPAN = st.integers(min_value=0, max_value=70)
DAY_SET = st.sets(st.sampled_from(calendar.DAYS), min_size=1)


class TestDatesHoldOverAnyWindow:
    @given(start=START, span=SPAN, days=DAY_SET)
    @settings(max_examples=200, deadline=None)
    def test_weekly_is_exactly_the_named_weekdays(self, start, span, days):
        end = start + timedelta(days=span)
        slot = _slot(_without(POST, "days"), days=sorted(days))
        expected = [d for d in _span(start, end) if calendar.DAYS[d.weekday()] in days]
        assert calendar.dates(slot, start, end) == expected

    @given(start=START, span=SPAN, day=st.sampled_from(calendar.DAYS))
    @settings(max_examples=200, deadline=None)
    def test_fortnightly_is_the_weekday_in_even_iso_weeks(self, start, span, day):
        end = start + timedelta(days=span)
        expected = [
            d
            for d in _span(start, end)
            if calendar.DAYS[d.weekday()] == day and d.isocalendar().week % 2 == 0
        ]
        assert calendar.dates(_slot(BLOG, day=day), start, end) == expected

    @given(start=START, span=SPAN, day=st.integers(min_value=1, max_value=28))
    @settings(max_examples=200, deadline=None)
    def test_monthly_is_that_day_of_every_month(self, start, span, day):
        end = start + timedelta(days=span)
        expected = [d for d in _span(start, end) if d.day == day]
        assert calendar.dates(_slot(CAROUSEL, day=day), start, end) == expected


class TestCheckNamesWhatIsWrong:
    def test_the_four_contract_slots_pass(self, tmp_path):
        assert calendar.check(_write(tmp_path, {"slots": SLOTS})) == []

    def test_the_default_path_is_the_calendar_file(self, tmp_path, monkeypatch):
        path = _write(tmp_path, {"slots": SLOTS})
        monkeypatch.setattr(calendar, "DEFAULT_CALENDAR", path)
        assert calendar.check() == []

    def test_a_missing_file_is_one_problem(self, tmp_path):
        problems = calendar.check(tmp_path / "calendar.yaml")
        assert len(problems) == 1, problems
        assert "calendar.yaml" in problems[0]
        assert "missing" in problems[0]

    def test_a_file_that_is_not_a_mapping(self, tmp_path):
        path = tmp_path / "calendar.yaml"
        path.write_text("- a\n")
        problems = calendar.check(path)
        assert len(problems) == 1, problems
        assert "calendar.yaml" in problems[0]
        assert "mapping" in problems[0]

    def test_a_file_that_does_not_parse(self, tmp_path):
        path = tmp_path / "calendar.yaml"
        path.write_text("slots: [\n")
        problems = calendar.check(path)
        assert len(problems) == 1, problems
        assert "calendar.yaml" in problems[0]
        assert "does not parse" in problems[0]

    @pytest.mark.parametrize("doc", [{}, {"slots": ["a"]}], ids=["absent", "a_list"])
    def test_slots_that_are_not_a_mapping(self, tmp_path, doc):
        problems = calendar.check(_write(tmp_path, doc))
        assert len(problems) == 1, problems
        assert "calendar.yaml" in problems[0]
        assert "`slots` must be a mapping" in problems[0]

    def test_a_slot_that_is_not_a_mapping(self, tmp_path):
        problems = _problems(tmp_path, "weekly")
        assert len(problems) == 1, problems
        assert "'linkedin_post'" in problems[0]
        assert "mapping" in problems[0]

    @pytest.mark.parametrize(
        "spec,reason",
        [
            (_slot(kind="video"), "kind 'video'"),
            (_without(POST, "kind"), "kind None"),
            (_slot(skill="post"), "skill 'post'"),
            (_slot(skill=7), "skill 7"),
            (_without(POST, "skill"), "skill None"),
            (_slot(when="daily"), "when 'daily'"),
            (_without(POST, "when"), "when None"),
            (_without(POST, "days"), "`day` or `days`"),
            (_slot(day="tue"), "`day` or `days`"),
            (_slot(_without(POST, "days"), day="tuesday"), "day 'tuesday'"),
            (_slot(days="tue"), "days must be"),
            (_slot(days=[]), "days must be"),
            (_slot(days=["tue", "friday"]), "days must be"),
            (_slot(time="6:00"), "time '6:00'"),
            (_slot(time="24:00"), "time '24:00'"),
            (_slot(time="06:60"), "time '06:60'"),
            (_slot(time=360), "time 360"),
            (_without(POST, "time"), "time None"),
            (_slot(theme=""), "theme"),
            (_slot(theme=7), "theme"),
            (_without(POST, "theme"), "theme"),
            (_slot(look=7), "look 7"),
            (_slot(ratio=1), "ratio 1"),
        ],
        ids=[
            "unknown_kind",
            "no_kind",
            "skill_without_prefix",
            "skill_not_a_string",
            "no_skill",
            "unknown_cadence",
            "no_cadence",
            "neither_day_nor_days",
            "both_day_and_days",
            "day_not_a_weekday",
            "days_not_a_list",
            "days_empty",
            "days_with_a_stranger",
            "time_without_leading_zero",
            "time_past_midnight",
            "time_past_the_hour",
            "time_unquoted",
            "no_time",
            "theme_empty",
            "theme_not_a_string",
            "no_theme",
            "look_not_a_string",
            "ratio_not_a_string",
        ],
    )
    def test_a_malformed_slot_is_named(self, tmp_path, spec, reason):
        problems = _problems(tmp_path, spec)
        assert len(problems) == 1, problems
        assert "calendar.yaml" in problems[0]
        assert "'linkedin_post'" in problems[0]
        assert reason in problems[0]

    def test_fortnightly_needs_a_weekday_like_weekly(self, tmp_path):
        problems = _problems(tmp_path, _slot(BLOG, day="thursday"))
        assert len(problems) == 1, problems
        assert "day 'thursday'" in problems[0]

    def test_fortnightly_with_days_passes(self, tmp_path):
        slot = _slot(_without(BLOG, "day"), days=["mon", "thu"])
        assert _problems(tmp_path, slot) == []

    @pytest.mark.parametrize(
        "day",
        [0, 29, True, "1", None],
        ids=["zero", "twenty_nine", "a_bool", "a_string", "absent"],
    )
    def test_a_monthly_day_outside_one_to_twenty_eight(self, tmp_path, day):
        problems = _problems(tmp_path, _slot(CAROUSEL, day=day))
        assert len(problems) == 1, problems
        assert "1 to 28" in problems[0]

    def test_a_monthly_slot_on_the_twenty_eighth_passes(self, tmp_path):
        assert _problems(tmp_path, _slot(CAROUSEL, day=28)) == []

    def test_a_skill_outside_the_given_list(self, tmp_path):
        problems = _problems(tmp_path, POST, skills=["dw-newsletter"])
        assert len(problems) == 1, problems
        assert "dw-linkedin-post" in problems[0]
        assert "dw-newsletter" in problems[0]

    def test_a_skill_in_the_given_list_passes(self, tmp_path):
        assert _problems(tmp_path, POST, skills=["dw-linkedin-post"]) == []

    def test_without_a_list_any_dw_skill_passes(self, tmp_path):
        assert _problems(tmp_path, _slot(skill="dw-anything")) == []

    def test_every_problem_in_a_slot_is_reported(self, tmp_path):
        assert len(_problems(tmp_path, _slot(kind="video", time="6"))) == 2

    def test_a_bad_cadence_skips_the_day_checks(self, tmp_path):
        assert len(_problems(tmp_path, _slot(when="daily", days=[]))) == 1


class TestTheShippedCalendar:
    def test_it_passes_check(self):
        assert calendar.check() == []

    def test_it_declares_the_four_contract_slots(self):
        slots = calendar.slots()
        assert list(slots) == [
            "newsletter_weekly",
            "linkedin_post",
            "blog_fortnightly",
            "carousel_monthly",
        ]
        assert [slot["skill"] for slot in slots.values()] == [
            "dw-newsletter",
            "dw-linkedin-post",
            "dw-blog",
            "dw-carousel",
        ]

    def test_every_slot_fires_in_september(self):
        slots = calendar.slots()
        fired = {name: calendar.dates(slot, *SEPTEMBER) for name, slot in slots.items()}
        assert fired == {
            "newsletter_weekly": MONDAYS,
            "linkedin_post": TUESDAYS_AND_FRIDAYS,
            "blog_fortnightly": EVEN_WEEK_THURSDAYS,
            "carousel_monthly": [date(2026, 9, 1)],
        }

    def test_every_theme_is_one_sentence(self):
        for slot in calendar.slots().values():
            theme = slot["theme"]
            assert theme.endswith(".")
            assert ". " not in theme
