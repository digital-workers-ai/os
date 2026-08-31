# Mixpanel API

> Category: Analytics

---

## Base URLs

| Endpoint Type | Base URL |
|---------------|----------|
| Data Export | `https://data.mixpanel.com` |
| Query (Engage, Insights) | `https://mixpanel.com` |
| EU Data Residency | `https://data-eu.mixpanel.com` / `https://eu.mixpanel.com` |
| India Data Residency | `https://data-in.mixpanel.com` / `https://in.mixpanel.com` |

## Authentication

**Service Account** (preferred) — Basic Auth with service account username and secret:

```
Authorization: Basic base64(sa_username_mock:sa_secret_mock_xxxxxxxxxxxx)
```

Or equivalently:

```bash
curl -u "sa_username_mock:sa_secret_mock_xxxxxxxxxxxx" https://data.mixpanel.com/api/2.0/export
```

When using service account auth, `project_id` must be passed as a query parameter on all endpoints.

**Project Secret** (legacy) — same Basic Auth format with project secret instead. Does not require `project_id` parameter.

Returns `401 Unauthorized` without valid credentials.

Additional required header:
```
Accept: application/json
```

---

## Endpoints

### GET /api/2.0/export

Export raw event data. Returns **newline-delimited JSON** (NDJSON) — one JSON object per line.

**Base URL:** `https://data.mixpanel.com`

**Query Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `project_id` | int | Yes* | Mixpanel project ID (*required with service account auth) |
| `from_date` | string | Yes | Start date `YYYY-MM-DD` |
| `to_date` | string | Yes | End date `YYYY-MM-DD` |
| `event` | string | No | JSON array of event names to filter, e.g. `["Signup","Purchase"]` |
| `where` | string | No | Expression to filter by properties, e.g. `properties["plan"] == "pro"` |

**Example Request:**

```bash
curl -u "sa_username_mock:sa_secret_mock_xxxxxxxxxxxx" \
  "https://data.mixpanel.com/api/2.0/export?project_id=12345&from_date=2026-07-01&to_date=2026-07-07"
```

**Example Response:**

Response is **NDJSON** (one JSON object per line, NOT a JSON array):

```
{"event":"Signup","properties":{"time":1719835200,"distinct_id":"user_jane_acme","$insert_id":"abc123","$browser":"Chrome","$browser_version":"126","$city":"San Francisco","$region":"California","$country_code":"US","$os":"Mac OS X","$device":"Mac","mp_lib":"web","$current_url":"https://app.acme.io/signup","plan":"growth","company":"Acme Corp","$mp_api_endpoint":"api.mixpanel.com","$mp_api_timestamp_ms":1719835200000}}
{"event":"Page View","properties":{"time":1719835260,"distinct_id":"user_jane_acme","$insert_id":"def456","$browser":"Chrome","$browser_version":"126","$city":"San Francisco","$region":"California","$country_code":"US","$os":"Mac OS X","page":"/dashboard","title":"Dashboard - Acme","$current_url":"https://app.acme.io/dashboard","$referrer":"https://app.acme.io/signup","mp_lib":"web"}}
{"event":"Purchase","properties":{"time":1719921600,"distinct_id":"user_bob_globex","$insert_id":"ghi789","$browser":"Firefox","$browser_version":"128","$city":"New York","$region":"New York","$country_code":"US","$os":"Windows","amount":2400.00,"currency":"USD","plan":"professional","company":"Globex Inc","product_id":"prod_growth","mp_lib":"web"}}
{"event":"Feature Used","properties":{"time":1719921660,"distinct_id":"user_bob_globex","$insert_id":"jkl012","$browser":"Firefox","$browser_version":"128","$city":"New York","$region":"New York","$country_code":"US","$os":"Windows","feature":"analytics_dashboard","duration_seconds":342,"mp_lib":"web"}}
```

### Event Object Fields

