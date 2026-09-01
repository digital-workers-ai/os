import inspect
import math

import pytest

from app.engine import strategies

NAN = float("nan")
INF = float("inf")


class TestTheRegistry:
    def test_the_four_shipped_are_registered(self):
        assert set(strategies.STRATEGIES) == {
            "at_least",
            "at_most",
            "increasing",
            "threshold_band",
        }

    def test_only_the_trend_strategy_needs_history(self):
        assert strategies.NEEDS_HISTORY == {"increasing"}

    def test_every_strategy_declares_the_params_it_accepts(self):
        assert set(strategies.PARAMS) == set(strategies.STRATEGIES)
        assert strategies.PARAMS == {
            "at_least": (),
            "at_most": (),
            "increasing": (),
            "threshold_band": ("band_low", "band_high"),
        }

    def test_defaults_returns_a_fresh_copy(self):
        first = strategies.defaults("threshold_band")
        assert first == {"band_low": 0.8, "band_high": 1.2}
        first["band_low"] = 0.0
        assert strategies.defaults("threshold_band") == {
            "band_low": 0.8,
            "band_high": 1.2,
        }
        assert strategies.defaults("at_least") == {}
        assert strategies.defaults("at_most") == {}
        assert strategies.defaults("increasing") == {}

    def test_every_strategy_shares_one_calling_convention(self):
        for name, fn in strategies.STRATEGIES.items():
            params = list(inspect.signature(fn).parameters)
            assert params == ["current", "target", "history", "params"], name

    def test_a_strategy_is_pure(self):
        source = inspect.getsource(strategies)
        for banned in ("datetime.now", "open(", "session", "requests", "Path("):
            assert banned not in source, banned


class TestTotality:
    @pytest.mark.parametrize("current", [0, -5, 17147.0, NAN, INF])
    @pytest.mark.parametrize("target", [0, 100, -3, NAN])
    @pytest.mark.parametrize("history", [[], [1], [1, 2], [NAN, 2]])
    def test_no_input_in_the_grid_raises(self, current, target, history):
        for name, fn in strategies.STRATEGIES.items():
            outcome = fn(current, target, history, {})
            assert outcome.met in (True, False, None), name
            assert outcome.progress is None or isinstance(outcome.progress, float)
            assert isinstance(outcome.detail, dict), name

    @pytest.mark.parametrize("current", [0, -5, 17147.0])
    @pytest.mark.parametrize("target", [0, 100, -3])
    @pytest.mark.parametrize("history", [[], [1, 2]])
    def test_progress_stays_between_zero_and_one_hundred(
        self, current, target, history
    ):
        for name, fn in strategies.STRATEGIES.items():
            progress = fn(current, target, history, {}).progress
            if progress is not None:
                assert 0.0 <= progress <= 100.0, name
                assert math.isfinite(progress), name


class TestAZeroTargetReadsAsDoneOrNot:
    def test_at_least_met_over_zero_is_full_progress(self):
        outcome = strategies.at_least(5.0, 0.0, [], {})
        assert outcome.met is True
        assert outcome.progress == 100.0

    def test_at_least_missed_under_zero_is_no_progress(self):
        outcome = strategies.at_least(-5.0, 0.0, [], {})
        assert outcome.met is False
        assert outcome.progress == 0.0

    def test_at_most_under_a_zero_ceiling_is_full_progress(self):
        outcome = strategies.at_most(-5.0, 0.0, [], {})
        assert outcome.met is True
        assert outcome.progress == 100.0

    def test_at_most_over_a_zero_ceiling_is_no_progress(self):
        outcome = strategies.at_most(5.0, 0.0, [], {})
        assert outcome.met is False
        assert outcome.progress == 0.0

    def test_a_negative_target_reads_the_same_way(self):
        assert strategies.at_least(5.0, -3.0, [], {}).progress == 100.0
        assert strategies.at_least(-5.0, -3.0, [], {}).progress == 0.0


class TestMetAndProgressAgreeAtTheBoundary:
    @pytest.mark.parametrize("name", ["at_least", "at_most"])
    def test_equality_is_met_with_full_progress(self, name):
        outcome = strategies.STRATEGIES[name](100.0, 100.0, [], {})
        assert outcome.met is True, name
        assert outcome.progress == 100.0, name


class TestThresholdBand:
    def test_met_inside_and_at_both_edges(self):
        assert strategies.threshold_band(80.0, 100.0, [], {}).met is True
        assert strategies.threshold_band(100.0, 100.0, [], {}).met is True
        assert strategies.threshold_band(120.0, 100.0, [], {}).met is True

    def test_missed_just_outside_either_edge(self):
        assert strategies.threshold_band(79.9, 100.0, [], {}).met is False
        assert strategies.threshold_band(120.1, 100.0, [], {}).met is False

    def test_progress_is_full_on_a_hit_and_none_on_a_miss(self):
        assert strategies.threshold_band(100.0, 100.0, [], {}).progress == 100.0
        assert strategies.threshold_band(500.0, 100.0, [], {}).progress is None

    def test_the_edges_come_from_the_goal_params(self):
        params = {"band_low": 0.5, "band_high": 2.0}
        assert strategies.threshold_band(150.0, 100.0, [], params).met is True
        assert strategies.threshold_band(49.9, 100.0, [], params).met is False

    def test_a_negative_target_orders_its_own_edges(self):
        params = {"band_low": 0.9, "band_high": 1.1}
        outcome = strategies.threshold_band(-100.0, -100.0, [], params)
        assert outcome.met is True
        assert outcome.detail["band"] == [-110.0, -90.0]

    def test_a_non_finite_input_is_unknown_not_a_verdict(self):
        for current, target in ((NAN, 100.0), (INF, 100.0), (100.0, NAN)):
            outcome = strategies.threshold_band(current, target, [], {})
            assert outcome.met is None
            assert outcome.progress is None
            assert outcome.detail["unknown"]

    def test_the_detail_carries_the_band_and_the_distance_outside_it(self):
        assert strategies.threshold_band(100.0, 100.0, [], {}).detail["band"] == [
            80.0,
            120.0,
        ]
        assert (
            strategies.threshold_band(100.0, 100.0, [], {}).detail["outside_band_by"]
            == 0.0
        )
        assert (
            strategies.threshold_band(130.0, 100.0, [], {}).detail["outside_band_by"]
            == 10.0
        )
        assert (
            strategies.threshold_band(70.0, 100.0, [], {}).detail["outside_band_by"]
            == 10.0
        )
