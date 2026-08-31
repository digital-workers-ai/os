# Shopify Admin REST API

> API Version: 2024-01
> Category: E-commerce

---

## Base URL

```
https://{store}.myshopify.com/admin/api/2024-01/
```

## Authentication

Custom header with access token:

```
X-Shopify-Access-Token: shpat_mock_xxxxxxxxxxxx
Content-Type: application/json
```

Returns `401 Unauthorized` without valid token.

---

## Endpoints

### GET /orders.json

List orders.

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `status` | string | `open` | Filter by status: `open`, `closed`, `cancelled`, `any` |
| `created_at_min` | string | — | ISO 8601 minimum creation date |
| `created_at_max` | string | — | ISO 8601 maximum creation date |
| `updated_at_min` | string | — | ISO 8601 minimum update date |
| `updated_at_max` | string | — | ISO 8601 maximum update date |
| `financial_status` | string | `any` | `authorized`, `pending`, `paid`, `partially_paid`, `refunded`, `voided`, `partially_refunded`, `any`, `unpaid` |
| `fulfillment_status` | string | `any` | `shipped`, `partial`, `unshipped`, `any`, `unfulfilled` |
| `limit` | int | 50 | Max 250 |
| `fields` | string | — | Comma-separated field list |
| `since_id` | int | — | Restrict results to after the specified ID |

**Example Request:**

```bash
curl -H "X-Shopify-Access-Token: shpat_mock_xxxxxxxxxxxx" \
  "https://mystore.myshopify.com/admin/api/2024-01/orders.json?status=any&limit=2"
```

**Example Response:**

```json
{
  "orders": [
    {
      "id": 5678901234,
      "admin_graphql_api_id": "gid://shopify/Order/5678901234",
      "name": "#1001",
      "email": "jane@acme.io",
      "created_at": "2026-06-15T10:30:00-04:00",
      "updated_at": "2026-06-16T08:15:00-04:00",
      "closed_at": null,
      "cancelled_at": null,
      "number": 1,
      "order_number": 1001,
      "note": "Please ship ASAP",
      "token": "abc123def456",
      "total_price": "299.97",
      "subtotal_price": "269.97",
      "total_weight": 1500,
      "total_tax": "30.00",
      "taxes_included": false,
      "currency": "USD",
      "financial_status": "paid",
      "fulfillment_status": "unfulfilled",
      "confirmed": true,
      "total_discounts": "0.00",
      "total_line_items_price": "269.97",
      "buyer_accepts_marketing": true,
      "referring_site": "https://www.google.com",
      "landing_site": "/products/widget-pro",
      "cancel_reason": null,
      "total_price_usd": "299.97",
      "checkout_token": "tok_check_abc123",
      "tags": "vip, repeat-buyer",
      "contact_email": "jane@acme.io",
      "order_status_url": "https://mystore.myshopify.com/orders/abc123/authenticate",
      "processing_method": "direct",
      "source_name": "web",
      "test": false,
      "customer": {
        "id": 1234567890,
        "email": "jane@acme.io",
        "first_name": "Jane",
        "last_name": "Smith",
        "orders_count": 5,
        "total_spent": "1249.85",
        "created_at": "2025-03-15T10:30:00-04:00",
        "tags": "vip",
        "default_address": {
          "id": 9876543210,
          "first_name": "Jane",
          "last_name": "Smith",
          "address1": "123 Main St",
          "address2": "Suite 400",
          "city": "San Francisco",
          "province": "California",
          "province_code": "CA",
          "country": "United States",
          "country_code": "US",
          "zip": "94105",
          "phone": "+14155551234"
        }
      },
      "line_items": [
        {
          "id": 11111111,
          "variant_id": 22222222,
          "product_id": 33333333,
          "title": "Widget Pro",
          "variant_title": "Blue / Large",
          "sku": "WP-BL-LG",
          "quantity": 3,
          "price": "89.99",
          "total_discount": "0.00",
          "fulfillment_status": null,
          "grams": 500,
          "vendor": "Acme Corp",
          "requires_shipping": true,
          "taxable": true,
          "gift_card": false,
          "name": "Widget Pro - Blue / Large",
          "properties": [],
          "tax_lines": [
            {
              "title": "State Tax",
              "price": "7.65",
              "rate": 0.085
            }
          ],
          "discount_allocations": []
        }
      ],
      "shipping_lines": [
        {
          "id": 44444444,
          "title": "Standard Shipping",
          "price": "9.99",
          "code": "standard",
          "source": "shopify",
          "carrier_identifier": null
        }
      ],
      "billing_address": {
        "first_name": "Jane",
        "last_name": "Smith",
        "address1": "123 Main St",
        "address2": "Suite 400",
        "city": "San Francisco",
        "province": "California",
        "province_code": "CA",
        "country": "United States",
        "country_code": "US",
        "zip": "94105",
        "phone": "+14155551234"
      },
      "shipping_address": {
        "first_name": "Jane",
        "last_name": "Smith",
        "address1": "123 Main St",
        "address2": "Suite 400",
        "city": "San Francisco",
        "province": "California",
        "province_code": "CA",
        "country": "United States",
        "country_code": "US",
        "zip": "94105",
        "phone": "+14155551234"
      },
      "fulfillments": [],
      "refunds": []
    }
  ]
}
```

