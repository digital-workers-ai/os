import pytest

from app.sources import paginators as pag


def paginator(name):
    return pag.PAGINATORS[name]


class TestTheBaseContract:
    def test_the_base_class_declares_rather_than_implements(self):
        base = pag.Paginator()
        with pytest.raises(NotImplementedError):
            base.extract({})
        with pytest.raises(NotImplementedError):
            base.next_params({}, {})


class TestRequireList:
    @pytest.mark.parametrize("body", ["a string", ["a", "list"], 42, None])
    def test_a_body_that_is_not_an_object_is_refused(self, body):
        with pytest.raises(pag.PaginationError, match="expected an object"):
            pag.Paginator()._require_list(body, "results")

    def test_a_missing_key_is_named_as_shape_drift(self):
        with pytest.raises(pag.PaginationError, match="no 'results' list"):
            pag.Paginator()._require_list({"error": "bad token"}, "results")

    def test_a_key_holding_something_other_than_a_list_names_the_type(self):
        with pytest.raises(pag.PaginationError, match="'results' is str, not a list"):
            pag.Paginator()._require_list({"results": "oops"}, "results")

    def test_a_well_shaped_body_passes_through(self):
        assert pag.Paginator()._require_list({"results": [1, 2]}, "results") == [1, 2]


class TestResolve:
    def test_an_already_built_paginator_passes_through(self):
        built = paginator("cursor_hubspot")
        assert pag.resolve(built) is built

    def test_an_unknown_mode_lists_the_known_ones(self):
        with pytest.raises(ValueError) as caught:
            pag.resolve("cursor_imaginary")
        assert "cursor_imaginary" in str(caught.value)
        assert "cursor_hubspot" in str(caught.value)

    @pytest.mark.parametrize("name", sorted(pag.PAGINATORS))
    def test_every_registered_mode_resolves(self, name):
        assert isinstance(pag.resolve(name), pag.Paginator)


class TestWhereTheCursorLives:
    def test_hubspot_reads_paging_next_after(self):
        body = {"results": [], "paging": {"next": {"after": "c1"}}}
        assert paginator("cursor_hubspot").next_params(body, {"limit": 2}) == {
            "limit": 2,
            "after": "c1",
        }


class TestWhatStopsTheWalk:
    @pytest.mark.parametrize(
        "body",
        [
            {"results": [], "paging": {}},
            {"results": [], "paging": {"next": {}}},
            {"results": []},
        ],
    )
    def test_the_walk_ends(self, body):
        assert paginator("cursor_hubspot").next_params(body, {"limit": 2}) is None


class TestExistingParamsAreCarried:
    def test_the_original_query_survives_the_hop(self):
        body = {"results": [], "paging": {"next": {"after": "c1"}}}
        nxt = paginator("cursor_hubspot").next_params(
            body, {"updated_since": "2026-01-01", "limit": 50}
        )
        assert nxt["updated_since"] == "2026-01-01"
        assert nxt["limit"] == 50
