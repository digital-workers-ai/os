# Stripe API

## Overview

Stripe's REST API provides access to customers, subscriptions, invoices, and payment data. Used by OS for billing/revenue data ingestion.

- **Category:** Payments
- **Production Base URL:** `https://api.stripe.com`
- **Mock Base URL:** `http://localhost:8100/stripe`
- **API Version:** 2025-03-31.basil — pinned by the connector, see *API Version Pinning* below
- **Response Format:** JSON
- **Official Docs:** https://docs.stripe.com/api

## Authentication

Stripe supports two authentication methods. Both are accepted on every endpoint.

### HTTP Basic Auth (Primary)

API key as username, empty password:

```bash
curl -u sk_test_4eC39HqLyjWDarjtT1zdp7dc: https://api.stripe.com/v1/customers
```

### Bearer Token (Alternative)

```
Authorization: Bearer sk_test_4eC39HqLyjWDarjtT1zdp7dc
```

### Mock Server Tokens

The mock server accepts any token starting with `sk_test_mock_`.

### API Version Pinning

The connector sends `Stripe-Version: 2025-03-31.basil` on every request.

Without the header Stripe applies **the account's own default version**, which
moves when Stripe upgrades it or when somebody presses upgrade in the dashboard.
That already happened here: on 2026-09-14 the sandbox account answered with
`stripe-version: 2026-08-26.dahlia`, two named versions past the one this
contract was written against. An unpinned connector would have absorbed that
shape change with no code change and no failing test.

`2025-03-31.basil` is the version pinned because it is the one whose documented
shapes the connector, the mock and the fixtures all model — in particular it is
the version that moved `current_period_start` / `current_period_end` onto the
subscription **items**. Raising the pin is a deliberate edit: change the header,
re-capture, and re-diff the fields below.

Sending the header is verified live: `Stripe-Version: 2025-03-31.basil` answers
`200` and echoes the same value back in the response header. An unknown value
answers `400`, so a typo in the pin fails loudly rather than silently falling
back to the account default.

### Rate Limits

- **Global limit (live mode):** 100 requests/second (per account)
- **Global limit (sandbox/test mode):** 25 requests/second (per account)
- **Individual endpoints:** 25 requests/second unless otherwise noted
- **Read allocation:** 500 read requests per transaction over a rolling 30-day window (minimum 10,000 reads/month)
- Returns HTTP 429 with a `Stripe-Rate-Limited-Reason` header when exceeded

---

## List Envelope

All list endpoints share the same response envelope:

```json
{
  "object": "list",
  "url": "/v1/customers",
  "has_more": true,
  "data": [...]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `object` | string | Always `"list"` |
| `url` | string | The endpoint path (e.g. `"/v1/customers"`) |
| `has_more` | boolean | `true` if more results exist beyond this page |
| `data` | array | Array of resource objects |

Nested sub-lists (e.g., `subscription.items`) add a 5th field:

| Field | Type | Description |
|-------|------|-------------|
| `total_count` | integer | Total number of items in the sub-list |

---

## Endpoints

### 1. List Customers

```
GET /v1/customers
```

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 10 | Results per page (1–100) |
| `starting_after` | string | — | Cursor: ID of the last object from previous page |
| `ending_before` | string | — | Cursor: ID of the first object from previous page (mutually exclusive with `starting_after`) |
| `email` | string | — | Filter by exact email |
| `created` | object | — | Filter by created time (e.g., `created[gte]=1609459200`) |

**Example request:**

```bash
curl -u sk_test_4eC39HqLyjWDarjtT1zdp7dc: \
  "https://api.stripe.com/v1/customers?limit=2"
