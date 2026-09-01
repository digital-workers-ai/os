import pkgutil

import pytest

from app.engine.resolver import FREE_MAIL_DOMAINS
from app.sources import hooks
from app.sources.hubspot import extract as hubspot_hook
from app.sources.stripe import extract as stripe_hook


def _info(name, ispkg=True):
    return type("I", (), {"name": name, "ispkg": ispkg})()


def _sub(items, **extra):
    return {
        "id": "sub_9",
        "customer": "cus_123",
        "status": "Active",
        "items": {"data": items},
        **extra,
    }


def _item(unit_amount, quantity=1, interval="month", interval_count=1):
    return {
        "quantity": quantity,
        "price": {
            "unit_amount": unit_amount,
            "recurring": {"interval": interval, "interval_count": interval_count},
        },
    }


class TestStripeItemsFold:
    def test_the_plan_worked_example(self):
        out = stripe_hook.reshape("subscriptions", _sub([_item(2450, quantity=2)]))
        assert out[0]["_amount_monthly"] == 49.0

    def test_quantity_multiplies(self):
        out = stripe_hook.reshape("subscriptions", _sub([_item(1000, quantity=3)]))
        assert out[0]["_amount_monthly"] == 30.0

    def test_annual_plans_divide_by_twelve(self):
        out = stripe_hook.reshape(
            "subscriptions", _sub([_item(120000, interval="year")])
        )
        assert out[0]["_amount_monthly"] == 100.0

    def test_interval_count_divides_too(self):
        out = stripe_hook.reshape(
            "subscriptions", _sub([_item(6000, interval="month", interval_count=3)])
        )
        assert out[0]["_amount_monthly"] == 20.0

    def test_several_items_sum(self):
        out = stripe_hook.reshape(
            "subscriptions", _sub([_item(1000), _item(500, quantity=2)])
        )
        assert out[0]["_amount_monthly"] == 20.0

    def test_unit_amount_decimal_fallback(self):
        item = {
            "quantity": 1,
            "price": {
                "unit_amount_decimal": "2450",
                "recurring": {"interval": "month"},
            },
        }
        out = stripe_hook.reshape("subscriptions", _sub([item]))
        assert out[0]["_amount_monthly"] == 24.5

    def test_missing_quantity_defaults_to_one(self):
        item = {"price": {"unit_amount": 700, "recurring": {"interval": "month"}}}
        out = stripe_hook.reshape("subscriptions", _sub([item]))
        assert out[0]["_amount_monthly"] == 7.0

    def test_a_daily_plan_is_scaled_by_the_days_in_an_average_month(self):
        out = stripe_hook.reshape("subscriptions", _sub([_item(100, interval="day")]))
        assert out[0]["_amount_monthly"] == pytest.approx(30.437, abs=0.005)

    def test_a_weekly_plan_is_scaled_by_the_weeks_in_an_average_month(self):
        out = stripe_hook.reshape("subscriptions", _sub([_item(100, interval="week")]))
        assert out[0]["_amount_monthly"] == pytest.approx(4.348, abs=0.005)

    def test_the_four_intervals_order_the_way_a_calendar_does(self):
        monthly = {}
        for interval in ("day", "week", "month", "year"):
            out = stripe_hook.reshape(
                "subscriptions", _sub([_item(1200, interval=interval)])
            )
            monthly[interval] = out[0]["_amount_monthly"]
        assert monthly["day"] > monthly["week"] > monthly["month"] > monthly["year"]

    def test_interval_count_divides_a_daily_plan_too(self):
        daily = stripe_hook.reshape(
            "subscriptions", _sub([_item(100, interval="day")])
        )[0]
        fortnightly = stripe_hook.reshape(
            "subscriptions", _sub([_item(100, interval="day", interval_count=14)])
        )[0]
        assert fortnightly["_amount_monthly"] == pytest.approx(
            daily["_amount_monthly"] / 14, abs=0.005
        )

    def test_no_items_is_a_counted_skip_not_a_silent_zero(self):
        out = stripe_hook.reshape("subscriptions", _sub([]))
        assert "_amount_monthly" not in out[0]
        assert out[0]["_hook_skips"] == [["_amount_monthly", "no_subscription_items"]]

    def test_unknown_interval_is_refused_not_guessed(self):
        out = stripe_hook.reshape(
            "subscriptions", _sub([_item(1000, interval="fortnight")])
        )
        assert out[0]["_hook_skips"] == [["_amount_monthly", "bad_billing_interval"]]

    def test_an_item_with_no_unit_amount_is_refused(self):
        item = {"quantity": 1, "price": {"recurring": {"interval": "month"}}}
        out = stripe_hook.reshape("subscriptions", _sub([item]))
        assert out[0]["_hook_skips"] == [["_amount_monthly", "no_unit_amount"]]

    def test_a_negative_interval_count_is_refused(self):
        out = stripe_hook.reshape(
            "subscriptions", _sub([_item(1000, interval_count=-1)])
        )
        assert out[0]["_hook_skips"] == [["_amount_monthly", "bad_billing_interval"]]

    def test_an_unreadable_quantity_is_refused_as_unfoldable(self):
        out = stripe_hook.reshape("subscriptions", _sub([_item(1000, quantity="two")]))
        assert out[0]["_hook_skips"] == [["_amount_monthly", "unfoldable_items"]]

    def test_the_other_facts_still_land_when_the_amount_cannot_be_computed(self):
        out = stripe_hook.reshape("subscriptions", _sub([]))
        assert out[0]["customer"] == "cus_123"
        assert out[0]["status"] == "Active"

    def test_customers_pass_through_untouched(self):
        payload = {"id": "cus_1", "email": "a@b.com"}
        assert stripe_hook.reshape("customers", payload) == [payload]

    def test_the_original_payload_is_not_mutated(self):
        payload = _sub([_item(1000)])
        stripe_hook.reshape("subscriptions", payload)
        assert "_amount_monthly" not in payload


