import math
import re
from datetime import UTC, datetime
from pathlib import Path

from app.caches import DEFINITIONS_DIR, load_mapping, register

DEFAULT_TRANSFORMS = DEFINITIONS_DIR / "transforms.yaml"
DEFAULT_SYNONYMS = DEFINITIONS_DIR / "synonyms.yaml"

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


_MICROS = {"google_ads"}

MAX_TRANSCRIPT_CHARS = 60_000


def normalize_money(source, object_type, value):
    amount = _finite_float(value)
    if source in _MICROS:
        amount = amount / 1_000_000
    return round(amount, 6)


def normalize_number(source, object_type, value):
    return round(_finite_float(value), 6)


def normalize_phone(source, object_type, value):
    text = str(value).strip()
    plus = text.startswith("+")
    digits = re.sub(r"\D", "", text)
    if not 7 <= len(digits) <= 15:
        raise TransformError("not_a_phone", text[:40])
    return f"+{digits}" if plus else digits


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


def normalize_ref(source, object_type, value):
    ref = str(value).strip()
    if not ref:
        raise TransformError("empty")
    return ref


def normalize_text(source, object_type, value):
    text = _WS.sub(" ", str(value)).strip()
    if not text:
        raise TransformError("empty")
    return text


def normalize_transcript(source, object_type, value):
    lines = [line.strip() for line in str(value).replace("\r\n", "\n").split("\n")]
    text = "\n".join(line for line in lines if line)
    return text[:MAX_TRANSCRIPT_CHARS]


_synonyms_cache: dict | None = None


@register
def _reset() -> None:
    global _synonyms_cache
    _synonyms_cache = None


def load_synonyms(path=None) -> dict:
    global _synonyms_cache
    if path is None and _synonyms_cache is not None:
        return _synonyms_cache
    target = Path(path or DEFAULT_SYNONYMS)
    doc = load_mapping(target, TransformError)
    for source, object_types in doc.items():
        if not isinstance(object_types, dict):
            raise TransformError(
                f"{target.name}: {source} must map object types to synonym tables"
            )
        for object_type, table in object_types.items():
            if not isinstance(table, dict):
                raise TransformError(
                    f"{target.name}: {source}.{object_type} must map "
                    "raw statuses to canonical ones"
                )
            for raw, canonical in table.items():
                if not isinstance(canonical, str):
                    raise TransformError(
                        f"{target.name}: {source}.{object_type}.{raw} must be a string"
                    )
    if path is None:
        _synonyms_cache = doc
    return doc


def normalize_status(source, object_type, value):
    status = _WS.sub("_", str(value).strip().lower()).replace("-", "_")
    status = re.sub(r"_+", "_", status).strip("_")
    if not status:
        raise TransformError("empty")
    return load_synonyms().get(source, {}).get(object_type, {}).get(status, status)


_UNIX_MIN, _UNIX_MAX = 100_000_000, 4_000_000_000

_DATE_FORMATS = (
    "%Y-%m-%dT%H:%M:%S.%f%z",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S.%f",
    "%a, %d %b %Y %H:%M:%S %z",
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
    compact = str(value).strip()
    if re.fullmatch(r"\d{8}", compact) and "1970" <= compact[:4] <= "2100":
        try:
            return _iso_utc(datetime.strptime(compact, "%Y%m%d").replace(tzinfo=UTC))
        except ValueError:
            raise TransformError("not_a_date", compact) from None
    numeric = value.strip() if isinstance(value, str) else value
    if isinstance(value, int | float) or (
        isinstance(numeric, str) and re.fullmatch(r"-?\d+(\.\d+)?", numeric)
    ):
        try:
            seconds = float(numeric)
        except OverflowError:
            raise TransformError("not_a_date", str(value)[:40]) from None
        if abs(seconds) >= _UNIX_MAX * 1000:
            raise TransformError("not_a_date", str(value)[:40])
        if abs(seconds) > _UNIX_MAX:
            seconds = seconds / 1000
        if not _UNIX_MIN <= abs(seconds) <= _UNIX_MAX:
            raise TransformError("not_a_date", str(value)[:40])
        return _iso_utc(datetime.fromtimestamp(seconds, tz=UTC))
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
    "normalize_number": normalize_number,
    "normalize_phone": normalize_phone,
    "normalize_ref": normalize_ref,
    "normalize_status": normalize_status,
    "normalize_text": normalize_text,
    "normalize_transcript": normalize_transcript,
}

TRANSFORM_TYPES = {
    "normalize_currency": "string",
    "normalize_date": "date",
    "normalize_domain": "string",
    "normalize_email": "string",
    "normalize_money": "number",
    "normalize_number": "number",
    "normalize_phone": "string",
    "normalize_ref": "string",
    "normalize_status": "string",
    "normalize_text": "string",
    "normalize_transcript": "string",
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
