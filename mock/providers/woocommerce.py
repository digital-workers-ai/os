"""
WooCommerce REST API v3 mock provider.
Contract: seeds/docs/23-woocommerce.md

Basic Auth. Page-number pagination with X-WP-Total/X-WP-TotalPages headers.
Flat JSON arrays (no envelope). Monetary values as strings.
"""

from fastapi import APIRouter, Request, Query
from fastapi.responses import JSONResponse
from seeds.helpers import require_basic_auth, page_paginate
from seeds.world import COMPANIES_BY_ID, PEOPLE_BY_ID, VENDORS

router = APIRouter()

_STORE = VENDORS["store"]
_PRODUCT_DATA = _STORE["products"]


def _buyer(row: dict) -> dict:
    person = PEOPLE_BY_ID[row["person_id"]]
    company = COMPANIES_BY_ID[person.company_id]
    return {"email": person.email, "first_name": person.first_name, "last_name": person.last_name, "company": company.name, "city": company.city, "state": company.state, "phone": row["phone"]}


_BUYERS = [_buyer(row) for row in _STORE["customers"]]


def _address(buyer: dict, address_1: str, postcode: str, contact: bool) -> dict:
    address = {"first_name": buyer["first_name"], "last_name": buyer["last_name"], "company": buyer["company"], "address_1": address_1, "city": buyer["city"], "state": buyer["state"], "postcode": postcode, "country": "US"}
    if contact:
        address.update({"email": buyer["email"], "phone": buyer["phone"]})
    return address


def _identity(buyer: dict) -> dict:
    return {"email": buyer["email"], "first_name": buyer["first_name"], "last_name": buyer["last_name"]}


def _username(buyer: dict) -> str:
    return f"{buyer['first_name']}{buyer['last_name']}".lower()


def _category(product: dict, category_id: int) -> dict:
    return {"id": category_id, "name": product["category"], "slug": product["category"].lower()}


def _image(product: dict, image_id: int) -> dict:
    return {"id": image_id, "src": f"https://mystore.com/wp-content/uploads/{product['slug']}.jpg", "name": product["slug"], "alt": product["name"]}

_ORDERS = [
    {
        "id": 727, "parent_id": 0, "status": "processing", "currency": "USD",
        "date_created": "2026-06-15T10:30:00", "date_modified": "2026-06-16T08:15:00",
        "discount_total": "0.00", "shipping_total": "10.00", "cart_tax": "22.95",
        "total": "279.97", "total_tax": "22.95", "customer_id": 12,
        "order_key": "wc_order_abc123", "number": "727",
        "payment_method": "stripe", "payment_method_title": "Credit Card (Stripe)",
        "date_paid": "2026-06-15T10:31:00",
        "billing": _address(_BUYERS[0], "123 Main St", "94105", True),
        "shipping": _address(_BUYERS[0], "123 Main St", "94105", False),
        "line_items": [{"id": 315, "name": _PRODUCT_DATA[0]["name"], "product_id": 93, "quantity": 3, "subtotal": "269.97", "total": "269.97", "sku": _PRODUCT_DATA[0]["sku"], "price": 89.99}],
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
        "billing": _address(_BUYERS[1], "456 Oak Ave", "78701", True),
        "shipping": _address(_BUYERS[1], "456 Oak Ave", "78701", False),
        "line_items": [{"id": 316, "name": _PRODUCT_DATA[1]["name"], "product_id": 94, "quantity": 1, "subtotal": "89.99", "total": "74.99", "sku": _PRODUCT_DATA[1]["sku"], "price": 89.99}],
        "currency_symbol": "$",
        "_links": {"self": [{"href": "http://localhost:8100/woocommerce/wc/v3/orders/728"}], "collection": [{"href": "http://localhost:8100/woocommerce/wc/v3/orders"}]},
    },
]

_CUSTOMERS = [
    {
        "id": 12, **_identity(_BUYERS[0]),
        "role": "customer", "username": _username(_BUYERS[0]),
        "date_created": "2025-03-15T10:30:00",
        "billing": _address(_BUYERS[0], "123 Main St", "94105", True),
        "shipping": _address(_BUYERS[0], "123 Main St", "94105", False),
        "is_paying_customer": True, "avatar_url": "https://secure.gravatar.com/avatar/mock1",
        "_links": {"self": [{"href": "http://localhost:8100/woocommerce/wc/v3/customers/12"}], "collection": [{"href": "http://localhost:8100/woocommerce/wc/v3/customers"}]},
    },
    {
        "id": 13, **_identity(_BUYERS[1]),
        "role": "customer", "username": _username(_BUYERS[1]),
        "date_created": "2025-02-01T14:00:00",
        "billing": _address(_BUYERS[1], "456 Oak Ave", "78701", True),
        "shipping": _address(_BUYERS[1], "456 Oak Ave", "78701", False),
        "is_paying_customer": True, "avatar_url": "https://secure.gravatar.com/avatar/mock2",
        "_links": {"self": [{"href": "http://localhost:8100/woocommerce/wc/v3/customers/13"}], "collection": [{"href": "http://localhost:8100/woocommerce/wc/v3/customers"}]},
    },
]

_PRODUCTS = [
    {
        "id": 93, "name": _PRODUCT_DATA[0]["name"], "slug": _PRODUCT_DATA[0]["slug"], "type": "simple",
        "status": "publish", "featured": False, "sku": _PRODUCT_DATA[0]["sku"],
        "price": "89.99", "regular_price": "89.99", "sale_price": "",
        "on_sale": False, "purchasable": True, "total_sales": 245,
        "stock_status": "instock", "stock_quantity": 150,
        "manage_stock": True, "weight": "0.88",
        "dimensions": {"length": "10", "width": "5", "height": "3"},
        "categories": [_category(_PRODUCT_DATA[0], 15)],
        "tags": [{"id": 30, "name": "bestseller", "slug": "bestseller"}],
        "images": [_image(_PRODUCT_DATA[0], 201)],
        "date_created": "2025-01-10T09:00:00",
        "_links": {"self": [{"href": "http://localhost:8100/woocommerce/wc/v3/products/93"}], "collection": [{"href": "http://localhost:8100/woocommerce/wc/v3/products"}]},
    },
    {
        "id": 94, "name": _PRODUCT_DATA[1]["name"], "slug": _PRODUCT_DATA[1]["slug"], "type": "simple",
        "status": "publish", "featured": False, "sku": _PRODUCT_DATA[1]["sku"],
        "price": "89.99", "regular_price": "89.99", "sale_price": "",
        "on_sale": False, "purchasable": True, "total_sales": 120,
        "stock_status": "instock", "stock_quantity": 300,
        "manage_stock": True, "weight": "0.35",
        "dimensions": {"length": "8", "width": "4", "height": "2"},
        "categories": [_category(_PRODUCT_DATA[1], 16)],
        "tags": [],
        "images": [_image(_PRODUCT_DATA[1], 202)],
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
