import pytest

from app.engine import mappings, metrics, transforms


def parse(spec):
    return metrics.parse_spec(spec)


class TestExpressions:
    @pytest.mark.parametrize(
        "expression", ["SUM(mrr)", "AVG(mrr)", "COUNT(entity)", "COUNT(industry)"]
    )
    def test_accepted(self, expression):
        assert parse({"entity": "subscription", "expression": expression})

    @pytest.mark.parametrize(
        "expression",
        [
            "MEDIAN(mrr)",
            "SUM(mrr",
            "SUM()",
            "sum(mrr)",
            "SUM(mrr) % SUM(x)",
            "SUM(mrr); DROP TABLE entity",
            "SUM(a.b)",
            "",
            "COUNT_DISTINCT(email)",
        ],
    )
    def test_rejected(self, expression):
        with pytest.raises(metrics.MetricSpecError):
            parse({"entity": "subscription", "expression": expression})

    def test_a_missing_entity_is_an_error(self):
        with pytest.raises(metrics.MetricSpecError, match="entity"):
            parse({"expression": "SUM(mrr)"})

    def test_a_non_mapping_spec_is_an_error(self):
        with pytest.raises(metrics.MetricSpecError):
            parse("SUM(mrr)")

    def test_a_scalar_filter_validates(self):
        assert parse(
            {
                "entity": "subscription",
                "expression": "SUM(mrr)",
                "filter": {"status": "active"},
            }
        )

    def test_a_dotted_filter_attr_is_rejected(self):
        with pytest.raises(metrics.MetricSpecError):
            parse(
                {
                    "entity": "subscription",
                    "expression": "SUM(mrr)",
                    "filter": {"company.industry": "Software"},
                }
            )


class TestRatioGrammar:
    @pytest.mark.parametrize("count", [1, 3])
    def test_a_terms_form_needs_exactly_two_terms(self, count):
        with pytest.raises(metrics.MetricSpecError, match="exactly two"):
            parse(
                {
                    "entity": "subscription",
                    "op": "/",
                    "terms": [
                        {"expression": "COUNT(entity)", "filter": {"n": str(i)}}
                        for i in range(count)
                    ],
                }
            )

    def test_an_unknown_operator_is_an_error_not_a_silent_divide(self):
        with pytest.raises(metrics.MetricSpecError) as err:
            parse(
                {
                    "entity": "subscription",
                    "op": "%",
                    "terms": [
                        {"expression": "SUM(mrr)"},
                        {"expression": "COUNT(entity)"},
                    ],
                }
            )
        assert "'%'" in str(err.value)
        assert "'/'" in str(err.value)

    def test_a_ratio_of_a_thing_to_itself_is_rejected(self):
        with pytest.raises(metrics.MetricSpecError, match="degenerate"):
            parse(
                {
                    "entity": "subscription",
                    "op": "/",
                    "terms": [
                        {"expression": "COUNT(entity)"},
                        {"expression": "COUNT(entity)"},
                    ],
                }
            )

    def test_differing_filters_make_the_same_expression_a_real_ratio(self):
        parsed = parse(
            {
                "entity": "subscription",
                "op": "/",
                "terms": [
                    {"expression": "COUNT(entity)", "filter": {"status": "canceled"}},
                    {"expression": "COUNT(entity)", "filter": {}},
                ],
            }
        )
        assert parsed["terms"][0]["filter"] == {"status": "canceled"}
        assert parsed["terms"][1]["filter"] == {}

    def test_division_by_zero_is_unknown_never_a_number(self):
        assert metrics._combine(10, 0) is None

    def test_an_unknown_operand_propagates_as_unknown(self):
        assert metrics._combine(None, 5) is None
        assert metrics._combine(10, 4) == 2.5


class TestTermSources:
    def test_a_source_outside_the_layers_is_refused(self):
        with pytest.raises(metrics.MetricSpecError) as err:
            parse({"entity": "deal", "expression": "SUM(amount)", "source": "raw"})
        assert "canonical" in str(err.value)
        assert "enriched" in str(err.value)

    def test_a_term_level_source_is_held_to_the_same_layers(self):
        with pytest.raises(metrics.MetricSpecError) as err:
            parse(
                {
                    "entity": "subscription",
                    "op": "/",
                    "terms": [
                        {"expression": "SUM(mrr)", "source": "raw"},
                        {"expression": "COUNT(entity)"},
                    ],
                }
            )
        assert "'raw'" in str(err.value)


