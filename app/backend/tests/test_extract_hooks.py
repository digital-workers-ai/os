import pkgutil

import pytest

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


class TestDiscovery:
    def test_every_source_package_with_an_extract_module_is_a_hook(self):
        assert set(hooks.hooks()) == {"hubspot", "stripe"}

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
        assert hooks.reshape("salesforce", "accounts", payload) == [payload]

    def test_a_single_dict_return_is_wrapped(self, monkeypatch):
        monkeypatch.setattr(hooks, "_cache", {"hubspot": lambda o, p: {"a": 1}})
        assert hooks.reshape("hubspot", "contacts", {}) == [{"a": 1}]
