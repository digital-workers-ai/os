import pytest

from app.engine import goals, strategies

NOT_FINITE = [float("nan"), float("inf"), float("-inf")]

SIMPLE = ["at_least", "at_most"]
HISTORICAL = ["increasing"]


class TestEveryStrategyRefusesNonFiniteInput:
    @pytest.mark.parametrize("name", SIMPLE)
    @pytest.mark.parametrize("bad", NOT_FINITE)
    def test_a_non_finite_current_value_is_undecided(self, name, bad):
        outcome = strategies.STRATEGIES[name](bad, 100.0, [], {})
        assert outcome.met is None
        assert "finite" in outcome.detail.get("unknown", "")

    @pytest.mark.parametrize("name", SIMPLE)
    @pytest.mark.parametrize("bad", NOT_FINITE)
    def test_a_non_finite_target_is_undecided(self, name, bad):
        outcome = strategies.STRATEGIES[name](100.0, bad, [], {})
        assert outcome.met is None

    @pytest.mark.parametrize("name", HISTORICAL)
    @pytest.mark.parametrize("bad", NOT_FINITE)
    def test_a_non_finite_current_over_history_is_undecided(self, name, bad):
        outcome = strategies.STRATEGIES[name](bad, 100.0, [50.0, 60.0], {})
        assert outcome.met is None

    @pytest.mark.parametrize("name", HISTORICAL)
    @pytest.mark.parametrize("bad", NOT_FINITE)
    def test_a_non_finite_target_over_history_is_undecided(self, name, bad):
        outcome = strategies.STRATEGIES[name](100.0, bad, [50.0, 60.0], {})
        assert outcome.met is None

    @pytest.mark.parametrize("name", HISTORICAL)
    @pytest.mark.parametrize("bad", NOT_FINITE)
    def test_a_non_finite_first_history_point_is_undecided(self, name, bad):
        outcome = strategies.STRATEGIES[name](100.0, 10.0, [bad, 50.0, 60.0], {})
        assert outcome.met is None

    @pytest.mark.parametrize("name", HISTORICAL)
    @pytest.mark.parametrize("bad", NOT_FINITE)
    def test_a_non_finite_last_history_point_is_undecided(self, name, bad):
        outcome = strategies.STRATEGIES[name](100.0, 10.0, [40.0, 50.0, bad], {})
        assert outcome.met is None


class TestProgressRefusesToBeComputedFromNonsense:
    @pytest.mark.parametrize("bad", NOT_FINITE)
    def test_upward_progress_is_none_rather_than_a_percentage(self, bad):
        assert strategies._toward(bad, 100.0) is None
        assert strategies._toward(100.0, bad) is None

    @pytest.mark.parametrize("bad", NOT_FINITE)
    def test_downward_progress_is_none_rather_than_a_percentage(self, bad):
        assert strategies._under(bad, 100.0) is None
        assert strategies._under(100.0, bad) is None


class TestGoalEvaluation:
    def test_a_goals_file_that_is_not_a_mapping_is_refused(self, tmp_path):
        path = tmp_path / "goals.yaml"
        path.write_text("- a\n- b\n")
        with pytest.raises(goals.GoalError, match="top level must be a mapping"):
            goals.load(path)

    async def test_a_goal_naming_an_unknown_strategy_is_undecided(self, session):
        defs = {
            "grow": {
                "metric": "deal_count",
                "strategy": "vibes",
                "target": 10,
                "label": "Grow",
            }
        }
        rows = await goals.evaluate_over(session, defs, {"deal_count": {"value": 5}})
        assert rows[0]["met"] is None
        assert "vibes" in str(rows[0])

    @pytest.mark.parametrize("target", ["not a number", None, [1, 2]])
    async def test_a_target_that_is_not_a_number_is_undecided(self, session, target):
        defs = {
            "grow": {
                "metric": "deal_count",
                "strategy": "at_least",
                "target": target,
                "label": "Grow",
            }
        }
        rows = await goals.evaluate_over(session, defs, {"deal_count": {"value": 5}})
        assert rows[0]["met"] is None

    async def test_an_undecided_goal_always_carries_a_reason(self, session):
        defs = {
            "trend": {
                "metric": "deal_count",
                "strategy": "improving",
                "target": 3,
                "label": "Trend",
            }
        }
        rows = await goals.evaluate_over(session, defs, {"deal_count": {"value": 5}})
        row = rows[0]
        assert row["met"] is None
        assert row.get("unknown") or row.get("error"), row
