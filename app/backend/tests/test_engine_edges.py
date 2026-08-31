import pytest
import yaml
from sqlalchemy.exc import IntegrityError

from app.engine import metrics


class TestMetricSpecRefusals:
    def test_a_metrics_file_that_is_not_a_mapping_is_refused(self, tmp_path):
        path = tmp_path / "metrics.yaml"
        path.write_text("- a\n- b\n")
        with pytest.raises(metrics.MetricSpecError, match="top level"):
            metrics.load_definitions(path)

    def test_an_unparseable_expression_names_itself(self):
        with pytest.raises(metrics.MetricSpecError, match="bad expression"):
            metrics.parse_spec({"entity": "deal", "expression": "reticulate(x)"})

    def test_a_filter_that_is_not_a_mapping_is_refused(self):
        with pytest.raises(metrics.MetricSpecError, match="filter must be"):
            metrics.parse_spec(
                {
                    "entity": "deal",
                    "expression": "COUNT(entity)",
                    "filter": ["status"],
                }
            )

    def test_the_money_label_set_is_read_from_the_transform_file(self, tmp_path):
        path = tmp_path / "transforms.yaml"
        path.write_text(
            yaml.safe_dump({"amount": "normalize_money", "name": "normalize_text"})
        )
        assert metrics.money_labels(path) == {"amount"}


class TestMetricArithmeticRefusesNonsense:
    async def test_the_database_itself_refuses_to_store_a_non_finite_number(
        self, session, canonical
    ):
        with pytest.raises(IntegrityError):
            await canonical("deal", {"amount": "nan"})
        await session.rollback()

    async def test_an_ordinary_average_is_unaffected(self, session, canonical):
        await canonical("deal", {"amount": "100"})
        await canonical("deal", {"amount": "200"})
        result = (
            await metrics.evaluate_definitions(
                session,
                {"avg_deal_size": {"entity": "deal", "expression": "AVG(amount)"}},
            )
        )["avg_deal_size"]
        assert result["value"] == 150

    async def test_a_metric_over_nothing_has_no_value_rather_than_zero(self, session):
        result = (
            await metrics.evaluate_definitions(
                session,
                {"avg_deal_size": {"entity": "deal", "expression": "AVG(amount)"}},
            )
        )["avg_deal_size"]
        assert result.get("value") is None
        assert result.get("entities") == 0
