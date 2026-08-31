"""
WooCommerce REST API v3 mock provider.
Contract: seeds/docs/23-woocommerce.md

Basic Auth. Page-number pagination with X-WP-Total/X-WP-TotalPages headers.
Flat JSON arrays (no envelope). Monetary values as strings.
"""

from fastapi import APIRouter, Request, Query
from fastapi.responses import JSONResponse
from seeds.helpers import require_basic_auth, page_paginate
from seeds.world import PEOPLE, COMPANIES_BY_ID

router = APIRouter()

_ORDERS = [
    {
        "id": 727, "parent_id": 0, "status": "processing", "currency": "USD",
        "date_created": "2026-06-15T10:30:00", "date_modified": "2026-06-16T08:15:00",
        "discount_total": "0.00", "shipping_total": "10.00", "cart_tax": "22.95",
        "total": "279.97", "total_tax": "22.95", "customer_id": 12,
        "order_key": "wc_order_abc123", "number": "727",
        "payment_method": "stripe", "payment_method_title": "Credit Card (Stripe)",
        "date_paid": "2026-06-15T10:31:00",
        "billing": {"first_name": "Jane", "last_name": "Smith", "company": "Acme Corp", "address_1": "123 Main St", "city": "San Francisco", "state": "CA", "postcode": "94105", "country": "US", "email": "jane@acme.io", "phone": "+14155551234"},
        "shipping": {"first_name": "Jane", "last_name": "Smith", "company": "Acme Corp", "address_1": "123 Main St", "city": "San Francisco", "state": "CA", "postcode": "94105", "country": "US"},
        "line_items": [{"id": 315, "name": "Widget Pro", "product_id": 93, "quantity": 3, "subtotal": "269.97", "total": "269.97", "sku": "WP-001", "price": 89.99}],
        "currency_symbol": "$",
        "_links": {"self": [{"href": "http://localhost:8100/woocommerce/wc/v3/orders/727"}], "collection": [{"href": "http://localhost:8100/woocommerce/wc/v3/orders"}]},
    },
    {
        "id": 728, "parent_id": 0, "status": "completed", "currency": "USD",
        "date_created": "2026-07-01T08:00:00", "date_modified": "2026-07-02T10:30:00",
        "discount_total": "15.00", "shipping_total": "0.00", "cart_tax": "7.65",
        "total": "82.64", "total_tax": "7.65", "customer_id": 13,
        "order_key": "wc_order_def456", "number": "728",
        "payment_method": "stripe", "payment_method_title": "Credit Card (Stripe)",
        "date_paid": "2026-07-01T08:01:00",
        "billing": {"first_name": "Mike", "last_name": "Chen", "company": "Globex Inc", "address_1": "456 Oak Ave", "city": "Austin", "state": "TX", "postcode": "78701", "country": "US", "email": "mike@globex.com", "phone": "+15125550201"},
        "shipping": {"first_name": "Mike", "last_name": "Chen", "company": "Globex Inc", "address_1": "456 Oak Ave", "city": "Austin", "state": "TX", "postcode": "78701", "country": "US"},
        "line_items": [{"id": 316, "name": "Gadget Lite", "product_id": 94, "quantity": 1, "subtotal": "89.99", "total": "74.99", "sku": "GL-001", "price": 89.99}],
        "currency_symbol": "$",
        "_links": {"self": [{"href": "http://localhost:8100/woocommerce/wc/v3/orders/728"}], "collection": [{"href": "http://localhost:8100/woocommerce/wc/v3/orders"}]},
    },
]

