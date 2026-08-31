import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.engine import ontology, resolver
from app.engine import transforms as tf
from app.engine.report import SyncReport

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
