import inspect
import uuid

import pytest
from sqlalchemy import select, text

from app.engine import metrics as m
from app.models import FactCurrent


async def evaluate(session, spec, name="m"):
    return (await m.evaluate_definitions(session, {name: spec}))[name]


class TestAggregates:
    async def test_sum(self, session, canonical):
        await canonical("subscription", {"mrr": 100, "status": "active"})
        await canonical("subscription", {"mrr": 50, "status": "active"})
        result = await evaluate(
            session, {"entity": "subscription", "expression": "SUM(mrr)"}
        )
        assert result["value"] == 150.0

    async def test_sum_of_nothing_is_zero(self, session):
        result = await evaluate(
            session, {"entity": "subscription", "expression": "SUM(mrr)"}
        )
        assert result["value"] == 0

    async def test_avg_of_nothing_is_unknown_not_zero(self, session):
        result = await evaluate(
            session, {"entity": "subscription", "expression": "AVG(mrr)"}
        )
        assert result["value"] is None

    async def test_count_entity_counts_canonical_things(self, session, canonical):
        await canonical("company", {"domain": "a.io"})
        await canonical("company", {"domain": "b.io"})
        result = await evaluate(
            session, {"entity": "company", "expression": "COUNT(entity)"}
        )
        assert result["value"] == 2

    async def test_count_of_an_attr_counts_rows_that_have_it(self, session, canonical):
        await canonical("company", {"domain": "a.io", "industry": "X"})
        await canonical("company", {"domain": "b.io"})
        result = await evaluate(
            session, {"entity": "company", "expression": "COUNT(industry)"}
        )
        assert result["value"] == 1
        assert result["entities"] == 2
        assert result["entities_without_attr"] == 1

    async def test_an_aggregate_says_how_many_entities_actually_had_a_value(
        self, session, canonical
    ):
        await canonical("product", {"price": 80})
        await canonical("product", {"price": 100})
        await canonical("product", {"sku": "C"})
        await canonical("product", {"sku": "D"})
        result = await evaluate(
            session, {"entity": "product", "expression": "AVG(price)"}
        )
        assert result["value"] == 90.0
        assert result["entities"] == 4
        assert result["values_aggregated"] == 2
        assert result["entities_without_attr"] == 2

    async def test_full_coverage_reports_no_missing_entities(self, session, canonical):
        await canonical("product", {"price": 80})
        await canonical("product", {"price": 100})
        result = await evaluate(
            session, {"entity": "product", "expression": "SUM(price)"}
        )
        assert result["value"] == 180.0
        assert "entities_without_attr" not in result

    async def test_a_missing_entity_type_reports_no_data_not_zero(self, session):
        result = await evaluate(
            session, {"entity": "campaign", "expression": "COUNT(entity)"}
        )
        assert result["value"] == 0
        assert "no data" in result["note"]


class TestFilters:
    async def test_equality_is_case_insensitive(self, session, canonical):
        await canonical("subscription", {"mrr": 10, "status": "Active"})
        result = await evaluate(
            session,
            {
                "entity": "subscription",
                "expression": "SUM(mrr)",
                "filter": {"status": "active"},
            },
        )
        assert result["value"] == 10.0

    async def test_a_percent_in_a_value_stays_a_literal(self, session, canonical):
        await canonical("subscription", {"mrr": 10, "status": "50%_off"})
        await canonical("subscription", {"mrr": 20, "status": "anything"})
        result = await evaluate(
            session,
            {
                "entity": "subscription",
                "expression": "SUM(mrr)",
                "filter": {"status": "%_off"},
            },
        )
        assert result["value"] == 0


class TestZeroMatchesOverARealPopulationIsAMeasurement:
    async def test_a_filtered_count_reports_the_population_it_filtered(
        self, session, canonical
    ):
        await canonical("subscription", {"mrr": 10, "status": "active"})
        await canonical("subscription", {"mrr": 10, "status": "active"})
        result = await evaluate(
            session,
            {
                "entity": "subscription",
                "expression": "COUNT(entity)",
                "filter": {"status": "canceled"},
            },
        )
        assert result["value"] == 0
        assert result["population_size"] == 2

    async def test_an_empty_estate_reports_an_empty_population(self, session):
        result = await evaluate(
            session,
            {
                "entity": "subscription",
                "expression": "COUNT(entity)",
                "filter": {"status": "canceled"},
            },
        )
        assert result["population_size"] == 0


class TestCurrencyGuard:
    async def test_mixed_currencies_refuse_to_aggregate(self, session, canonical):
        await canonical("subscription", {"mrr": 100, "currency": "usd"})
        await canonical("subscription", {"mrr": 100, "currency": "eur"})
        result = await evaluate(
            session, {"entity": "subscription", "expression": "SUM(mrr)"}
        )
        assert result["value"] is None
        assert result["mixed_currencies"] == ["eur", "usd"]
        assert "refusing to aggregate" in result["note"]

    async def test_one_currency_aggregates_normally(self, session, canonical):
        await canonical("subscription", {"mrr": 100, "currency": "usd"})
        await canonical("subscription", {"mrr": 100, "currency": "usd"})
        result = await evaluate(
            session, {"entity": "subscription", "expression": "SUM(mrr)"}
        )
        assert result["value"] == 200.0

    async def test_the_guard_only_applies_to_money_labels(self, session, canonical):
        await canonical("company", {"employee_count": 1, "currency": "usd"})
        await canonical("company", {"employee_count": 2, "currency": "eur"})
        result = await evaluate(
            session, {"entity": "company", "expression": "SUM(employee_count)"}
        )
        assert result["value"] == 3.0


