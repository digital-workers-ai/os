import re
from datetime import date
from typing import Annotated

from fastapi import Path
from fastapi.exceptions import RequestValidationError
from pydantic import BeforeValidator

ISO_DAY = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


def _iso_day(value: str) -> str:
    if not ISO_DAY.fullmatch(value):
        raise ValueError("a date is YYYY-MM-DD")
    return value


Day = Annotated[date, BeforeValidator(_iso_day)]
Seq = Annotated[int, Path(ge=-(2**63), le=2**63 - 1)]
Version = Annotated[int, Path(ge=-(2**31), le=2**31 - 1)]


def refused(message: str) -> RequestValidationError:
    return RequestValidationError(
        [{"loc": ("query",), "msg": message, "type": "value_error"}]
    )
