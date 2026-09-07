import inspect
import uuid
from datetime import UTC, date, datetime

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


NOW = datetime(2026, 9, 7, 12, tzinfo=UTC)


async def evaluate_at(session, spec, now=NOW, name="m"):
    return (await m.evaluate_definitions(session, {name: spec}, now=now))[name]


class TestBreakdowns:
    async def test_a_breakdown_over_an_own_attr_buckets_by_value(
        self, session, canonical
    ):
        await canonical("company", {"domain": "a.io", "industry": "Finance"})
        await canonical("company", {"domain": "b.io", "industry": "Software"})
        await canonical("company", {"domain": "c.io", "industry": "Software"})
        result = await evaluate_at(
            session,
            {
                "entity": "company",
                "expression": "COUNT(entity)",
                "group_by": "industry",
            },
        )
        assert result["value"] == 3
        assert result["breakdown"] == {"Finance": 1, "Software": 2}
        assert result["group_by"] == "industry"

    async def test_a_breakdown_walks_a_declared_edge(self, session, canonical, link):
        finance = await canonical("company", {"domain": "a.io", "industry": "Finance"})
        software = await canonical(
            "company", {"domain": "b.io", "industry": "Software"}
        )
        for owner in (finance, software, software):
            sub = await canonical("subscription", {"mrr": 10, "status": "active"})
            await link(sub, "belongs_to", owner)
        result = await evaluate_at(
            session,
            {
                "entity": "subscription",
                "expression": "COUNT(entity)",
                "group_by": "company.industry",
            },
        )
        assert result["breakdown"] == {"Finance": 1, "Software": 2}
        assert result["group_by_via"] == "belongs_to"

    async def test_an_entity_off_the_edge_is_counted_not_hidden(
        self, session, canonical, link
    ):
        finance = await canonical("company", {"domain": "a.io", "industry": "Finance"})
        linked = await canonical("subscription", {"mrr": 10, "status": "active"})
        await link(linked, "belongs_to", finance)
        await canonical("subscription", {"mrr": 10, "status": "active"})
        result = await evaluate_at(
            session,
            {
                "entity": "subscription",
                "expression": "COUNT(entity)",
                "group_by": "company.industry",
            },
        )
        assert result["breakdown"] == {"Finance": 1}
        assert result["ungrouped_entities"] == 1

    async def test_buckets_come_only_from_what_the_metric_measured(
        self, session, canonical
    ):
        await canonical("subscription", {"status": "active", "currency": "usd"})
        await canonical("subscription", {"status": "canceled", "currency": "eur"})
        result = await evaluate_at(
            session,
            {
                "entity": "subscription",
                "expression": "COUNT(entity)",
                "filter": {"status": "active"},
                "group_by": "currency",
            },
        )
        assert result["breakdown"] == {"usd": 1}

    async def test_a_breakdown_over_an_undeclared_edge_is_one_metrics_error(
        self, session, canonical
    ):
        await canonical("subscription", {"mrr": 10})
        result = await evaluate_at(
            session,
            {
                "entity": "subscription",
                "expression": "COUNT(entity)",
                "group_by": "person.title",
            },
        )
        assert "walks no declared edge" in result["error"]

    async def test_a_bucket_that_spans_currencies_is_unknown(self, session, canonical):
        await canonical(
            "subscription", {"mrr": 100, "currency": "usd", "status": "active"}
        )
        await canonical(
            "subscription", {"mrr": 100, "currency": "eur", "status": "active"}
        )
        await canonical(
            "subscription", {"mrr": 30, "currency": "usd", "status": "trial"}
        )
        result = await evaluate_at(
            session,
            {"entity": "subscription", "expression": "SUM(mrr)", "group_by": "status"},
        )
        assert result["breakdown"] == {"active": None, "trial": 30.0}


class TestGrainBuckets:
    async def _seed(self, canonical):
        for started in ("2025-11-20", "2026-03-05", "2026-07-02"):
            await canonical(
                "subscription", {"mrr": 10, "started_at": f"{started}T00:00:00Z"}
            )

    @pytest.mark.parametrize(
        ("grain", "keys"),
        [
            ("day", ["2025-11-20", "2026-03-05", "2026-07-02"]),
            ("week", ["2025-W47", "2026-W10", "2026-W27"]),
            ("month", ["2025-11", "2026-03", "2026-07"]),
            ("quarter", ["2025-Q4", "2026-Q1", "2026-Q3"]),
        ],
    )
    async def test_a_date_breakdown_buckets_at_the_declared_grain(
        self, session, canonical, grain, keys
    ):
        await self._seed(canonical)
        result = await evaluate_at(
            session,
            {
                "entity": "subscription",
                "expression": "COUNT(entity)",
                "group_by": "started_at",
                "grain": grain,
            },
        )
        assert list(result["breakdown"]) == keys
        assert result["grain"] == grain

    async def test_a_year_grain_collects_the_dates_that_share_a_year(
        self, session, canonical
    ):
        await self._seed(canonical)
        result = await evaluate_at(
            session,
            {
                "entity": "subscription",
                "expression": "COUNT(entity)",
                "group_by": "started_at",
                "grain": "year",
            },
        )
        assert result["breakdown"] == {"2025": 1, "2026": 2}

    async def test_a_date_that_will_not_parse_is_counted_and_left_ungrouped(
        self, session, canonical
    ):
        await canonical(
            "subscription", {"mrr": 10, "started_at": "2026-03-05T00:00:00Z"}
        )
        await canonical("subscription", {"mrr": 10, "started_at": "whenever"})
        result = await evaluate_at(
            session,
            {
                "entity": "subscription",
                "expression": "COUNT(entity)",
                "group_by": "started_at",
                "grain": "month",
            },
        )
        assert result["breakdown"] == {"2026-03": 1}
        assert result["group_bad_values"] == 1


