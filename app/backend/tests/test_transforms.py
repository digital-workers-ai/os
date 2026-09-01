from datetime import datetime

import pytest

from app.engine import transforms as t


class TestMoney:
    def test_sub_cent_prices_survive_storage(self):
        assert t.normalize_money("hubspot", "messages", "-0.0075") == -0.0075

    def test_float_noise_is_still_killed(self):
        assert t.normalize_money("hubspot", "x", 0.1 + 0.2) == 0.3

    def test_string_typed_numbers_coerce(self):
        assert t.normalize_money("hubspot", "invoices", "4900") == 4900.0

    def test_non_numeric_is_a_named_skip(self):
        with pytest.raises(t.TransformError) as e:
            t.normalize_money("hubspot", "invoices", "not money")
        assert e.value.reason == "not_a_number"

    def test_booleans_are_not_numbers(self):
        with pytest.raises(t.TransformError):
            t.normalize_money("hubspot", "invoices", True)

    def test_infinity_is_refused_before_it_reaches_the_db(self):
        with pytest.raises(t.TransformError) as e:
            t.normalize_money("hubspot", "invoices", float("inf"))
        assert e.value.reason == "not_finite"

    def test_nan_is_refused(self):
        with pytest.raises(t.TransformError):
            t.normalize_money("hubspot", "invoices", float("nan"))


class TestOversizedNumbers:
    HUGE = int("1" * 400)

    def test_an_oversized_int_is_a_transform_error(self):
        with pytest.raises(t.TransformError):
            t.normalize_money("hubspot", "deals", self.HUGE)

    def test_the_string_form_was_already_safe_and_stays_safe(self):
        with pytest.raises(t.TransformError):
            t.normalize_money("hubspot", "deals", "1" * 400)


class TestDomain:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("acme.io", "acme.io"),
            ("ACME.IO", "acme.io"),
            ("  acme.io  ", "acme.io"),
            ("https://acme.com/about", "acme.com"),
            ("http://www.acme.com", "acme.com"),
            ("https://acme.com:8443/x?y=1#z", "acme.com"),
            ("acme.com.", "acme.com"),
            ("ada@acme.com", "acme.com"),
            ("Ada.Lovelace+tag@ACME.co.uk", "acme.co.uk"),
        ],
    )
    def test_url_host_and_email_all_land_on_the_same_label(self, raw, expected):
        assert t.normalize_domain("salesforce", "accounts", raw) == expected

    def test_the_salesforce_hubspot_pair_agrees(self):
        assert t.normalize_domain(
            "salesforce", "accounts", "https://acme.io"
        ) == t.normalize_domain("hubspot", "companies", "acme.io")

    def test_garbage_is_refused_not_guessed(self):
        with pytest.raises(t.TransformError) as e:
            t.normalize_domain("hubspot", "companies", "not a domain")
        assert e.value.reason == "not_a_domain"

    def test_bare_word_has_no_tld(self):
        with pytest.raises(t.TransformError):
            t.normalize_domain("hubspot", "companies", "acme")

    def test_empty_is_refused(self):
        with pytest.raises(t.TransformError):
            t.normalize_domain("hubspot", "companies", "   ")


class TestEmail:
    def test_lowercases_and_strips(self):
        assert (
            t.normalize_email("hubspot", "contacts", "  Jane@ACME.io ")
            == "jane@acme.io"
        )

    def test_subaddress_tags_are_stripped(self):
        assert (
            t.normalize_email("hubspot", "contacts", "jane+crm@acme.io")
            == "jane@acme.io"
        )

    def test_a_plus_in_the_domain_is_not_a_tag(self):
        assert (
            t.normalize_email("hubspot", "contacts", "jane@ac+me.io") == "jane@ac+me.io"
        )

    def test_not_an_email(self):
        with pytest.raises(t.TransformError) as e:
            t.normalize_email("hubspot", "contacts", "jane at acme")
        assert e.value.reason == "not_an_email"


