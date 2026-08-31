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


class TestShippedCatalog:
    def test_every_definition_parses(self):
        defs = metrics.load_definitions()
        assert defs
        for spec in defs.values():
            metrics.parse_spec(spec)

    def test_money_labels_are_discovered_from_the_transforms(self):
        assert metrics.money_labels() == {"amount", "mrr"}


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
