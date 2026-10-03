"""
Google Sheets API v4 mock provider.
Contract: seeds/docs/09-google-sheets.md

Single GET endpoint for reading spreadsheet values. No pagination.
"""

from fastapi import APIRouter, Request, Query
from seeds.helpers import require_bearer
from seeds.world import VENDORS

router = APIRouter()

_SHEETS = VENDORS["google_sheets"]
_PIPELINE_DATA = _SHEETS["pipeline"]
_EMAILS_DATA = _SHEETS["emails"]


def _detect_sheet(range_str: str):
    lower = range_str.lower()
    if "email" in lower:
        return "emails"
    if "empty" in lower:
        return "empty"
    return "pipeline"


@router.get("/spreadsheets/{spreadsheet_id}/values/{range:path}")
async def get_values(
    request: Request,
    spreadsheet_id: str,
    range: str,
    majorDimension: str = Query("ROWS"),
    valueRenderOption: str = Query("FORMATTED_VALUE"),
    dateTimeRenderOption: str = Query("SERIAL_NUMBER"),
):
    require_bearer(request)

    sheet = _detect_sheet(range)

    if sheet == "empty":
        return {"range": range, "majorDimension": majorDimension}

    if sheet == "emails":
        return {"range": range, "majorDimension": majorDimension, "values": _EMAILS_DATA}

    return {"range": range, "majorDimension": majorDimension, "values": _PIPELINE_DATA}
