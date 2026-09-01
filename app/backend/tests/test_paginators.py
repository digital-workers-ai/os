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

    def test_the_default_header_advance_is_none(self):
        assert pag.Paginator().next_from_headers({"Link": "<x>"}, {}) is None


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

    def test_stripe_extracts_its_data_list(self):
        assert paginator("cursor_stripe").extract({"data": [{"id": "a"}]}) == [
            {"id": "a"}
        ]

    def test_stripe_pages_on_the_last_id_it_returned(self):
        body = {"data": [{"id": "a"}, {"id": "b"}], "has_more": True}
        assert paginator("cursor_stripe").next_params(body, {"limit": 6}) == {
            "limit": 6,
            "starting_after": "b",
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

    @pytest.mark.parametrize(
        "body",
        [
            {"data": [{"id": "a"}], "has_more": False},
            {"data": [], "has_more": True},
            {"data": [{"id": "a"}]},
        ],
    )
    def test_the_stripe_walk_ends(self, body):
        assert paginator("cursor_stripe").next_params(body, {"limit": 6}) is None


class TestExistingParamsAreCarried:
    def test_the_original_query_survives_the_hop(self):
        body = {"results": [], "paging": {"next": {"after": "c1"}}}
        nxt = paginator("cursor_hubspot").next_params(
            body, {"updated_since": "2026-01-01", "limit": 50}
        )
        assert nxt["updated_since"] == "2026-01-01"
        assert nxt["limit"] == 50

    @pytest.mark.parametrize(
        "name,body",
        [
            (
                "cursor_intercom",
                {"data": [], "pages": {"next": {"starting_after": "c1"}}},
            ),
            ("cursor_customerio", {"campaigns": [], "next_cursor": "c1"}),
            (
                "token_calendly",
                {"collection": [], "pagination": {"next_page_token": "t1"}},
            ),
        ],
    )
    def test_the_original_query_survives_a_batch_one_hop(self, name, body):
        nxt = paginator(name).next_params(body, {"updated_since": "2026-01-01"})
        assert nxt["updated_since"] == "2026-01-01"


class TestBatchOneRegistration:
    def test_the_six_new_modes_are_registered(self):
        assert {
            "cursor_zendesk",
            "cursor_intercom",
            "cursor_customerio",
            "cursor_customerio_activities",
            "cursor_klaviyo",
            "token_calendly",
        } <= set(pag.PAGINATORS)


class TestWhereTheBatchOneCursorsLive:
    def test_zendesk_reads_meta_after_cursor(self):
        body = {"tickets": [], "meta": {"has_more": True, "after_cursor": "c1"}}
        assert paginator("cursor_zendesk").next_params(body, {"page[size]": 6}) == {
            "page[size]": 6,
            "page[after]": "c1",
        }

    def test_intercom_reads_pages_next_starting_after(self):
        body = {"data": [], "pages": {"next": {"starting_after": "c1"}}}
        assert paginator("cursor_intercom").next_params(body, {}) == {
            "starting_after": "c1"
        }

    def test_customerio_pages_on_cursor(self):
        assert paginator("cursor_customerio").next_params(
            {"campaigns": [], "next_cursor": "c1"}, {}
        ) == {"cursor": "c1"}

    def test_customerio_activities_page_on_start_not_cursor(self):
        assert paginator("cursor_customerio_activities").next_params(
            {"activities": [], "next_cursor": "c1"}, {}
        ) == {"start": "c1"}

    def test_klaviyo_lifts_the_cursor_out_of_its_next_link(self):
        body = {
            "data": [],
            "links": {
                "next": "https://a.klaviyo.com/api/x?page%5Bcursor%5D=c1&sort=id"
            },
        }
        assert paginator("cursor_klaviyo").next_params(body, {}) == {
            "page[cursor]": "c1"
        }

    def test_calendly_reads_pagination_next_page_token(self):
        body = {"collection": [], "pagination": {"next_page_token": "t1"}}
        assert paginator("token_calendly").next_params(body, {}) == {"page_token": "t1"}


class TestWhatStopsTheBatchOneWalk:
    @pytest.mark.parametrize(
        "name,body",
        [
            (
                "cursor_zendesk",
                {"tickets": [], "meta": {"has_more": False, "after_cursor": "c1"}},
            ),
            ("cursor_zendesk", {"tickets": [], "meta": {"has_more": True}}),
            ("cursor_intercom", {"data": [], "pages": {"next": {}}}),
            ("cursor_customerio", {"campaigns": [], "next_cursor": None}),
            ("cursor_customerio_activities", {"activities": []}),
            ("cursor_klaviyo", {"data": [], "links": {}}),
            ("token_calendly", {"collection": [], "pagination": {}}),
        ],
    )
    def test_the_walk_ends(self, name, body):
        assert paginator(name).next_params(body, {"limit": 2}) is None

    def test_klaviyo_stops_when_no_recognised_marker_is_present(self):
        assert (
            paginator("cursor_klaviyo").next_params(
                {
                    "data": [],
                    "links": {"next": "https://a.klaviyo.com/api/x?something=else"},
                },
                {},
            )
            is None
        )


class TestKlaviyoCursorsAreNotDoubleEncoded:
    def test_an_encoded_cursor_is_decoded_before_it_is_re_sent(self):
        body = {
            "data": [],
            "links": {
                "next": "https://a.klaviyo.com/api/x?page%5Bcursor%5D=bWFyaw%3D%3D"
            },
        }
        assert paginator("cursor_klaviyo").next_params(body, {}) == {
            "page[cursor]": "bWFyaw=="
        }

    @pytest.mark.parametrize("marker", ["page%5Bcursor%5D=", "page[cursor]="])
    def test_either_encoding_of_the_cursor_is_read(self, marker):
        body = {
            "data": [],
            "links": {"next": f"https://a.klaviyo.com/api/x?{marker}c1&z=1"},
        }
        assert paginator("cursor_klaviyo").next_params(body, {}) == {
            "page[cursor]": "c1"
        }


class TestKeyedCursors:
    @pytest.mark.parametrize("name", ["cursor_zendesk", "cursor_customerio"])
    def test_a_body_that_is_not_an_object_is_refused(self, name):
        with pytest.raises(pag.PaginationError, match="expected object"):
            paginator(name).extract(["not", "an", "object"])

    @pytest.mark.parametrize("name", ["cursor_zendesk", "cursor_customerio"])
    def test_an_error_envelope_is_refused_rather_than_iterated(self, name):
        with pytest.raises(pag.PaginationError, match="shape drift or error body"):
            paginator(name).extract({"error": "invalid token"})

    def test_zendesk_finds_whichever_collection_is_present(self):
        assert paginator("cursor_zendesk").extract({"organizations": [{"id": 1}]}) == [
            {"id": 1}
        ]

    def test_customerio_finds_whichever_collection_is_present(self):
        assert paginator("cursor_customerio").extract({"segments": [{"id": 1}]}) == [
            {"id": 1}
        ]


class TestIntercomCollectionKeyIsParameterized:
    def test_the_declared_key_is_extracted(self):
        assert pag.IntercomCursor("conversations").extract(
            {"conversations": [{"id": 1}]}
        ) == [{"id": 1}]

    def test_the_default_key_is_data(self):
        assert pag.IntercomCursor().extract({"data": [{"id": 1}]}) == [{"id": 1}]

    def test_an_instance_resolves_as_itself(self):
        built = pag.IntercomCursor("conversations")
        assert pag.resolve(built) is built


class TestBatchTwoRegistration:
    def test_the_twilio_mode_is_registered(self):
        assert "page_twilio" in pag.PAGINATORS
        assert isinstance(pag.resolve("page_twilio"), pag.TwilioPage)


class TestOffsetPagination:
    def make(self):
        return pag.Offset("results")

    def test_it_steps_by_the_callers_page_size_not_a_guess(self):
        body = {"results": [{}] * 25, "total_count": 100}
        assert self.make().next_params(body, {"count": 25, "offset": 0}) == {
            "count": 25,
            "offset": 25,
        }

    def test_it_stops_exactly_at_the_advertised_total(self):
        body = {"results": [{}] * 25, "total_count": 50}
        assert self.make().next_params(body, {"count": 25, "offset": 25}) is None

    def test_it_keeps_going_while_the_total_is_ahead(self):
        body = {"results": [{}] * 25, "total_count": 51}
        assert self.make().next_params(body, {"count": 25, "offset": 25}) == {
            "count": 25,
            "offset": 50,
        }

    @pytest.mark.parametrize("total_key", ["total_count", "total_items", "total"])
    def test_any_of_the_declared_total_keys_is_honoured(self, total_key):
        body = {"results": [{}] * 10, total_key: 10}
        assert self.make().next_params(body, {"count": 10, "offset": 0}) is None

    def test_a_short_page_ends_the_walk_when_no_total_is_advertised(self):
        body = {"results": [{}] * 9}
        assert self.make().next_params(body, {"count": 10, "offset": 0}) is None

    def test_a_full_page_keeps_going_when_no_total_is_advertised(self):
        body = {"results": [{}] * 10}
        assert self.make().next_params(body, {"count": 10, "offset": 0}) == {
            "count": 10,
            "offset": 10,
        }

    def test_defaults_apply_when_the_caller_named_nothing(self):
        body = {"results": [{}] * 100}
        assert self.make().next_params(body, {}) == {"offset": 100}

    def test_a_non_numeric_total_is_ignored_rather_than_trusted(self):
        body = {"results": [{}] * 10, "total_count": "many"}
        assert self.make().next_params(body, {"count": 10, "offset": 0}) == {
            "count": 10,
            "offset": 10,
        }

    def test_the_declared_list_key_is_extracted(self):
        assert pag.Offset("lists").extract({"lists": [{"id": "l1"}]}) == [{"id": "l1"}]

    def test_an_instance_resolves_as_itself(self):
        built = pag.Offset("lists")
        assert pag.resolve(built) is built


class TestShopifyLinkHeader:
    def _shopify(self):
        return pag.ShopifyLink("orders")

    def test_the_page_info_cursor_is_lifted_out_of_the_link_header(self):
        headers = {
            "Link": "<https://x.myshopify.com/admin/orders.json?"
            'limit=50&page_info=abc123>; rel="next"'
        }
        assert self._shopify().next_from_headers(headers, {"limit": 50}) == {
            "limit": 50,
            "page_info": "abc123",
        }

    def test_the_header_name_is_matched_case_insensitively(self):
        headers = {"link": '<https://x/orders.json?page_info=abc>; rel="next"'}
        assert self._shopify().next_from_headers(headers, {})["page_info"] == "abc"

    def test_a_previous_link_is_not_followed(self):
        headers = {"Link": '<https://x/orders.json?page_info=abc>; rel="previous"'}
        assert self._shopify().next_from_headers(headers, {}) is None

    def test_no_link_header_ends_the_walk(self):
        assert self._shopify().next_from_headers({}, {}) is None

    def test_the_page_info_request_carries_only_the_limit(self):
        headers = {"Link": '<https://x/orders.json?page_info=abc>; rel="next"'}
        nxt = self._shopify().next_from_headers(
            headers, {"limit": 50, "updated_at_min": "2026-01-01"}
        )
        assert nxt == {"limit": 50, "page_info": "abc"}

    def test_shopify_never_advances_from_the_body(self):
        assert (
            pag.ShopifyLink("orders").next_params({"orders": [], "next": "c1"}, {})
            is None
        )

    def test_the_declared_collection_key_is_extracted(self):
        assert pag.ShopifyLink("orders").extract({"orders": [{"id": 1}]}) == [{"id": 1}]


class TestTwilioPage:
    def test_twilio_increments_the_page_number_and_carries_its_token(self):
        body = {
            "messages": [],
            "next_page_uri": "/x?Page=2",
            "page": 1,
            "next_page_token": "t1",
        }
        assert paginator("page_twilio").next_params(body, {}) == {
            "Page": 2,
            "PageToken": "t1",
        }

    def test_twilio_sends_an_empty_token_when_the_vendor_omits_one(self):
        body = {"messages": [], "next_page_uri": "/x?Page=2", "page": 0}
        assert paginator("page_twilio").next_params(body, {})["PageToken"] == ""

    @pytest.mark.parametrize(
        "body",
        [
            {"messages": []},
            {"messages": [], "next_page_uri": ""},
        ],
    )
    def test_the_walk_ends(self, body):
        assert paginator("page_twilio").next_params(body, {"PageSize": 1}) is None

    def test_the_messages_list_is_extracted(self):
        assert paginator("page_twilio").extract({"messages": [{"sid": "s1"}]}) == [
            {"sid": "s1"}
        ]
