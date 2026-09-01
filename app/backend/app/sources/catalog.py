from app.sources.registry import discover

_META: dict[str, tuple[str, str, str]] = {
    "stripe": ("Stripe", "Billing", "MRR, subscriptions, invoices, churn"),
    "shopify": ("Shopify", "Billing", "Orders, average order value"),
    "woocommerce": ("WooCommerce", "Billing", "Orders, revenue"),
    "hubspot": ("HubSpot", "CRM & Sales", "Deals, pipeline, contacts"),
    "salesforce": ("Salesforce", "CRM & Sales", "Deals, accounts, pipeline"),
    "calendly": ("Calendly", "CRM & Sales", "Booked meetings"),
    "zoom": ("Zoom", "CRM & Sales", "Call transcripts, buying signals"),
    "zendesk": ("Zendesk", "Support", "Tickets, response health"),
    "intercom": ("Intercom", "Support", "Conversations, tickets"),
    "mailchimp": ("Mailchimp", "Marketing", "Campaigns, email engagement"),
    "klaviyo": ("Klaviyo", "Marketing", "Flows, email performance"),
    "activecampaign": ("ActiveCampaign", "Marketing", "Campaigns, contacts"),
    "customerio": ("Customer.io", "Marketing", "Messaging campaigns"),
    "sendgrid": ("SendGrid", "Marketing", "Email delivery, opens"),
    "twilio": ("Twilio", "Marketing", "SMS messages, delivery"),
    "google_ads": ("Google Ads", "Advertising", "Ad spend, conversions"),
    "meta": ("Meta Ads", "Advertising", "Ad spend, campaign metrics"),
    "linkedin": ("LinkedIn Ads", "Advertising", "Ad spend, reach"),
    "pinterest": ("Pinterest Ads", "Advertising", "Ad spend, engagement"),
    "snapchat": ("Snapchat Ads", "Advertising", "Ad spend, reach"),
    "twitter": ("X Ads", "Advertising", "Ad spend, engagement"),
    "google_analytics": ("Google Analytics", "Analytics", "Traffic, events"),
    "amplitude": ("Amplitude", "Analytics", "Product events, funnels"),
    "mixpanel": ("Mixpanel", "Analytics", "Product events, funnels"),
    "segment": ("Segment", "Analytics", "Event stream, identity"),
    "smartlook": ("Smartlook", "Analytics", "Session events"),
    "google_sheets": ("Google Sheets", "Other", "Custom tabular data"),
}


def entry(source: str) -> dict:
    label, category, unlocks = _META.get(source, (source, "Other", ""))
    return {
        "source": source,
        "label": label,
        "category": category,
        "unlocks": unlocks,
    }


def catalog() -> list[dict]:
    missing = sorted(set(discover()) - set(_META))
    if missing:
        raise RuntimeError(f"connector catalog missing metadata for: {missing}")
    return [entry(s) for s in sorted(discover())]
