import pytest
from test_conversation_loop import Reply, ScriptedModel, Text, ToolUse

from app.config import settings
from app.conversation import agent

SLICE_FIELDS = {
    "metric": "string",
    "group_by": "string",
    "grain": "string",
    "window_days": "integer",
    "window_attr": "string",
    "window_direction": "string",
    "filter_attr": "string",
    "filter_value": "string",
}


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setattr(settings, "CONVERSATION_ENABLED", True)


async def subscriptions_by_industry(canonical, link) -> dict:
    acme = await canonical("company", {"name": "Acme", "industry": "saas"})
    globex = await canonical("company", {"name": "Globex", "industry": "retail"})
    first = await canonical(
        "subscription", {"mrr": 100, "status": "active", "started_at": "2026-01-15"}
    )
    second = await canonical(
        "subscription", {"mrr": 50, "status": "active", "started_at": "2026-02-20"}
    )
    third = await canonical(
        "subscription", {"mrr": 25, "status": "active", "started_at": "2026-02-28"}
    )
    await link(first, "belongs_to", acme)
    await link(second, "belongs_to", globex)
    await link(third, "belongs_to", globex)
    return {"acme": acme, "globex": globex}


class TestAnUnknownMetricIsNamedNotGuessed:
    async def test_it_says_which_metrics_exist(self, session):
        result = await agent.slice_metric(session, metric="x")
        assert result["error"] == "no metric named 'x'"
        assert "mrr" in result["available"]


class TestABreakdownSplitsADeclaredMetric:
    async def test_a_hop_over_a_declared_edge_names_the_edge(
        self, session, canonical, link
    ):
        await subscriptions_by_industry(canonical, link)
        result = await agent.slice_metric(
            session, metric="mrr", group_by="company.industry"
        )
        assert result["metric"] == "mrr"
        assert result["value"] == 175.0
        assert result["breakdown"] == {"retail": 75.0, "saas": 100.0}
        assert result["group_by_via"] == "belongs_to"

    async def test_an_own_attr_splits_the_count(self, session, canonical):
        await canonical("deal", {"name": "A", "status": "closed_won"})
        await canonical("deal", {"name": "B", "status": "open"})
        await canonical("deal", {"name": "C", "status": "open"})
        result = await agent.slice_metric(
            session, metric="deal_count", group_by="status"
        )
        assert result["value"] == 3
        assert result["breakdown"] == {"closed_won": 1, "open": 2}

    async def test_a_date_dimension_buckets_at_the_grain(
        self, session, canonical, link
    ):
        await subscriptions_by_industry(canonical, link)
        result = await agent.slice_metric(
            session, metric="subscription_count", group_by="started_at", grain="month"
        )
        assert result["grain"] == "month"
        assert result["breakdown"] == {"2026-01": 1, "2026-02": 2}


class TestAWindowNarrowsByDate:
    async def test_a_trailing_window_reports_the_bounds_it_used(self, session):
        result = await agent.slice_metric(
            session,
            metric="subscription_count",
            window_days=30,
            window_attr="started_at",
        )
        assert result["window_days"] == 30
        assert result["window_direction"] == "trailing"
        assert result["window_from"] < result["window_to"]

    async def test_a_forward_window_is_honoured(self, session):
        result = await agent.slice_metric(
            session,
            metric="deal_count",
            window_days=30,
            window_attr="closed_at",
            window_direction="forward",
        )
        assert result["window_direction"] == "forward"
        assert result["window_from"] < result["window_to"]

    async def test_a_window_that_is_not_a_number_is_an_error_not_a_crash(self, session):
        result = await agent.slice_metric(
            session,
            metric="subscription_count",
            window_days="thirty",
            window_attr="started_at",
        )
        assert "error" in result
        assert "window_days" in result["error"]


class TestOneEqualityFilter:
    async def test_a_filter_narrows_the_population_and_says_so(
        self, session, canonical
    ):
        await canonical("subscription", {"mrr": 100, "currency": "usd"})
        await canonical("subscription", {"mrr": 50, "currency": "usd"})
        await canonical("subscription", {"mrr": 900, "currency": "eur"})
        result = await agent.slice_metric(
            session, metric="contracted_mrr", filter_attr="currency", filter_value="usd"
        )
        assert result["applied_filter"] == {"currency": "usd"}
        assert result["value"] == 150.0
        assert result["entities"] == 2

    async def test_a_filter_over_an_attr_the_metric_already_fixes_is_refused(
        self, session
    ):
        result = await agent.slice_metric(
            session, metric="mrr", filter_attr="status", filter_value="canceled"
        )
        assert "already fixes status=active" in result["error"]

    async def test_an_attr_without_a_value_is_refused(self, session):
        result = await agent.slice_metric(
            session, metric="contracted_mrr", filter_attr="currency"
        )
        assert "go together" in result["error"]

    async def test_a_value_without_an_attr_is_refused(self, session):
        result = await agent.slice_metric(
            session, metric="contracted_mrr", filter_value="usd"
        )
        assert "go together" in result["error"]

    async def test_an_attr_the_entity_never_declares_is_refused(self, session):
        result = await agent.slice_metric(
            session, metric="contracted_mrr", filter_attr="foo", filter_value="x"
        )
        assert "'foo' is not an attr of subscription" in result["error"]


