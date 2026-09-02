import ast
import inspect
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.engine import goals, strategies
from app.models import MetricSnapshot


def _goal(**over):
    base = {"label": "L", "metric": "mrr", "target": 100.0, "strategy": "at_least"}
    base.update(over)
    return {"g": base}


class TestAnUnmeasurableGoalIsUnknown:
    async def test_a_metric_that_errored(self, session):
        results = await goals.evaluate_over(
            session, _goal(), {"mrr": {"error": "bad spec"}}
        )
        assert results[0]["met"] is None
        assert "unavailable" in results[0]["unknown"]

    async def test_a_metric_whose_value_is_none(self, session):
        results = await goals.evaluate_over(
            session, _goal(), {"mrr": {"value": None, "entities": 4}}
        )
        assert results[0]["met"] is None
        assert "no value" in results[0]["unknown"]

    async def test_a_metric_refused_for_mixed_currencies(self, session):
        results = await goals.evaluate_over(
            session,
            _goal(),
            {"mrr": {"value": None, "entities": 9, "mixed_currencies": ["eur", "usd"]}},
        )
        assert results[0]["met"] is None
        assert "currenc" in results[0]["unknown"]

    async def test_a_sum_over_nothing_is_not_a_measurement(self, session):
        results = await goals.evaluate_over(
            session,
            _goal(strategy="at_most"),
            {"mrr": {"value": 0, "entities": 0, "population_size": 0}},
        )
        assert results[0]["met"] is None
        assert "no entities" in results[0]["unknown"]
        assert "progress" not in results[0]

    async def test_a_metric_missing_from_the_catalog_entirely(self, session):
        results = await goals.evaluate_over(session, _goal(), {})
        assert results[0]["met"] is None
        assert "no such metric" in results[0]["unknown"]

    async def test_a_zero_match_over_a_real_population_is_a_measurement(self, session):
        results = await goals.evaluate_over(
            session,
            _goal(strategy="at_most"),
            {"mrr": {"value": 0, "entities": 0, "population_size": 10}},
        )
        assert results[0]["met"] is True

    async def test_a_real_zero_over_a_real_population_is_a_measurement(self, session):
        results = await goals.evaluate_over(
            session,
            _goal(strategy="at_most"),
            {"mrr": {"value": 0, "entities": 12}},
        )
        assert results[0]["met"] is True


class TestReadsNeverWrite:
    async def test_evaluating_goals_appends_no_snapshot(self, session):
        before = len((await session.execute(select(MetricSnapshot))).all())
        for _ in range(5):
            await goals.evaluate_over(
                session, _goal(), {"mrr": {"value": 500, "entities": 3}}
            )
        after = len((await session.execute(select(MetricSnapshot))).all())
        assert before == after == 0

    def test_the_module_calls_no_writer(self):
        called, attributes = set(), set()
        for node in ast.walk(ast.parse(inspect.getsource(goals))):
            if isinstance(node, ast.Call):
                called.add(getattr(node.func, "id", getattr(node.func, "attr", "")))
            if isinstance(node, ast.Attribute):
                attributes.add(node.attr)
        assert "record_snapshots" not in called
        assert not ({"add", "commit", "flush", "merge"} & attributes)


class TestTrendHistoryComesFromSnapshots:
    async def _snapshot(self, session, metric, value, at, **over):
        session.add(
            MetricSnapshot(
                metric=metric, value=value, entities=5, recorded_at=at, **over
            )
        )
        await session.flush()

    async def test_history_feeds_the_strategy_oldest_first(self, session):
        base = datetime(2026, 7, 1, tzinfo=UTC)
        for i, value in enumerate([10.0, 20.0, 30.0]):
            await self._snapshot(session, "mrr", value, base + timedelta(days=i))
        results = await goals.evaluate_over(
            session,
            _goal(strategy="increasing", target=25.0),
            {"mrr": {"value": 30.0, "entities": 5}},
        )
        assert results[0]["met"] is True

    async def test_no_history_reports_unknown_rather_than_failure(self, session):
        results = await goals.evaluate_over(
            session,
            _goal(strategy="increasing", target=10.0),
            {"mrr": {"value": 30.0, "entities": 5}},
        )
        assert results[0]["met"] is None

    async def test_null_valued_snapshots_are_not_history(self, session):
        base = datetime(2026, 7, 1, tzinfo=UTC)
        for i in range(3):
            await self._snapshot(session, "mrr", None, base + timedelta(days=i))
        results = await goals.evaluate_over(
            session,
            _goal(strategy="increasing", target=10.0),
            {"mrr": {"value": 30.0, "entities": 5}},
        )
        assert results[0]["met"] is None
        assert "not enough history" in results[0]["unknown"]

    async def test_a_series_that_spans_two_producers_is_not_a_trend(self, session):
        base = datetime(2026, 7, 1, tzinfo=UTC)
        await self._snapshot(
            session,
            "interest_share",
            10.0,
            base,
            inferred=True,
            vocabulary_sha="a" * 64,
            produced_by="claude-opus-5@v1",
        )
        await self._snapshot(
            session,
            "interest_share",
            90.0,
            base + timedelta(days=1),
            inferred=True,
            vocabulary_sha="b" * 64,
            produced_by="claude-opus-5@v2",
        )
        results = await goals.evaluate_over(
            session,
            _goal(metric="interest_share", strategy="increasing", target=50.0),
            {"interest_share": {"value": 90.0, "entities": 5, "inferred": True}},
        )
        assert results[0]["met"] is None
        assert "comparable" in results[0]["unknown"]