```

**Example response (200):**

```json
{
  "object": "list",
  "url": "/v1/customers",
  "has_more": true,
  "data": [
    {
      "id": "cus_acme001",
      "object": "customer",
      "name": "ACME Corporation",
      "email": "billing@acme.io",
      "created": 1710500000,
      "currency": "usd",
      "default_source": null,
      "description": "Enterprise customer - Growth plan",
      "delinquent": false,
      "livemode": false,
      "metadata": {
        "company_domain": "acme.io",
        "hubspot_id": "hs_company_001"
      },
      "address": {
        "line1": "123 Market St",
        "line2": "Suite 400",
        "city": "San Francisco",
        "state": "CA",
        "postal_code": "94105",
        "country": "US"
      },
      "balance": 0,
      "invoice_prefix": "ACME01",
      "invoice_settings": {
        "custom_fields": null,
        "default_payment_method": "pm_card_visa",
        "footer": null,
        "rendering_options": null
      },
      "next_invoice_sequence": 14,
      "phone": "+14155551234",
      "preferred_locales": ["en"],
      "shipping": null,
      "tax_exempt": "none",
      "test_clock": null
    },
    {
      "id": "cus_globex002",
      "object": "customer",
      "name": "Globex Inc",
      "email": "accounts@globex.com",
      "created": 1712000000,
      "currency": "usd",
      "default_source": null,
      "description": null,
      "delinquent": false,
      "livemode": false,
      "metadata": {
        "company_domain": "globex.com"
      },
      "address": null,
      "balance": 0,
      "invoice_prefix": "GLBX01",
      "invoice_settings": {
        "custom_fields": null,
        "default_payment_method": null,
        "footer": null,
        "rendering_options": null
      },
      "next_invoice_sequence": 8,
      "phone": null,
      "preferred_locales": [],
      "shipping": null,
      "tax_exempt": "none",
      "test_clock": null
    }
  ]
}
```

### Customer Object Fields (21 fields)

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Prefixed with `cus_` |
| `object` | string | Always `"customer"` |
| `name` | string or null | Customer name |
| `email` | string or null | Customer email |
| `created` | integer | Unix timestamp |
| `currency` | string or null | Three-letter ISO code (e.g. `"usd"`) |
| `default_source` | string or null | Default payment source ID |
| `description` | string or null | Free-form description |
| `delinquent` | boolean | Whether customer has unpaid invoices |
| `livemode` | boolean | Live vs test mode |
| `metadata` | object | Key-value pairs |
| `address` | object or null | Customer address |
| `balance` | integer | Current balance in cents |
| `invoice_prefix` | string | Prefix for invoice numbers |
| `invoice_settings` | object | Invoice configuration |
| `next_invoice_sequence` | integer | Next invoice number |
| `phone` | string or null | Phone number |
| `preferred_locales` | array | Language preferences |
| `shipping` | object or null | Shipping info |
| `tax_exempt` | string | `"none"`, `"exempt"`, or `"reverse"` |
| `test_clock` | string or null | Test clock ID |

---

### 2. List Subscriptions

```
GET /v1/subscriptions
```

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 10 | Results per page (1–100) |
| `starting_after` | string | — | Cursor: last object ID |
| `customer` | string | — | Filter by customer ID |
| `status` | string | — | Filter by status, or `all` / `ended` (see below) |
| `price` | string | — | Filter by price ID |

**The default is not "everything".** With no `status`, Stripe returns *all
subscriptions that have not been canceled*. A canceled subscription is
invisible to an unfiltered query, so churn and lifetime revenue read as if it
never existed.

The connector therefore sends `status=all`. That value is confirmed against the
live API: `status=bogus_value` answers `400` with

> Invalid status: must be one of active, past_due, unpaid, canceled,
> incomplete, incomplete_expired, trialing, paused, all, or ended

`all` and `ended` are filter-only values — they are not statuses an object can
carry. The mock treats `all` as a wildcard and, given no `status` at all, hides
canceled subscriptions the way the live API does.

**Example request:**

```bash
curl -u sk_test_4eC39HqLyjWDarjtT1zdp7dc: \
  "https://api.stripe.com/v1/subscriptions?limit=2"
