from itertools import zip_longest

from app.sources.util import client_for, content_id

SOURCE = "google_sheets"

OBSERVED_AT: dict = {}

ACCOUNT_CURRENCY = "usd"


async def pull(session, store):
    api = client_for(SOURCE)
    data = await api.get("/spreadsheets/mock_spreadsheet_id/values/Pipeline!A1:F20")
    rows = data.get("values", [])
    if len(rows) <= 1:
        return None

    headers = rows[0]
    notes: dict = {}
    for row in rows[1:]:
        if len(row) > len(headers):
            notes["ragged_rows"] = notes.get("ragged_rows", 0) + 1
        record = {}
        for i, (header, value) in enumerate(zip_longest(headers, row)):
            record[header or f"_extra_{i}"] = value
        key_value = str(record.get(headers[0]) or "").strip()
        source_id = key_value or content_id(str(record))
        await store(
            session,
            source=SOURCE,
            object_type="rows",
            source_id=source_id,
            raw_payload=record,
        )
    return notes or None
