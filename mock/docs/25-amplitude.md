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

Response is a **zipped archive** of JSON files. After extraction, each file
holds one JSON object per line. One line, expanded here to be read:

```json
{
  "event_type": "page_view",
  "event_time": "2026-07-14 10:00:00.000000",
  "client_event_time": "2026-07-14 10:00:00.000000",
  "client_upload_time": "2026-07-14 10:00:02.000000",
  "server_received_time": "2026-07-14 10:00:02.000000",
  "server_upload_time": "2026-07-14 10:00:02.007000",
  "processed_time": "2026-07-14 10:00:02.649000",
  "event_id": 1000,
  "user_id": "user_jane_acme",
  "device_id": "device_ev1",
  "session_id": 1720835200000,
  "$insert_id": "evt_ev1",
  "$insert_key": null,
  "$schema": null,
  "uuid": "721e5863-0b2f-56fe-b27d-a2071c432ab4",
  "event_properties": {
    "page": "/dashboard",
    "session_id": "sess_001"
  },
  "user_properties": {
    "email": "jane@acme.io",
    "name": "Jane Smith",
    "company": "Acme Corp",
    "plan": "professional"
  },
  "global_user_properties": null,
  "group_properties": {},
  "groups": {},
  "plan": {},
  "data": {
    "group_first_event": {},
    "group_ids": {},
    "path": "/2/httpapi",
    "user_properties_updated": true
  },
  "data_type": "event",
  "ip_address": "203.0.113.42",
  "platform": "Web",
  "os_name": "Mac OS X",
  "os_version": "14.5",
  "device_family": "Mac",
  "device_type": "Mac",
  "device_brand": null,
  "device_carrier": null,
  "device_manufacturer": null,
  "device_model": null,
  "language": "en-US",
  "country": "United States",
  "region": "CA",
  "city": "San Francisco",
  "dma": null,
  "location_lat": null,
  "location_lng": null,
  "adid": null,
  "idfa": null,
  "amplitude_id": 9876543210,
  "amplitude_attribution_ids": null,
  "amplitude_event_type": null,
  "is_attribution_event": null,
  "partner_id": null,
  "source_id": null,
  "sample_rate": null,
  "paying": true,
  "user_creation_time": null,
  "start_version": null,
  "version_name": null,
  "app": 12345,
  "library": "amplitude-js/8.21.0"
}
```

### Event Object Fields

An export record is **55 columns wide, and the same 55 on every row**. Amplitude
writes the whole set every time and omits nothing: a column it has no value for
arrives as `null`, never as an absent key. So `event["dma"]` is safe to index on
any row and `"dma" in event` is always true — a reader that tests for presence
to decide whether a value exists learns nothing. The stand-in serves that exact
set: `pull_source amplitude --compare` finds no key present on one side and
missing on the other, in either direction.

Thirty-two of the 55 were null on every captured event, because those events
came in through the HTTP API. The stand-in seeds a browser and a location into
the device and geography columns an SDK would fill, and leaves 21 columns null
because there is nothing honest to put in them. Those 21 are marked below.

#### Identity and event

| Field | Type | Description |
|-------|------|-------------|
| `event_type` | string | Event name |
| `event_id` | int | Amplitude-assigned sequential ID |
| `$insert_id` | string | Deduplication key — **dollar-prefixed**; there is no `insert_id` |
| `$insert_key` | null | Present on every row, **null in the stand-in** |
| `$schema` | null | Present on every row, **null in the stand-in** |
| `uuid` | string | Per-row identifier, the fallback when `$insert_id` is absent |
| `data_type` | string | `event` on an ingested event |
| `session_id` | int | Session start in epoch **milliseconds**, or `-1` for an event with no session |
| `user_id` | string | Application user identifier |
| `device_id` | string | Device/browser identifier |
| `amplitude_id` | int | Amplitude internal user ID (different from `user_id`) |
| `app` | int | Amplitude project/app ID |
| `library` | string | SDK identifier — `http/2.0` for events posted straight to the HTTP API |

#### Timestamps

| Field | Type | Description |
|-------|------|-------------|
| `event_time` | string | When the event happened — the field `OBSERVED_AT` names |
| `client_event_time` | string | The same moment as the client's own clock read it |
| `client_upload_time` | string | When the client flushed the batch |
| `server_received_time` | string | When Amplitude took delivery |
| `server_upload_time` | string | When the batch was written |
| `processed_time` | string | When the row became exportable |

All six share one format, `YYYY-MM-DD HH:MM:SS.ffffff` — space-separated, six
decimal places, no timezone. It is not ISO 8601 and `fromisoformat` refuses it.

The stand-in does not clock these independently. It derives all five from the
event time with fixed lags, so the ordering a reader sorts on is the same on
every run:

| Column | Lag behind `event_time` |
|--------|-------------------------|
| `client_event_time` | none — the same string |
| `client_upload_time` | 2 s |
| `server_received_time` | 2 s |
| `server_upload_time` | 2.007 s |
| `processed_time` | 2.649 s |

The sub-second offsets are the gaps the live capture showed between
`server_received_time`, `server_upload_time` and `processed_time`. The
two-second client-to-server gap stands in for an upload delay that was a full
minute on the captured events and has no fixed value on a real client; only its
sign is a contract.

#### Property containers