class TestStatus:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("Active", "active"),
            ("PAST_DUE", "past_due"),
            ("past due", "past_due"),
            ("Closed-Won", "closed_won"),
            ("  trialing ", "trialing"),
        ],
    )
    def test_one_vocabulary(self, raw, expected):
        assert t.normalize_status("hubspot", "deals", raw) == expected

    def test_near_synonyms_are_folded_per_source_and_object_type(self):
        assert t.normalize_status("hubspot", "deals", "closedwon") == "closed_won"
        assert t.normalize_status("hubspot", "deals", "closedlost") == "closed_lost"

    def test_the_synonym_table_is_scoped_not_global(self):
        assert t.normalize_status("hubspot", "deals", "enabled") == "enabled"
        assert t.normalize_status("hubspot", "contacts", "closedwon") == "closedwon"

    def test_folding_is_scoped_to_the_deal_object_types(self):
        assert t.normalize_status("hubspot", "invoices", "closedwon") == "closedwon"
        assert t.normalize_status("hubspot", "tickets", "Closed Won") == "closed_won"


class TestSynonymsLoader:
    def test_the_shipped_file_loads_and_folds_closedwon(self):
        doc = t.load_synonyms()
        assert doc["hubspot"]["deals"]["closedwon"] == "closed_won"

    def test_the_default_load_is_memoized(self):
        assert t.load_synonyms() is t.load_synonyms()

    def test_an_explicit_path_bypasses_the_cache(self, tmp_path):
        path = tmp_path / "synonyms.yaml"
        path.write_text("stripe:\n  invoices:\n    uncollectible: void\n")
        doc = t.load_synonyms(path)
        assert doc == {"stripe": {"invoices": {"uncollectible": "void"}}}
        assert t.load_synonyms() != doc

    def test_a_non_mapping_top_level_is_refused(self, tmp_path):
        path = tmp_path / "synonyms.yaml"
        path.write_text("- hubspot\n")
        with pytest.raises(t.TransformError, match="top level must be a mapping"):
            t.load_synonyms(path)

    def test_a_non_mapping_source_value_is_refused(self, tmp_path):
        path = tmp_path / "synonyms.yaml"
        path.write_text("hubspot: deals\n")
        with pytest.raises(t.TransformError, match="hubspot must map object types"):
            t.load_synonyms(path)

    def test_a_non_mapping_object_type_value_is_refused(self, tmp_path):
        path = tmp_path / "synonyms.yaml"
        path.write_text("hubspot:\n  deals:\n    - closedwon\n")
        with pytest.raises(t.TransformError, match="hubspot.deals must map"):
            t.load_synonyms(path)

    def test_a_non_str_synonym_value_is_refused(self, tmp_path):
        path = tmp_path / "synonyms.yaml"
        path.write_text("hubspot:\n  deals:\n    closedwon: 3\n")
        with pytest.raises(
            t.TransformError, match="hubspot.deals.closedwon must be a string"
        ):
            t.load_synonyms(path)


class TestDateIsAlwaysReparseable:
    @pytest.mark.parametrize("year", [1, 99, 500, 999, 1000, 2026])
    def test_a_year_under_1000_is_zero_padded(self, year):
        out = t.normalize_date("hubspot", "deals", f"{year:04d}-06-01T00:00:00Z")
        assert out.startswith(f"{year:04d}-06-01"), out
        assert datetime.fromisoformat(out.replace("Z", "+00:00")).year == year

    def test_the_dotnet_min_date_survives_the_round_trip(self):
        out = t.normalize_date("hubspot", "deals", "0001-01-01T00:00:00Z")
        assert out == "0001-01-01T00:00:00Z"
        assert datetime.fromisoformat(out.replace("Z", "+00:00"))

    @pytest.mark.parametrize(
        "raw",
        [
            "0001-01-01T00:00:00Z",
            "0001-01-01",
            "0500-06-01T12:00:00+00:00",
        ],
    )
    def test_every_branch_returns_something_reparseable(self, raw):
        out = t.normalize_date("hubspot", "deals", raw)
        assert len(out.split("-")[0]) == 4, out
        assert datetime.fromisoformat(out.replace("Z", "+00:00"))


