import pytest

from app.engine import transforms as t


class TestEveryRefusalNamesItsBucket:
    CASES = [
        ("normalize_money", True, "not_a_number"),
        ("normalize_money", "n/a", "not_a_number"),
        ("normalize_money", 10**400, "not_a_number"),
        ("normalize_money", float("inf"), "not_finite"),
        ("normalize_money", float("nan"), "not_finite"),
        ("normalize_date", True, "not_a_date"),
        ("normalize_date", "not a date", "not_a_date"),
        ("normalize_date", "", "empty"),
        ("normalize_date", "   ", "empty"),
        ("normalize_email", "not an email", "not_an_email"),
        ("normalize_domain", "localhost", "not_a_domain"),
        ("normalize_domain", "", "empty"),
        ("normalize_currency", "dollars", "not_a_currency_code"),
        ("normalize_status", "___", "empty"),
        ("normalize_text", "  ", "empty"),
    ]

    @pytest.mark.parametrize("name,value,reason", CASES)
    def test_the_reason_is_the_one_the_report_will_group_by(self, name, value, reason):
        with pytest.raises(t.TransformError) as caught:
            t.apply(name, "hubspot", "companies", value)
        assert caught.value.reason == reason

    @pytest.mark.parametrize("name,value,reason", CASES)
    def test_the_message_carries_the_reason(self, name, value, reason):
        with pytest.raises(t.TransformError) as caught:
            t.apply(name, "hubspot", "companies", value)
        assert reason in str(caught.value)

    def test_an_unknown_transform_name_names_itself(self):
        with pytest.raises(t.TransformError) as caught:
            t.apply("normalize_vibes", "hubspot", "companies", "x")
        assert caught.value.reason == "unknown_transform"
        assert "normalize_vibes" in str(caught.value)

    def test_a_transform_returning_none_is_bucketed_as_refused(self):
        t.TRANSFORMS["normalize_nothing"] = lambda s, o, v: None
        try:
            with pytest.raises(t.TransformError) as caught:
                t.apply("normalize_nothing", "hubspot", "companies", "x")
            assert caught.value.reason == "refused"
        finally:
            t.TRANSFORMS.pop("normalize_nothing")

    def test_a_detail_is_truncated_so_a_payload_cannot_fill_the_report(self):
        with pytest.raises(t.TransformError) as caught:
            t.apply("normalize_domain", "hubspot", "companies", "x" * 5000)
        assert len(str(caught.value)) < 200


class TestMoneyUnits:
    def test_google_ads_quotes_micros(self):
        assert t.normalize_money("google_ads", "campaigns", 1_500_000) == 1.5

    @pytest.mark.parametrize("source", ["stripe", "hubspot", "shopify", "linkedin"])
    def test_everyone_else_quotes_major_units(self, source):
        assert t.normalize_money(source, "orders", "272.93") == 272.93


class TestTranscriptCap:
    def test_the_cap_is_the_storage_bound(self):
        assert t.MAX_TRANSCRIPT_CHARS == 60_000

    def test_an_over_cap_transcript_is_truncated_not_refused(self):
        got = t.normalize_transcript("zoom", "meetings", "x" * 70_000)
        assert len(got) == t.MAX_TRANSCRIPT_CHARS

    def test_a_transcript_under_the_cap_is_untouched(self):
        assert (
            t.normalize_transcript("zoom", "meetings", "Jane: hello") == "Jane: hello"
        )
