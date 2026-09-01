from datetime import UTC, datetime

import pytest

from app.engine import rules

NOW = datetime(2026, 8, 2, tzinfo=UTC)


class TestThePredicateIsTotal:
    @pytest.mark.parametrize(
        "stored",
        [
            None,
            "",
            "   ",
            "not-a-number",
            "not-a-date",
            "2026/08/02",
            "NaN",
            "inf",
            "-inf",
            "9" * 400,
            "0",
            "-1",
            "1e400",
            "true",
            "[]",
            "{}",
            "\x00",
            "café",
            "%",
            "_",
        ],
    )
    @pytest.mark.parametrize(
        "op,operand",
        [
            ("equals", "open"),
            ("not_equals", "open"),
            ("gt", 1),
            ("gte", 1),
            ("lt", 1),
            ("lte", 1),
            ("contains", "op"),
            ("not_contains", "op"),
            ("starts_with", "op"),
            ("older_than_days", 30),
            ("within_days", 30),
            ("exists", True),
            ("is_null", True),
        ],
    )
    def test_every_operator_over_every_defective_value_returns_a_bool(
        self, op, operand, stored
    ):
        result = rules.match(op, operand, stored, now=NOW)
        assert isinstance(result, bool)

    def test_a_value_too_large_for_a_float_is_unreadable_not_a_match(self):
        assert rules.match("gte", 1, "9" * 400, now=NOW) is False
        assert rules.readable("gte", "9" * 400) is False

    def test_a_non_finite_number_never_satisfies_a_bound(self):
        for stored in ("NaN", "inf", "-inf"):
            assert rules.match("gte", 1, stored, now=NOW) is False
            assert rules.match("lte", 1, stored, now=NOW) is False


class TestAbsenceIsNotFalsity:
    @pytest.mark.parametrize(
        "op,operand",
        [
            ("equals", "open"),
            ("not_equals", "open"),
            ("gt", 1),
            ("gte", 1),
            ("lt", 1),
            ("lte", 1),
            ("contains", "op"),
            ("not_contains", "op"),
            ("starts_with", "op"),
            ("older_than_days", 30),
            ("within_days", 30),
        ],
    )
    def test_a_missing_value_never_matches_a_claim_about_its_value(self, op, operand):
        assert rules.match(op, operand, None, now=NOW) is False

    def test_not_equals_does_not_fire_on_an_absent_attr(self):
        assert rules.match("not_equals", "closed", None, now=NOW) is False
        assert rules.match("not_equals", "closed", "open", now=NOW) is True

    def test_is_null_is_the_op_that_asks_about_absence(self):
        assert rules.match("is_null", True, None, now=NOW) is True
        assert rules.match("is_null", True, "open", now=NOW) is False

    def test_exists_is_its_inverse(self):
        assert rules.match("exists", True, "open", now=NOW) is True
        assert rules.match("exists", True, None, now=NOW) is False


class TestTheOperators:
    def test_equality_is_case_insensitive_and_trimmed(self):
        assert rules.match("equals", "Open", " open ", now=NOW) is True

    def test_equality_treats_a_wildcard_as_a_literal(self):
        assert rules.match("equals", "100%", "100%", now=NOW) is True
        assert rules.match("contains", "100%", "at 100% capacity", now=NOW) is True
        assert rules.match("contains", "a_c", "abc", now=NOW) is False

    def test_numeric_comparison_reads_the_stored_text_as_a_number(self):
        assert rules.match("gte", 500, "500.0", now=NOW) is True
        assert rules.match("lt", 500, "499.99", now=NOW) is True

    def test_older_than_days_measures_against_the_injected_clock(self):
        old = "2026-01-01T00:00:00Z"
        assert rules.match("older_than_days", 30, old, now=NOW) is True
        assert rules.match("older_than_days", 3000, old, now=NOW) is False

    def test_within_days_is_not_the_negation_of_older_than(self):
        future = "2026-12-01T00:00:00Z"
        assert rules.match("older_than_days", 30, future, now=NOW) is False
        assert rules.match("within_days", 30, future, now=NOW) is False

    def test_a_naive_timestamp_is_read_as_utc(self):
        assert rules.match("older_than_days", 30, "2026-01-01", now=NOW) is True


