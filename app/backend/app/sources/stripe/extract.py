SOURCE = "stripe"

_MONTHS = {"day": 1 / 30.437, "week": 1 / 4.348, "month": 1.0, "year": 12.0}

_ZERO_DECIMAL = frozenset(
    {
        "bif",
        "clp",
        "djf",
        "gnf",
        "jpy",
        "kmf",
        "krw",
        "mga",
        "pyg",
        "rwf",
        "ugx",
        "vnd",
        "vuv",
        "xaf",
        "xof",
        "xpf",
    }
)
_THREE_DECIMAL = frozenset({"bhd", "iqd", "jod", "kwd", "lyd", "omr", "tnd"})


def _minor_units_per_major(currency) -> int:
    code = str(currency or "").strip().lower()
    if code in _ZERO_DECIMAL:
        return 1
    if code in _THREE_DECIMAL:
        return 1000
    return 100


def _monthly_cents(item: dict) -> float:
    price = item.get("price") or {}
    unit_amount = price.get("unit_amount")
    if unit_amount is None:
        unit_amount = price.get("unit_amount_decimal")
    if unit_amount is None:
        raise ValueError("item price carries no unit_amount")
    quantity = item.get("quantity")
    quantity = 1 if quantity is None else float(quantity)
    recurring = price.get("recurring") or {}
    interval = str(recurring.get("interval") or "month").lower()
    if interval not in _MONTHS:
        raise ValueError(f"unknown billing interval {interval!r}")
    interval_count = float(recurring.get("interval_count") or 1)
    if interval_count <= 0:
        raise ValueError("interval_count must be positive")
    period_months = _MONTHS[interval] * interval_count
    return float(unit_amount) * quantity / period_months


def reshape(object_type: str, payload: dict) -> list[dict]:
    if object_type != "subscriptions":
        return [payload]

    record = dict(payload)
    container = payload.get("items") or {}
    items = container.get("data") or []
    if container.get("has_more"):
        record["_hook_skips"] = [["_amount_monthly", "items_truncated"]]
        return [record]
    if not isinstance(items, list) or not items:
        record["_hook_skips"] = [["_amount_monthly", "no_subscription_items"]]
        return [record]
    try:
        total = sum(_monthly_cents(i) for i in items if isinstance(i, dict))
    except (ValueError, TypeError) as e:
        record["_hook_skips"] = [["_amount_monthly", _reason(e)]]
        return [record]
    per_major = _minor_units_per_major(payload.get("currency"))
    record["_amount_monthly"] = round(total / per_major, 6)
    return [record]


def _reason(error: Exception) -> str:
    text = str(error)
    if "interval" in text:
        return "bad_billing_interval"
    if "unit_amount" in text:
        return "no_unit_amount"
    return "unfoldable_items"
