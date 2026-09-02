import pytest

from app.engine import mappings, metrics
from app.engine.metrics import MetricSpecError

SALES = {
    "entity": "meeting",
    "source": "enriched",
    "inferred": True,
    "reading": "sales_call",
}


def spec(**overrides):
    return {**SALES, "expression": "COUNT(entity)", **overrides}


class TestTheEstimateFlag:
    def test_a_metric_touching_a_reading_must_declare_itself(self):
        with pytest.raises(MetricSpecError, match="inferred: true"):
            metrics.parse_spec({k: v for k, v in spec().items() if k != "inferred"})

    def test_a_measured_metric_may_not_claim_the_flag(self):
        with pytest.raises(MetricSpecError, match="touches no reading"):
            metrics.parse_spec(
                {"entity": "company", "inferred": True, "expression": "COUNT(entity)"}
            )

    def test_one_inferred_term_makes_the_whole_metric_an_estimate(self):
        parsed = metrics.parse_spec(
            {
                "entity": "subscription",
                "inferred": True,
                "reading": "sales_call",
                "op": "/",
                "terms": [
                    {"expression": "SUM(mrr)"},
                    {
                        "expression": "COUNT(entity)",
                        "entity": "meeting",
                        "source": "enriched",
                        "filter": {"interest": "strong"},
                    },
                ],
            }
        )
        assert parsed["inferred"] is True
        assert [t.get("source") for t in parsed["terms"]] == ["canonical", "enriched"]

    def test_a_mixed_metric_may_still_sum_money_on_its_canonical_side(self):
        parsed = metrics.parse_spec(
            {
                "entity": "subscription",
                "inferred": True,
                "reading": "sales_call",
                "op": "/",
                "terms": [
                    {"expression": "SUM(mrr)"},
                    {
                        "expression": "COUNT(entity)",
                        "entity": "meeting",
                        "source": "enriched",
                        "filter": {"interest": "strong"},
                    },
                ],
            }
        )
        assert parsed["terms"][0]["agg"] == "SUM"


class TestWhatIsStillRefused:
    @pytest.mark.parametrize("agg", ["SUM", "AVG"])
    def test_arithmetic_over_a_label(self, agg):
        with pytest.raises(MetricSpecError, match="category error"):
            metrics.parse_spec(spec(expression=f"{agg}(interest)"))

    def test_a_label_the_vocabulary_does_not_declare(self):
        with pytest.raises(MetricSpecError, match="is not a label"):
            metrics.parse_spec(spec(filter={"interest": "lukewarm"}))

    def test_a_field_the_reading_does_not_declare(self):
        with pytest.raises(MetricSpecError, match="not a field of reading"):
            metrics.parse_spec(spec(filter={"mood": "sunny"}))

    def test_a_reading_that_does_not_exist(self):
        with pytest.raises(MetricSpecError, match="not declared in enrichment"):
            metrics.parse_spec(spec(reading="no_such_reading"))

    @pytest.mark.parametrize(
        "op,value",
        [("contains", "strong"), ("not_contains", "strong"), ("gte", 1)],
    )
    def test_substring_and_threshold_operators(self, op, value):
        with pytest.raises(MetricSpecError, match="meaningless over a closed"):
            metrics.parse_spec(spec(filter={"interest": {op: value}}))

    def test_negation_is_allowed_and_checked_against_the_vocabulary(self):
        metrics.parse_spec(spec(filter={"interest": {"not_equals": "none"}}))
        with pytest.raises(MetricSpecError, match="is not a label"):
            metrics.parse_spec(spec(filter={"interest": {"not_equals": "lukewarm"}}))

    def test_an_entity_that_is_not_the_readings_entity(self):
        with pytest.raises(MetricSpecError, match=r"sales_call.*meeting"):
            metrics.parse_spec(spec(entity="company"))


class TestTheShippedCatalog:
    def test_the_inferred_metrics_all_declare_themselves(self):
        defs = metrics.load_definitions()
        for name, entry in defs.items():
            if str((entry or {}).get("source") or "") == "enriched":
                assert entry.get("inferred") is True, name
                assert entry.get("reading"), name

    def test_no_canonical_metric_carries_the_flag(self):
        defs = metrics.load_definitions()
        for name, entry in defs.items():
            if (entry or {}).get("inferred"):
                assert str(entry.get("source") or "") == "enriched" or any(
                    t.get("source") == "enriched" for t in (entry.get("terms") or [])
                ), name

    def test_every_definition_parses(self):
        for entry in metrics.load_definitions().values():
            metrics.parse_spec(entry)


class TestProvenance:
    def test_an_inferred_metric_reports_what_produced_it(self):
        lineage = metrics.provenance(metrics.load_definitions(), mappings.load())
        entry = lineage["strong_interest_share"]
        assert entry["inferred"] is True
        assert entry["inferred_from"]["reading"] == "sales_call"
        assert entry["inferred_from"]["reads"] == "meeting.transcript"
        assert entry["inferred_from"]["fields"] == ["interest"]
        assert entry["inferred_from"]["vocabulary_sha"]

    def test_it_still_traces_the_text_it_read_to_a_raw_payload(self):
        lineage = metrics.provenance(metrics.load_definitions(), mappings.load())
        assert lineage["strong_interest_share"]["raw_fields"] == [
            "zoom.meetings._transcript_text"
        ]

    def test_a_canonical_metric_carries_no_inferred_marker(self):
        lineage = metrics.provenance(metrics.load_definitions(), mappings.load())
        assert "inferred" not in lineage["mrr"]