class TestATruncatedItemListIsNotSummedAsWhole:
    def test_a_truncated_item_list_is_refused_rather_than_undercounted(self):
        payload = _sub([_item(1000)])
        payload["items"]["has_more"] = True
        out = stripe_hook.reshape("subscriptions", payload)
        assert "_amount_monthly" not in out[0]
        assert out[0]["_hook_skips"] == [["_amount_monthly", "items_truncated"]]

    def test_a_complete_item_list_is_summed(self):
        payload = _sub([_item(1000)])
        payload["items"]["has_more"] = False
        out = stripe_hook.reshape("subscriptions", payload)
        assert out[0]["_amount_monthly"] == 10.0

    def test_an_absent_has_more_is_read_as_complete(self):
        out = stripe_hook.reshape("subscriptions", _sub([_item(1000)]))
        assert out[0]["_amount_monthly"] == 10.0

    def test_the_other_facts_still_land_when_the_items_are_truncated(self):
        payload = _sub([_item(1000)])
        payload["items"]["has_more"] = True
        out = stripe_hook.reshape("subscriptions", payload)
        assert out[0]["customer"] == "cus_123"


class TestCurrencyDecidesTheDivisor:
    def test_a_two_decimal_currency_becomes_major_units(self):
        out = stripe_hook.reshape("subscriptions", _sub([_item(4900)], currency="usd"))
        assert out[0]["_amount_monthly"] == 49.0

    @pytest.mark.parametrize("currency", ["jpy", "krw", "vnd", "clp", "JPY"])
    def test_a_zero_decimal_currency_is_not_divided(self, currency):
        out = stripe_hook.reshape(
            "subscriptions", _sub([_item(50000)], currency=currency)
        )
        assert out[0]["_amount_monthly"] == 50000.0

    @pytest.mark.parametrize("currency", ["bhd", "kwd", "tnd"])
    def test_a_three_decimal_currency_divides_by_a_thousand(self, currency):
        out = stripe_hook.reshape(
            "subscriptions", _sub([_item(50000)], currency=currency)
        )
        assert out[0]["_amount_monthly"] == 50.0

    def test_an_absent_currency_falls_back_to_two_decimals(self):
        out = stripe_hook.reshape("subscriptions", _sub([_item(4900)]))
        assert out[0]["_amount_monthly"] == 49.0

    def test_an_annual_zero_decimal_plan_divides_by_the_year_only(self):
        out = stripe_hook.reshape(
            "subscriptions",
            _sub([_item(1_200_000, interval="year")], currency="jpy"),
        )
        assert out[0]["_amount_monthly"] == 100_000.0