| Field | Type | Description |
|-------|------|-------------|
| `event` | string | Event name |
| `properties.time` | int | Unix timestamp (seconds) |
| `properties.distinct_id` | string | User identifier |
| `properties.$insert_id` | string | Deduplication key |
| `properties.$browser` | string | Browser name |
| `properties.$city` | string | GeoIP city |
| `properties.$region` | string | GeoIP region |
| `properties.$country_code` | string | GeoIP country |
| `properties.$os` | string | Operating system |
| `properties.$current_url` | string | Page URL |
| `properties.mp_lib` | string | SDK library (`web`, `python`, etc.) |
| Custom properties | any | Arbitrary event-specific data |

---

### POST /api/query/engage

Query user profiles (People Analytics).

**Base URL:** `https://mixpanel.com`

**Request Body (form-encoded or JSON):**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `project_id` | int | Yes* | Mixpanel project ID (*required with service account auth) |
| `where` | string | No | Filter expression, e.g. `properties["plan"] == "pro"` |
| `filter_by_cohort` | string | No | JSON object with cohort ID to filter by |
| `session_id` | string | No | Session ID for paginating (from previous response) |
| `page` | int | No | Page number (starts at 0) |
| `output_properties` | array | No | JSON array of property names to return |
| `include_all_users` | boolean | No | Include profiles without user data (default: true) |

**Example Request:**

```bash
curl -u "sa_username_mock:sa_secret_mock_xxxxxxxxxxxx" \
  -X POST "https://mixpanel.com/api/query/engage" \
  -d 'project_id=12345' \
  -d 'where=properties["plan"] == "growth"' \
  -d 'output_properties=["$email","$name","plan","company"]'
```

**Example Response:**

```json
{
  "page": 0,
  "page_size": 1000,
  "results": [
    {
      "$distinct_id": "user_jane_acme",
      "$properties": {
        "$email": "jane@acme.io",
        "$first_name": "Jane",
        "$last_name": "Smith",
        "$name": "Jane Smith",
        "$created": "2025-03-15T10:30:00",
        "$last_seen": "2026-07-14T18:45:00",
        "$browser": "Chrome",
        "$city": "San Francisco",
        "$region": "California",
        "$country_code": "US",
        "$os": "Mac OS X",
        "plan": "growth",
        "company": "Acme Corp",
        "company_domain": "acme.io",
        "signup_source": "organic"
      }
    },
    {
      "$distinct_id": "user_bob_globex",
      "$properties": {
        "$email": "bob@globex.com",
        "$first_name": "Bob",
        "$last_name": "Johnson",
        "$name": "Bob Johnson",
        "$created": "2025-06-20T14:00:00",
        "$last_seen": "2026-07-13T09:30:00",
        "$browser": "Firefox",
        "$city": "New York",
        "$region": "New York",
        "$country_code": "US",
        "$os": "Windows",
        "plan": "growth",
        "company": "Globex Inc",
        "company_domain": "globex.com",
        "signup_source": "referral"
      }
    }
  ],
  "session_id": "sess_1719835200_abc123",
  "status": "ok",
  "total": 15
}
```

### Profile Object Fields

| Field | Type | Description |
|-------|------|-------------|
| `$distinct_id` | string | User identifier |
| `$properties.$email` | string | User email |
| `$properties.$first_name` | string | First name |
| `$properties.$last_name` | string | Last name |
| `$properties.$name` | string | Full display name |
| `$properties.$created` | string | Profile creation time |
| `$properties.$last_seen` | string | Last activity time |
| `$properties.$browser` | string | Last known browser |
| `$properties.$city` | string | GeoIP city |
| `$properties.$country_code` | string | GeoIP country |
| Custom properties | any | Arbitrary profile properties |

---

### GET /api/query/insights

Query computed insights (funnels, retention, etc.). Available on Growth and Enterprise plans.

**Base URL:** `https://mixpanel.com`

**Query Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `project_id` | int | Yes* | Mixpanel project ID (*required with service account auth) |
| `bookmark_id` | int | Yes | Saved report ID |
| `workspace_id` | int | No | Workspace ID (required if project uses workspaces) |

**Example Request:**

