# Amplitude API

> Category: Analytics

---

## Base URL

```
https://amplitude.com
```

For EU data center:
```
https://analytics.eu.amplitude.com
```

## Authentication

HTTP Basic Auth with API key as username and secret key as password:

```
Authorization: Basic base64({api_key}:{secret_key})
```

```bash
curl -u "amp_api_key_mock:amp_secret_mock" https://amplitude.com/api/2/export
```

Returns `401 Unauthorized` without valid credentials.

---

## Endpoints

### GET /api/2/export

Export raw event data. Returns a **zipped archive of gzipped JSON files** — one JSON object per line in each file. Depending on data volume, there can be several files per hour.

The archive is compressed **twice**. The response body is a zip; each member inside it is itself gzipped and named `<project_id>/<project_id>_<YYYY-MM-DD>_<hour>#<part>.json.gz`. Reading the body as text yields zip header bytes, not events — a client that does so stores nothing and reports no error. Unzip the body, then gunzip each member, then split on newlines.

**Query Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `start` | string | Yes | Start datetime `YYYYMMDDTHH` (e.g., `20260701T00`) |
| `end` | string | Yes | End datetime `YYYYMMDDTHH` (e.g., `20260707T23`) |

The connector derives both from the shared rolling 90-day window rather than
from literals, converting each date to Amplitude's hour form: `start` is the
first hour of the earliest day, `end` the last hour of today. A hardcoded
window silently stops covering the present the day after it is written.

**Example Request:**

```bash
curl -u "amp_api_key_mock:amp_secret_mock" \
  "https://amplitude.com/api/2/export?start=20260701T00&end=20260701T23" \
  -o export.zip
```

**Example Response:**

Response is a **zipped archive** of JSON files. After extraction, each file contains one JSON object per line:

```
{"event_type":"Signup","event_time":"2026-07-01 10:30:00.000000","event_id":1001,"user_id":"user_jane_acme","device_id":"device_abc123","session_id":1719835200000,"event_properties":{"plan":"growth","source":"organic","company":"Acme Corp"},"user_properties":{"email":"jane@acme.io","name":"Jane Smith","company":"Acme Corp","plan":"growth","created":"2025-03-15"},"ip_address":"203.0.113.42","platform":"Web","os_name":"Mac OS X","os_version":"14.5","device_type":"Mac","device_manufacturer":"Apple","language":"en-US","country":"United States","region":"California","city":"San Francisco","dma":"San Francisco-Oakland-San Jose, CA","revenue":null,"quantity":null,"price":null,"amplitude_id":9876543210,"app":12345,"library":"amplitude-js/8.21.0","uuid":"550e8400-e29b-41d4-a716-446655440000","$insert_key":"evt_abc123","$insert_id":"evt_abc123"}
{"event_type":"Page View","event_time":"2026-07-01 10:31:00.000000","event_id":1002,"user_id":"user_jane_acme","device_id":"device_abc123","session_id":1719835200000,"event_properties":{"page":"/dashboard","title":"Dashboard","referrer":"/signup"},"user_properties":{"email":"jane@acme.io","name":"Jane Smith","company":"Acme Corp","plan":"growth"},"ip_address":"203.0.113.42","platform":"Web","os_name":"Mac OS X","os_version":"14.5","country":"United States","region":"California","city":"San Francisco","amplitude_id":9876543210,"app":12345,"library":"amplitude-js/8.21.0","$insert_id":"evt_def456","uuid":"33c0de6f-9c7d-500e-acae-72980da724f1","$insert_key":null}
{"event_type":"Purchase","event_time":"2026-07-01 14:00:00.000000","event_id":1003,"user_id":"user_bob_globex","device_id":"device_def456","session_id":1719849600000,"event_properties":{"product":"Professional Plan","billing_cycle":"monthly"},"user_properties":{"email":"bob@globex.com","name":"Bob Johnson","company":"Globex Inc","plan":"professional"},"ip_address":"198.51.100.23","platform":"Web","os_name":"Windows","os_version":"11","country":"United States","region":"New York","city":"New York","revenue":2400.0,"quantity":1,"price":2400.0,"amplitude_id":9876543211,"app":12345,"library":"amplitude-js/8.21.0","$insert_id":"evt_ghi789","uuid":"fd0c78ac-d510-5265-85c8-2aa030c77434","$insert_key":null}
```