class TestCompositeNames:
    def test_hubspot_composes(self):
        out = hubspot_hook.reshape(
            "contacts", {"properties": {"firstname": "Jane", "lastname": "Smith"}}
        )
        assert out[0]["_full_name"] == "Jane Smith"

    def test_hubspot_handles_a_missing_half(self):
        out = hubspot_hook.reshape("contacts", {"properties": {"lastname": "Smith"}})
        assert out[0]["_full_name"] == "Smith"

    def test_hubspot_omits_the_field_entirely_when_there_is_no_name(self):
        out = hubspot_hook.reshape("contacts", {"properties": {}})
        assert "_full_name" not in out[0]

    def test_companies_pass_through(self):
        payload = {"properties": {"name": "Acme"}}
        assert hubspot_hook.reshape("companies", payload) == [payload]


class TestCalendlyArrayHook:
    @staticmethod
    def _reshape(payload):
        from app.sources.calendly import extract

        return extract.reshape("scheduled_events", payload)

    def test_other_object_types_pass_through(self):
        from app.sources.calendly import extract

        payload = {"uri": "https://api.calendly.com/x/1"}
        assert extract.reshape("invitees", payload) == [payload]

    def test_the_first_membership_becomes_the_host(self):
        out = self._reshape(
            {
                "name": "30 Minute Demo",
                "event_memberships": [{"user_email": "jane@acme.io"}],
            }
        )
        assert out[0]["_host_email"] == "jane@acme.io"
        assert "_hook_skips" not in out[0]

    def test_a_multi_host_meeting_counts_what_it_dropped(self):
        out = self._reshape(
            {
                "event_memberships": [
                    {"user_email": "jane@acme.io"},
                    {"user_email": "mike@globex.com"},
                ]
            }
        )
        assert out[0]["_host_email"] == "jane@acme.io"
        assert out[0]["_hook_skips"] == [["_host_email", "multi_host_meeting"]]

    def test_no_memberships_is_a_counted_skip(self):
        out = self._reshape({"event_memberships": []})
        assert "_host_email" not in out[0]
        assert out[0]["_hook_skips"] == [["_host_email", "no_event_memberships"]]

    def test_memberships_that_are_not_a_list_are_a_counted_skip(self):
        out = self._reshape({"event_memberships": "oops"})
        assert "_host_email" not in out[0]
        assert out[0]["_hook_skips"] == [["_host_email", "no_event_memberships"]]


class TestBatchOneCompositeNames:
    def test_klaviyo_composes_from_the_attributes_block(self):
        from app.sources.klaviyo import extract

        out = extract.reshape(
            "profiles",
            {"id": "p1", "attributes": {"first_name": "Jane", "last_name": "Smith"}},
        )
        assert out[0]["_full_name"] == "Jane Smith"

    def test_klaviyo_flows_pass_through(self):
        from app.sources.klaviyo import extract

        payload = {"id": "f1", "attributes": {"name": "Welcome"}}
        assert extract.reshape("flows", payload) == [payload]

    def test_sendgrid_composes_from_the_top_level(self):
        from app.sources.sendgrid import extract

        out = extract.reshape(
            "contacts", {"id": "s1", "first_name": "Jane", "last_name": "Smith"}
        )
        assert out[0]["_full_name"] == "Jane Smith"

    def test_sendgrid_singlesends_pass_through(self):
        from app.sources.sendgrid import extract

        payload = {"id": "ss1", "name": "July Newsletter"}
        assert extract.reshape("singlesends", payload) == [payload]