class TestShippedCatalog:
    def test_every_definition_parses(self):
        defs = metrics.load_definitions()
        assert defs
        for spec in defs.values():
            metrics.parse_spec(spec)

    def test_money_labels_are_discovered_from_the_transforms(self):
        assert transforms.money_labels() == {
            "amount",
            "mrr",
            "price",
            "spend",
            "budget",
        }


class TestProvenance:
    def test_a_metric_names_the_raw_fields_that_feed_it(self):
        lineage = metrics.provenance(metrics.load_definitions(), mappings.load())
        assert lineage["mrr"]["raw_fields"] == [
            "stripe.subscriptions._amount_monthly",
            "stripe.subscriptions.status",
        ]

    def test_every_shipped_metric_has_lineage(self):
        lineage = metrics.provenance(metrics.load_definitions(), mappings.load())
        assert set(lineage) == set(metrics.load_definitions())

    def test_count_only_metrics_have_no_raw_fields(self):
        lineage = metrics.provenance(metrics.load_definitions(), mappings.load())
        for name in ("subscription_count", "deal_count", "company_count"):
            assert lineage[name]["raw_fields"] == []

    def test_a_broken_definition_is_skipped_not_fatal(self):
        lineage = metrics.provenance(
            {"bad": {"entity": "deal", "expression": "MEDIAN(x)"}}, mappings.load()
        )
        assert lineage == {}


INFERRED = {
    "entity": "meeting",
    "source": "enriched",
    "inferred": True,
    "reading": "sales_call",
    "expression": "COUNT(entity)",
}


def counted(**extra):
    return {"entity": "subscription", "expression": "COUNT(entity)", **extra}


class TestClosedKeySets:
    def test_the_spec_key_set_names_every_key_a_metric_may_carry(self):
        assert set(metrics.SPEC_KEYS) == {
            "label",
            "description",
            "synonyms",
            "entity",
            "expression",
            "filter",
            "source",
            "inferred",
            "reading",
            "population",
            "op",
            "terms",
            "group_by",
            "grain",
            "window_days",
            "window_attr",
            "window_direction",
        }

    def test_the_term_key_set_names_every_key_a_term_may_carry(self):
        assert set(metrics.TERM_KEYS) == {"expression", "filter", "source", "entity"}

    def test_the_grains_are_the_five_calendar_buckets(self):
        assert metrics.GRAINS == ("day", "week", "month", "quarter", "year")

    def test_an_unknown_top_level_key_is_refused(self):
        with pytest.raises(metrics.MetricSpecError) as err:
            parse(counted(groupby="status"))
        assert "unknown key" in str(err.value)
        assert "groupby" in str(err.value)

    def test_an_unknown_term_key_is_refused(self):
        with pytest.raises(metrics.MetricSpecError) as err:
            parse(
                {
                    "entity": "subscription",
                    "op": "/",
                    "terms": [
                        {"expression": "SUM(mrr)", "grouping": "status"},
                        {"expression": "COUNT(entity)"},
                    ],
                }
            )
        assert "unknown key" in str(err.value)
        assert "grouping" in str(err.value)


class TestGroupByGrammar:
    def test_a_plain_attr_is_accepted(self):
        assert parse(counted(group_by="status"))["group_by"] == "status"

    def test_a_single_hop_path_is_accepted(self):
        assert parse(counted(group_by="company.industry"))["group_by"] == (
            "company.industry"
        )

    def test_a_second_hop_is_refused(self):
        with pytest.raises(metrics.MetricSpecError) as err:
            parse(counted(group_by="company.owner.name"))
        assert "entity.attr" in str(err.value)

    def test_a_breakdown_of_a_cross_entity_ratio_is_refused(self):
        with pytest.raises(metrics.MetricSpecError) as err:
            parse(
                {
                    "entity": "deal",
                    "op": "/",
                    "group_by": "status",
                    "terms": [
                        {"entity": "deal", "expression": "COUNT(entity)"},
                        {"entity": "company", "expression": "COUNT(entity)"},
                    ],
                }
            )
        assert "cross-entity ratio" in str(err.value)

    def test_a_metric_with_no_breakdown_parses_to_none(self):
        parsed = parse(counted())
        assert parsed["group_by"] is None
        assert parsed["grain"] is None


