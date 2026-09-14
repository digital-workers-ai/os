"""
Shopify Admin API mock provider.
Contract: seeds/docs/22-shopify.md

X-Shopify-Access-Token header. Link header cursor pagination.
Monetary values as strings.
"""

from fastapi import APIRouter, Request, Query
from fastapi.responses import JSONResponse
from seeds.helpers import require_header, link_header_paginate
from seeds.world import PEOPLE, COMPANIES_BY_ID, SUBSCRIPTIONS_BY_COMPANY

router = APIRouter()


def _sh_auth(request: Request):
    require_header(request, "x-shopify-access-token")


_ORDERS = [
    {
        "id": 5000000001, "admin_graphql_api_id": "gid://shopify/Order/5000000001",
        "name": "#1001", "order_number": 1001, "email": "jane@acme.io",
        "created_at": "2026-07-10T14:30:00-04:00", "updated_at": "2026-07-11T09:15:00-04:00",
        "processed_at": "2026-07-10T14:30:00-04:00", "closed_at": None, "cancelled_at": None,
        "financial_status": "paid", "fulfillment_status": "fulfilled",
        "currency": "USD", "current_subtotal_price": "249.98",
        "current_total_price": "272.93", "current_total_tax": "22.95",
        "subtotal_price": "249.98", "total_price": "272.93", "total_tax": "22.95",
        "total_discounts": "0.00", "total_shipping_price_set": {"shop_money": {"amount": "0.00", "currency_code": "USD"}},
        "total_line_items_price": "249.98",
        "customer": {"id": 7000000001, "email": "jane@acme.io", "first_name": "Jane", "last_name": "Smith", "orders_count": 3, "total_spent": "820.00"},
        "billing_address": {"first_name": "Jane", "last_name": "Smith", "company": "Acme Corp", "address1": "123 Main St", "city": "San Francisco", "province": "California", "country": "United States", "zip": "94105", "phone": "+14155551234"},
        "shipping_address": {"first_name": "Jane", "last_name": "Smith", "company": "Acme Corp", "address1": "123 Main St", "city": "San Francisco", "province": "California", "country": "United States", "zip": "94105", "phone": "+14155551234"},
        "line_items": [
            {"id": 10001, "title": "Widget Pro", "quantity": 2, "price": "124.99", "sku": "WP-001", "variant_id": 40001, "product_id": 30001, "fulfillment_status": "fulfilled", "taxable": True, "tax_lines": [{"title": "CA State Tax", "price": "22.95", "rate": 0.085}]},
        ],
        "shipping_lines": [{"id": 20001, "title": "Standard Shipping", "price": "0.00", "code": "standard", "source": "shopify"}],
        "fulfillments": [], "refunds": [],
        "tags": "vip, repeat-customer",
        "number": 1, "total_weight": 1760, "taxes_included": False, "confirmed": True,
        "buyer_accepts_marketing": True, "source_name": "web", "test": False,
        "contact_email": "jane@acme.io",
    },
    {
        "id": 5000000002, "admin_graphql_api_id": "gid://shopify/Order/5000000002",
        "name": "#1002", "order_number": 1002, "email": "mike@globex.com",
        "created_at": "2026-07-12T08:00:00-04:00", "updated_at": "2026-07-12T10:30:00-04:00",
        "processed_at": "2026-07-12T08:00:00-04:00", "closed_at": None, "cancelled_at": None,
        "financial_status": "paid", "fulfillment_status": None,
        "currency": "USD", "current_subtotal_price": "89.99",
        "current_total_price": "97.64", "current_total_tax": "7.65",
        "subtotal_price": "89.99", "total_price": "97.64", "total_tax": "7.65",
        "total_discounts": "0.00", "total_shipping_price_set": {"shop_money": {"amount": "0.00", "currency_code": "USD"}},
        "total_line_items_price": "89.99",
        "customer": {"id": 7000000002, "email": "mike@globex.com", "first_name": "Mike", "last_name": "Chen", "orders_count": 1, "total_spent": "97.64"},
        "billing_address": {"first_name": "Mike", "last_name": "Chen", "company": "Globex Inc", "address1": "456 Oak Ave", "city": "Austin", "province": "Texas", "country": "United States", "zip": "78701", "phone": "+15125550201"},
        "shipping_address": {"first_name": "Mike", "last_name": "Chen", "company": "Globex Inc", "address1": "456 Oak Ave", "city": "Austin", "province": "Texas", "country": "United States", "zip": "78701", "phone": "+15125550201"},
        "line_items": [
            {"id": 10002, "title": "Gadget Lite", "quantity": 1, "price": "89.99", "sku": "GL-001", "variant_id": 40002, "product_id": 30002, "fulfillment_status": None, "taxable": True, "tax_lines": [{"title": "TX State Tax", "price": "7.65", "rate": 0.085}]},
        ],
        "shipping_lines": [{"id": 20002, "title": "Standard Shipping", "price": "0.00", "code": "standard", "source": "shopify"}],
        "fulfillments": [], "refunds": [],
        "tags": "new-customer",
        "number": 2, "total_weight": 350, "taxes_included": False, "confirmed": True,
        "buyer_accepts_marketing": False, "source_name": "web", "test": False,
        "contact_email": "mike@globex.com",
    },
]

