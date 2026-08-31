# WooCommerce REST API

> API Version: v3
> Category: E-commerce

---

## Base URL

```
https://{site}/wp-json/wc/v3/
```

## Authentication

HTTP Basic Auth with consumer key and consumer secret:

```
Authorization: Basic base64({consumer_key}:{consumer_secret})
```

For HTTPS connections, pass credentials as Basic Auth. For HTTP (not recommended), pass as query parameters:

```
?consumer_key=ck_mock_xxxxxxxxxxxx&consumer_secret=cs_mock_xxxxxxxxxxxx
```

Returns `401 Unauthorized` without valid credentials.

---

## Endpoints

### GET /orders

List orders.

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `page` | int | 1 | Page number |
| `per_page` | int | 10 | Items per page (max 100) |
| `search` | string | — | Limit results to those matching a string |
| `status` | string | `any` | `pending`, `processing`, `on-hold`, `completed`, `cancelled`, `refunded`, `failed`, `trash`, `any` |
| `after` | string | — | ISO 8601 date, limit to after this date |
| `before` | string | — | ISO 8601 date, limit to before this date |
| `order` | string | `desc` | `asc` or `desc` |
| `orderby` | string | `date` | `date`, `modified`, `id`, `include`, `title`, `slug` |
| `customer` | int | — | Filter by customer ID |
| `product` | int | — | Filter by product ID |
| `dp` | int | 2 | Number of decimal points to use in each resource |

**Example Request:**

```bash
curl -u ck_mock_xxxxxxxxxxxx:cs_mock_xxxxxxxxxxxx \
  "https://mystore.com/wp-json/wc/v3/orders?per_page=2&page=1"
```

**Example Response:**

Response is a **flat JSON array** (not wrapped in an envelope). Pagination metadata is in response headers.

**Response Headers:**
```
X-WP-Total: 48
X-WP-TotalPages: 24
Link: <https://mystore.com/wp-json/wc/v3/orders?page=2>; rel="next"
```

**Response Body:**
```json
[
  {
    "id": 727,
    "parent_id": 0,
    "status": "processing",
    "currency": "USD",
    "version": "9.0.0",
    "prices_include_tax": false,
    "date_created": "2026-06-15T10:30:00",
    "date_created_gmt": "2026-06-15T14:30:00",
    "date_modified": "2026-06-16T08:15:00",
    "date_modified_gmt": "2026-06-16T12:15:00",
    "discount_total": "0.00",
    "discount_tax": "0.00",
    "shipping_total": "10.00",
    "shipping_tax": "0.00",
    "cart_tax": "22.95",
    "total": "262.92",
    "total_tax": "22.95",
    "customer_id": 12,
    "order_key": "wc_order_abc123def456",
    "number": "727",
    "payment_method": "stripe",
    "payment_method_title": "Credit Card (Stripe)",
    "transaction_id": "ch_3abc123",
    "customer_ip_address": "192.168.1.1",
    "customer_note": "",
    "date_completed": null,
    "date_paid": "2026-06-15T10:31:00",
    "date_paid_gmt": "2026-06-15T14:31:00",
    "cart_hash": "abc123",
    "billing": {
      "first_name": "Jane",
      "last_name": "Smith",
      "company": "Acme Corp",
      "address_1": "123 Main St",
      "address_2": "Suite 400",
      "city": "San Francisco",
      "state": "CA",
      "postcode": "94105",
      "country": "US",
      "email": "jane@acme.io",
      "phone": "+14155551234"
    },
    "shipping": {
      "first_name": "Jane",
      "last_name": "Smith",
      "company": "Acme Corp",
      "address_1": "123 Main St",
      "address_2": "Suite 400",
      "city": "San Francisco",
      "state": "CA",
      "postcode": "94105",
      "country": "US",
      "phone": "+14155551234"
    },
    "line_items": [
      {
        "id": 315,
        "name": "Widget Pro - Blue / Large",
        "product_id": 93,
        "variation_id": 94,
        "quantity": 3,
        "tax_class": "",
        "subtotal": "269.97",
        "subtotal_tax": "22.95",
        "total": "269.97",
        "total_tax": "22.95",
        "taxes": [
          {
            "id": 1,
            "total": "22.95",
            "subtotal": "22.95"
          }
        ],
        "meta_data": [
          {
            "id": 2550,
            "key": "pa_color",
            "value": "blue",
            "display_key": "Color",
            "display_value": "Blue"
          },
          {
            "id": 2551,
            "key": "pa_size",
            "value": "large",
            "display_key": "Size",
            "display_value": "Large"
          }
        ],
        "sku": "WP-BL-LG",
        "price": 89.99,
        "image": {
          "id": 201,
          "src": "https://mystore.com/wp-content/uploads/widget-pro-blue.jpg"
        }
      }
    ],
    "tax_lines": [
      {
        "id": 318,
        "rate_code": "US-CA-STATE TAX-1",
        "rate_id": 1,
        "label": "State Tax",
        "compound": false,
        "tax_total": "22.95",
        "shipping_tax_total": "0.00",
        "rate_percent": 8.5,
        "meta_data": []
      }
    ],
    "shipping_lines": [
      {
        "id": 317,
        "method_title": "Flat Rate",
        "method_id": "flat_rate",
        "instance_id": "1",
        "total": "10.00",
        "total_tax": "0.00",
        "taxes": [],
        "meta_data": []
      }
    ],
    "fee_lines": [],
    "coupon_lines": [],
    "refunds": [],
    "payment_url": "https://mystore.com/checkout/order-pay/727/",
    "currency_symbol": "$",
    "meta_data": [
      {
        "id": 13106,
        "key": "_stripe_customer_id",
        "value": "cus_abc123"
      }
    ],
    "_links": {
      "self": [{"href": "https://mystore.com/wp-json/wc/v3/orders/727"}],
      "collection": [{"href": "https://mystore.com/wp-json/wc/v3/orders"}]
    }
  }
]
```