_CUSTOMERS = [
    {
        "id": 12, "email": "jane@acme.io", "first_name": "Jane", "last_name": "Smith",
        "role": "customer", "username": "janesmith",
        "date_created": "2025-03-15T10:30:00",
        "billing": {"first_name": "Jane", "last_name": "Smith", "company": "Acme Corp", "address_1": "123 Main St", "city": "San Francisco", "state": "CA", "postcode": "94105", "country": "US", "email": "jane@acme.io", "phone": "+14155551234"},
        "shipping": {"first_name": "Jane", "last_name": "Smith", "company": "Acme Corp", "address_1": "123 Main St", "city": "San Francisco", "state": "CA", "postcode": "94105", "country": "US"},
        "is_paying_customer": True, "avatar_url": "https://secure.gravatar.com/avatar/mock1",
        "_links": {"self": [{"href": "http://localhost:8100/woocommerce/wc/v3/customers/12"}], "collection": [{"href": "http://localhost:8100/woocommerce/wc/v3/customers"}]},
    },
    {
        "id": 13, "email": "mike@globex.com", "first_name": "Mike", "last_name": "Chen",
        "role": "customer", "username": "mikechen",
        "date_created": "2025-02-01T14:00:00",
        "billing": {"first_name": "Mike", "last_name": "Chen", "company": "Globex Inc", "address_1": "456 Oak Ave", "city": "Austin", "state": "TX", "postcode": "78701", "country": "US", "email": "mike@globex.com", "phone": "+15125550201"},
        "shipping": {"first_name": "Mike", "last_name": "Chen", "company": "Globex Inc", "address_1": "456 Oak Ave", "city": "Austin", "state": "TX", "postcode": "78701", "country": "US"},
        "is_paying_customer": True, "avatar_url": "https://secure.gravatar.com/avatar/mock2",
        "_links": {"self": [{"href": "http://localhost:8100/woocommerce/wc/v3/customers/13"}], "collection": [{"href": "http://localhost:8100/woocommerce/wc/v3/customers"}]},
    },
]

_PRODUCTS = [
    {
        "id": 93, "name": "Widget Pro", "slug": "widget-pro", "type": "simple",
        "status": "publish", "featured": False, "sku": "WP-001",
        "price": "89.99", "regular_price": "89.99", "sale_price": "",
        "on_sale": False, "purchasable": True, "total_sales": 245,
        "stock_status": "instock", "stock_quantity": 150,
        "manage_stock": True, "weight": "0.88",
        "dimensions": {"length": "10", "width": "5", "height": "3"},
        "categories": [{"id": 15, "name": "Widgets", "slug": "widgets"}],
        "tags": [{"id": 30, "name": "bestseller", "slug": "bestseller"}],
        "images": [{"id": 201, "src": "https://mystore.com/wp-content/uploads/widget-pro.jpg", "name": "widget-pro", "alt": "Widget Pro"}],
        "date_created": "2025-01-10T09:00:00",
        "_links": {"self": [{"href": "http://localhost:8100/woocommerce/wc/v3/products/93"}], "collection": [{"href": "http://localhost:8100/woocommerce/wc/v3/products"}]},
    },
    {
        "id": 94, "name": "Gadget Lite", "slug": "gadget-lite", "type": "simple",
        "status": "publish", "featured": False, "sku": "GL-001",
        "price": "89.99", "regular_price": "89.99", "sale_price": "",
        "on_sale": False, "purchasable": True, "total_sales": 120,
        "stock_status": "instock", "stock_quantity": 300,
        "manage_stock": True, "weight": "0.35",
        "dimensions": {"length": "8", "width": "4", "height": "2"},
        "categories": [{"id": 16, "name": "Gadgets", "slug": "gadgets"}],
        "tags": [],
        "images": [{"id": 202, "src": "https://mystore.com/wp-content/uploads/gadget-lite.jpg", "name": "gadget-lite", "alt": "Gadget Lite"}],
        "date_created": "2025-06-15T10:00:00",
        "_links": {"self": [{"href": "http://localhost:8100/woocommerce/wc/v3/products/94"}], "collection": [{"href": "http://localhost:8100/woocommerce/wc/v3/products"}]},
    },
]


def _wc_list(items, page, per_page):
    page_items, total = page_paginate(items, page - 1, per_page)
    total_pages = max(1, -(-total // per_page))
    headers = {"X-WP-Total": str(total), "X-WP-TotalPages": str(total_pages)}
    if page < total_pages:
        headers["Link"] = f'<http://localhost:8100/woocommerce/wc/v3/?page={page+1}>; rel="next"'
    return JSONResponse(content=page_items, headers=headers)


@router.get("/orders")
async def list_orders(request: Request, page: int = Query(1, ge=1), per_page: int = Query(10, ge=1, le=100)):
    require_basic_auth(request)
    return _wc_list(_ORDERS, page, per_page)


@router.get("/customers")
async def list_customers(request: Request, page: int = Query(1, ge=1), per_page: int = Query(10, ge=1, le=100)):
    require_basic_auth(request)
    return _wc_list(_CUSTOMERS, page, per_page)


@router.get("/products")
async def list_products(request: Request, page: int = Query(1, ge=1), per_page: int = Query(10, ge=1, le=100)):
    require_basic_auth(request)
    return _wc_list(_PRODUCTS, page, per_page)