---

### GET /customers.json

List customers.

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `ids` | string | — | Restrict results to specified comma-separated IDs |
| `created_at_min` | string | — | ISO 8601 minimum creation date |
| `created_at_max` | string | — | ISO 8601 maximum creation date |
| `updated_at_min` | string | — | ISO 8601 minimum update date |
| `updated_at_max` | string | — | ISO 8601 maximum update date |
| `limit` | int | 50 | Max 250 |
| `since_id` | int | — | Restrict results to after the specified ID |
| `fields` | string | — | Comma-separated field list |

**Example Request:**

```bash
curl -H "X-Shopify-Access-Token: shpat_mock_xxxxxxxxxxxx" \
  "https://mystore.myshopify.com/admin/api/2024-01/customers.json?limit=2"
```

**Example Response:**

```json
{
  "customers": [
    {
      "id": 1234567890,
      "email": "jane@acme.io",
      "first_name": "Jane",
      "last_name": "Smith",
      "created_at": "2025-03-15T10:30:00-04:00",
      "updated_at": "2026-06-01T14:22:00-04:00",
      "orders_count": 5,
      "state": "enabled",
      "total_spent": "1249.85",
      "last_order_id": 5678901234,
      "last_order_name": "#1001",
      "note": "VIP customer",
      "verified_email": true,
      "multipass_identifier": null,
      "tax_exempt": false,
      "tags": "vip, repeat-buyer",
      "currency": "USD",
      "phone": "+14155551234",
      "email_marketing_consent": {
        "state": "subscribed",
        "opt_in_level": "single_opt_in",
        "consent_updated_at": "2025-03-15T10:30:00-04:00"
      },
      "sms_marketing_consent": null,
      "admin_graphql_api_id": "gid://shopify/Customer/1234567890",
      "tax_exemptions": [],
      "default_address": {
        "id": 9876543210,
        "customer_id": 1234567890,
        "first_name": "Jane",
        "last_name": "Smith",
        "company": "Acme Corp",
        "address1": "123 Main St",
        "address2": "Suite 400",
        "city": "San Francisco",
        "province": "California",
        "province_code": "CA",
        "country": "United States",
        "country_code": "US",
        "zip": "94105",
        "phone": "+14155551234",
        "name": "Jane Smith",
        "default": true
      },
      "addresses": [
        {
          "id": 9876543210,
          "customer_id": 1234567890,
          "first_name": "Jane",
          "last_name": "Smith",
          "company": "Acme Corp",
          "address1": "123 Main St",
          "address2": "Suite 400",
          "city": "San Francisco",
          "province": "California",
          "province_code": "CA",
          "country": "United States",
          "country_code": "US",
          "zip": "94105",
          "phone": "+14155551234",
          "name": "Jane Smith",
          "default": true
        }
      ]
    }
  ]
}
```

---

### GET /products.json

