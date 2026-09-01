import re

MONEY_COLUMNS = ("Amount",)

_CURRENCY_SYMBOLS = "$€£¥₹"
_HAS_LETTER = re.compile(r"[^\W\d_]")


def _to_number(raw):
    text = str(raw).strip()
    if not text:
        return None

    negative = False
    if text.startswith("(") and text.endswith(")"):
        negative, text = True, text[1:-1].strip()
    if text.startswith("-"):
        negative, text = True, text[1:].strip()
    text = text.lstrip(_CURRENCY_SYMBOLS).strip()
    if text.startswith("-"):
        negative, text = True, text[1:].strip()

    if _HAS_LETTER.search(text):
        return None
    had_space = " " in text
    text = text.replace(" ", "")

    if "," in text and "." in text:
        thousands, decimal = (
            (",", ".") if text.rfind(".") > text.rfind(",") else (".", ",")
        )
        text = text.replace(thousands, "").replace(decimal, ".")
    elif "," in text:
        if had_space:
            text = text.replace(",", ".")
        else:
            head, _, tail = text.rpartition(",")
            if len(tail) == 3 and tail.isdigit() and head:
                text = text.replace(",", "")
            else:
                return None

    try:
        value = float(text)
    except ValueError:
        return None
    return -value if negative else value


def reshape(object_type: str, payload: dict) -> list[dict]:
    if object_type != "rows":
        return [payload]
    record = dict(payload)
    skips = []
    for column in MONEY_COLUMNS:
        raw = payload.get(column)
        if raw is None or not str(raw).strip():
            continue
        value = _to_number(raw)
        if value is None:
            skips.append([f"_{column.lower()}", "unparseable_cell"])
            continue
        record[f"_{column.lower()}"] = value
    if skips:
        record["_hook_skips"] = skips
    return [record]