class TestADimensionIsCheckedBeforeItIsMeasured:
    async def test_a_missing_attr_on_the_far_side_is_named(self, session):
        result = await agent.slice_metric(session, metric="mrr", group_by="company.foo")
        assert "'foo' is not an attr of company" in result["error"]

    async def test_a_hop_over_no_declared_edge_is_refused(self, session):
        result = await agent.slice_metric(
            session, metric="mrr", group_by="person.title"
        )
        assert "walks no declared edge" in result["error"]

    async def test_a_grain_over_a_string_is_refused(self, session):
        result = await agent.slice_metric(
            session, metric="mrr", group_by="status", grain="month"
        )
        assert "not a date" in result["error"]

    async def test_two_hops_are_refused(self, session):
        result = await agent.slice_metric(session, metric="mrr", group_by="a.b.c")
        assert "error" in result


class TestDiscoveryComesBackWithTheScalar:
    async def test_a_bare_call_lists_what_the_metric_can_be_split_by(
        self, session, canonical, link
    ):
        await subscriptions_by_industry(canonical, link)
        result = await agent.slice_metric(session, metric="mrr")
        assert result["value"] == 175.0
        assert "breakdown" not in result
        dimensions = {entry["path"]: entry for entry in result["dimensions"]}
        assert dimensions["status"]["type"] == "string"
        assert dimensions["started_at"]["type"] == "date"
        assert dimensions["company.industry"]["via"] == "belongs_to"
        assert "mrr" not in dimensions
        assert result["window_attrs"] == ["started_at"]

    async def test_a_declared_meaning_rides_along_with_the_dimension(self, session):
        result = await agent.slice_metric(session, metric="mrr")
        [entry] = [d for d in result["dimensions"] if d["path"] == "company.industry"]
        assert "description" in entry

    async def test_a_sliced_call_does_not_re_list_the_dimensions(self, session):
        result = await agent.slice_metric(session, metric="mrr", group_by="status")
        assert "dimensions" not in result
        assert "window_attrs" not in result

    async def test_an_inferred_metric_offers_only_its_single_label_fields(
        self, session
    ):
        result = await agent.slice_metric(session, metric="strong_interest_share")
        paths = {entry["path"] for entry in result["dimensions"]}
        assert {"interest", "timing"} <= paths
        assert "pain_points" not in paths


class TestAnInferredSliceStaysMarked:
    async def test_a_sliced_inferred_metric_keeps_its_flag_and_its_reading(
        self, session
    ):
        result = await agent.slice_metric(
            session, metric="strong_interest_share", group_by="interest"
        )
        assert result["inferred"] is True
        assert result["reading"] == "sales_call"


class TestTheToolSpec:
    def test_the_tool_declares_exactly_the_eight_slicing_fields(self):
        [tool] = [t for t in agent.TOOLS if t["name"] == "slice_metric"]
        properties = tool["input_schema"]["properties"]
        assert set(properties) == set(SLICE_FIELDS)
        assert {n: s["type"] for n, s in properties.items()} == SLICE_FIELDS
        assert tool["input_schema"]["required"] == ["metric"]


class TestTheModelCanReachIt:
    async def test_a_slice_call_is_run_and_kept_as_a_receipt(
        self, session, enabled, canonical, link
    ):
        await subscriptions_by_industry(canonical, link)
        arguments = {"metric": "mrr", "group_by": "company.industry"}
        model = ScriptedModel(
            Reply([ToolUse("slice_metric", arguments)]),
            Reply([Text("Saas is the larger of the two.")]),
        )
        result = await agent.run_turn(
            session, "mrr by industry?", history=[], model_client=model
        )
        assert result["receipts"] == [{"tool": "slice_metric", "input": arguments}]
        [sent] = model.sent[1]["messages"][-1]["content"]
        assert "breakdown" in sent["content"]