class TestDiscovery:
    def test_every_source_package_with_an_extract_module_is_a_hook(self):
        assert set(hooks.hooks()) == {
            "hubspot",
            "stripe",
            "calendly",
            "klaviyo",
            "sendgrid",
            "salesforce",
            "shopify",
            "woocommerce",
            "google_sheets",
            "google_analytics",
            "activecampaign",
            "zoom",
        }

    def test_a_package_without_an_extract_module_contributes_no_hook(self, monkeypatch):
        hooks._reset()
        monkeypatch.setattr(pkgutil, "iter_modules", lambda path: [_info("bare")])
        monkeypatch.setattr(hooks.importlib.util, "find_spec", lambda name: None)
        assert hooks.hooks() == {}
        hooks._reset()

    def test_an_extract_module_with_no_reshape_is_refused(self, monkeypatch):
        hooks._reset()
        monkeypatch.setattr(pkgutil, "iter_modules", lambda path: [_info("broken")])
        monkeypatch.setattr(hooks.importlib.util, "find_spec", lambda name: object())
        monkeypatch.setattr(
            hooks.importlib, "import_module", lambda name: type("M", (), {})
        )
        with pytest.raises(hooks.ExtractError, match="defines no reshape"):
            hooks.hooks()
        hooks._reset()

    def test_a_hook_that_returns_something_other_than_dicts_is_refused(
        self, monkeypatch
    ):
        monkeypatch.setattr(hooks, "_cache", {"hubspot": lambda o, p: "nope"})
        with pytest.raises(hooks.ExtractError, match="must return dicts"):
            hooks.reshape("hubspot", "contacts", {})


class TestReshapeGrammar:
    def test_a_source_without_a_hook_passes_through(self):
        payload = {"id": "cus_1"}
        assert hooks.reshape("twilio", "messages", payload) == [payload]

    def test_a_single_dict_return_is_wrapped(self, monkeypatch):
        monkeypatch.setattr(hooks, "_cache", {"hubspot": lambda o, p: {"a": 1}})
        assert hooks.reshape("hubspot", "contacts", {}) == [{"a": 1}]


class TestWooCommerceOrderTimeIsUtc:
    @staticmethod
    def _order(**extra):
        return {
            "id": 1,
            "billing": {"first_name": "Jane", "last_name": "Doe"},
            **extra,
        }

    def _reshape(self, payload):
        from app.sources.woocommerce import extract

        return extract.reshape("orders", payload)

    def test_the_gmt_field_is_preferred(self):
        out = self._reshape(
            self._order(
                date_created="2026-06-15T10:30:00",
                date_created_gmt="2026-06-15T14:30:00",
            )
        )
        assert out[0]["_placed_at"] == "2026-06-15T14:30:00"

    def test_the_local_field_is_the_fallback(self):
        out = self._reshape(self._order(date_created="2026-06-15T10:30:00"))
        assert out[0]["_placed_at"] == "2026-06-15T10:30:00"

    def test_an_order_with_no_timestamp_composes_nothing(self):
        out = self._reshape(self._order())
        assert "_placed_at" not in out[0]

    def test_the_name_composition_still_happens(self):
        out = self._reshape(self._order(date_created_gmt="2026-06-15T14:30:00"))
        assert out[0]["_full_name"] == "Jane Doe"


