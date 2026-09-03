import pytest

from app.engine import mappings, metrics


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
        assert metrics.money_labels() == {"amount", "mrr", "price", "spend", "budget"}


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