class TestDate:
    def test_hubspot_iso_with_millis_and_z(self):
        assert (
            t.normalize_date("hubspot", "companies", "2026-07-01T10:00:00.000Z")
            == "2026-07-01T10:00:00Z"
        )

    def test_plain_date(self):
        assert (
            t.normalize_date("hubspot", "deals", "2026-08-01") == "2026-08-01T00:00:00Z"
        )

    def test_garbage_is_refused(self):
        with pytest.raises(t.TransformError) as e:
            t.normalize_date("hubspot", "deals", "last tuesday")
        assert e.value.reason == "not_a_date"

    def test_an_isoformat_only_aware_timestamp_lands_in_utc(self):
        assert (
            t.normalize_date("hubspot", "deals", "2026-07-01 12:30:00+02:00")
            == "2026-07-01T10:30:00Z"
        )


class TestCurrency:
    def test_lowercases(self):
        assert t.normalize_currency("stripe", "subscriptions", "USD") == "usd"

    def test_rejects_anything_that_is_not_a_code(self):
        with pytest.raises(t.TransformError):
            t.normalize_currency("stripe", "subscriptions", "dollars")


class TestText:
    def test_text_collapses_whitespace(self):
        assert t.normalize_text("hubspot", "companies", " Acme   Corp ") == "Acme Corp"

    def test_empty_text_refused(self):
        with pytest.raises(t.TransformError):
            t.normalize_text("hubspot", "companies", "")


class TestRef:
    def test_ref_strips_surrounding_whitespace(self):
        assert t.normalize_ref("stripe", "subscriptions", " cus_ABC ") == "cus_ABC"

    def test_ref_keeps_case_because_vendor_ids_are_opaque(self):
        assert t.normalize_ref("hubspot", "deals", " Hs-Deal-01 ") == "Hs-Deal-01"

    @pytest.mark.parametrize("raw", ["", "   "])
    def test_an_empty_ref_is_refused(self, raw):
        with pytest.raises(t.TransformError):
            t.normalize_ref("stripe", "subscriptions", raw)


class TestEpochTimestamps:
    EPOCH_2026 = 1_785_000_000

    def test_unix_seconds(self):
        assert (
            t.normalize_date("stripe", "subscriptions", 1719400000)
            == "2024-06-26T11:06:40Z"
        )

    def test_an_integer_too_wide_for_a_float_is_refused(self):
        with pytest.raises(t.TransformError) as e:
            t.normalize_date("stripe", "subscriptions", 10**400)
        assert e.value.reason == "not_a_date"

    def test_unix_seconds_as_string(self):
        assert (
            t.normalize_date("hubspot", "deals", "1720500000") == "2024-07-09T04:40:00Z"
        )

    def test_milliseconds_land_on_the_same_day_as_their_seconds_twin(self):
        millis = t.normalize_date("hubspot", "deals", self.EPOCH_2026 * 1000)
        seconds = t.normalize_date("hubspot", "deals", self.EPOCH_2026)
        assert millis[:10] == seconds[:10]

    def test_the_lower_bound_itself_is_accepted(self):
        assert t.normalize_date("hubspot", "deals", 100_000_000).startswith("1973-")

    def test_a_number_below_the_lower_bound_is_refused(self):
        with pytest.raises(t.TransformError):
            t.normalize_date("hubspot", "deals", -1)

    def test_the_upper_bound_itself_is_accepted(self):
        assert t.normalize_date("hubspot", "deals", 4_000_000_000).startswith("2096-")

    def test_a_number_beyond_even_milliseconds_is_refused(self):
        with pytest.raises(t.TransformError):
            t.normalize_date("hubspot", "deals", 4_000_000_000 * 1000)

    def test_a_bare_year_is_not_a_unix_timestamp(self):
        with pytest.raises(t.TransformError):
            t.normalize_date("hubspot", "deals", "2026")

    def test_a_negative_epoch_is_read_by_magnitude_with_its_sign(self):
        assert t.normalize_date("hubspot", "deals", -self.EPOCH_2026).startswith("19")