class TestBatchTwoCompositeNames:
    def test_salesforce_composes_its_own_capitalisation(self):
        from app.sources.salesforce import extract

        out = extract.reshape(
            "contacts", {"FirstName": "Rich", "LastName": "Hendricks"}
        )
        assert out[0]["_full_name"] == "Rich Hendricks"

    def test_salesforce_accounts_pass_through(self):
        from app.sources.salesforce import extract

        payload = {"Id": "001", "Name": "Acme"}
        assert extract.reshape("accounts", payload) == [payload]

    def test_shopify_products_pass_through(self):
        from app.sources.shopify import extract

        payload = {"id": 1, "title": "Widget"}
        assert extract.reshape("products", payload) == [payload]

    def test_woocommerce_products_pass_through(self):
        from app.sources.woocommerce import extract

        payload = {"id": 1, "name": "Widget"}
        assert extract.reshape("products", payload) == [payload]

    def test_the_seven_composite_name_hooks_agree(self):
        from app.sources.activecampaign import extract as activecampaign

        from app.sources.hubspot import extract as hubspot
        from app.sources.klaviyo import extract as klaviyo
        from app.sources.salesforce import extract as salesforce
        from app.sources.sendgrid import extract as sendgrid
        from app.sources.shopify import extract as shopify
        from app.sources.woocommerce import extract as woocommerce

        cases = [
            (
                hubspot,
                "contacts",
                {"properties": {"firstname": "Jane", "lastname": "Smith"}},
            ),
            (salesforce, "contacts", {"FirstName": "Jane", "LastName": "Smith"}),
            (shopify, "customers", {"first_name": "Jane", "last_name": "Smith"}),
            (woocommerce, "customers", {"first_name": "Jane", "last_name": "Smith"}),
            (
                klaviyo,
                "profiles",
                {"attributes": {"first_name": "Jane", "last_name": "Smith"}},
            ),
            (activecampaign, "contacts", {"firstName": "Jane", "lastName": "Smith"}),
            (sendgrid, "contacts", {"first_name": "Jane", "last_name": "Smith"}),
        ]
        for module, object_type, payload in cases:
            out = module.reshape(object_type, payload)
            assert out[0]["_full_name"] == "Jane Smith", module.__name__

    def test_woocommerce_reads_the_orders_billing_block(self):
        from app.sources.woocommerce import extract

        out = extract.reshape(
            "orders",
            {"id": 727, "billing": {"first_name": "Jane", "last_name": "Smith"}},
        )
        assert out[0]["_full_name"] == "Jane Smith"


class TestGoogleSheetsHook:
    def test_the_money_columns_are_declared_not_sniffed(self):
        from app.sources.google_sheets import extract

        assert extract.MONEY_COLUMNS == ("Amount",)

    def test_other_object_types_pass_through(self):
        from app.sources.google_sheets import extract

        payload = {"Amount": "ask Dave"}
        assert extract.reshape("tabs", payload) == [payload]

    def test_a_typed_money_cell_is_cleaned(self):
        from app.sources.google_sheets import extract

        out = extract.reshape("rows", {"Amount": "$45,000"})
        assert out[0]["_amount"] == 45000.0

    def test_a_blank_cell_is_absent_not_zero(self):
        from app.sources.google_sheets import extract

        out = extract.reshape("rows", {"Amount": "  "})
        assert "_amount" not in out[0]
        assert "_hook_skips" not in out[0]

    def test_an_uninterpretable_cell_is_a_counted_skip(self):
        from app.sources.google_sheets import extract

        out = extract.reshape("rows", {"Amount": "ask Dave"})
        assert "_amount" not in out[0]
        assert out[0]["_hook_skips"] == [["_amount", "unparseable_cell"]]

    def test_the_strict_money_transform_still_refuses_the_raw_cell(self):
        from app.engine import transforms

        with pytest.raises(transforms.TransformError):
            transforms.normalize_money("google_sheets", "rows", "$45,000")