class TestRuleParsing:
    def test_a_rule_that_is_not_a_mapping_is_refused(self):
        with pytest.raises(rules.RuleError, match="must be a mapping"):
            rules.parse("stale_deal", ["not", "a", "mapping"])

    def test_a_condition_that_is_not_a_mapping_is_refused(self):
        with pytest.raises(rules.RuleError, match="each condition"):
            rules.parse(
                "r",
                {"entity": "deal", "label": "L", "severity": "high", "all": ["status"]},
            )

    def test_a_condition_naming_no_attr_is_refused(self):
        with pytest.raises(rules.RuleError, match="names no attr"):
            rules.parse(
                "r",
                {
                    "entity": "deal",
                    "label": "L",
                    "severity": "high",
                    "all": [{"equals": "open"}],
                },
            )

    def test_a_condition_with_two_operators_is_refused(self):
        with pytest.raises(rules.RuleError, match="exactly one operator"):
            rules.parse(
                "r",
                {
                    "entity": "deal",
                    "label": "L",
                    "severity": "high",
                    "all": [{"attr": "amount", "gte": 100, "lte": 1000}],
                },
            )

    def test_a_severity_outside_the_closed_set_is_refused(self):
        with pytest.raises(rules.RuleError, match="severity"):
            rules.parse(
                "r",
                {
                    "entity": "deal",
                    "label": "L",
                    "severity": "apocalyptic",
                    "all": [{"attr": "status", "equals": "open"}],
                },
            )

    def test_a_rules_file_that_is_not_a_mapping_is_refused(self, tmp_path):
        path = tmp_path / "rules.yaml"
        path.write_text("- a\n")
        with pytest.raises(rules.RuleError, match="top level"):
            rules.load(path)

    @pytest.mark.parametrize("text", ["not a date", "2026-13-45", ""])
    def test_an_unparseable_date_reads_as_absent_rather_than_raising(self, text):
        assert rules._as_datetime(text) is None

    async def test_no_rules_is_no_findings_without_touching_the_database(
        self, session, count_queries
    ):
        with count_queries() as counter:
            assert await rules.evaluate(session, rules={}, now=NOW) == []
        assert counter.total == 0

    async def test_an_exists_condition_reports_the_size_not_the_text(
        self, session, canonical
    ):
        await canonical("meeting", {"transcript": "a long private conversation"})
        rule = rules.parse(
            "unread",
            {
                "entity": "meeting",
                "label": "Unread",
                "severity": "low",
                "all": [{"attr": "transcript", "exists": True}],
            },
        )
        findings = await rules.evaluate(session, rules={"unread": rule}, now=NOW)
        assert findings
        evidence = findings[0].as_dict()["evidence"]
        assert "chars" in evidence["transcript"]
        assert "private conversation" not in str(evidence)

    async def test_an_any_of_that_matches_nothing_produces_no_finding(
        self, session, canonical
    ):
        await canonical("deal", {"status": "open"})
        rule = rules.parse(
            "odd",
            {
                "entity": "deal",
                "label": "Odd",
                "severity": "low",
                "any": [{"attr": "status", "equals": "cancelled"}],
            },
        )
        assert await rules.evaluate(session, rules={"odd": rule}, now=NOW) == []


class TestTheShippedRulesCanActuallyFire:
    async def test_a_past_due_subscription_is_flagged(self, session, canonical):
        await canonical("subscription", {"status": "past_due", "mrr": "100"})
        findings = await rules.evaluate(session, now=NOW)
        assert "subscription_past_due" in {f.rule for f in findings}

    async def test_an_active_subscription_is_not_flagged(self, session, canonical):
        await canonical("subscription", {"status": "active", "mrr": "100"})
        findings = await rules.evaluate(session, now=NOW)
        assert "subscription_past_due" not in {f.rule for f in findings}

    async def test_an_aging_open_deal_is_stalled(self, session, canonical):
        await canonical(
            "deal",
            {"status": "qualifiedtobuy", "closed_at": "2026-01-01T00:00:00Z"},
        )
        findings = await rules.evaluate(session, now=NOW)
        assert "stalled_deal" in {f.rule for f in findings}

    async def test_a_won_deal_is_not_stalled(self, session, canonical):
        await canonical(
            "deal",
            {"status": "closed_won", "closed_at": "2026-01-01T00:00:00Z"},
        )
        findings = await rules.evaluate(session, now=NOW)
        assert "stalled_deal" not in {f.rule for f in findings}


SYNTHETIC = {
    "open_deal": {
        "label": "Open deal",
        "entity": "deal",
        "severity": "low",
        "all": [{"attr": "status", "equals": "open"}],
    },
    "deal_not_closed": {
        "label": "Not closed",
        "entity": "deal",
        "severity": "low",
        "all": [{"attr": "status", "not_equals": "closed_won"}],
    },
    "urgent_open_subscription": {
        "label": "Urgent",
        "entity": "subscription",
        "severity": "high",
        "all": [
            {"attr": "status", "equals": "open"},
            {"attr": "priority", "equals": "urgent"},
        ],
    },
    "stale_deal": {
        "label": "Stale",
        "entity": "deal",
        "severity": "high",
        "all": [{"attr": "closed_at", "older_than_days": 30}],
    },
}


