# Google Sheets API v4

## Overview

Google Sheets API for reading spreadsheet data. Single endpoint reads a range of values from a sheet. Used for importing manual/external data that teams maintain in spreadsheets.

## Base URL

```
https://sheets.googleapis.com/v4
```

Mock server prefix: `/sheets/v4`

## Authentication

Google Service Account credentials with Bearer token.

```
Authorization: Bearer {access_token}
Content-Type: application/json
```

**Service Account auth:** Uses `google.oauth2.service_account.Credentials` from either:
- `GOOGLE_SERVICE_ACCOUNT_JSON` — inline JSON string
- `GOOGLE_SERVICE_ACCOUNT_FILE` — path to JSON key file

## Endpoints

### GET /spreadsheets/{spreadsheet_id}/values/{range}

Read values from a spreadsheet range.

**Path parameters:**
- `spreadsheet_id` — the spreadsheet ID from the Google Sheets URL (e.g., `1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms`)
- `range` — A1 notation range (e.g., `'Sheet1'!A1:Z100`)

**Query parameters:**
- `majorDimension` — how results are oriented: `ROWS` (default), `COLUMNS`
- `valueRenderOption` — how values are rendered: `FORMATTED_VALUE` (default), `UNFORMATTED_VALUE`, `FORMULA`
- `dateTimeRenderOption` — how dates are rendered: `SERIAL_NUMBER` (default), `FORMATTED_STRING`. Ignored when `valueRenderOption` is `FORMATTED_VALUE`.

**Example request:**

```
GET /sheets/v4/spreadsheets/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms/values/'Pipeline Data'!A1:F20?valueRenderOption=FORMATTED_VALUE&dateTimeRenderOption=FORMATTED_STRING
```

**Response:**

```json
{
  "range": "'Pipeline Data'!A1:F20",
  "majorDimension": "ROWS",
  "values": [
    ["Company", "Deal Stage", "Amount", "Close Date", "Owner", "Source"],
    ["Acme Corp", "Negotiation", "$45,000", "2026-08-15", "Jane Smith", "Inbound"],
    ["Globex Inc", "Proposal", "$28,000", "2026-07-30", "Bob Johnson", "Outbound"],
    ["Initech LLC", "Discovery", "$12,500", "2026-09-01", "Jane Smith", "Referral"],
    ["Wayne Enterprises", "Closed Won", "$85,000", "2026-06-20", "Alice Brown", "Inbound"],
    ["Hooli Technologies", "Negotiation", "$120,000", "2026-08-01", "Bob Johnson", "Partner"],
    ["Pied Piper", "Proposal", "$15,000", "2026-07-25", "Jane Smith", "Inbound"],
    ["Stark Industries", "Discovery", "$67,000", "2026-09-15", "Alice Brown", "Outbound"],
    ["Cyberdyne Systems", "Qualification", "$33,000", "2026-10-01", "Bob Johnson", "Inbound"]
  ]
}
```

**Empty spreadsheet response:**

```json
{
  "range": "'Empty Sheet'!A1:Z100",
  "majorDimension": "ROWS"
}
```

Note: `values` key is absent (not an empty array) when the range has no data. Client code checks `result.get("values") or []`.

**Single column response:**

```json
{
  "range": "'Emails'!A1:A5",
  "majorDimension": "ROWS",
  "values": [
    ["Email"],
    ["jane@acme.io"],
    ["bob@globex.com"],
    ["richard@piedpiper.com"]
  ]
}
```

## Pagination

**None.** A single request returns all values in the specified range. For large sheets, narrow the range in the request.

## Range Format

A1 notation with optional sheet name:

| Pattern | Example | Description |
|---------|---------|-------------|
| Sheet + range | `'Sheet1'!A1:Z100` | Specific range on named sheet |
| Range only | `A1:Z100` | Range on first sheet |
| Full column | `'Data'!A:F` | All rows in columns A-F |
| Single cell | `'Config'!B2` | One cell |
| Named range | `MyNamedRange` | Predefined named range |

Sheet names with spaces must be wrapped in single quotes: `'Pipeline Data'!A1:F20`

## Error Responses

**401 Unauthorized:**
```json
{
  "error": {
    "code": 401,
    "message": "Request had invalid authentication credentials. Expected OAuth 2 access token.",
    "status": "UNAUTHENTICATED"
  }
}
```

**403 Forbidden (no access to spreadsheet):**
```json
{
  "error": {
    "code": 403,
    "message": "The caller does not have permission.",
    "status": "PERMISSION_DENIED"
  }
}
```

**404 Not found:**
```json
{
  "error": {
    "code": 404,
    "message": "Requested entity was not found.",
    "status": "NOT_FOUND"
  }
}
```

**400 Bad range:**
```json
{
  "error": {
    "code": 400,
    "message": "Unable to parse range: 'NonExistentSheet'!A1:Z100",
    "status": "INVALID_ARGUMENT"
  }
}
```

**429 Rate limited:**
```json
{
  "error": {
    "code": 429,
    "message": "Quota exceeded for quota group 'ReadGroup'.",
    "status": "RESOURCE_EXHAUSTED"
  }
}
```

## Notes

- First row is typically headers — client code treats `values[0]` as column names
- All values come back as strings when using `FORMATTED_VALUE` (numbers include formatting like `$45,000`)
- Use `UNFORMATTED_VALUE` to get raw numbers without formatting
- Empty cells at the end of a row are trimmed (row arrays may have different lengths)
- The real API uses Google API client library (`sheets v4`), but the mock serves the same JSON over plain HTTP
- Config: `GOOGLE_SPREADSHEET_ID` (from the sheet URL)
- Retry: 3 attempts, exponential backoff (2^attempt seconds), on 429/500/502/503

## Reference

- [Method: spreadsheets.values.get](https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets.values/get) -- Endpoint parameters and request/response details
- [REST Resource: spreadsheets.values](https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets.values) -- ValueRange resource definition
- [Read & write cell values](https://developers.google.com/workspace/sheets/api/guides/values) -- Guide for reading and writing spreadsheet data