### Event Object Fields

| Field | Type | Description |
|-------|------|-------------|
| `event_type` | string | Event name |
| `event_time` | string | Timestamp `YYYY-MM-DD HH:MM:SS.ffffff` |
| `event_id` | int | Amplitude-assigned sequential ID |
| `user_id` | string | Application user identifier |
| `device_id` | string | Device/browser identifier |
| `session_id` | int | Session start time in ms (Unix epoch) |
| `$insert_id` | string | Deduplication key — **dollar-prefixed**; there is no `insert_id` |
| `uuid` | string | Per-row identifier, the fallback when `$insert_id` is absent |
| `$insert_key` | string/null | Present, usually null |
| `event_properties` | object | Custom event properties |
| `user_properties` | object | User profile properties at event time |
| `ip_address` | string | Client IP |
| `platform` | string | `Web`, `iOS`, `Android` |
| `os_name` | string | Operating system; on web this carries the browser name |
| `country` | string | GeoIP country |
| `region` | string | GeoIP region |
| `city` | string | GeoIP city |
| `revenue` | float/null | Revenue amount (if applicable) |
| `quantity` | int/null | Item quantity (if applicable) |
| `price` | float/null | Item unit price (if applicable) |
| `amplitude_id` | int | Amplitude internal user ID |
| `app` | int | Amplitude project/app ID |
| `library` | string | SDK identifier |

---

### GET /api/3/cohorts

List behavioral cohorts.

**Query Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `includeSyncInfo` | boolean | No | Set to `true` to include cohort sync metadata |

**Example Request:**

```bash
curl -u "amp_api_key_mock:amp_secret_mock" \
  "https://amplitude.com/api/3/cohorts"
```

**Example Response:**

```json
{
  "cohorts": [
    {
      "appId": 12345,
      "archived": false,
      "chart_id": "abc123",
      "createdAt": 1719835200000,
      "definition": {
        "version": 2,
        "countGroup": "user_id",
        "cohortType": "BEHAVIORAL"
      },
      "description": "Users who signed up in the last 30 days",
      "edit_id": "edit_abc123",
      "finished": true,
      "id": "cohort_001",
      "is_hidden": false,
      "is_official": false,
      "lastComputed": 1720454400000,
      "lastMod": 1720454400000,
      "name": "New Signups (30d)",
      "owners": [
        {
          "email": "admin@acme.io",
          "name": "Admin User"
        }
      ],
      "published": true,
      "size": 342,
      "type": "dynamic",
      "view_count": 15
    },
    {
      "appId": 12345,
      "archived": false,
      "chart_id": "def456",
      "createdAt": 1718625600000,
      "definition": {
        "version": 2,
        "countGroup": "user_id",
        "cohortType": "BEHAVIORAL"
      },
      "description": "Users at risk of churning based on declining engagement",
      "edit_id": "edit_def456",
      "finished": true,
      "id": "cohort_002",
      "is_hidden": false,
      "is_official": false,
      "lastComputed": 1720454400000,
      "lastMod": 1720454400000,
      "name": "Churn Risk",
      "owners": [
        {
          "email": "admin@acme.io",
          "name": "Admin User"
        }
      ],
      "published": true,
      "size": 58,
      "type": "dynamic",
      "view_count": 42
    }
  ]
}
```

---

### GET /api/2/usersearch

Search for users by user ID or email.

**Query Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `user` | string | Yes | User ID or email to search for |

**Example Request:**

```bash
curl -u "amp_api_key_mock:amp_secret_mock" \
  "https://amplitude.com/api/2/usersearch?user=jane@acme.io"
```

**Example Response:**

```json
{
  "matches": [
    {
      "amplitude_id": 9876543210,
      "user_id": "user_jane_acme",
      "last_seen": "2026-07-14T18:45:00.000000",
      "platform": "Web",
      "os": "Mac OS X",
      "device": "Mac",
      "device_type": "Mac",
      "country": "United States",
      "region": "California",
      "city": "San Francisco",
      "language": "en-US",
      "start_version": "2.1.0",
      "last_used": "2026-07-14T18:45:00.000000",
      "user_properties": {
        "email": "jane@acme.io",
        "name": "Jane Smith",
        "company": "Acme Corp",
        "plan": "growth",
        "company_domain": "acme.io",
        "created": "2025-03-15"
      }
    }
  ],
  "type": "match_user_or_device_id"
}
```