class TestGrainGrammar:
    @pytest.mark.parametrize("grain", ["day", "week", "month", "quarter", "year"])
    def test_every_grain_is_accepted(self, grain):
        parsed = parse(counted(group_by="started_at", grain=grain))
        assert parsed["grain"] == grain

    def test_a_grain_without_a_breakdown_is_refused(self):
        with pytest.raises(metrics.MetricSpecError) as err:
            parse(counted(grain="month"))
        assert "grain without group_by" in str(err.value)

    def test_a_grain_that_is_not_a_calendar_bucket_is_refused(self):
        with pytest.raises(metrics.MetricSpecError) as err:
            parse(counted(group_by="started_at", grain="fortnight"))
        assert "fortnight" in str(err.value)
        assert "must be one of" in str(err.value)


class TestWindowGrammar:
    def test_a_window_carries_days_attr_and_a_default_direction(self):
        parsed = parse(counted(window_days=30, window_attr="started_at"))
        assert parsed["window"] == {
            "days": 30,
            "attr": "started_at",
            "direction": "trailing",
        }

    def test_a_metric_with_no_window_parses_to_none(self):
        assert parse(counted())["window"] is None

    @pytest.mark.parametrize("direction", ["trailing", "forward"])
    def test_both_directions_are_accepted(self, direction):
        parsed = parse(
            counted(window_days=7, window_attr="started_at", window_direction=direction)
        )
        assert parsed["window"]["direction"] == direction

    def test_a_window_without_an_attr_to_read_is_refused(self):
        with pytest.raises(metrics.MetricSpecError) as err:
            parse(counted(window_days=30))
        assert "window_days needs window_attr" in str(err.value)

    @pytest.mark.parametrize("days", [0, -3, 1.5, "30", True])
    def test_a_window_that_is_not_a_positive_whole_number_of_days_is_refused(
        self, days
    ):
        with pytest.raises(metrics.MetricSpecError) as err:
            parse(counted(window_days=days, window_attr="started_at"))
        assert "positive integer" in str(err.value)

    def test_a_direction_without_a_window_is_refused(self):
        with pytest.raises(metrics.MetricSpecError) as err:
            parse(counted(window_attr="started_at", window_direction="forward"))
        assert "window_direction without window_days" in str(err.value)

    def test_a_direction_that_is_neither_way_is_refused(self):
        with pytest.raises(metrics.MetricSpecError) as err:
            parse(
                counted(
                    window_days=30,
                    window_attr="started_at",
                    window_direction="sideways",
                )
            )
        assert "sideways" in str(err.value)
        assert "must be one of" in str(err.value)


class TestInferredMetricsKeepTheirLimits:
    def test_an_inferred_metric_still_refuses_a_window(self):
        with pytest.raises(metrics.MetricSpecError, match="never ran"):
            parse({**INFERRED, "window_days": 30, "window_attr": "started_at"})
        assert parse(INFERRED)["window"] is None

    def test_a_breakdown_over_a_many_of_field_is_refused(self):
        with pytest.raises(metrics.MetricSpecError) as err:
            parse({**INFERRED, "group_by": "pain_points"})
        assert "many_of" in str(err.value)

    def test_a_breakdown_over_a_one_of_field_is_allowed(self):
        assert parse({**INFERRED, "group_by": "interest"})["group_by"] == "interest"


class TestProvenanceOverDimensions:
    def _lineage(self, spec):
        return metrics.provenance({"sliced": spec}, mappings.load())["sliced"]

    def test_a_windowed_metric_names_the_attr_the_window_reads(self):
        lineage = self._lineage(
            counted(window_days=30, window_attr="started_at"),
        )
        assert "subscription.started_at" in lineage["attrs"]

    def test_a_dotted_breakdown_names_the_attr_on_the_far_side(self):
        lineage = self._lineage(counted(group_by="company.industry"))
        assert "company.industry" in lineage["attrs"]

    def test_a_plain_breakdown_names_the_attr_it_buckets_on(self):
        lineage = self._lineage(
            {"entity": "deal", "expression": "COUNT(entity)", "group_by": "status"}
        )
        assert "deal.status" in lineage["attrs"]