class TestSheetNumbersAreParsedNotStripped:
    @staticmethod
    def _to_number(raw):
        from app.sources.google_sheets import extract

        return extract._to_number(raw)

    def test_an_accounting_negative_keeps_its_sign(self):
        assert self._to_number("(1,200)") == -1200.0

    def test_a_magnitude_suffix_is_refused_rather_than_truncated(self):
        assert self._to_number("$1.2M") is None

    def test_a_european_decimal_comma_is_read_correctly(self):
        assert self._to_number("45.000,00") == 45000.0

    def test_a_us_thousands_separator_still_reads(self):
        assert self._to_number("45,000.00") == 45000.0
        assert self._to_number("1,200") == 1200.0

    def test_an_ambiguous_comma_group_is_refused(self):
        assert self._to_number("1,2") is None

    def test_a_spaced_thousands_group_with_a_decimal_comma_is_read(self):
        assert self._to_number("€1 234,56") == 1234.56

    def test_a_double_dotted_string_is_refused(self):
        assert self._to_number("$4.5.0") is None

    def test_a_currency_symbol_is_still_decoration(self):
        assert self._to_number("$42.50") == 42.5

    def test_a_leading_minus_survives_the_cleaning(self):
        assert self._to_number("-$1,200") == -1200.0

    def test_a_blank_cell_is_absent(self):
        assert self._to_number("   ") is None

    @pytest.mark.parametrize("raw", ["n/a", "TBD", "1.2M", "45 EUR", "--"])
    def test_anything_carrying_a_unit_or_a_word_is_refused(self, raw):
        assert self._to_number(raw) is None


class TestGoogleAnalyticsHook:
    @staticmethod
    def _row(dims, metrics):
        return {
            "dimensionValues": [{"value": d} for d in dims],
            "metricValues": [{"value": m} for m in metrics],
        }

    def _reshape(self, payload):
        from app.sources.google_analytics import extract

        return extract.reshape("report_rows", payload)

    def test_positional_arrays_are_zipped_using_the_report_schema(self):
        out = self._reshape(
            self._row(["20260701", "Organic Search"], ["1250", "980", "3200"])
        )
        assert out[0]["_report_date"] == "20260701"
        assert out[0]["_channel"] == "Organic Search"
        assert out[0]["_sessions"] == "1250"
        assert out[0]["_users"] == "980"
        assert out[0]["_pageviews"] == "3200"

    def test_a_row_whose_arity_disagrees_is_refused_not_zipped(self):
        with pytest.raises(hooks.ExtractError):
            self._reshape(self._row(["20260701"], ["1250", "980"]))

    def test_other_object_types_pass_through(self):
        from app.sources.google_analytics import extract

        payload = {"name": "properties/123"}
        assert extract.reshape("properties", payload) == [payload]


