"""
Stripe API mock provider.
Contract: seeds/docs/02-stripe.md
"""

import time
from fastapi import APIRouter, Request, Query, HTTPException
from seeds.helpers import require_bearer, require_basic_auth
from seeds.world import (
    COMPANIES, COMPANIES_BY_ID, PEOPLE, PEOPLE_BY_COMPANY,
    SUBSCRIPTIONS, SUBSCRIPTIONS_BY_COMPANY,
    ER_COMPANY_NAMES, ER_PERSON_NAMES, ER_PERSON_EMAILS,
)

router = APIRouter()


def _stripe_auth(request: Request):
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        if len(auth) <= 7:
            raise HTTPException(status_code=401, detail={"error": {"message": "Invalid API Key provided", "type": "invalid_request_error"}})
        return
    if auth.startswith("Basic "):
        require_basic_auth(request)
        return
    raise HTTPException(status_code=401, detail={"error": {"message": "You did not provide an API key.", "type": "invalid_request_error"}})


def _stripe_customer(company):
    name = ER_COMPANY_NAMES.get(("stripe", company.id), company.name)
    contacts = PEOPLE_BY_COMPANY.get(company.id, [])
    email = contacts[0].email if contacts else f"billing@{company.domain}"
    sub = SUBSCRIPTIONS_BY_COMPANY.get(company.id)

    return {
        "id": f"cus_{company.id[1:].zfill(6)}",
        "object": "customer",
        "name": name,
        "email": email,
        "created": 1705300000 + int(company.id[1:]) * 86400,
        "currency": "usd",
        "default_source": None,
        "description": f"Customer for {company.domain}",
        "delinquent": sub.status == "past_due" if sub else False,
        "livemode": False,
        "metadata": {"company_domain": company.domain},
        "address": {
            "city": company.city,
            "state": company.state,
            "country": company.country,
            "line1": None,
            "line2": None,
            "postal_code": None,
        } if company.city else None,
        "balance": 0,
        "invoice_prefix": company.domain[:4].upper(),
        "invoice_settings": {"default_payment_method": None, "footer": None, "rendering_options": None, "custom_fields": None},
        "next_invoice_sequence": 12,
        "phone": None,
        "preferred_locales": [],
        "shipping": None,
        "tax_exempt": "none",
        "test_clock": None,
    }


def _stripe_subscription(sub, company):
    price_cents = sub.mrr_cents

    created_ts = 1705300000 + int(sub.id[3:]) * 86400
    period_start = int(time.mktime(time.strptime(sub.current_period_start, "%Y-%m-%d")))
    period_end = int(time.mktime(time.strptime(sub.current_period_end, "%Y-%m-%d")))

    return {
        "id": f"sub_{sub.id[3:].zfill(6)}",
        "object": "subscription",
        "customer": f"cus_{company.id[1:].zfill(6)}",
        "status": sub.status,
        "collection_method": "charge_automatically",
        "created": created_ts,
        "currency": sub.currency,
        "cancel_at_period_end": False,
        "canceled_at": int(time.mktime(time.strptime(sub.canceled_at, "%Y-%m-%d"))) if sub.canceled_at else None,
        "ended_at": None,
        "start_date": created_ts,
        "billing_cycle_anchor": created_ts,
        "current_period_start": period_start,
        "current_period_end": period_end,
        "default_payment_method": "pm_mock_001",
        "items": {
            "object": "list",
            "url": f"/v1/subscription_items?subscription=sub_{sub.id[3:].zfill(6)}",
            "has_more": False,
            "total_count": 1,
            "data": [
                {
                    "id": f"si_{sub.id[3:].zfill(6)}",
                    "object": "subscription_item",
                    "created": created_ts,
                    "subscription": f"sub_{sub.id[3:].zfill(6)}",
                    "current_period_start": period_start,
                    "current_period_end": period_end,
                    "price": {
                        "id": f"price_{sub.plan}",
                        "object": "price",
                        "active": True,
                        "billing_scheme": "per_unit",
                        "unit_amount": price_cents,
                        "unit_amount_decimal": str(price_cents),
                        "currency": sub.currency,
                        "recurring": {
                            "interval": "month",
                            "interval_count": 1,
                            "usage_type": "licensed",
                        },
                        "product": f"prod_{sub.plan}",
                        "type": "recurring",
                    },
                    "quantity": 1,
                }
            ],
        },
        "latest_invoice": f"in_{sub.id[3:].zfill(6)}_latest",
        "livemode": False,
        "metadata": {},
        "plan": {
            "id": f"price_{sub.plan}",
            "object": "plan",
            "amount": price_cents,
            "currency": sub.currency,
            "interval": "month",
            "product": f"prod_{sub.plan}",
        },
        "trial_end": int(time.mktime(time.strptime(sub.trial_end, "%Y-%m-%d"))) if sub.trial_end else None,
        "trial_start": None,
    }