```

**Example response (200):**

```json
{
  "object": "list",
  "url": "/v1/subscriptions",
  "has_more": true,
  "data": [
    {
      "id": "sub_acme001",
      "object": "subscription",
      "customer": "cus_acme001",
      "status": "active",
      "collection_method": "charge_automatically",
      "currency": "usd",
      "created": 1710500000,
      "cancel_at_period_end": false,
      "canceled_at": null,
      "ended_at": null,
      "start_date": 1710500000,
      "billing_cycle_anchor": 1710500000,
      "livemode": false,
      "metadata": {},
      "latest_invoice": "in_acme001",
      "default_payment_method": "pm_card_visa",
      "items": {
        "object": "list",
        "url": "/v1/subscription_items?subscription=sub_acme001",
        "has_more": false,
        "total_count": 1,
        "data": [
          {
            "id": "si_acme001",
            "object": "subscription_item",
            "created": 1710500000,
            "quantity": 1,
            "subscription": "sub_acme001",
            "current_period_start": 1720000000,
            "current_period_end": 1722678400,
            "price": {
              "id": "price_growth",
              "object": "price",
              "active": true,
              "billing_scheme": "per_unit",
              "currency": "usd",
              "product": "prod_growth",
              "recurring": {
                "interval": "month",
                "interval_count": 1,
                "usage_type": "licensed"
              },
              "type": "recurring",
              "unit_amount": 480000,
              "unit_amount_decimal": "480000"
            }
          }
        ]
      }
    },
    {
      "id": "sub_globex002",
      "object": "subscription",
      "customer": "cus_globex002",
      "status": "active",
      "collection_method": "charge_automatically",
      "currency": "usd",
      "created": 1712000000,
      "cancel_at_period_end": false,
      "canceled_at": null,
      "ended_at": null,
      "start_date": 1712000000,
      "billing_cycle_anchor": 1712000000,
      "livemode": false,
      "metadata": {},
      "latest_invoice": "in_globex002",
      "default_payment_method": null,
      "items": {
        "object": "list",
        "url": "/v1/subscription_items?subscription=sub_globex002",
        "has_more": false,
        "total_count": 1,
        "data": [
          {
            "id": "si_globex002",
            "object": "subscription_item",
            "created": 1712000000,
            "quantity": 1,
            "subscription": "sub_globex002",
            "current_period_start": 1720000000,
            "current_period_end": 1722678400,
            "price": {
              "id": "price_starter",
              "object": "price",
              "active": true,
              "billing_scheme": "per_unit",
              "currency": "usd",
              "product": "prod_starter",
              "recurring": {
                "interval": "month",
                "interval_count": 1,
                "usage_type": "licensed"
              },
              "type": "recurring",
              "unit_amount": 240000,
              "unit_amount_decimal": "240000"
            }
          }
        ]
      }
    }
  ]
}
```

### Subscription Status Enum

| Status | Description |
|--------|-------------|
| `incomplete` | Initial payment attempt failed |
| `incomplete_expired` | First invoice not paid within 23 hours |
| `trialing` | In trial period |
| `active` | Fully active and paid |
| `past_due` | Latest invoice payment failed |
| `canceled` | Canceled by customer or API |
| `unpaid` | Still unpaid after all retry attempts |
| `paused` | Payment collection paused |

---

### 3. List Invoices

```
GET /v1/invoices
```

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 10 | Results per page (1–100) |
| `starting_after` | string | — | Cursor: last object ID |
| `customer` | string | — | Filter by customer ID |
| `subscription` | string | — | Filter by subscription ID |
| `status` | string | — | Filter by status |

**Example response (200):**

```json
{
  "object": "list",
  "url": "/v1/invoices",
  "has_more": false,
  "data": [
    {
      "id": "in_acme001",
      "object": "invoice",
      "customer": "cus_acme001",
      "subscription": "sub_acme001",
      "status": "paid",
      "currency": "usd",
      "amount_due": 480000,
      "amount_paid": 480000,
      "amount_remaining": 0,
      "total": 480000,
      "subtotal": 480000,
      "created": 1720000000,
      "period_start": 1720000000,
      "period_end": 1722678400,
      "paid": true,
      "livemode": false,
      "metadata": {},
      "number": "ACME01-0014",
      "hosted_invoice_url": "https://invoice.stripe.com/i/acct_mock/test_inv_acme001"
    }
  ]
}
```

### Invoice Status Enum

| Status | Description |
|--------|-------------|
| `draft` | Not yet finalized |
| `open` | Finalized, awaiting payment |
| `paid` | Successfully paid |
| `uncollectible` | Marked uncollectible |
| `void` | Voided |

---

## Pagination

Stripe uses **cursor-based pagination** with the list envelope.

### How it works

1. Make initial request with optional `limit`
2. If `has_more` is `true`, take the `id` of the **last** object in `data` and pass it as `starting_after`
3. Repeat until `has_more` is `false`

### Rules

- `limit` range: 1–100 (default 10)
- `starting_after` and `ending_before` are **mutually exclusive**
- Results are returned in **reverse chronological order** (newest first)
- `starting_after` fetches the next page going forward in time (older items)
- `ending_before` fetches items newer than the given ID

### Pseudocode

```python
customers = []
starting_after = None
while True:
    params = {"limit": 100}
    if starting_after:
        params["starting_after"] = starting_after
    response = get("/v1/customers", params=params)
    customers.extend(response["data"])
    if not response["has_more"]:
        break
    starting_after = response["data"][-1]["id"]
