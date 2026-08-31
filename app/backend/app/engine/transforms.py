import math
import re
from datetime import UTC, datetime

from app.caches import KNOWLEDGE_DIR, load_mapping

DEFAULT_TRANSFORMS = KNOWLEDGE_DIR / "transforms.yaml"

_WS = re.compile(r"\s+")
_HOST = re.compile(
    r"^[a-z0-9]([a-z0-9\-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9\-]*[a-z0-9])?)+$"
)
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_CURRENCY = re.compile(r"^[a-z]{3}$")


class TransformError(ValueError):
    def __init__(self, reason: str, detail: str = ""):
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason


def _finite_float(value) -> float:
    if isinstance(value, bool):
        raise TransformError("not_a_number", repr(value))
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        raise TransformError("not_a_number", str(value)[:40]) from None
    if not math.isfinite(number):
        raise TransformError("not_finite", str(value)[:40])
    return number


def normalize_money(source, object_type, value):
    return round(_finite_float(value), 6)


def normalize_currency(source, object_type, value):
    code = str(value).strip().lower()
    if not _CURRENCY.match(code):
        raise TransformError("not_a_currency_code", code[:40])
    return code


def normalize_email(source, object_type, value):
    email = str(value).strip().lower()
    if not _EMAIL.match(email):
        raise TransformError("not_an_email", email[:60])
    local, _, domain = email.partition("@")
    if "+" not in local:
        return email
    base = local.split("+", 1)[0]
    if not base:
        return email
    return f"{base}@{domain}"


def normalize_domain(source, object_type, value):
    text = str(value).strip().lower()
    if not text:
        raise TransformError("empty")
    if "@" in text:
        text = text.rsplit("@", 1)[-1]
    text = re.sub(r"^[a-z][a-z0-9+.\-]*://", "", text)
    text = text.split("/", 1)[0]
    text = text.split("?", 1)[0].split("#", 1)[0]
    text = text.split(":", 1)[0]
    text = text.rstrip(".")
    text = text.removeprefix("www.")
    if not _HOST.match(text):
        raise TransformError("not_a_domain", text[:60])
    return text


def normalize_text(source, object_type, value):
    text = _WS.sub(" ", str(value)).strip()
    if not text:
        raise TransformError("empty")
    return text


_STATUS_SYNONYMS = {
    ("hubspot", "deals"): {"closedwon": "closed_won", "closedlost": "closed_lost"},
}


def normalize_status(source, object_type, value):
    status = _WS.sub("_", str(value).strip().lower()).replace("-", "_")
    status = re.sub(r"_+", "_", status).strip("_")
    if not status:
        raise TransformError("empty")
    return _STATUS_SYNONYMS.get((source, object_type), {}).get(status, status)


_DATE_FORMATS = (
    "%Y-%m-%dT%H:%M:%S.%f%z",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d",
)


def _iso_utc(dt: datetime) -> str:
    return (
        f"{dt.year:04d}-{dt.month:02d}-{dt.day:02d}"
        f"T{dt.hour:02d}:{dt.minute:02d}:{dt.second:02d}Z"
    )


def _aware_utc(parsed: datetime) -> datetime:
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _parse_format(text: str, fmt: str) -> datetime:
    if fmt.endswith("%z"):
        return datetime.strptime(text, fmt).astimezone(UTC)
    return datetime.strptime(text, fmt).replace(tzinfo=UTC)


def normalize_date(source, object_type, value):
    text = str(value).strip()
    if not text:
        raise TransformError("empty")
    for fmt in _DATE_FORMATS:
        try:
            parsed = _parse_format(text, fmt)
        except ValueError:
            continue
        return _iso_utc(parsed)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        raise TransformError("not_a_date", text[:40]) from None
    return _iso_utc(_aware_utc(parsed))


TRANSFORMS = {
    "normalize_currency": normalize_currency,
    "normalize_date": normalize_date,
    "normalize_domain": normalize_domain,
    "normalize_email": normalize_email,
    "normalize_money": normalize_money,
    "normalize_status": normalize_status,
    "normalize_text": normalize_text,
}

TRANSFORM_TYPES = {
    "normalize_currency": "string",
    "normalize_date": "date",
    "normalize_domain": "string",
    "normalize_email": "string",
    "normalize_money": "number",
    "normalize_status": "string",
    "normalize_text": "string",
}


def apply(name: str, source: str, object_type: str, value):
    try:
        fn = TRANSFORMS[name]
    except KeyError:
        raise TransformError("unknown_transform", name) from None
    result = fn(source, object_type, value)
    if result is None:
        raise TransformError("refused")
    return result


def load_map(path=None) -> dict:
    return load_mapping(path or DEFAULT_TRANSFORMS, TransformError)