---

### GET /customers

List customers.

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `page` | int | 1 | Page number |
| `per_page` | int | 10 | Items per page (max 100) |
| `search` | string | — | Limit results to those matching a string |
| `email` | string | — | Filter by email |
| `role` | string | `customer` | Filter by role: `all`, `administrator`, `editor`, `author`, `contributor`, `subscriber`, `customer`, `shop_manager` |
| `order` | string | `asc` | `asc` or `desc` |
| `orderby` | string | `name` | `id`, `include`, `name`, `registered_date` |

**Example Request:**

```bash
curl -u ck_mock_xxxxxxxxxxxx:cs_mock_xxxxxxxxxxxx \
  "https://mystore.com/wp-json/wc/v3/customers?per_page=2"
```

**Example Response:**

```json
[
  {
    "id": 12,
    "date_created": "2025-03-15T10:30:00",
    "date_created_gmt": "2025-03-15T14:30:00",
    "date_modified": "2026-06-01T14:22:00",
    "date_modified_gmt": "2026-06-01T18:22:00",
    "email": "jane@acme.io",
    "first_name": "Jane",
    "last_name": "Smith",
    "role": "customer",
    "username": "janesmith",
    "billing": {
      "first_name": "Jane",
      "last_name": "Smith",
      "company": "Acme Corp",
      "address_1": "123 Main St",
      "address_2": "Suite 400",
      "city": "San Francisco",
      "state": "CA",
      "postcode": "94105",
      "country": "US",
      "email": "jane@acme.io",
      "phone": "+14155551234"
    },
    "shipping": {
      "first_name": "Jane",
      "last_name": "Smith",
      "company": "Acme Corp",
      "address_1": "123 Main St",
      "address_2": "Suite 400",
      "city": "San Francisco",
      "state": "CA",
      "postcode": "94105",
      "country": "US",
      "phone": "+14155551234"
    },
    "is_paying_customer": true,
    "avatar_url": "https://secure.gravatar.com/avatar/abc123?s=96",
    "meta_data": [
      {
        "id": 40,
        "key": "company_domain",
        "value": "acme.io"
      }
    ],
    "_links": {
      "self": [{"href": "https://mystore.com/wp-json/wc/v3/customers/12"}],
      "collection": [{"href": "https://mystore.com/wp-json/wc/v3/customers"}]
    }
  }
]
```

---

### GET /products

List products.

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `page` | int | 1 | Page number |
| `per_page` | int | 10 | Items per page (max 100) |
| `search` | string | — | Limit results to those matching a string |
| `status` | string | `any` | `draft`, `pending`, `private`, `publish`, `any` |
| `type` | string | — | `simple`, `grouped`, `external`, `variable` |
| `category` | string | — | Filter by category ID |
| `tag` | string | — | Filter by tag ID |
| `sku` | string | — | Filter by SKU |
| `featured` | boolean | — | Filter by featured products |
| `on_sale` | boolean | — | Filter by on-sale products |
| `min_price` | string | — | Minimum price threshold |
| `max_price` | string | — | Maximum price threshold |
| `stock_status` | string | — | `instock`, `outofstock`, `onbackorder` |
| `order` | string | `desc` | `asc` or `desc` |
| `orderby` | string | `date` | `date`, `modified`, `id`, `include`, `title`, `slug`, `price`, `popularity`, `rating`, `menu_order` |

**Example Request:**

```bash
curl -u ck_mock_xxxxxxxxxxxx:cs_mock_xxxxxxxxxxxx \
  "https://mystore.com/wp-json/wc/v3/products?per_page=2"
```

**Example Response:**

