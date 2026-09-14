# HubSpot CRM API v3

## Overview

HubSpot CRM API provides access to contacts, companies, deals, and tickets. Used by OS for CRM data ingestion.

- **Category:** CRM
- **Production Base URL:** `https://api.hubapi.com`
- **Mock Base URL:** `http://localhost:8100/hubspot`
- **API Version:** CRM v3
- **Response Format:** JSON

## Authentication

HubSpot uses OAuth 2.0 with a token refresh flow. A static Bearer token is also supported for single-account installs.

### Token Refresh

```
POST /oauth/v1/token
Content-Type: application/x-www-form-urlencoded
```

> **Note:** HubSpot also offers newer OAuth endpoints at `/oauth/v3/token` and `/oauth/2026-03/token` with enhanced security. The v1 endpoint is deprecated but still operational. HubSpot recommends new integrations use the v3 or latest endpoints.

**Request body (form-encoded):**

| Parameter | Required | Description |
|-----------|----------|-------------|
| `grant_type` | Yes | Must be `refresh_token` |
| `refresh_token` | Yes | The refresh token from initial OAuth flow |
| `client_id` | Yes | Your app's client ID |
| `client_secret` | Yes | Your app's client secret |

**Example request:**

```bash
curl -X POST https://api.hubapi.com/oauth/v1/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=refresh_token&refresh_token=your_refresh_token&client_id=your_client_id&client_secret=your_client_secret"
```

**Example response (200):**

```json
{
  "access_token": "CKn2p5KdLhICAQEYs...",
  "refresh_token": "6b128390-3e89-4c63-b82a-...",
  "expires_in": 1800,
  "token_type": "bearer"
}
```

### Using the Token

All API endpoints require the Bearer token in the `Authorization` header:

```
Authorization: Bearer CKn2p5KdLhICAQEYs...
```

### Rate Limits

| Tier | Burst (per 10s) | Daily |
|------|-----------------|-------|
| Free/Starter | 100 | 250,000 |
| Professional | 190 | 625,000 |
| Enterprise | 190 | 1,000,000 |

---

## Endpoints

### 1. List Contacts

```
GET /crm/v3/objects/contacts
```

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 100 | Results per page (max 100) |
| `after` | string | — | Cursor for next page (from `paging.next.after`) |
| `properties` | string | — | Comma-separated list of property names to include |
| `propertiesWithHistory` | string | — | Comma-separated list of properties to return with their history of previous values |
| `associations` | string | — | Comma-separated list of object types to retrieve associated IDs for |
| `archived` | boolean | false | Include archived contacts |

**Example request:**

```bash
curl -H "Authorization: Bearer CKn2p5KdLhICAQEYs..." \
  "https://api.hubapi.com/crm/v3/objects/contacts?limit=2&properties=firstname,lastname,email,lifecyclestage,company"
```

**Example response (200) — with more pages:**

```json
{
  "results": [
    {
      "id": "550000000001",
      "properties": {
        "firstname": "Jane",
        "lastname": "Smith",
        "email": "jane@acme.io",
        "createdate": "2025-03-15T10:30:00.000Z",
        "lastmodifieddate": "2026-06-01T14:22:00.000Z",
        "lifecyclestage": "customer",
        "company": "Acme Corp",
        "hs_object_id": "550000000001"
      },
      "createdAt": "2025-03-15T10:30:00.000Z",
      "updatedAt": "2026-06-01T14:22:00.000Z",
      "archived": false,
      "url": "https://app-na2.hubspot.com/contacts/12345678/record/0-1/550000000001"
    },
    {
      "id": "550000000021",
      "properties": {
        "firstname": "Bob",
        "lastname": "Smith",
        "email": "bob@soylent.co",
        "createdate": "2025-04-20T08:15:00.000Z",
        "lastmodifieddate": "2026-05-10T11:00:00.000Z",
        "lifecyclestage": "lead",
        "company": "Soylent Corp",
        "hs_object_id": "550000000021"
      },
      "createdAt": "2025-04-20T08:15:00.000Z",
      "updatedAt": "2026-05-10T11:00:00.000Z",
      "archived": false,
      "url": "https://app-na2.hubspot.com/contacts/12345678/record/0-1/550000000021"
    }
  ],
  "paging": {
    "next": {
      "after": "550000000021",
      "link": "https://api.hubapi.com/crm/v3/objects/contacts?limit=2&properties=firstname,lastname,email,lifecyclestage,company&after=550000000021"
    }
  }
}
```

**Example response (200) — last page (no more results):**

