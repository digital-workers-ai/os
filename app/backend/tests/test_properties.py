import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.engine import transforms as tf

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
