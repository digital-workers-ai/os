import uuid
from datetime import UTC, datetime

import pytest

from app.engine import metrics
from app.enrichment import vocabulary
from app.models import CanonicalAlias, EnrichedFact, EntityCanonical, FactCurrent

RETIRED_VOCAB = "a-vocabulary-since-replaced"
SEEN = datetime(2026, 8, 1, tzinfo=UTC)

BASE = {
    "entity": "meeting",
    "source": "enriched",
    "inferred": True,
    "reading": "sales_call",
}


@pytest.fixture
def reading():
    return vocabulary.load()["sales_call"]


async def _meeting(session, seq, transcript="a call happened"):
    canonical_id = uuid.uuid4()
    session.add(
        EntityCanonical(
            canonical_id=canonical_id,
            entity_type="meeting",
            anchor_key=f"zoom|meeting|m{seq}",
            minted_seq=seq,
            member_count=1,
        )
    )
    session.add(
        FactCurrent(
            canonical_id=canonical_id,
            entity_type="meeting",
            attr="transcript",
            value=transcript,
            observed_at=SEEN,
        )
    )
    return canonical_id


def _label(
    canonical_id,
    reading,
    attr,
    value,
    *,
    verified=True,
    vocab=None,
    model="test-model",
    prompt="test-1",
):
    return EnrichedFact(
        canonical_id=canonical_id,
        entity_type="meeting",
        reading=reading.name,
        attr=attr,
        value=value,
        quote="…",
        quote_verified=verified,
        input_sha="sha",
        vocabulary_sha=vocab or reading.sha,
        model=model,
        prompt_version=prompt,
    )


@pytest.fixture
async def estate(session, reading):
    ids = {}
    for seq in range(1, 7):
        ids[f"m{seq}"] = await _meeting(session, seq)

    session.add_all(
        [
            _label(ids["m1"], reading, "interest", "strong"),
            _label(ids["m1"], reading, "pain_points", "pricing"),
            _label(ids["m1"], reading, "pain_points", "manual_work"),
            _label(ids["m2"], reading, "interest", "strong"),
            _label(ids["m2"], reading, "pain_points", "pricing"),
            _label(ids["m3"], reading, "interest", "weak"),
            _label(ids["m4"], reading, "interest", "moderate"),
            _label(
                ids["m4"],
                reading,
                "pain_points",
                "security_compliance",
                verified=False,
            ),
            _label(ids["m5"], reading, "interest", "strong", vocab=RETIRED_VOCAB),
            _label(ids["m5"], reading, "pain_points", "pricing", vocab=RETIRED_VOCAB),
        ]
    )

    for seq, mrr in ((7, 1000.0), (8, 3000.0)):
        sub = uuid.uuid4()
        session.add(
            EntityCanonical(
                canonical_id=sub,
                entity_type="subscription",
                anchor_key=f"stripe|subscription|s{seq}",
                minted_seq=seq,
                member_count=1,
            )
        )
        session.add(
            FactCurrent(
                canonical_id=sub,
                entity_type="subscription",
                attr="mrr",
                value=str(mrr),
                value_num=mrr,
                observed_at=SEEN,
            )
        )
    await session.commit()
    return ids


async def evaluate(session, spec, name="m"):
    out = await metrics.evaluate_definitions(session, {name: spec})
    return out[name]


class TestABreakdownOverAReadingField:
    async def test_read_calls_bucket_by_the_label_the_model_gave_them(
        self, session, estate
    ):
        result = await evaluate(
            session,
            {**BASE, "expression": "COUNT(entity)", "group_by": "interest"},
        )
        assert result["breakdown"] == {"moderate": 1, "strong": 2, "weak": 1}
        assert result["group_by"] == "interest"


class TestProducedByNamesWhatWasCounted:
    async def test_a_filtered_metric_names_only_its_own_producers(
        self, session, estate, reading
    ):
        other = await _meeting(session, 99)
        session.add(
            _label(
                other, reading, "interest", "weak", model="other-model", prompt="v99"
            )
        )
        await session.commit()

        result = await evaluate(
            session,
            {**BASE, "expression": "COUNT(entity)", "filter": {"interest": "strong"}},
        )
        assert result["produced_by"] == ["test-model@test-1"]

    async def test_a_metric_spanning_two_prompts_still_reports_both(
        self, session, estate, reading
    ):
        extra = await _meeting(session, 98)
        session.add(
            _label(
                extra,
                reading,
                "interest",
                "strong",
                model="test-model",
                prompt="test-2",
            )
        )
        await session.commit()

        result = await evaluate(
            session,
            {**BASE, "expression": "COUNT(entity)", "filter": {"interest": "strong"}},
        )
        assert result["produced_by"] == ["test-model@test-1", "test-model@test-2"]