```json
{
  "results": [
    {
      "id": "550000000020",
      "properties": {
        "firstname": "Miles",
        "lastname": "Dyson",
        "email": "miles@cyberdyne.ai",
        "createdate": "2026-01-10T16:45:00.000Z",
        "lastmodifieddate": "2026-07-01T09:30:00.000Z",
        "lifecyclestage": "customer",
        "company": "Cyberdyne Systems",
        "hs_object_id": "550000000020"
      },
      "createdAt": "2026-01-10T16:45:00.000Z",
      "updatedAt": "2026-07-01T09:30:00.000Z",
      "archived": false,
      "url": "https://app-na2.hubspot.com/contacts/12345678/record/0-1/550000000020"
    }
  ]
}
```

Note: When there are no more pages, the `paging` key is **completely absent** from the response (not null, not empty).

---

### 2. List Companies

```
GET /crm/v3/objects/companies
```

**Query parameters:** Same as contacts (`limit`, `after`, `properties`, `propertiesWithHistory`, `associations`, `archived`).

**Example request:**

```bash
curl -H "Authorization: Bearer CKn2p5KdLhICAQEYs..." \
  "https://api.hubapi.com/crm/v3/objects/companies?limit=2&properties=name,domain,industry,numberofemployees,city,state,country"
```

**Example response (200):**

```json
{
  "results": [
    {
      "id": "346000000001",
      "properties": {
        "name": "Acme Corp",
        "domain": "acme.io",
        "industry": "COMPUTER_SOFTWARE",
        "numberofemployees": "150",
        "city": "San Francisco",
        "state": "CA",
        "country": "United States",
        "createdate": "2025-01-10T09:00:00.000Z",
        "hs_lastmodifieddate": "2026-06-15T12:00:00.000Z",
        "hs_object_id": "346000000001"
      },
      "createdAt": "2025-01-10T09:00:00.000Z",
      "updatedAt": "2026-06-15T12:00:00.000Z",
      "archived": false,
      "url": "https://app-na2.hubspot.com/contacts/12345678/record/0-2/346000000001"
    },
    {
      "id": "346000000009",
      "properties": {
        "name": null,
        "domain": "cyberdyne.ai",
        "industry": null,
        "numberofemployees": null,
        "city": "Denver",
        "state": "CO",
        "country": "United States",
        "createdate": "2025-02-05T14:30:00.000Z",
        "hs_lastmodifieddate": "2026-07-01T10:15:00.000Z",
        "hs_object_id": "346000000009"
      },
      "createdAt": "2025-02-05T14:30:00.000Z",
      "updatedAt": "2026-07-01T10:15:00.000Z",
      "archived": false,
      "url": "https://app-na2.hubspot.com/contacts/12345678/record/0-2/346000000009"
    }
  ],
  "paging": {
    "next": {
      "after": "346000000009",
      "link": "https://api.hubapi.com/crm/v3/objects/companies?limit=2&properties=name,domain,industry,numberofemployees,city,state,country&after=346000000009"
    }
  }
}
```

`industry` is an enumeration: the API returns the internal value (`COMPUTER_SOFTWARE`), not the label the app shows (`Computer Software`). A property a record never had comes back as `null`, never as `""` — `name` included, because HubSpot creates a company from a contact's email domain before anyone names it.

---

### 3. List Deals

```
GET /crm/v3/objects/deals
```

**Query parameters:** Same as contacts (`limit`, `after`, `properties`, `propertiesWithHistory`, `associations`, `archived`).

**Example request:**

```bash
curl -H "Authorization: Bearer CKn2p5KdLhICAQEYs..." \
  "https://api.hubapi.com/crm/v3/objects/deals?limit=2&properties=dealname,amount,closedate,deal_currency_code,hs_is_closed,hs_is_closed_won"
```

**Example response (200):**

```json
{
  "results": [
    {
      "id": "348000000001",
      "properties": {
        "dealname": "Acme Corp - Growth Plan",
        "amount": "57600",
        "deal_currency_code": null,
        "hs_is_closed": "true",
        "hs_is_closed_won": "true",
        "closedate": "2025-06-01T00:00:00.000Z",
        "createdate": "2025-03-01T10:00:00.000Z",
        "hs_lastmodifieddate": "2025-06-01T15:30:00.000Z",
        "hs_object_id": "348000000001"
      },
      "createdAt": "2025-03-01T10:00:00.000Z",
      "updatedAt": "2025-06-01T15:30:00.000Z",
      "archived": false,
      "url": "https://app-na2.hubspot.com/contacts/12345678/record/0-3/348000000001"
    },
    {
      "id": "348000000005",
      "properties": {
        "dealname": "Wayne Enterprises - Professional Plan",
        "amount": "21600",
        "deal_currency_code": null,
        "hs_is_closed": "false",
        "hs_is_closed_won": "false",
        "closedate": "2026-07-15T00:00:00.000Z",
        "createdate": "2026-07-01T09:00:00.000Z",
        "hs_lastmodifieddate": "2026-07-01T16:45:00.000Z",
        "hs_object_id": "348000000005"
      },
      "createdAt": "2026-07-01T09:00:00.000Z",
      "updatedAt": "2026-07-01T16:45:00.000Z",
      "archived": false,
      "url": "https://app-na2.hubspot.com/contacts/12345678/record/0-3/348000000005"
    }
  ],
  "paging": {
    "next": {
      "after": "348000000005",
      "link": "https://api.hubapi.com/crm/v3/objects/deals?limit=2&properties=dealname,amount,closedate,deal_currency_code,hs_is_closed,hs_is_closed_won&after=348000000005"
    }
  }
}
```

