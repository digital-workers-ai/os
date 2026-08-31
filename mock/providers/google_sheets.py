"""
Google Sheets API v4 mock provider.
Contract: seeds/docs/09-google-sheets.md

Single GET endpoint for reading spreadsheet values. No pagination.
"""

from fastapi import APIRouter, Request, Query
from seeds.helpers import require_bearer
from seeds.world import COMPANIES, PEOPLE_BY_COMPANY, SUBSCRIPTIONS_BY_COMPANY

router = APIRouter()

_PIPELINE_DATA = [
    ["Company", "Deal Stage", "Amount", "Close Date", "Owner", "Source"],
    ["Acme Corp", "Negotiation", "$45,000", "2026-08-15", "Jane Smith", "Inbound"],
    ["Globex Inc", "Proposal", "$28,000", "2026-07-30", "Bob Johnson", "Outbound"],
    ["Initech LLC", "Discovery", "$12,500", "2026-09-01", "Jane Smith", "Referral"],
    ["Wayne Enterprises", "Closed Won", "$85,000", "2026-06-20", "Alice Brown", "Inbound"],
    ["Hooli Technologies", "Negotiation", "$120,000", "2026-08-01", "Bob Johnson", "Partner"],
    ["Pied Piper", "Proposal", "$15,000", "2026-07-25", "Jane Smith", "Inbound"],
    ["Stark Industries", "Discovery", "$67,000", "2026-09-15", "Alice Brown", "Outbound"],
    ["Cyberdyne Systems", "Qualification", "$33,000", "2026-10-01", "Bob Johnson", "Inbound"],
]

_EMAILS_DATA = [
    ["Email"],
    ["jane@acme.io"],
    ["bob@globex.com"],
    ["richard@piedpiper.com"],
]


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