class TestErrorIsolation:
    async def test_one_broken_metric_does_not_take_the_others_down(
        self, session, canonical
    ):
        await canonical("company", {"domain": "a.io"})
        values = await m.evaluate_definitions(
            session,
            {
                "good": {"entity": "company", "expression": "COUNT(entity)"},
                "bad": {"entity": "company", "expression": "MEDIAN(domain)"},
            },
        )
        assert values["good"]["value"] == 1
        assert "error" in values["bad"]

    async def test_a_failure_that_is_not_a_spec_error_is_isolated_too(
        self, session, canonical, monkeypatch
    ):
        await canonical("company", {"domain": "a.io"})
        real = m._aggregate

        async def explode(session_, ids, agg, operand, *args, **kwargs):
            if operand == "domain":
                raise RuntimeError("driver went away")
            return await real(session_, ids, agg, operand, *args, **kwargs)

        monkeypatch.setattr(m, "_aggregate", explode)
        values = await m.evaluate_definitions(
            session,
            {
                "good": {"entity": "company", "expression": "COUNT(entity)"},
                "bad": {"entity": "company", "expression": "COUNT(domain)"},
            },
        )
        assert values["good"]["value"] == 1
        assert "RuntimeError" in values["bad"]["error"]


class TestOneFailedMetricDoesNotPoisonTheRest:
    async def test_metrics_after_a_database_failure_still_evaluate(
        self, session, canonical, monkeypatch
    ):
        await canonical("company", {"domain": "a.io"})
        await session.commit()
        real = m._aggregate
        calls = {"n": 0}

        async def explode_once(session_, ids, agg, operand, *args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                await session_.execute(text("SELECT * FROM no_such_table"))
            return await real(session_, ids, agg, operand, *args, **kwargs)

        monkeypatch.setattr(m, "_aggregate", explode_once)
        values = await m.evaluate_definitions(
            session,
            {
                "first": {"entity": "company", "expression": "COUNT(domain)"},
                "second": {"entity": "company", "expression": "COUNT(domain)"},
                "third": {"entity": "company", "expression": "COUNT(domain)"},
            },
        )

        assert "error" in values["first"]
        assert values["second"]["value"] == 1, values["second"]
        assert values["third"]["value"] == 1, values["third"]

    async def test_a_rollback_that_itself_fails_does_not_escape(
        self, session, canonical, monkeypatch
    ):
        await canonical("company", {"domain": "a.io"})
        await session.commit()

        async def explode(session_, ids, agg, operand, *args, **kwargs):
            raise RuntimeError("driver went away")

        async def rollback_also_fails():
            raise RuntimeError("connection is gone, nothing to roll back")

        monkeypatch.setattr(m, "_aggregate", explode)
        monkeypatch.setattr(session, "rollback", rollback_also_fails)

        values = await m.evaluate_definitions(
            session,
            {
                "first": {"entity": "company", "expression": "COUNT(domain)"},
                "second": {"entity": "company", "expression": "COUNT(domain)"},
            },
        )

        assert set(values) == {"first", "second"}
        assert "driver went away" in values["first"]["error"]
        assert "nothing to roll back" not in values["first"]["error"]


class TestTheBindParameterCeiling:
    async def test_a_set_past_the_wire_limit_does_not_raise(self, session):
        rows = await m._in_chunks(
            session,
            {uuid.uuid4() for _ in range(40_000)},
            lambda chunk: select(FactCurrent.canonical_id).where(
                FactCurrent.canonical_id.in_(chunk)
            ),
        )
        assert rows == []

    @pytest.mark.parametrize("chunk_size", [1, 2, 3, 7])
    async def test_chunking_returns_exactly_what_one_statement_would(
        self, session, canonical, monkeypatch, chunk_size
    ):
        for index in range(9):
            await canonical(
                "subscription",
                {
                    "mrr": 10 * index,
                    "status": "active" if index % 2 else "churned",
                },
            )

        whole = await evaluate(
            session,
            {
                "entity": "subscription",
                "expression": "SUM(mrr)",
                "filter": {"status": "active"},
            },
        )
        monkeypatch.setattr(m, "ID_CHUNK", chunk_size)
        split = await evaluate(
            session,
            {
                "entity": "subscription",
                "expression": "SUM(mrr)",
                "filter": {"status": "active"},
            },
        )
        assert split["value"] == whole["value"] == 160.0
        assert split["entities"] == whole["entities"] == 4

    def test_no_query_in_this_module_is_built_from_an_unbounded_set(self):
        source = inspect.getsource(m)
        assert ".in_(ids)" not in source

    async def test_snapshots_skip_broken_metrics(self, session, canonical):
        await canonical("company", {"domain": "a.io"})
        written = await m.record_snapshots(session)
        assert written > 0
