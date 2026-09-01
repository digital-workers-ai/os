import pytest

from app.engine import strategies as strat


def outcome(name, current, target, history=()):
    return strat.STRATEGIES[name](current, target, list(history), {})


class TestAtLeastAndAtMost:
    @pytest.mark.parametrize(
        "current,met", [(99.0, False), (100.0, True), (101.0, True)]
    )
    def test_at_least_meets_on_equality(self, current, met):
        assert outcome("at_least", current, 100.0).met is met

    @pytest.mark.parametrize(
        "current,met", [(99.0, True), (100.0, True), (101.0, False)]
    )
    def test_at_most_meets_on_equality(self, current, met):
        assert outcome("at_most", current, 100.0).met is met

    def test_progress_toward_a_target_is_the_ratio(self):
        assert outcome("at_least", 25.0, 100.0).progress == 25.0

    def test_progress_is_capped_at_a_hundred(self):
        assert outcome("at_least", 500.0, 100.0).progress == 100.0

    def test_progress_never_goes_negative(self):
        assert outcome("at_least", -50.0, 100.0).progress == 0.0

    def test_a_non_positive_target_reads_as_done_or_not(self):
        assert outcome("at_least", 5.0, 0.0).progress == 100.0

    def test_being_under_a_ceiling_is_full_progress(self):
        assert outcome("at_most", 5.0, 100.0).progress == 100.0

    def test_being_over_a_ceiling_is_partial(self):
        assert outcome("at_most", 200.0, 100.0).progress < 100.0


class TestIncreasing:
    def test_it_needs_both_a_rising_series_and_the_target(self):
        assert outcome("increasing", 100.0, 100.0, [1.0, 2.0]).met is True
        assert outcome("increasing", 99.0, 100.0, [1.0, 2.0]).met is False
        assert outcome("increasing", 100.0, 100.0, [2.0, 1.0]).met is False

    def test_a_flat_series_still_counts_as_not_falling(self):
        assert outcome("increasing", 100.0, 100.0, [2.0, 2.0]).met is True

    def test_the_trend_is_named_on_the_receipt(self):
        up = outcome("increasing", 100.0, 100.0, [1.0, 2.0])
        down = outcome("increasing", 100.0, 100.0, [2.0, 1.0])
        assert up.detail["trend"] == "up"
        assert down.detail["trend"] == "flat/down"

    def test_one_point_is_not_a_trend(self):
        assert outcome("increasing", 100.0, 100.0, [1.0]).met is None
        assert outcome("increasing", 100.0, 100.0, []).met is None


class TestATrendReadsTheSeriesNotJustItsEnds:
    def test_a_dip_that_recovers_higher_is_still_a_rise(self):
        assert outcome("increasing", 100.0, 100.0, [1.0, 0.0, 2.0]).met is True

    def test_shedding_and_re_adding_to_the_same_level_is_not(self):
        assert outcome("increasing", 100.0, 100.0, [20.0, 15.0, 20.0]).met is False

    def test_a_flat_series_is_still_not_falling(self):
        assert outcome("increasing", 100.0, 100.0, [2.0, 2.0]).met is True

    def test_a_steady_climb_is_a_rise(self):
        assert outcome("increasing", 100.0, 100.0, [1.0, 2.0, 3.0]).met is True
