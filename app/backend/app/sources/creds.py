from dataclasses import dataclass, field

from app.config import settings


@dataclass
class Credentials:
    base_url: str
    headers: dict = field(default_factory=dict)
    auth: tuple | None = None
    params: dict = field(default_factory=dict)


_MOCK: dict[str, tuple[str, dict, tuple | None, dict]] = {
    "hubspot": ("/hubspot", {"Authorization": "Bearer mock_hs_token"}, None, {}),
    "stripe": ("/stripe", {"Authorization": "Bearer mock_stripe_key"}, None, {}),
    "zendesk": (
        "/zendesk/api/v2",
        {"Authorization": "Bearer mock_zendesk_token"},
        None,
        {},
    ),
    "intercom": (
        "/intercom",
        {
            "Authorization": "Bearer mock_intercom_token",
            "Accept": "application/json",
            "intercom-version": "2.10",
        },
        None,
        {},
    ),
    "klaviyo": (
        "/klaviyo",
        {
            "Authorization": "Klaviyo-API-Key mock_klaviyo_key",
            "revision": "2024-10-15",
        },
        None,
        {},
    ),
    "calendly": (
        "/calendly",
        {"Authorization": "Bearer mock_calendly_token"},
        None,
        {},
    ),
    "sendgrid": (
        "/sendgrid",
        {"Authorization": "Bearer mock_sendgrid_key"},
        None,
        {},
    ),
    "customerio": ("/customerio", {"Authorization": "Bearer mock_cio_token"}, None, {}),
    "salesforce": (
        "/salesforce/services/data/v67.0",
        {"Authorization": "Bearer mock_sf_token"},
        None,
        {},
    ),
    "shopify": (
        "/shopify",
        {"X-Shopify-Access-Token": "mock_shopify_token"},
        None,
        {},
    ),
    "google_sheets": (
        "/sheets/v4",
        {"Authorization": "Bearer mock_sheets_token"},
        None,
        {},
    ),
    "mailchimp": ("/mailchimp", {}, ("anystring", "mock_mailchimp_key"), {}),
    "twilio": ("/twilio", {}, ("mock_account_sid", "mock_auth_token"), {}),
    "woocommerce": (
        "/woocommerce/wc/v3",
        {},
        ("mock_consumer_key", "mock_consumer_secret"),
        {},
    ),
    "meta": ("/meta", {}, None, {"access_token": "mock_meta_token"}),
    "google_ads": (
        "/google-ads",
        {
            "Authorization": "Bearer mock_gads_token",
            "developer-token": "mock_dev_token",
        },
        None,
        {},
    ),
    "google_analytics": (
        "/ga4/v1beta",
        {"Authorization": "Bearer mock_ga_token"},
        None,
        {},
    ),
    "activecampaign": ("/activecampaign", {"Api-Token": "mock_ac_token"}, None, {}),
    "zoom": ("/zoom", {"Authorization": "Bearer mock_zoom_token"}, None, {}),
    "amplitude": (
        "/amplitude",
        {},
        ("mock_amplitude_key", "mock_amplitude_secret"),
        {},
    ),
    "mixpanel": ("/mixpanel", {}, ("mock_mixpanel_secret", ""), {}),
    "smartlook": (
        "/smartlook",
        {"Authorization": "Bearer mock_smartlook_token"},
        None,
        {},
    ),
    "snapchat": (
        "/snapchat",
        {"Authorization": "Bearer mock_snapchat_token"},
        None,
        {},
    ),
    "twitter": (
        "/twitter",
        {"Authorization": "Bearer mock_twitter_token"},
        None,
        {},
    ),
    "pinterest": (
        "/pinterest/v5",
        {"Authorization": "Bearer mock_pinterest_token"},
        None,
        {},
    ),
    "linkedin": (
        "/linkedin/rest",
        {
            "Authorization": "Bearer mock_linkedin_token",
            "linkedin-version": "202401",
            "x-restli-protocol-version": "2.0.0",
        },
        None,
        {},
    ),
    "segment": ("/segment", {"Authorization": "Bearer mock_segment_token"}, None, {}),
}


def credentials_for(source: str) -> Credentials:
    if source not in _MOCK:
        raise KeyError(f"no credentials configured for source {source!r}")
    prefix, headers, auth, params = _MOCK[source]
    return Credentials(
        base_url=f"{settings.MOCK_BASE_URL}{prefix}",
        headers=headers,
        auth=auth,
        params=params,
    )