| Field | Type | Description |
|-------|------|-------------|
| `event_properties` | object | Customer-defined — whatever the sender attached to this event |
| `user_properties` | object | Profile state **at event time**, not current values; `.email` is the field the mapping reads |
| `global_user_properties` | null | Cross-project profile — **null in the stand-in** |
| `group_properties` | object | `{}` without Amplitude Accounts |
| `groups` | object | `{}` without Amplitude Accounts |
| `plan` | object | `{}` without a tracking plan |
| `data` | object | Ingest metadata — `group_first_event`, `group_ids`, `path`, `user_properties_updated` |

`data`, `groups`, `group_properties` and `plan` are objects on every row, never
null and never absent, so they can be iterated unguarded. Three of the four are
empty; `data` always carries at least the ingest `path`. The two customer-defined
containers are the only free-form columns: `event_properties` and
`user_properties` hold whatever the project sends, so their keys differ between
the stand-in and any live project and a difference there is not a defect.

#### Device and geography

| Field | Type | Description |
|-------|------|-------------|
| `platform` | string/null | `Web`, `iOS`, `Android` |
| `os_name` | string/null | Operating system; on web this carries the browser name |
| `os_version` | string/null | |
| `device_family` | string/null | |
| `device_type` | string/null | |
| `device_brand` | null | Mobile-only — **null in the stand-in** |
| `device_carrier` | null | Mobile-only — **null in the stand-in** |
| `device_manufacturer` | null | Mobile-only — **null in the stand-in** |
| `device_model` | null | Mobile-only — **null in the stand-in** |
| `language` | string/null | |
| `ip_address` | string/null | Client IP |
| `country` | string/null | GeoIP country |
| `region` | string/null | GeoIP region |
| `city` | string/null | GeoIP city |
| `dma` | null | GeoIP metro area — **null in the stand-in** |
| `location_lat` | float/null | Only with location tracking on — **null in the stand-in** |
| `location_lng` | float/null | Only with location tracking on — **null in the stand-in** |

The captured events reached Amplitude through the HTTP API rather than a browser
SDK, so every column in this group came back null live. Their **presence** is
what the capture verifies. The stand-in seeds a web browser and a US location
into the five that a browser SDK does fill, and leaves the rest null.

#### Attribution and lifecycle

Every column here is `null` on every stand-in row except `paying`.

| Field | Type | Description |
|-------|------|-------------|
| `adid` | null | Android advertising ID |
| `idfa` | null | iOS advertising ID |
| `amplitude_attribution_ids` | null | |
| `amplitude_event_type` | null | Set only on Amplitude's own synthetic events |
| `is_attribution_event` | null | |
| `partner_id` | null | |
| `source_id` | null | Not the connector's `source_id` — an Amplitude column that shares the name |
| `sample_rate` | null | |
| `user_creation_time` | null | |
| `start_version` | null | First app version the user was seen on |
| `version_name` | null | |
| `paying` | bool/null | `true` for a stand-in person on a subscription; null live, where Amplitude had no answer |

#### Columns that are not there

`revenue`, `quantity` and `price` appear in none of the 55. No captured event
carried them and the stand-in does not emit them, so an extractor that reads
them gets a `KeyError`, not a null. The captured project has never sent a
revenue event, so whether a project that has gets extra columns is untested here.

`insert_id`, `browser` and `browser_version` are not columns either — see the
verification table at the end of this file.

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
- An export record is 55 columns wide and every row carries all 55. A column with no value is `null`, never absent, so membership tests tell a reader nothing.
- `revenue`, `quantity` and `price` are not among those 55 and no captured event carried them. Reading them raises rather than returning null.
- `amplitude_id` is Amplitude's internal user identifier (different from `user_id`).
- `session_id` is Unix epoch in milliseconds (not seconds), or `-1` for an event sent with no session.
- The six timestamp columns all use `YYYY-MM-DD HH:MM:SS.ffffff`, which is not ISO 8601. `client_event_time` through `processed_time` never precede `event_time`.
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
| The record is 55 columns wide, the same set on every event | **verified** — and the stand-in's set now matches it exactly, in both directions |
| A column with no value is null rather than absent | **verified** — 32 of the 55 were null on all five events |
| `revenue` / `quantity` / `price` are columns | **refuted** — absent from every event; the project has never sent a revenue event |
| `event_time` is present | **verified** — the field `OBSERVED_AT` names |
| `user_properties.email` is present | **verified** — the field the mapping reads |
| `browser` / `browser_version` exist | **refuted** — in neither the payload nor the schema |
| A 90-day window is accepted | **verified** — `200`, same archive |
| A wrong key answers 403 | **verified** — `"Invalid API Key"` |
| A window with no data answers 404 | **verified** — `"Raw data files were not found."` |

Event fields were verified against live data. The live events came from the
HTTP API rather than a browser SDK, so device and geo columns were present but
null; their **presence** is verified, their populated values are not.

The stand-in's column set was reconciled against that capture rather than
against the vendor reference: key set to key set, nothing extra on either side.
`event_properties` and `user_properties` are the exception, and deliberately so
— they are customer-defined, the captured project sends `source` and
`email`/`plan`, the stand-in sends its own, and a difference inside them is the
API working as documented rather than a defect.

## Reference

- [Export API](https://amplitude.com/docs/apis/analytics/export)
- [Behavioral Cohorts API](https://amplitude.com/docs/apis/analytics/behavioral-cohorts)
- [API Authentication](https://amplitude.com/docs/apis/authentication)
- [APIs overview](https://amplitude.com/docs/apis)