def synthetic():
    return {name: rules.parse(name, body) for name, body in SYNTHETIC.items()}


class TestEvaluationOverTheCanonicalLayer:
    async def test_a_rule_fires_once_per_real_thing_not_once_per_source(
        self, session, canonical
    ):
        await canonical(
            "deal",
            {"status": "open", "amount": "5000"},
            sources=["hubspot", "stripe"],
        )
        findings = await rules.evaluate(session, rules=synthetic(), now=NOW)
        assert len([f for f in findings if f.rule == "open_deal"]) == 1

    async def test_a_cleared_attr_does_not_fire_a_not_equals_rule(
        self, session, canonical
    ):
        await canonical("deal", {"amount": "5000"})
        findings = await rules.evaluate(session, rules=synthetic(), now=NOW)
        assert [f for f in findings if f.rule == "deal_not_closed"] == []

    async def test_all_requires_every_condition(self, session, canonical):
        await canonical("subscription", {"status": "open", "priority": "low"})
        findings = await rules.evaluate(session, rules=synthetic(), now=NOW)
        assert [f for f in findings if f.rule == "urgent_open_subscription"] == []

    async def test_every_condition_satisfied_fires(self, session, canonical):
        await canonical("subscription", {"status": "open", "priority": "urgent"})
        findings = await rules.evaluate(session, rules=synthetic(), now=NOW)
        assert [f for f in findings if f.rule == "urgent_open_subscription"] != []

    async def test_a_finding_carries_the_facts_that_fired_it(self, session, canonical):
        await canonical("subscription", {"status": "open", "priority": "urgent"})
        finding = next(
            f
            for f in await rules.evaluate(session, rules=synthetic(), now=NOW)
            if f.rule == "urgent_open_subscription"
        )
        assert finding.evidence["priority"] == "urgent"
        assert finding.severity == "high"

    async def test_a_finding_names_the_company_it_hangs_off(
        self, session, canonical, link
    ):
        company = await canonical("company", {"name": "Acme"})
        deal = await canonical("deal", {"status": "open", "amount": "1"})
        await link(deal, "belongs_to", company)
        finding = next(
            f
            for f in await rules.evaluate(session, rules=synthetic(), now=NOW)
            if f.rule == "open_deal"
        )
        assert finding.company == "Acme"

    async def test_findings_are_ordered_deterministically(self, session, canonical):
        for i in range(5):
            await canonical("deal", {"status": "open", "amount": str(i)})
        first = [
            (f.rule, f.anchor)
            for f in await rules.evaluate(session, rules=synthetic(), now=NOW)
        ]
        second = [
            (f.rule, f.anchor)
            for f in await rules.evaluate(session, rules=synthetic(), now=NOW)
        ]
        assert first == second

    async def test_the_clock_is_injected_so_the_result_is_reproducible(
        self, session, canonical
    ):
        await canonical(
            "deal",
            {"status": "open", "amount": "1", "closed_at": "2026-07-01T00:00:00Z"},
        )
        early = await rules.evaluate(
            session, rules=synthetic(), now=datetime(2026, 7, 2, tzinfo=UTC)
        )
        late = await rules.evaluate(
            session, rules=synthetic(), now=datetime(2027, 7, 2, tzinfo=UTC)
        )
        assert "stale_deal" not in {f.rule for f in early}
        assert "stale_deal" in {f.rule for f in late}

    async def test_one_query_per_entity_type_not_one_per_rule(
        self, session, canonical, count_queries
    ):
        await canonical("deal", {"status": "open", "amount": "1"})
        await canonical("subscription", {"status": "past_due", "mrr": "1"})
        with count_queries() as counter:
            await rules.evaluate(session, now=NOW)
        types = {r.entity for r in rules.definitions().values()}
        assert counter.total <= len(types) + 2

    async def test_an_empty_estate_produces_no_findings_and_does_not_raise(
        self, session
    ):
        assert await rules.evaluate(session, now=NOW) == []

    async def test_a_defective_value_is_refused_and_counted_not_swallowed(
        self, session, canonical
    ):
        await canonical(
            "deal",
            {"status": "open", "amount": "1", "closed_at": "2026/08/02"},
        )
        report = rules.Report()
        await rules.evaluate(session, now=NOW, report=report)
        assert report.unreadable, report.as_dict()