class TestZoomAccountLink:
    @staticmethod
    def _reshape(payload):
        from app.sources.zoom import extract

        return extract.reshape("meetings", payload)

    def _meeting(self, participants, **extra):
        return {
            "host_email": "jane@elise.dev",
            "start_time": "2026-07-08T15:00:00Z",
            "duration": 30,
            "_participants": participants,
            **extra,
        }

    def test_the_attendees_domain_becomes_the_account_link(self):
        out = self._reshape(
            self._meeting(
                [{"user_email": "jane@elise.dev"}, {"user_email": "bruce@wayne.co"}]
            )
        )[0]
        assert out["_external_email"] == "bruce@wayne.co"
        assert out["_external_domain"] == "wayne.co"
        assert "_hook_skips" not in out

    @pytest.mark.parametrize("domain", sorted(FREE_MAIL_DOMAINS))
    def test_a_consumer_mailbox_is_not_an_employer(self, domain):
        mailbox = f"bruce@{domain}"
        out = self._reshape(self._meeting([{"user_email": mailbox}]))[0]
        assert "_external_domain" not in out
        assert out["_external_email"] == mailbox
        assert ["_external_domain", "free_mail_domain"] in out["_hook_skips"]

    def test_no_host_email_means_no_account_guess(self):
        out = self._reshape(
            {
                "start_time": "2026-07-08T15:00:00Z",
                "duration": 30,
                "_participants": [
                    {"user_email": "jane@elise.dev"},
                    {"user_email": "bruce@wayne.co"},
                ],
            }
        )[0]
        assert "_external_email" not in out
        assert "_external_domain" not in out

    def test_a_missing_host_is_a_counted_skip(self):
        out = self._reshape(
            {
                "start_time": "2026-07-08T15:00:00Z",
                "duration": 30,
                "_participants": [{"user_email": "bruce@wayne.co"}],
            }
        )[0]
        assert ["_external_email", "no_host_email"] in out["_hook_skips"]

    def test_an_empty_host_email_is_treated_as_missing(self):
        out = self._reshape(
            self._meeting([{"user_email": "bruce@wayne.co"}], host_email="  ")
        )[0]
        assert "_external_email" not in out
        assert ["_external_email", "no_host_email"] in out["_hook_skips"]

    def test_our_own_side_of_the_call_is_never_the_account(self):
        out = self._reshape(self._meeting([{"user_email": "alex@elise.dev"}]))[0]
        assert "_external_domain" not in out

    def test_a_participant_that_is_not_a_dict_is_skipped_over(self):
        out = self._reshape(
            self._meeting(["not a dict", {"user_email": "bruce@wayne.co"}])
        )[0]
        assert out["_external_email"] == "bruce@wayne.co"

    def test_an_entry_without_an_at_sign_is_skipped_over(self):
        out = self._reshape(
            self._meeting([{"user_email": "masked"}, {"user_email": "bruce@wayne.co"}])
        )[0]
        assert out["_external_email"] == "bruce@wayne.co"

    def test_an_all_internal_call_is_a_counted_absence(self):
        out = self._reshape(
            self._meeting(
                [{"user_email": "jane@elise.dev"}, {"user_email": "alex@elise.dev"}]
            )
        )[0]
        assert "_external_email" not in out
        assert ["_external_email", "no_external_attendee"] in out["_hook_skips"]

    def test_the_first_surviving_attendee_wins(self):
        out = self._reshape(
            self._meeting(
                [
                    {"user_email": "jane@elise.dev"},
                    {"user_email": "bruce@wayne.co"},
                    {"user_email": "tony@stark.io"},
                ]
            )
        )[0]
        assert out["_external_email"] == "bruce@wayne.co"
        assert out["_external_domain"] == "wayne.co"


class TestZoomTranscripts:
    @staticmethod
    def _reshape(payload):
        from app.sources.zoom import extract

        return extract.reshape("meetings", payload)

    def _payload(self, vtt=None, **extra):
        body = {"uuid": "abc", "topic": "Call", "_participants": []}
        if vtt is not None:
            body["_transcript_vtt"] = vtt
        body.update(extra)
        return body

    def test_a_vtt_with_speakers_becomes_dialogue_joined_by_newlines(self):
        vtt = (
            "WEBVTT\n\n1\n00:00:01.000 --> 00:00:03.000\n"
            "Jane Smith: what is blocking you?\n\n"
            "2\n00:00:04.000 --> 00:00:06.000\n"
            "Mike Ross: the deploy\n"
        )
        record = self._reshape(self._payload(vtt))[0]
        assert record["_transcript_text"] == (
            "Jane Smith: what is blocking you?\nMike Ross: the deploy"
        )

    def test_a_transcript_that_never_downloaded_is_a_counted_skip(self):
        record = self._reshape(self._payload(_transcript_error="HTTPError: 404"))[0]
        assert "_transcript_text" not in record
        assert ["_transcript_text", "download_failed"] in record["_hook_skips"]

    def test_a_vtt_with_no_speech_is_a_counted_skip(self):
        record = self._reshape(self._payload("WEBVTT\n\n"))[0]
        assert "_transcript_text" not in record
        assert ["_transcript_text", "vtt_had_no_speech"] in record["_hook_skips"]

    def test_a_speakerless_cue_is_noted_alongside_the_dialogue(self):
        vtt = (
            "WEBVTT\n\n1\n00:00:01.000 --> 00:00:03.000\n"
            "Jane Smith: hello\n\n"
            "2\n00:00:04.000 --> 00:00:06.000\n"
            "a line with no speaker label\n"
        )
        record = self._reshape(self._payload(vtt))[0]
        assert record["_transcript_text"] == "Jane Smith: hello"
        assert ["_transcript_text", "cues_without_a_speaker"] in record["_hook_skips"]

    def test_an_enormous_transcript_is_truncated_and_noted(self):
        from app.engine import transforms

        line = "Jane Smith: " + ("word " * 50) + "\n"
        cue = "1\n00:00:01.000 --> 00:00:03.000\n"
        vtt = "WEBVTT\n\n" + "\n".join(cue + line for _ in range(400))
        record = self._reshape(self._payload(vtt))[0]
        assert len(record["_transcript_text"]) <= transforms.MAX_TRANSCRIPT_CHARS
        assert ["_transcript_text", "truncated_at_cap"] in record["_hook_skips"]

    def test_the_end_time_is_start_plus_the_duration_in_minutes(self):
        record = self._reshape(
            self._payload(start_time="2026-07-08T15:00:00Z", duration=30)
        )[0]
        assert record["_ended_at"] == "2026-07-08T15:30:00Z"

    def test_an_unparseable_start_time_is_a_counted_skip(self):
        record = self._reshape(
            self._payload("WEBVTT\n", start_time="not a timestamp", duration=30)
        )[0]
        assert "_ended_at" not in record
        assert ["_ended_at", "unparseable_start_time"] in record["_hook_skips"]

    def test_other_object_types_pass_through(self):
        from app.sources.zoom import extract

        payload = {"id": "u1", "email": "jane@elise.dev"}
        assert extract.reshape("users", payload) == [payload]

    def test_the_shared_constants_are_imported_not_copied(self):
        from app.sources.zoom import extract

        from app.engine import resolver, transforms

        assert extract.FREE_MAIL_DOMAINS is resolver.FREE_MAIL_DOMAINS
        assert extract.MAX_TRANSCRIPT_CHARS is transforms.MAX_TRANSCRIPT_CHARS