class TestScenarios:
    async def test_1_a_share_over_read_calls(self, session, estate):
        result = await evaluate(
            session,
            {
                **BASE,
                "op": "/",
                "terms": [
                    {"expression": "COUNT(entity)", "filter": {"interest": "strong"}},
                    {"expression": "COUNT(entity)", "filter": {}},
                ],
            },
        )
        assert result["value"] == 0.5
        assert result["inferred"] is True

    async def test_2_the_never_read_call_is_not_in_the_denominator(
        self, session, estate
    ):
        result = await evaluate(
            session, {**BASE, "expression": "COUNT(entity)", "filter": {}}
        )
        assert result["value"] == 4
        assert result["population"] == "entities read under the current vocabulary"

    async def test_3_population_all_deliberately_includes_it(self, session, estate):
        wide = await evaluate(
            session,
            {
                **BASE,
                "population": "all",
                "op": "/",
                "terms": [
                    {"expression": "COUNT(entity)", "filter": {"interest": "strong"}},
                    {"expression": "COUNT(entity)", "filter": {}},
                ],
            },
        )
        assert wide["value"] == 0.3333
        assert "all entities" in wide["population"]

    async def test_4_a_retired_vocabulary_is_excluded_and_reported(
        self, session, estate
    ):
        result = await evaluate(
            session,
            {**BASE, "expression": "COUNT(entity)", "filter": {"interest": "strong"}},
        )
        assert result["value"] == 2
        assert result["read_under_a_retired_vocabulary"] == 1

    async def test_5_count_and_count_distinct_differ_over_a_many_of_field(
        self, session, estate
    ):
        mentions = await evaluate(session, {**BASE, "expression": "COUNT(pain_points)"})
        calls = await evaluate(
            session, {**BASE, "expression": "COUNT_DISTINCT(pain_points)"}
        )
        assert mentions["value"] == 4
        assert calls["value"] == 3

    async def test_6_a_ratio_over_a_many_of_field(self, session, estate):
        result = await evaluate(
            session,
            {
                **BASE,
                "op": "/",
                "terms": [
                    {"expression": "COUNT(pain_points)", "filter": {}},
                    {"expression": "COUNT(entity)", "filter": {}},
                ],
            },
        )
        assert result["value"] == 1.0

    async def test_7_negation_means_no_such_label_not_some_other_label(
        self, session, estate
    ):
        result = await evaluate(
            session,
            {
                **BASE,
                "expression": "COUNT(entity)",
                "filter": {"pain_points": {"not_equals": "pricing"}},
            },
        )
        assert result["value"] == 2

    async def test_9_a_mixed_metric_divides_real_money_by_an_inferred_count(
        self, session, estate
    ):
        result = await evaluate(
            session,
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
            },
        )
        assert result["value"] == 2000.0
        assert result["inferred"] is True
        assert result["produced_by"] == ["test-model@test-1"]

    async def test_10_an_unverified_quote_is_counted_never_dropped(
        self, session, estate
    ):
        result = await evaluate(session, {**BASE, "expression": "COUNT(pain_points)"})
        assert result["value"] == 4
        assert result["unverified_quotes"] == 1

    async def test_11_a_canonical_metric_is_untouched_by_any_of_this(
        self, session, estate
    ):
        result = await evaluate(
            session, {"entity": "subscription", "expression": "SUM(mrr)"}
        )
        assert result["value"] == 4000.0
        assert "inferred" not in result
        assert "population" not in result

    async def test_12_a_reading_filed_under_a_merged_id_is_not_counted_twice(
        self, session, estate, reading
    ):
        retired = uuid.uuid4()
        session.add(
            CanonicalAlias(alias_id=retired, canonical_id=estate["m1"], reason="merged")
        )
        session.add(_label(retired, reading, "interest", "strong"))
        await session.commit()

        result = await evaluate(
            session,
            {**BASE, "expression": "COUNT(entity)", "filter": {"interest": "strong"}},
        )
        assert result["value"] == 2, "the merged-away id was counted as a call"

    async def test_13_an_empty_result_says_no_data_rather_than_zero(
        self, session, estate
    ):
        result = await evaluate(
            session,
            {**BASE, "expression": "COUNT(entity)", "filter": {"timing": "immediate"}},
        )
        assert result["entities"] == 0
        assert result["inferred"] is True
        assert "no data" in result.get("note", "")