class TestWindowBounds:
    def test_a_trailing_window_ends_today_and_spans_its_days(self):
        low, high = m.window_bounds(30, "trailing", NOW)
        assert high == "2026-09-07"
        assert (
            date.fromisoformat(high).toordinal()
            - date.fromisoformat(low).toordinal()
            + 1
            == 30
        )

    def test_a_forward_window_starts_today(self):
        low, high = m.window_bounds(30, "forward", NOW)
        assert low == "2026-09-07"
        assert high == "2026-10-06"

    def test_a_one_day_window_is_a_single_date(self):
        assert m.window_bounds(1, "trailing", NOW) == ("2026-09-07", "2026-09-07")
        assert m.window_bounds(1, "forward", NOW) == ("2026-09-07", "2026-09-07")


class TestWindowedMetrics:
    def _windowed(self, **extra):
        return {
            "entity": "subscription",
            "expression": "COUNT(entity)",
            "window_days": 30,
            "window_attr": "started_at",
            **extra,
        }

    async def test_a_trailing_window_has_a_ceiling(self, session, canonical):
        await canonical("subscription", {"started_at": "2026-08-20T00:00:00Z"})
        await canonical("subscription", {"started_at": "2026-12-01T00:00:00Z"})
        await canonical("subscription", {"started_at": "2025-01-01T00:00:00Z"})
        result = await evaluate_at(session, self._windowed())
        assert result["value"] == 1

    async def test_a_forward_window_counts_the_future_not_the_past(
        self, session, canonical
    ):
        await canonical("subscription", {"started_at": "2026-09-20T00:00:00Z"})
        await canonical("subscription", {"started_at": "2026-08-20T00:00:00Z"})
        result = await evaluate_at(session, self._windowed(window_direction="forward"))
        assert result["value"] == 1

    async def test_the_receipt_names_the_window_it_measured(self, session, canonical):
        await canonical("subscription", {"started_at": "2026-08-20T00:00:00Z"})
        result = await evaluate_at(session, self._windowed())
        assert result["window_days"] == 30
        assert result["window_direction"] == "trailing"
        assert result["window_from"] == "2026-08-09"
        assert result["window_to"] == "2026-09-07"

    async def test_a_value_that_is_not_a_date_is_counted_and_excluded(
        self, session, canonical
    ):
        await canonical("subscription", {"started_at": "2026-08-20T00:00:00Z"})
        await canonical("subscription", {"started_at": "soon"})
        result = await evaluate_at(session, self._windowed())
        assert result["value"] == 1
        assert result["window_bad_values"] == 1

    async def test_an_entity_with_no_row_for_the_attr_drops_out(
        self, session, canonical
    ):
        await canonical("subscription", {"started_at": "2026-08-20T00:00:00Z"})
        await canonical("subscription", {"mrr": 10})
        result = await evaluate_at(session, self._windowed())
        assert result["value"] == 1
        assert "window_bad_values" not in result

    async def test_the_window_narrows_before_the_filter_does(self, session, canonical):
        await canonical(
            "subscription", {"started_at": "2026-08-20T00:00:00Z", "status": "active"}
        )
        await canonical(
            "subscription", {"started_at": "2026-08-21T00:00:00Z", "status": "canceled"}
        )
        await canonical(
            "subscription", {"started_at": "2025-01-01T00:00:00Z", "status": "active"}
        )
        result = await evaluate_at(session, self._windowed(filter={"status": "active"}))
        assert result["value"] == 1
        assert result["population_size"] == 3

    async def test_a_clock_free_call_reads_the_wall_clock(self, session, canonical):
        today = datetime.now(UTC).date().isoformat()
        await canonical("subscription", {"started_at": f"{today}T00:00:00Z"})
        await canonical("subscription", {"started_at": "2020-01-01T00:00:00Z"})
        values = await m.evaluate_definitions(session, {"m": self._windowed()})
        assert values["m"]["value"] == 1