List products.

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `ids` | string | — | Return only products specified by comma-separated IDs |
| `collection_id` | int | — | Filter by collection |
| `product_type` | string | — | Filter by product type |
| `vendor` | string | — | Filter by vendor |
| `handle` | string | — | Filter by comma-separated list of product handles |
| `status` | string | `active` | `active`, `archived`, `draft` |
| `created_at_min` | string | — | ISO 8601 minimum creation date |
| `created_at_max` | string | — | ISO 8601 maximum creation date |
| `updated_at_min` | string | — | ISO 8601 minimum update date |
| `updated_at_max` | string | — | ISO 8601 maximum update date |
| `published_at_min` | string | — | ISO 8601 minimum publish date |
| `published_at_max` | string | — | ISO 8601 maximum publish date |
| `limit` | int | 50 | Max 250 |
| `since_id` | int | — | Restrict results to after the specified ID |
| `fields` | string | — | Comma-separated field list |

**Example Request:**

```bash
curl -H "X-Shopify-Access-Token: shpat_mock_xxxxxxxxxxxx" \
  "https://mystore.myshopify.com/admin/api/2024-01/products.json?limit=2"
```

**Example Response:**

```json
{
  "products": [
    {
      "id": 33333333,
      "title": "Widget Pro",
      "body_html": "<p>The best widget for professionals.</p>",
      "vendor": "Acme Corp",
      "product_type": "Widgets",
      "created_at": "2025-01-10T09:00:00-05:00",
      "updated_at": "2026-06-10T11:30:00-04:00",
      "published_at": "2025-01-10T09:15:00-05:00",
      "handle": "widget-pro",
      "template_suffix": null,
      "published_scope": "global",
      "tags": "bestseller, premium",
      "status": "active",
      "admin_graphql_api_id": "gid://shopify/Product/33333333",
      "variants": [
        {
          "id": 22222221,
          "product_id": 33333333,
          "title": "Blue / Small",
          "price": "79.99",
          "compare_at_price": "99.99",
          "sku": "WP-BL-SM",
          "position": 1,
          "inventory_policy": "deny",
          "fulfillment_service": "manual",
          "inventory_management": "shopify",
          "option1": "Blue",
          "option2": "Small",
          "option3": null,
          "created_at": "2025-01-10T09:00:00-05:00",
          "updated_at": "2026-06-10T11:30:00-04:00",
          "taxable": true,
          "barcode": "1234567890123",
          "grams": 400,
          "weight": 0.88,
          "weight_unit": "lb",
          "inventory_item_id": 55555551,
          "inventory_quantity": 150,
          "old_inventory_quantity": 150,
          "requires_shipping": true
        },
        {
          "id": 22222222,
          "product_id": 33333333,
          "title": "Blue / Large",
          "price": "89.99",
          "compare_at_price": "109.99",
          "sku": "WP-BL-LG",
          "position": 2,
          "inventory_policy": "deny",
          "fulfillment_service": "manual",
          "inventory_management": "shopify",
          "option1": "Blue",
          "option2": "Large",
          "option3": null,
          "created_at": "2025-01-10T09:00:00-05:00",
          "updated_at": "2026-06-10T11:30:00-04:00",
          "taxable": true,
          "barcode": "1234567890124",
          "grams": 500,
          "weight": 1.1,
          "weight_unit": "lb",
          "inventory_item_id": 55555552,
          "inventory_quantity": 85,
          "old_inventory_quantity": 85,
          "requires_shipping": true
        }
      ],
      "options": [
        {
          "id": 66666661,
          "product_id": 33333333,
          "name": "Color",
          "position": 1,
          "values": ["Blue", "Red", "Green"]
        },
        {
          "id": 66666662,
          "product_id": 33333333,
          "name": "Size",
          "position": 2,
          "values": ["Small", "Medium", "Large"]
        }
      ],
      "images": [
        {
          "id": 77777771,
          "product_id": 33333333,
          "position": 1,
          "created_at": "2025-01-10T09:00:00-05:00",
          "updated_at": "2025-01-10T09:00:00-05:00",
          "alt": "Widget Pro in Blue",
          "width": 1200,
          "height": 1200,
          "src": "https://cdn.shopify.com/s/files/1/0000/0001/products/widget-pro-blue.jpg",
          "variant_ids": [22222221, 22222222]
        }
      ],
      "image": {
        "id": 77777771,
        "product_id": 33333333,
        "position": 1,
        "created_at": "2025-01-10T09:00:00-05:00",
        "updated_at": "2025-01-10T09:00:00-05:00",
        "alt": "Widget Pro in Blue",
        "width": 1200,
        "height": 1200,
        "src": "https://cdn.shopify.com/s/files/1/0000/0001/products/widget-pro-blue.jpg",
        "variant_ids": [22222221, 22222222]
      }
    }
  ]
}
```