class TestAnEstimateSaysSo:
    async def test_a_goal_on_an_inferred_metric_is_marked_inferred(self, session):
        results = await goals.evaluate_over(
            session,
            _goal(metric="interest_share"),
            {
                "interest_share": {
                    "value": 500,
                    "entities": 3,
                    "inferred": True,
                    "reading": "sales_call",
                    "vocabulary_sha": "abc123def456",
                }
            },
        )
        assert results[0]["inferred"] is True
        assert results[0]["reading"] == "sales_call"

    async def test_a_goal_on_a_measured_metric_is_not(self, session):
        results = await goals.evaluate_over(
            session, _goal(), {"mrr": {"value": 500, "entities": 3}}
        )
        assert results[0].get("inferred") is not True


class TestTheHappyPath:
    async def test_a_met_goal_reports_its_number_and_its_progress(self, session):
        results = await goals.evaluate_over(
            session, _goal(target=100.0), {"mrr": {"value": 500, "entities": 3}}
        )
        assert results[0]["met"] is True
        assert results[0]["current"] == 500
        assert results[0]["target"] == 100.0
        assert results[0]["progress"] == 100.0

    async def test_one_defective_goal_does_not_abort_the_others(self, session):
        defs = {"good": _goal()["g"], "bad": {"metric": "mrr"}}
        results = await goals.evaluate_over(
            session, defs, {"mrr": {"value": 500, "entities": 3}}
        )
        assert {r["goal"] for r in results} == {"good", "bad"}
        good = next(r for r in results if r["goal"] == "good")
        bad = next(r for r in results if r["goal"] == "bad")
        assert good["met"] is True
        assert bad["met"] is None
        assert "missing one of" in bad["error"]

    async def test_the_shipped_goals_evaluate_against_a_live_estate(self, session):
        results = await goals.evaluate(session)
        assert results["goals"]
        assert all("met" in g for g in results["goals"])
        assert {"met", "missed", "unknown"} <= set(results)


class TestTheSilentStrategyBackstop:
    async def test_an_undecided_outcome_without_a_reason_gains_one(
        self, session, monkeypatch
    ):
        monkeypatch.setitem(
            strategies.STRATEGIES,
            "at_least",
            lambda current, target, history, params: strategies.Outcome(None, None, {}),
        )
        results = await goals.evaluate_over(
            session, _goal(), {"mrr": {"value": 500, "entities": 3}}
        )
        assert results[0]["met"] is None
        assert (
            results[0]["unknown"] == "the strategy could not decide from these inputs"
        )


def _checks():
    from app.engine import checks

    return checks


class TestTheBuildRefusesAMalformedGoal:
    def test_a_metric_that_does_not_exist(self):
        problems = _checks().check_goals(_goal(metric="revenue_per_unicorn"))
        assert any("revenue_per_unicorn" in p for p in problems)

    def test_a_strategy_that_is_not_registered(self):
        problems = _checks().check_goals(_goal(strategy="vibes"))
        assert any("vibes" in p for p in problems)

    def test_a_target_that_is_not_a_number(self):
        problems = _checks().check_goals(_goal(target="lots"))
        assert any("lots" in p for p in problems)

    def test_a_param_the_strategy_does_not_accept(self):
        problems = _checks().check_goals(
            _goal(strategy="at_least", params={"band_low": 0.9})
        )
        assert any("band_low" in p for p in problems)

    def test_a_missing_field(self):
        problems = _checks().check_goals({"g": {"metric": "mrr"}})
        assert problems != []

    def test_the_committed_goals_pass(self):
        assert _checks().check_goals(goals.definitions()) == []

    def test_the_build_runs_them(self):
        assert _checks().run() == []


class TestAGoalParameterIsCheckedForItsValue:
    def test_a_non_numeric_param_is_a_build_problem(self):
        problems = _checks().check_goals(
            {
                "g": {
                    "metric": "mrr",
                    "target": 1,
                    "strategy": "threshold_band",
                    "label": "L",
                    "params": {"band_low": "wide"},
                }
            },
            metric_defs={"mrr": {}},
        )
        assert any("band_low" in p for p in problems)

    def test_a_numeric_param_still_passes(self):
        assert (
            _checks().check_goals(
                {
                    "g": {
                        "metric": "mrr",
                        "target": 1,
                        "strategy": "threshold_band",
                        "label": "L",
                        "params": {"band_low": 0.8},
                    }
                },
                metric_defs={"mrr": {}},
            )
            == []
        )

    def test_the_shipped_goals_still_pass(self):
        assert _checks().check_goals(goals.definitions()) == []