def _cursor_paginate_stripe(items, starting_after, limit):
    start_idx = 0
    if starting_after:
        for i, item in enumerate(items):
            if item["id"] == starting_after:
                start_idx = i + 1
                break

    page = items[start_idx : start_idx + limit]
    has_more = start_idx + limit < len(items)
    return page, has_more


# --- Endpoints ---

@router.get("/v1/customers")
async def list_customers(
    request: Request,
    limit: int = Query(10, ge=1, le=100),
    starting_after: str = Query(None),
    ending_before: str = Query(None),
    email: str = Query(None),
):
    _stripe_auth(request)
    all_customers = [_stripe_customer(c) for c in COMPANIES]

    if email:
        all_customers = [c for c in all_customers if c["email"] == email]

    page, has_more = _cursor_paginate_stripe(all_customers, starting_after, limit)

    return {
        "object": "list",
        "url": "/v1/customers",
        "has_more": has_more,
        "data": page,
    }


@router.get("/v1/subscriptions")
async def list_subscriptions(
    request: Request,
    limit: int = Query(10, ge=1, le=100),
    starting_after: str = Query(None),
    customer: str = Query(None),
    status: str = Query(None),
):
    _stripe_auth(request)
    all_subs = []
    for sub in SUBSCRIPTIONS:
        company = COMPANIES_BY_ID.get(sub.company_id)
        if company:
            all_subs.append(_stripe_subscription(sub, company))

    if customer:
        all_subs = [s for s in all_subs if s["customer"] == customer]
    if status:
        all_subs = [s for s in all_subs if s["status"] == status]

    page, has_more = _cursor_paginate_stripe(all_subs, starting_after, limit)

    return {
        "object": "list",
        "url": "/v1/subscriptions",
        "has_more": has_more,
        "data": page,
    }


def _stripe_invoice(sub, company):
    cus_id = f"cus_{company.id[1:].zfill(6)}"
    sub_id = f"sub_{sub.id[3:].zfill(6)}"
    inv_id = f"in_{sub.id[3:].zfill(6)}"
    period_start = int(time.mktime(time.strptime(sub.current_period_start, "%Y-%m-%d")))
    period_end = int(time.mktime(time.strptime(sub.current_period_end, "%Y-%m-%d")))
    is_paid = sub.status in ("active", "trialing")
    amount = sub.mrr_cents

    return {
        "id": inv_id,
        "object": "invoice",
        "customer": cus_id,
        "subscription": sub_id,
        "status": "paid" if is_paid else "open",
        "currency": sub.currency,
        "amount_due": amount,
        "amount_paid": amount if is_paid else 0,
        "amount_remaining": 0 if is_paid else amount,
        "total": amount,
        "subtotal": amount,
        "created": period_start,
        "period_start": period_start,
        "period_end": period_end,
        "paid": is_paid,
        "livemode": False,
        "metadata": {},
        "number": f"{company.domain[:4].upper()}-{int(sub.id[3:]):04d}",
        "hosted_invoice_url": f"https://invoice.stripe.com/i/acct_mock/test_{inv_id}",
    }


@router.get("/v1/invoices")
async def list_invoices(
    request: Request,
    limit: int = Query(10, ge=1, le=100),
    starting_after: str = Query(None),
    customer: str = Query(None),
    subscription: str = Query(None),
    status: str = Query(None),
):
    _stripe_auth(request)
    all_invoices = []
    for sub in SUBSCRIPTIONS:
        company = COMPANIES_BY_ID.get(sub.company_id)
        if company:
            all_invoices.append(_stripe_invoice(sub, company))

    if customer:
        all_invoices = [i for i in all_invoices if i["customer"] == customer]
    if subscription:
        all_invoices = [i for i in all_invoices if i["subscription"] == subscription]
    if status:
        all_invoices = [i for i in all_invoices if i["status"] == status]

    page, has_more = _cursor_paginate_stripe(all_invoices, starting_after, limit)

    return {
        "object": "list",
        "url": "/v1/invoices",
        "has_more": has_more,
        "data": page,
    }