_CUSTOMERS = [
    {
        "id": 7000000001, "email": "jane@acme.io", "first_name": "Jane", "last_name": "Smith",
        "created_at": "2025-03-15T10:30:00-04:00", "updated_at": "2026-07-14T18:45:00-04:00",
        "orders_count": 3, "total_spent": "820.00", "currency": "USD",
        "state": "enabled", "verified_email": True, "tax_exempt": False,
        "phone": "+14155551234", "tags": "vip, repeat-customer",
        "admin_graphql_api_id": "gid://shopify/Customer/7000000001",
        "last_order_id": 5000000001, "last_order_name": "#1001", "note": "VIP customer",
        "multipass_identifier": None, "tax_exemptions": [],
        "email_marketing_consent": {"state": "subscribed", "opt_in_level": "single_opt_in", "consent_updated_at": "2025-03-15T10:30:00-04:00"},
        "sms_marketing_consent": None,
        "default_address": {"id": 8001, "customer_id": 7000000001, "first_name": "Jane", "last_name": "Smith", "company": "Acme Corp", "address1": "123 Main St", "city": "San Francisco", "province": "California", "province_code": "CA", "country": "United States", "country_code": "US", "zip": "94105", "phone": "+14155551234", "name": "Jane Smith", "default": True},
        "addresses": [{"id": 8001, "customer_id": 7000000001, "first_name": "Jane", "last_name": "Smith", "company": "Acme Corp", "address1": "123 Main St", "city": "San Francisco", "province": "California", "province_code": "CA", "country": "United States", "country_code": "US", "zip": "94105", "phone": "+14155551234", "name": "Jane Smith", "default": True}],
    },
    {
        "id": 7000000002, "email": "mike@globex.com", "first_name": "Mike", "last_name": "Chen",
        "created_at": "2025-02-01T14:00:00-04:00", "updated_at": "2026-07-15T08:00:00-04:00",
        "orders_count": 1, "total_spent": "97.64", "currency": "USD",
        "state": "enabled", "verified_email": True, "tax_exempt": False,
        "phone": "+15125550201", "tags": "new-customer",
        "admin_graphql_api_id": "gid://shopify/Customer/7000000002",
        "last_order_id": 5000000002, "last_order_name": "#1002", "note": None,
        "multipass_identifier": None, "tax_exemptions": [],
        "email_marketing_consent": {"state": "subscribed", "opt_in_level": "single_opt_in", "consent_updated_at": "2025-02-01T14:00:00-04:00"},
        "sms_marketing_consent": None,
        "default_address": {"id": 8002, "customer_id": 7000000002, "first_name": "Mike", "last_name": "Chen", "company": "Globex Inc", "address1": "456 Oak Ave", "city": "Austin", "province": "Texas", "province_code": "TX", "country": "United States", "country_code": "US", "zip": "78701", "phone": "+15125550201", "name": "Mike Chen", "default": True},
        "addresses": [{"id": 8002, "customer_id": 7000000002, "first_name": "Mike", "last_name": "Chen", "company": "Globex Inc", "address1": "456 Oak Ave", "city": "Austin", "province": "Texas", "province_code": "TX", "country": "United States", "country_code": "US", "zip": "78701", "phone": "+15125550201", "name": "Mike Chen", "default": True}],
    },
]