---

## Pagination

### Export Endpoint (`/api/2/export`)

**No pagination.** Returns all events in the date range as one zip archive of gzipped NDJSON files. The client unzips the body, gunzips each member, and reads the lines.

Maximum date range is **365 days**. Recommended to chunk into smaller ranges (e.g., 1 day) for large volumes.

### Cohorts Endpoint (`/api/3/cohorts`)

**No pagination.** Returns all cohorts in a single response.

### User Search (`/api/2/usersearch`)

**No pagination.** Returns all matching users (typically 1-5 matches).

---

## Error Responses

### 401 Unauthorized

```json
{
  "error": "Unauthorized: Invalid API key or secret",
  "code": 401
}
```

### 400 Bad Request

```json
{
  "error": "Bad Request: start parameter is required in format YYYYMMDDTHH",
  "code": 400
}
```

### 404 Not Found

```json
{
  "error": "Not Found: No data found for the given parameters",
  "code": 404
}
```

### 429 Too Many Requests

```json
{
  "error": "Too Many Requests: Rate limit exceeded",
  "code": 429,
  "throttle": true,
  "retry_after": 30
}
```

---

## Rate Limits

| Endpoint | Limit |
|----------|-------|
| Export | 5 concurrent requests, max 60/hour |
| Cohorts | 1 request/second |
| User Search | 10 requests/second |
| Dashboard / Event queries | 12 requests/minute, max 2 concurrent |

---

## Notes

- Export data is a **zipped archive** of **gzipped** JSON files (one event per line). Clients must unzip the response and then gunzip each member.
- A 404 and a 403 mean different things. `404` with `"Raw data files were not found."` means there is no raw data for that window — raw export lags ingestion by up to two hours, so a window ending now can legitimately be empty. `403` with `"Invalid API Key"` means the credentials are wrong. Treating a 404 as an auth failure, or an auth failure as an empty window, hides both.
- There is no undollared `insert_id`. An id function reading `insert_id` finds nothing and silently falls through to whatever fallback it has.
- The `start` and `end` params use `YYYYMMDDTHH` format (e.g., `20260701T00`), NOT ISO 8601.
- Date range is inclusive on both `start` and `end` hours.
- Maximum export response size is 4GB; exceeding this returns a 400 error.
- Data is available to export within 2 hours of when Amplitude servers received it.
- Revenue events must have `revenue`, `quantity`, and `price` fields populated.
- `amplitude_id` is Amplitude's internal user identifier (different from `user_id`).
- `session_id` is Unix epoch in milliseconds (not seconds).
- `user_properties` in export events reflect the property state at event time, not current values.

---

## What Was Verified Live

Checked on 2026-09-14 against the real project, against five events ingested
through the HTTP API the same morning:

| Claim | Verdict |
|-------|---------|
| Basic auth on key + secret | **verified** — `200` |
| The body is `application/zip` | **verified** — content-type and `PK` magic |
| Members are gzipped and `.json.gz` | **verified** — one member, gzip magic inside |
| Member naming `<project>/<project>_<date>_<hour>#<part>.json.gz` | **verified** |
| Unpacks to newline-delimited JSON | **verified** — five events |
| `$insert_id` is the dedup key | **verified** — present on every event |
| No undollared `insert_id` exists | **verified** — absent from every event |
| `uuid` is present | **verified** |
| `event_time` is present | **verified** — the field `OBSERVED_AT` names |
| `user_properties.email` is present | **verified** — the field the mapping reads |
| `browser` / `browser_version` exist | **refuted** — in neither the payload nor the schema |
| A 90-day window is accepted | **verified** — `200`, same archive |
| A wrong key answers 403 | **verified** — `"Invalid API Key"` |
| A window with no data answers 404 | **verified** — `"Raw data files were not found."` |

Event fields were verified against live data. The live events came from the
HTTP API rather than a browser SDK, so device and geo columns were present but
null; their **presence** is verified, their populated values are not.

## Reference

- [Export API](https://amplitude.com/docs/apis/analytics/export)
- [Behavioral Cohorts API](https://amplitude.com/docs/apis/analytics/behavioral-cohorts)
- [API Authentication](https://amplitude.com/docs/apis/authentication)
- [APIs overview](https://amplitude.com/docs/apis)