`dealstage` and `pipeline` are ids, and a portal may rename or replace both, so a reader that spells out `closedwon` counts nothing in a custom pipeline. `hs_is_closed_won` and `hs_is_closed` are the pipeline-independent answer; both arrive as the strings `"true"` and `"false"`. `deal_currency_code` is what the amount is denominated in, and it is `null` on a deal that never carried a currency of its own.

---

## Pagination

HubSpot uses **cursor-based pagination** across all CRM v3 list endpoints.

### How it works

1. Make initial request (optionally with `limit`)
2. If response contains `paging.next.after`, pass that value as the `after` query parameter on the next request
3. Repeat until `paging` key is **absent** from the response

### Rules

- `limit` range: 1–100 (default 100); a `limit` below the maximum only buys more round trips and hits the page cap sooner
- `after` is the ID of the last object on the current page
- The `paging.next.link` field is an absolute URL that repeats the current query with `after` applied
- When there are no more results, the entire `paging` key is omitted (not set to null)

### Pseudocode

```python
results = []
after = None
while True:
    params = {"limit": 100}
    if after:
        params["after"] = after
    response = get("/crm/v3/objects/contacts", params=params)
    results.extend(response["results"])
    paging = response.get("paging")
    if not paging:
        break
    after = paging["next"]["after"]
```

---

## Error Responses

### 401 Unauthorized

```json
{
  "status": "error",
  "message": "Authentication credentials not found. This API supports OAuth 2.0 authentication and you can find more details at https://developers.hubspot.com/docs/methods/auth/oauth-overview",
  "correlationId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "category": "INVALID_AUTHENTICATION"
}
```

### 429 Rate Limit Exceeded

```json
{
  "status": "error",
  "message": "You have reached your secondly limit.",
  "correlationId": "f1e2d3c4-b5a6-7890-fedc-ba0987654321",
  "category": "RATE_LIMITS"
}
```

### 400 Bad Request

```json
{
  "status": "error",
  "message": "Invalid input (details will vary)",
  "correlationId": "d4c3b2a1-0987-6543-dcba-fedcba098765",
  "category": "VALIDATION_ERROR"
}
```

---

## Notes

- All property values are strings in HubSpot (even numeric fields like `numberofemployees` and `amount`, and boolean fields like `hs_is_closed`)
- The `properties` query parameter is the whole list of extra properties returned: anything not asked for is absent from the response, whatever the record holds
- `hs_object_id`, `createdate` and the last-modified stamp (`lastmodifieddate` on contacts, `hs_lastmodifieddate` on companies and deals) come back whether or not they were asked for
- A property with no value is `null`, not an empty string
- Object ids are numeric strings assigned by HubSpot, and every record carries a top-level `url` pointing at its record page in the portal
- `createdate` inside `properties` and `createdAt` at the top level are the same timestamp in different formats
- HubSpot has an OpenAPI spec available at `github.com/HubSpot/HubSpot-public-api-spec-collection` for additional endpoint details
- Webhook subscriptions (up to 1,000 per app) are exempt from rate limits when triggered via workflows

---

## Reference

- [CRM Objects API - Using Object APIs](https://developers.hubspot.com/docs/api-reference/latest/crm/using-object-apis) -- Endpoint paths, query parameters, and response structures for all CRM object types
- [Contacts Guide](https://developers.hubspot.com/docs/guides/api/crm/objects/contacts) -- Contacts-specific API guide
- [OAuth Token Management](https://developers.hubspot.com/docs/guides/api/app-management/oauth-tokens) -- OAuth token refresh flow and endpoint versions
- [Refresh an OAuth Token (latest)](https://developers.hubspot.com/docs/api-reference/latest/authentication/oauth-tokens/refresh-oauth-token) -- Latest OAuth token refresh endpoint reference
- [API Usage Guidelines and Limits](https://developers.hubspot.com/docs/developer-tooling/platform/usage-guidelines) -- Rate limits by subscription tier