---

## Pagination

Shopify uses **cursor-based pagination** via the HTTP `Link` header.

### How It Works

1. Make the initial request with a `limit` parameter.
2. Check the response `Link` header for `rel="next"`.
3. Extract the `page_info` value from the URL in the Link header.
4. Pass `page_info` as a query parameter on the next request.

### Link Header Format

```
Link: <https://mystore.myshopify.com/admin/api/2024-01/orders.json?page_info=eyJsYXN0X2lkIjo1Njc4OTAxMjM0fQ&limit=50>; rel="next",
      <https://mystore.myshopify.com/admin/api/2024-01/orders.json?page_info=eyJmaXJzdF9pZCI6MTIzNDU2Nzg5MH0&limit=50>; rel="previous"
```

### Pagination Rules

- When `page_info` is present, **no other query params** are allowed except `limit` and `fields`.
- `rel="next"` — present when there are more results ahead.
- `rel="previous"` — present when there are results behind.
- **Done** when the `Link` header has no `rel="next"`.

### Example Pagination Flow

```bash
# First page
curl -D- -H "X-Shopify-Access-Token: shpat_mock_xxxxxxxxxxxx" \
  "https://mystore.myshopify.com/admin/api/2024-01/orders.json?limit=50&status=any"
# Response Link header:
# Link: <...?page_info=abc123&limit=50>; rel="next"

# Next page (only page_info + limit allowed)
curl -D- -H "X-Shopify-Access-Token: shpat_mock_xxxxxxxxxxxx" \
  "https://mystore.myshopify.com/admin/api/2024-01/orders.json?page_info=abc123&limit=50"
# Response Link header:
# Link: <...?page_info=def456&limit=50>; rel="next", <...?page_info=xyz789&limit=50>; rel="previous"

# Last page (no rel="next")
# Link: <...?page_info=xyz789&limit=50>; rel="previous"
```

---

## Error Responses

### 401 Unauthorized

```json
{
  "errors": "[API] Invalid API key or access token (unrecognized login or wrong password)"
}
```

### 404 Not Found

```json
{
  "errors": "Not Found"
}
```

### 422 Unprocessable Entity

```json
{
  "errors": {
    "order": ["cannot be blank"]
  }
}
```

### 429 Too Many Requests

```json
{
  "errors": "Exceeded 2 calls per second for api client. Reduce request rates to resume uninterrupted service."
}
```

Response includes `Retry-After` header with seconds to wait.

---

## Rate Limits

Shopify uses a **leaky bucket** algorithm:

| Plan | Bucket Size | Leak Rate |
|------|------------|-----------|
| Basic/Standard | 40 requests | 2/second |
| Advanced | 40 requests | 4/second |
| Shopify Plus | 400 requests | 20/second |

Rate limit status is in the response header:
```
X-Shopify-Shop-Api-Call-Limit: 32/40
```

---

## Notes

- All monetary values are strings (e.g., `"299.97"`, not `299.97`).
- Timestamps are ISO 8601 with timezone offset.
- The `admin_graphql_api_id` field is the GraphQL global ID for the resource.
- `since_id` is the older pagination method — Link header cursor pagination is preferred.
- When using cursor pagination with `page_info`, original filter params (status, date ranges, etc.) are encoded in the cursor — do not re-send them.

---

## Reference

- [Order resource](https://shopify.dev/docs/api/admin-rest/latest/resources/order)
- [Customer resource](https://shopify.dev/docs/api/admin-rest/latest/resources/customer)
- [Product resource](https://shopify.dev/docs/api/admin-rest/latest/resources/product)
- [REST Admin API pagination](https://shopify.dev/docs/api/admin-rest/usage/pagination)
- [REST Admin API rate limits](https://shopify.dev/docs/api/admin-rest/usage/rate-limits)