```bash
curl -u "sa_username_mock:sa_secret_mock_xxxxxxxxxxxx" \
  "https://mixpanel.com/api/query/insights?project_id=12345&bookmark_id=67890"
```

**Example Response:**

```json
{
  "computed_at": "2026-07-07T23:59:59.000Z",
  "date_range": {
    "from_date": "2026-07-01",
    "to_date": "2026-07-07"
  },
  "headers": ["$overall"],
  "series": {
    "Signup": {
      "2026-07-01": 42,
      "2026-07-02": 38,
      "2026-07-03": 55,
      "2026-07-04": 31,
      "2026-07-05": 48,
      "2026-07-06": 52,
      "2026-07-07": 45
    }
  }
}
```

---

## Pagination

### Export Endpoint (`/api/2.0/export`)

**No pagination.** Returns all matching events as a streaming NDJSON response. The client reads line by line. For large exports, Mixpanel streams the response — there is no page mechanism.

### Engage Endpoint (`/api/query/engage`)

**Session-based pagination:**

1. First request: omit `session_id` and `page`.
2. Response includes `session_id` and `total`.
3. Next page: pass `session_id` from previous response + `page` incremented by 1.
4. **Done** when `(page + 1) * page_size >= total`.

```bash
# Page 0
curl -u "sa_user:sa_secret" -X POST "https://mixpanel.com/api/query/engage" \
  -d "project_id=12345"
# Response: {session_id: "sess_abc", total: 2500, page: 0, page_size: 1000}

# Page 1
curl -u "sa_user:sa_secret" -X POST "https://mixpanel.com/api/query/engage" \
  -d "project_id=12345&session_id=sess_abc&page=1"
# Response: {session_id: "sess_abc", total: 2500, page: 1, page_size: 1000}

# Page 2 (last — 2 * 1000 < 2500 but 3 * 1000 >= 2500)
curl -u "sa_user:sa_secret" -X POST "https://mixpanel.com/api/query/engage" \
  -d "project_id=12345&session_id=sess_abc&page=2"
# Response: {session_id: "sess_abc", total: 2500, page: 2, page_size: 1000, results: [...500 items]}
```

---

## Error Responses

### 401 Unauthorized

```json
{
  "error": "Unauthorized",
  "request": "/api/2.0/export",
  "status": 0
}
```

### 400 Bad Request

```json
{
  "error": "Invalid date range. from_date must be before to_date.",
  "request": "/api/2.0/export",
  "status": 0
}
```

### 429 Too Many Requests

No JSON body. Response headers contain rate limit info. Retry after the indicated delay.

---

## Rate Limits

| Plan | Queries/hour | Export | Engage |
|------|-------------|--------|--------|
| Free | 60 | 60/hr | 60/hr |
| Growth | 400 | 400/hr | 400/hr |
| Enterprise | 2000 | 2000/hr | 2000/hr |

Rate limit headers:
```
X-RateLimit-Limit: 400
X-RateLimit-Remaining: 398
X-RateLimit-Reset: 1719838800
```

---

## Notes

- Export data is NDJSON (newline-delimited JSON), not a JSON array. Each line is a standalone JSON object.
- Mixpanel property names starting with `$` are reserved/special properties set by the SDK.
- `distinct_id` is the primary user identifier — can be any string.
- Times in export events are Unix timestamps (seconds), not milliseconds.
- Engage profiles use `$distinct_id` (with prefix) at the top level and `$properties` as the nested property object.
- Export endpoint date range is inclusive on both ends.
- Engage and Insights query APIs have a maximum of 5 concurrent queries (rate limits per plan — see table above).

---

## Reference

- [Authentication](https://docs.mixpanel.com/reference/authentication)
- [Service Accounts](https://docs.mixpanel.com/reference/service-accounts)
- [Raw Data Export API authentication](https://docs.mixpanel.com/reference/raw-data-export-api-authentication)
- [Query Profiles (Engage)](https://docs.mixpanel.com/reference/engage-query)
- [Query Saved Report (Insights)](https://docs.mixpanel.com/reference/insights-query)