class TestPhone:
    def test_a_leading_plus_survives(self):
        assert (
            t.normalize_phone("zendesk", "users", "+1 (415) 555-0100") == "+14155550100"
        )

    def test_formatting_is_stripped(self):
        assert t.normalize_phone("intercom", "contacts", "415.555.0100") == "4155550100"

    def test_a_bare_number_is_not_given_a_country_code(self):
        assert t.normalize_phone("zendesk", "users", "4155550100") == "4155550100"

    def test_seven_digits_is_the_floor(self):
        assert t.normalize_phone("zendesk", "users", "555-0100") == "5550100"

    def test_six_digits_is_below_the_floor(self):
        with pytest.raises(t.TransformError) as e:
            t.normalize_phone("zendesk", "users", "555-010")
        assert e.value.reason == "not_a_phone"

    def test_fifteen_digits_is_the_ceiling(self):
        assert (
            t.normalize_phone("zendesk", "users", "+123456789012345")
            == "+123456789012345"
        )

    def test_sixteen_digits_is_beyond_the_ceiling(self):
        with pytest.raises(t.TransformError) as e:
            t.normalize_phone("zendesk", "users", "+1234567890123456")
        assert e.value.reason == "not_a_phone"

    @pytest.mark.parametrize("raw", ["", "n/a", "123"])
    def test_a_non_phone_is_refused(self, raw):
        with pytest.raises(t.TransformError) as e:
            t.normalize_phone("klaviyo", "profiles", raw)
        assert e.value.reason == "not_a_phone"


class TestNumber:
    def test_a_string_typed_number_coerces(self):
        assert t.normalize_number("klaviyo", "flows", "42.5") == 42.5

    def test_float_noise_is_killed_at_six_decimals(self):
        assert t.normalize_number("sendgrid", "singlesends", 0.1 + 0.2) == 0.3

    def test_the_seventh_decimal_is_rounded_away(self):
        assert t.normalize_number("sendgrid", "singlesends", 1.23456789) == 1.234568

    def test_booleans_are_refused(self):
        with pytest.raises(t.TransformError) as e:
            t.normalize_number("klaviyo", "flows", True)
        assert e.value.reason == "not_a_number"

    def test_nan_is_refused(self):
        with pytest.raises(t.TransformError):
            t.normalize_number("klaviyo", "flows", float("nan"))

    def test_infinity_is_refused(self):
        with pytest.raises(t.TransformError) as e:
            t.normalize_number("klaviyo", "flows", float("inf"))
        assert e.value.reason == "not_finite"


class TestRegistry:
    def test_the_batch_one_transforms_are_registered_with_their_types(self):
        assert t.TRANSFORMS["normalize_phone"] is t.normalize_phone
        assert t.TRANSFORMS["normalize_number"] is t.normalize_number
        assert t.TRANSFORM_TYPES["normalize_phone"] == "string"
        assert t.TRANSFORM_TYPES["normalize_number"] == "number"

    def test_every_yaml_name_resolves(self):
        for label, name in t.load_map().items():
            assert name in t.TRANSFORMS, f"{label} names an unknown transform"

    def test_every_registry_entry_declares_its_type(self):
        assert set(t.TRANSFORMS) == set(t.TRANSFORM_TYPES)

    def test_unknown_name_is_an_error_not_a_passthrough(self):
        with pytest.raises(t.TransformError) as e:
            t.apply("normalise_email", "hubspot", "contacts", "x@y.com")
        assert e.value.reason == "unknown_transform"

    def test_every_transform_takes_source_and_object_type(self):
        import inspect

        for name, fn in t.TRANSFORMS.items():
            params = list(inspect.signature(fn).parameters)
            assert params == ["source", "object_type", "value"], name


class TestATagOnlyLocalPartKeepsItsAddress:
    def test_two_tag_only_addresses_stay_apart(self):
        first = t.normalize_email("hubspot", "contacts", "+jane@acme.io")
        second = t.normalize_email("hubspot", "contacts", "+bob@acme.io")
        assert first != second

    def test_the_address_is_kept_whole(self):
        assert (
            t.normalize_email("hubspot", "contacts", "+jane@acme.io") == "+jane@acme.io"
        )

    def test_an_ordinary_tag_is_still_stripped(self):
        assert (
            t.normalize_email("hubspot", "contacts", "jane+crm@acme.io")
            == "jane@acme.io"
        )

    def test_the_output_is_always_something_it_would_accept_again(self):
        for address in ("+jane@acme.io", "jane+crm@acme.io", "jane@acme.io", "+@0.0"):
            once = t.normalize_email("hubspot", "contacts", address)
            assert t.normalize_email("hubspot", "contacts", once) == once
