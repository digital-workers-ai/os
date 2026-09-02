import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.engine import ontology, resolver, strategies
from app.engine import transforms as tf
from app.engine.report import SyncReport
from app.sources import paginators

BLANK_PRESERVING = {"normalize_transcript"}

FINITE = st.floats(
    allow_nan=False, allow_infinity=False, min_value=-1e12, max_value=1e12
)

ANY_SCALAR = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(),
    st.floats(allow_nan=True, allow_infinity=True),
    st.text(),
    st.text(alphabet=st.characters(min_codepoint=1)),
    st.datetimes().map(str),
    st.emails(),
)


class TestEveryTransformIsTotal:
    @pytest.mark.parametrize("name", sorted(tf.TRANSFORMS))
    @given(value=ANY_SCALAR)
    @settings(max_examples=200, deadline=None)
    def test_it_either_returns_a_value_or_raises_transform_error(self, name, value):
        try:
            result = tf.apply(name, "hubspot", "companies", value)
        except tf.TransformError:
            return
        assert result is not None

    @pytest.mark.parametrize("name", sorted(tf.TRANSFORMS))
    @given(value=ANY_SCALAR)
    @settings(max_examples=200, deadline=None)
    def test_what_it_returns_matches_the_type_it_declares(self, name, value):
        try:
            result = tf.apply(name, "hubspot", "companies", value)
        except tf.TransformError:
            return
        declared = tf.TRANSFORM_TYPES[name]
        if declared == "number":
            assert isinstance(result, int | float)
            assert math.isfinite(result)
        else:
            assert isinstance(result, str)
            if name not in BLANK_PRESERVING:
                assert result.strip(), "a blank string is a refusal wearing a value"

    @pytest.mark.parametrize("name", sorted(tf.TRANSFORMS))
    @given(value=ANY_SCALAR)
    @settings(max_examples=200, deadline=None)
    def test_it_is_idempotent(self, name, value):
        try:
            once = tf.apply(name, "hubspot", "companies", value)
        except tf.TransformError:
            return
        try:
            twice = tf.apply(name, "hubspot", "companies", once)
        except tf.TransformError:
            pytest.fail(f"{name} refused its own output: {once!r}")
        assert twice == once


@given(value=st.booleans())
def test_a_checkbox_never_becomes_a_quantity(value):
    for name in ("normalize_money", "normalize_date"):
        with pytest.raises(tf.TransformError):
            tf.apply(name, "hubspot", "companies", value)


ONTO = ontology.load()

RECORDS = st.lists(
    st.tuples(
        st.sampled_from(["hubspot", "stripe", "zendesk", "intercom"]),
        st.integers(min_value=1, max_value=50),
        st.sampled_from(["acme.io", "globex.com", "initech.dev", "umbrella.co"]),
    ),
    max_size=25,
    unique_by=lambda row: (row[0], row[1]),
).map(
    lambda rows: [
        resolver.Record(source, "company", f"id_{n}", order, {"domain": domain})
        for order, (source, n, domain) in enumerate(rows)
    ]
)


class TestResolveProperties:
    @given(records=RECORDS, rng=st.randoms())
    @settings(max_examples=200, deadline=None)
    def test_shuffling_the_input_produces_the_same_clusters(self, records, rng):
        shuffled = list(records)
        rng.shuffle(shuffled)
        first = resolver.resolve(records, ONTO, SyncReport())
        second = resolver.resolve(shuffled, ONTO, SyncReport())
        assert [c.canonical_id for c in first["clusters"]] == [
            c.canonical_id for c in second["clusters"]
        ]
        assert [sorted(c.members) for c in first["clusters"]] == [
            sorted(c.members) for c in second["clusters"]
        ]

    @given(records=RECORDS)
    @settings(max_examples=200, deadline=None)
    def test_every_record_lands_in_exactly_one_cluster(self, records):
        result = resolver.resolve(records, ONTO, SyncReport())
        memberships = [key for c in result["clusters"] for key in c.members]
        assert sorted(memberships) == sorted(record.key for record in records)
        assert set(result["of_record"]) == {record.key for record in records}


PERSON_RECORDS = st.lists(
    st.builds(
        lambda source, sid, order, email, ref: resolver.Record(
            source=source,
            entity_type="person",
            source_id=sid,
            order=order,
            identity={k: v for k, v in (("email", email), ("external_ref", ref)) if v},
        ),
        source=st.sampled_from(["hubspot", "stripe", "zendesk", "intercom"]),
        sid=st.text(alphabet="abcdef0123456789", min_size=1, max_size=4),
        order=st.integers(min_value=1, max_value=50),
        email=st.one_of(
            st.none(), st.sampled_from(["a@acme.io", "b@acme.io", "c@globex.com"])
        ),
        ref=st.one_of(st.none(), st.sampled_from(["X1", "X2", "X3"])),
    ),
    max_size=8,
    unique_by=lambda r: r.key,
)