```

---

## Error Responses

### 401 Unauthorized

```json
{
  "error": {
    "type": "authentication_error",
    "message": "Invalid API Key provided: sk_test_****1234",
    "code": "api_key_invalid"
  }
}
```

### 429 Rate Limit

```json
{
  "error": {
    "type": "rate_limit_error",
    "message": "Too many requests. Please retry after a brief wait.",
    "code": "rate_limit"
  }
}
```

### 400 Bad Request

```json
{
  "error": {
    "type": "invalid_request_error",
    "message": "Invalid integer: not_a_number",
    "param": "limit",
    "code": "parameter_invalid_integer"
  }
}
```

---

## Notes

- All monetary amounts are in the **smallest currency unit** (e.g., cents for USD). `480000` = $4,800.00
- `current_period_start` and `current_period_end` are on the **subscription_item** level, not the subscription level (moved in API version 2025-03-31.basil). They are not on the subscription itself at all — reading `subscription.current_period_end` yields nothing
- There is no top-level `subscription.plan`. The plan lives on each item as `items.data[].price`; a `plan` beside `items` is a pre-`items` shape and was removed from the mock and the fixtures
- Neither `customer` nor `subscription` carries an updated-at timestamp. `created` is the only timestamp either object has, so `created` is what `OBSERVED_AT` names for both — checked field by field against the Customer object reference
- Object IDs are prefixed by type: `cus_` (customer), `sub_` (subscription), `in_` (invoice), `si_` (subscription_item), `price_` (price), `prod_` (product), `pm_` (payment method)
- Stripe has an OpenAPI spec available for detailed field documentation
- The mock server does not enforce `starting_after`/`ending_before` mutual exclusivity — it ignores `ending_before` if both are provided

---

## What Was Verified Live

Checked on 2026-09-14 against the sandbox account with the restricted key:

| Claim | Verdict |
|-------|---------|
| Bearer auth on a restricted key | **verified** — `200` |
| List envelope `object` / `url` / `has_more` / `data` | **verified** on both endpoints |
| `status=all` is a valid filter value | **verified** — the `400` enum names it |
| `Stripe-Version` is honoured and echoed | **verified** — `200`, header echoed |
| An unknown `Stripe-Version` fails loudly | **verified** — `400` |
| `/v1/charges` is outside the key's scope | **verified** — `403 more_permissions_required` |
| Customer and subscription **record fields** | **NOT verified** — the account holds zero customers and zero subscriptions, so every field below is taken from this reference and Stripe's public docs, never from a live record |

The record shapes stay unverified until the account has data. Nothing in this
file should be read as field-level evidence from the live API.

## Reference

- [List Customers](https://docs.stripe.com/api/customers/list) -- Query parameters, response structure, and pagination for customers
- [List Subscriptions](https://docs.stripe.com/api/subscriptions/list) -- Subscription list endpoint and filtering parameters
- [Subscription Object](https://docs.stripe.com/api/subscriptions/object) -- Subscription status enum and field definitions
- [List Invoices](https://docs.stripe.com/api/invoices/list) -- Invoice list endpoint, status enum, and filtering
- [Rate Limits](https://docs.stripe.com/rate-limits) -- Global and per-endpoint rate limit details