_PRODUCTS = [
    {
        "id": 30001, "title": "Widget Pro", "body_html": "<p>Premium widget for professionals.</p>",
        "vendor": "Acme Corp", "product_type": "Widget", "handle": "widget-pro",
        "created_at": "2025-01-10T09:00:00-05:00", "updated_at": "2026-06-10T11:30:00-04:00",
        "published_at": "2025-01-10T09:00:00-05:00", "published_scope": "global", "status": "active",
        "tags": "bestseller, widget", "template_suffix": None,
        "admin_graphql_api_id": "gid://shopify/Product/30001",
        "variants": [
            {"id": 40001, "product_id": 30001, "title": "Default", "price": "124.99", "sku": "WP-001", "position": 1, "inventory_policy": "deny", "fulfillment_service": "manual", "inventory_management": "shopify", "option1": "Default", "option2": None, "option3": None, "created_at": "2025-01-10T09:00:00-05:00", "updated_at": "2026-06-10T11:30:00-04:00", "taxable": True, "barcode": "1234567890001", "grams": 400, "inventory_quantity": 150, "compare_at_price": "149.99", "weight": 0.88, "weight_unit": "lb", "inventory_item_id": 60001, "old_inventory_quantity": 150, "requires_shipping": True},
        ],
        "options": [{"id": 70001, "product_id": 30001, "name": "Title", "position": 1, "values": ["Default"]}],
        "images": [{"id": 50001, "product_id": 30001, "position": 1, "width": 800, "height": 600, "src": "https://cdn.shopify.com/mock/widget-pro.jpg", "alt": "Widget Pro", "created_at": "2025-01-10T09:00:00-05:00", "updated_at": "2025-01-10T09:00:00-05:00", "variant_ids": [40001]}],
        "image": {"id": 50001, "product_id": 30001, "position": 1, "width": 800, "height": 600, "src": "https://cdn.shopify.com/mock/widget-pro.jpg", "alt": "Widget Pro", "created_at": "2025-01-10T09:00:00-05:00", "updated_at": "2025-01-10T09:00:00-05:00", "variant_ids": [40001]},
    },
    {
        "id": 30002, "title": "Gadget Lite", "body_html": "<p>Lightweight everyday gadget.</p>",
        "vendor": "Acme Corp", "product_type": "Gadget", "handle": "gadget-lite",
        "created_at": "2025-06-15T10:00:00-04:00", "updated_at": "2026-07-01T14:00:00-04:00",
        "published_at": "2025-06-15T10:00:00-04:00", "published_scope": "global", "status": "active",
        "tags": "gadget, lightweight", "template_suffix": None,
        "admin_graphql_api_id": "gid://shopify/Product/30002",
        "variants": [
            {"id": 40002, "product_id": 30002, "title": "Default", "price": "89.99", "sku": "GL-001", "position": 1, "inventory_policy": "deny", "fulfillment_service": "manual", "inventory_management": "shopify", "option1": "Default", "option2": None, "option3": None, "created_at": "2025-06-15T10:00:00-04:00", "updated_at": "2026-07-01T14:00:00-04:00", "taxable": True, "barcode": "1234567890002", "grams": 160, "inventory_quantity": 300, "compare_at_price": None, "weight": 0.35, "weight_unit": "lb", "inventory_item_id": 60002, "old_inventory_quantity": 300, "requires_shipping": True},
        ],
        "options": [{"id": 70002, "product_id": 30002, "name": "Title", "position": 1, "values": ["Default"]}],
        "images": [{"id": 50002, "product_id": 30002, "position": 1, "width": 800, "height": 600, "src": "https://cdn.shopify.com/mock/gadget-lite.jpg", "alt": "Gadget Lite", "created_at": "2025-06-15T10:00:00-04:00", "updated_at": "2025-06-15T10:00:00-04:00", "variant_ids": [40002]}],
        "image": {"id": 50002, "product_id": 30002, "position": 1, "width": 800, "height": 600, "src": "https://cdn.shopify.com/mock/gadget-lite.jpg", "alt": "Gadget Lite", "created_at": "2025-06-15T10:00:00-04:00", "updated_at": "2025-06-15T10:00:00-04:00", "variant_ids": [40002]},
    },
]


@router.get("/admin/api/2024-01/orders.json")
async def list_orders(request: Request, limit: int = Query(50, ge=1, le=250), page_info: str = Query(None), status: str = Query("any")):
    _sh_auth(request)
    base_url = str(request.url).split("?")[0]
    page, links = link_header_paginate(_ORDERS, page_info, limit, base_url)
    headers = {}
    if links:
        headers["Link"] = ", ".join(links.values())
    return JSONResponse(content={"orders": page}, headers=headers)


@router.get("/admin/api/2024-01/customers.json")
async def list_customers(request: Request, limit: int = Query(50, ge=1, le=250), page_info: str = Query(None)):
    _sh_auth(request)
    base_url = str(request.url).split("?")[0]
    page, links = link_header_paginate(_CUSTOMERS, page_info, limit, base_url)
    headers = {}
    if links:
        headers["Link"] = ", ".join(links.values())
    return JSONResponse(content={"customers": page}, headers=headers)


@router.get("/admin/api/2024-01/products.json")
async def list_products(request: Request, limit: int = Query(50, ge=1, le=250), page_info: str = Query(None)):
    _sh_auth(request)
    base_url = str(request.url).split("?")[0]
    page, links = link_header_paginate(_PRODUCTS, page_info, limit, base_url)
    headers = {}
    if links:
        headers["Link"] = ", ".join(links.values())
    return JSONResponse(content={"products": page}, headers=headers)