```json
[
  {
    "id": 93,
    "name": "Widget Pro",
    "slug": "widget-pro",
    "permalink": "https://mystore.com/product/widget-pro/",
    "date_created": "2025-01-10T09:00:00",
    "date_created_gmt": "2025-01-10T14:00:00",
    "date_modified": "2026-06-10T11:30:00",
    "date_modified_gmt": "2026-06-10T15:30:00",
    "type": "variable",
    "status": "publish",
    "featured": false,
    "catalog_visibility": "visible",
    "description": "<p>The best widget for professionals.</p>",
    "short_description": "<p>Premium widget with customizable options.</p>",
    "sku": "WP",
    "price": "79.99",
    "regular_price": "",
    "sale_price": "",
    "on_sale": true,
    "purchasable": true,
    "total_sales": 245,
    "virtual": false,
    "downloadable": false,
    "tax_status": "taxable",
    "tax_class": "",
    "manage_stock": false,
    "stock_quantity": null,
    "stock_status": "instock",
    "backorders": "no",
    "backorders_allowed": false,
    "backordered": false,
    "weight": "0.88",
    "dimensions": {
      "length": "10",
      "width": "5",
      "height": "3"
    },
    "shipping_required": true,
    "reviews_allowed": true,
    "average_rating": "4.50",
    "rating_count": 12,
    "categories": [
      {
        "id": 15,
        "name": "Widgets",
        "slug": "widgets"
      }
    ],
    "tags": [
      {
        "id": 30,
        "name": "bestseller",
        "slug": "bestseller"
      }
    ],
    "images": [
      {
        "id": 201,
        "date_created": "2025-01-10T09:00:00",
        "date_created_gmt": "2025-01-10T14:00:00",
        "date_modified": "2025-01-10T09:00:00",
        "date_modified_gmt": "2025-01-10T14:00:00",
        "src": "https://mystore.com/wp-content/uploads/widget-pro-blue.jpg",
        "name": "widget-pro-blue",
        "alt": "Widget Pro in Blue"
      }
    ],
    "attributes": [
      {
        "id": 1,
        "name": "Color",
        "position": 0,
        "visible": true,
        "variation": true,
        "options": ["Blue", "Red", "Green"]
      },
      {
        "id": 2,
        "name": "Size",
        "position": 1,
        "visible": true,
        "variation": true,
        "options": ["Small", "Medium", "Large"]
      }
    ],
    "variations": [94, 95, 96, 97, 98, 99],
    "meta_data": [],
    "_links": {
      "self": [{"href": "https://mystore.com/wp-json/wc/v3/products/93"}],
      "collection": [{"href": "https://mystore.com/wp-json/wc/v3/products"}]
    }
  }
]
```

---

## Pagination

WooCommerce uses **page number** pagination.

### How It Works

1. Set `page` (default 1) and `per_page` (default 10, max 100).
2. Check response headers for total counts.
3. Increment `page` until you've fetched all pages.

### Response Headers

| Header | Description |
|--------|-------------|
| `X-WP-Total` | Total number of items |
| `X-WP-TotalPages` | Total number of pages |
| `Link` | Standard Link header with rel="next" and rel="prev" |

### Example Pagination Flow

```bash
# Page 1
curl -u ck_mock:cs_mock "https://mystore.com/wp-json/wc/v3/orders?page=1&per_page=25"
# Headers: X-WP-Total: 48, X-WP-TotalPages: 2

# Page 2 (last page)
curl -u ck_mock:cs_mock "https://mystore.com/wp-json/wc/v3/orders?page=2&per_page=25"
# Headers: X-WP-Total: 48, X-WP-TotalPages: 2
# No Link rel="next" → done
```

### Done Condition

Finished when `page >= X-WP-TotalPages` or when the `Link` header has no `rel="next"`.

---

## Error Responses

### 401 Unauthorized

```json
{
  "code": "woocommerce_rest_cannot_view",
  "message": "Sorry, you cannot list resources.",
  "data": {
    "status": 401
  }
}
```

### 404 Not Found

```json
{
  "code": "woocommerce_rest_order_invalid_id",
  "message": "Invalid ID.",
  "data": {
    "status": 404
  }
}
```

### 400 Bad Request

```json
{
  "code": "rest_invalid_param",
  "message": "Invalid parameter(s): per_page",
  "data": {
    "status": 400,
    "params": {
      "per_page": "per_page must be between 1 and 100 (inclusive)."
    }
  }
}
```

---

## Notes

- Response body is a **flat JSON array**, not wrapped in an envelope object.
- Pagination metadata is only in response headers (`X-WP-Total`, `X-WP-TotalPages`).
- All monetary values are strings (e.g., `"269.97"`).
- Dates are in local time by default; `_gmt` variants are UTC.
- The `meta_data` array on orders, customers, and products holds arbitrary key-value pairs.
- `_links` follows the HAL standard with `self` and `collection` links.

---

## Reference

- [WooCommerce REST API v3 overview](https://developer.woocommerce.com/docs/apis/rest-api/v3/)
- [Orders endpoint](https://developer.woocommerce.com/docs/apis/rest-api/v3/orders/)
- [Products endpoint](https://developer.woocommerce.com/docs/apis/rest-api/v3/products/)
- [Authentication](https://developer.woocommerce.com/docs/apis/rest-api/authentication/)
- [WooCommerce REST API Documentation (GitHub)](https://woocommerce.github.io/woocommerce-rest-api-docs/)