def _resolved(records):
    return resolver.resolve(records, ONTO, SyncReport())


@given(records=PERSON_RECORDS)
@settings(max_examples=200, deadline=None)
def test_no_alias_ever_points_at_another_alias(records):
    result = _resolved(records)
    assert not (set(result["aliases"].values()) & set(result["aliases"]))


@given(records=PERSON_RECORDS)
@settings(max_examples=200, deadline=None)
def test_no_alias_is_also_a_live_cluster(records):
    result = _resolved(records)
    live = {c.canonical_id for c in result["clusters"]}
    assert not (live & set(result["aliases"]))


@given(records=PERSON_RECORDS)
@settings(max_examples=200, deadline=None)
def test_a_cluster_never_holds_two_records_from_one_source(records):
    for cluster in _resolved(records)["clusters"]:
        sources = [key[0] for key in cluster.members]
        assert len(sources) == len(set(sources))


class TestStrategiesNeverInventAVerdict:
    NOT_FINITE = st.sampled_from([float("nan"), float("inf"), float("-inf")])

    @pytest.mark.parametrize("name", sorted(strategies.STRATEGIES))
    @given(
        bad=NOT_FINITE,
        target=FINITE,
        history=st.lists(FINITE, min_size=2, max_size=6),
    )
    @settings(max_examples=200, deadline=None)
    def test_a_non_finite_current_value_is_never_decided(
        self, name, bad, target, history
    ):
        assert strategies.STRATEGIES[name](bad, target, history, {}).met is None

    @pytest.mark.parametrize("name", sorted(strategies.STRATEGIES))
    @given(
        current=FINITE,
        bad=NOT_FINITE,
        history=st.lists(FINITE, min_size=2, max_size=6),
    )
    @settings(max_examples=200, deadline=None)
    def test_a_non_finite_target_is_never_decided(self, name, current, bad, history):
        assert strategies.STRATEGIES[name](current, bad, history, {}).met is None

    def test_the_trend_verdict_reads_the_series_not_the_current_value(self):
        history, target = [1.0, 2.0], 1.0
        baseline = strategies.increasing(0.0, target, history, {})
        for current in (1e9, -1e9):
            outcome = strategies.increasing(current, target, history, {})
            assert outcome.detail["trend"] == baseline.detail["trend"]

    @pytest.mark.parametrize("name", sorted(strategies.STRATEGIES))
    @given(current=FINITE, target=FINITE, history=st.lists(FINITE, max_size=6))
    @settings(max_examples=300, deadline=None)
    def test_progress_is_always_a_percentage_or_nothing(
        self, name, current, target, history
    ):
        outcome = strategies.STRATEGIES[name](current, target, history, {})
        if outcome.progress is not None:
            assert 0.0 <= outcome.progress <= 100.0

    @pytest.mark.parametrize("name", sorted(strategies.STRATEGIES))
    @given(current=FINITE, target=FINITE, history=st.lists(FINITE, max_size=6))
    @settings(max_examples=200, deadline=None)
    def test_an_undecided_outcome_always_says_why(self, name, current, target, history):
        outcome = strategies.STRATEGIES[name](current, target, history, {})
        if outcome.met is None:
            assert outcome.detail.get("unknown")


class TestPaginatorsFailLoudly:
    BODY = st.recursive(
        st.one_of(st.none(), st.booleans(), st.integers(), st.text()),
        lambda children: st.one_of(
            st.lists(children, max_size=3),
            st.dictionaries(st.text(max_size=6), children, max_size=3),
        ),
        max_leaves=8,
    )

    @pytest.mark.parametrize("name", sorted(paginators.PAGINATORS))
    @given(body=BODY)
    @settings(max_examples=200, deadline=None)
    def test_extract_returns_a_list_or_raises(self, name, body):
        try:
            records = paginators.PAGINATORS[name].extract(body)
        except paginators.PaginationError:
            return
        assert isinstance(records, list)

    @pytest.mark.parametrize("name", sorted(paginators.PAGINATORS))
    @given(
        body=BODY,
        params=st.dictionaries(st.text(max_size=5), st.text(max_size=5), max_size=3),
    )
    @settings(max_examples=200, deadline=None)
    def test_next_params_either_advances_or_stops(self, name, body, params):
        try:
            nxt = paginators.PAGINATORS[name].next_params(body, params)
        except (paginators.PaginationError, AttributeError, TypeError):
            return
        if nxt is None:
            return
        assert isinstance(nxt, dict)
        assert nxt != params
