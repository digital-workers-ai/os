import pytest
import yaml

from app.engine import calendar

SHIPPED_SLOTS = {
    "newsletter_weekly",
    "linkedin_post",
    "blog_biweekly",
    "video_monthly",
    "counter_ad",
}


def _slot(**fields):
    slot = {
        "kind": "post",
        "when": "weekly",
        "day": "tue",
        "time": "06:00",
        "theme": "brand",
    }
    for key, value in fields.items():
        if value is None:
            slot.pop(key, None)
        else:
            slot[key] = value
    return slot


def _file(root, slots):
    path = root / "calendar.yaml"
    path.write_text(yaml.safe_dump(slots, sort_keys=False))
    return path


def _check(root, **fields):
    return calendar.check(_file(root, {"slots": {"a_slot": _slot(**fields)}}))


class TestTheShippedFile:
    def test_the_shipped_file_has_no_problems(self):
        assert calendar.check() == []

    def test_load_returns_the_whole_document(self):
        assert set(calendar.load()) == {"slots"}

    def test_the_schedule_names_every_slot_studio_fills(self):
        assert set(calendar.slots()) == SHIPPED_SLOTS

    def test_the_weekly_post_lands_twice_a_week(self):
        assert calendar.slots()["linkedin_post"]["days"] == ["tue", "fri"]

    def test_the_reactive_slot_caps_itself(self):
        counter = calendar.slots()["counter_ad"]
        assert counter["when"] == "reactive"
        assert counter["cap_per_week"] == 2
        assert counter["theme"] == "competitor"

    def test_the_monthly_video_names_a_look(self):
        assert calendar.slots()["video_monthly"]["look"] == "aios"


class TestTheFileShape:
    def test_a_well_formed_slot_has_no_problems(self, tmp_path):
        assert _check(tmp_path) == []

    def test_a_file_that_is_not_a_mapping_is_one_problem(self, tmp_path):
        path = tmp_path / "calendar.yaml"
        path.write_text("- a\n")
        problems = calendar.check(path)
        assert len(problems) == 1, problems
        assert "calendar.yaml" in problems[0]

    def test_a_file_with_no_slots_block_is_one_problem(self, tmp_path):
        problems = calendar.check(_file(tmp_path, {"looks": {}}))
        assert len(problems) == 1, problems
        assert "slots" in problems[0]

    def test_a_slot_that_is_not_a_mapping_is_refused_and_named(self, tmp_path):
        problems = calendar.check(_file(tmp_path, {"slots": {"a_slot": "weekly"}}))
        assert problems == ["slot 'a_slot' must be a mapping"]


class TestEachSlotIsChecked:
    def test_an_unknown_kind_lists_the_known_ones(self, tmp_path):
        problems = _check(tmp_path, kind="hologram")
        assert any("hologram" in p and "newsletter" in p for p in problems), problems

    def test_an_unknown_cadence_lists_the_known_ones(self, tmp_path):
        problems = _check(tmp_path, when="hourly")
        assert any("hourly" in p and "monthly" in p for p in problems), problems

    @pytest.mark.parametrize("theme", ["rivals", None])
    def test_a_theme_that_names_no_material_is_refused(self, tmp_path, theme):
        problems = _check(tmp_path, theme=theme)
        assert any("theme" in p for p in problems), problems

    @pytest.mark.parametrize("bad", ["6am", "24:00", "6:00", 360])
    def test_a_time_that_is_not_a_clock_time_is_refused(self, tmp_path, bad):
        problems = _check(tmp_path, time=bad)
        assert any("time" in p for p in problems), problems

    def test_a_slot_with_no_time_is_allowed(self, tmp_path):
        assert _check(tmp_path, when="reactive", cap_per_week=2, time=None) == []


class TestCadencesCarryWhatTheyNeed:
    def test_a_weekly_slot_with_no_day_is_refused(self, tmp_path):
        problems = _check(tmp_path, day=None)
        assert any("weekday" in p for p in problems), problems

    def test_a_fortnightly_slot_with_no_day_is_refused(self, tmp_path):
        problems = _check(tmp_path, when="fortnightly", day=None)
        assert any("weekday" in p for p in problems), problems

    def test_a_weekly_slot_may_name_several_days(self, tmp_path):
        assert _check(tmp_path, day=None, days=["tue", "fri"]) == []

    def test_a_day_that_is_not_a_weekday_is_refused(self, tmp_path):
        problems = _check(tmp_path, day=None, days=["tue", "funday"])
        assert any("funday" in p and "mon" in p for p in problems), problems

    def test_a_monthly_slot_lands_on_a_day_every_month_has(self, tmp_path):
        assert _check(tmp_path, when="monthly", day=1) == []

    @pytest.mark.parametrize("day", [0, 29, "thu", None])
    def test_a_monthly_day_outside_the_safe_range_is_refused(self, tmp_path, day):
        problems = _check(tmp_path, when="monthly", day=day)
        assert any("day" in p and "28" in p for p in problems), problems

    def test_a_reactive_slot_without_a_cap_is_refused(self, tmp_path):
        problems = _check(tmp_path, when="reactive", day=None, time=None)
        assert any("cap_per_week" in p for p in problems), problems

    def test_a_reactive_slot_with_a_cap_needs_no_day(self, tmp_path):
        assert _check(tmp_path, when="reactive", day=None, cap_per_week=2) == []