class TestZoomCueParsing:
    @staticmethod
    def _parse(vtt):
        from app.sources.zoom import extract

        return extract.parse_vtt(vtt)

    def test_a_cue_carrying_only_a_number_and_a_timestamp_is_skipped(self):
        vtt = (
            "WEBVTT\n\n"
            "1\n00:00:01.000 --> 00:00:03.000\n\n"
            "2\n00:00:04.000 --> 00:00:06.000\nJane Smith: hello\n"
        )
        utterances, unattributed = self._parse(vtt)
        assert [u[0] for u in utterances] == ["Jane Smith"]
        assert unattributed == 0

    def test_a_speaker_of_eighty_chars_is_still_a_speaker(self):
        name = "x" * 80
        vtt = f"WEBVTT\n\n1\n00:00:01.000 --> 00:00:03.000\n{name}: hello\n"
        utterances, unattributed = self._parse(vtt)
        assert utterances == [(name, "hello")]
        assert unattributed == 0

    def test_a_speaker_beyond_eighty_chars_is_an_unattributed_cue(self):
        name = "x" * 81
        vtt = f"WEBVTT\n\n1\n00:00:01.000 --> 00:00:03.000\n{name}: hello\n"
        utterances, unattributed = self._parse(vtt)
        assert utterances == []
        assert unattributed == 1

    def test_a_speakerless_cue_is_counted_not_given_to_the_previous_speaker(self):
        vtt = (
            "WEBVTT\n\n1\n00:00:01.000 --> 00:00:03.000\n"
            "Jane Smith: hello\n\n"
            "2\n00:00:04.000 --> 00:00:06.000\n"
            "words from nobody\n"
        )
        utterances, unattributed = self._parse(vtt)
        assert utterances == [("Jane Smith", "hello")]
        assert unattributed == 1

    def test_a_multi_line_cue_is_joined_before_matching(self):
        vtt = (
            "WEBVTT\n\n1\n00:00:01.000 --> 00:00:03.000\n"
            "Jane Smith: part one\npart two\n"
        )
        utterances, _ = self._parse(vtt)
        assert utterances == [("Jane Smith", "part one part two")]
