import os
from collections.abc import Callable
from dataclasses import dataclass, field

from app.config import settings


@dataclass
class Credentials:
    base_url: str
    headers: dict = field(default_factory=dict)
    auth: tuple | None = None
    params: dict = field(default_factory=dict)
    values: dict = field(default_factory=dict)
    real: bool = False


class CredentialsError(RuntimeError):
    pass


def _bearer(token: str) -> tuple[dict, tuple | None, dict, dict]:
    return {"Authorization": f"Bearer {token}"}, None, {}, {}


def _basic(key: str, secret: str) -> tuple[dict, tuple | None, dict, dict]:
    return {}, (key, secret), {}, {}


def _intercom(token: str) -> tuple[dict, tuple | None, dict, dict]:
    return (
        {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "intercom-version": "2.10",
        },
        None,
        {},
        {},
    )


def _klaviyo(key: str) -> tuple[dict, tuple | None, dict, dict]:
    return (
        {"Authorization": f"Klaviyo-API-Key {key}", "revision": "2026-07-15"},
        None,
        {},
        {},
    )


def _calendly(token: str, user_uri: str) -> tuple[dict, tuple | None, dict, dict]:
    return {"Authorization": f"Bearer {token}"}, None, {"user": user_uri}, {}


def _mailchimp(key: str) -> tuple[dict, tuple | None, dict, dict]:
    _prefix, dash, data_centre = key.rpartition("-")
    if not dash:
        raise CredentialsError(
            "mailchimp: MAILCHIMP_API_KEY ends in no -<data centre>, so the host "
            "that answers for it is unknown"
        )
    return {}, ("anystring", key), {}, {"dc": data_centre}


def _twilio(
    account_sid: str, key_sid: str, key_secret: str
) -> tuple[dict, tuple | None, dict, dict]:
    return {}, (key_sid, key_secret), {}, {"account_sid": account_sid}


def _mixpanel(
    username: str, secret: str, project_id: str
) -> tuple[dict, tuple | None, dict, dict]:
    return {}, (username, secret), {"project_id": project_id}, {}


def _activecampaign(base_url: str, key: str) -> tuple[dict, tuple | None, dict, dict]:
    return (
        {"Api-Token": key},
        None,
        {},
        {"base": base_url.rstrip("/").removesuffix("/api/3")},
    )


def _twitter(token: str, user_id: str) -> tuple[dict, tuple | None, dict, dict]:
    return {"Authorization": f"Bearer {token}"}, None, {}, {"user_id": user_id}


def _shopify(domain: str, token: str) -> tuple[dict, tuple | None, dict, dict]:
    return {"X-Shopify-Access-Token": token}, None, {}, {"domain": domain}


def _serpapi_read_by_openrouter(
    key: str, _reader_key: str
) -> tuple[dict, tuple | None, dict, dict]:
    return {}, None, {"api_key": key}, {}


def _serpapi(key: str) -> tuple[dict, tuple | None, dict, dict]:
    return {}, None, {"api_key": key}, {}


_REAL: dict[str, tuple[str, tuple[str, ...], Callable]] = {
    "hubspot": ("https://api.hubapi.com", ("HUBSPOT_ACCESS_TOKEN",), _bearer),
    "stripe": ("https://api.stripe.com", ("STRIPE_API_KEY",), _bearer),
    "intercom": ("https://api.intercom.io", ("INTERCOM_ACCESS_TOKEN",), _intercom),
    "klaviyo": ("https://a.klaviyo.com", ("KLAVIYO_API_KEY",), _klaviyo),
    "calendly": (
        "https://api.calendly.com",
        ("CALENDLY_ACCESS_TOKEN", "CALENDLY_USER_URI"),
        _calendly,
    ),
    "mailchimp": (
        "https://{dc}.api.mailchimp.com",
        ("MAILCHIMP_API_KEY",),
        _mailchimp,
    ),
    "twilio": (
        "https://api.twilio.com",
        ("TWILIO_ACCOUNT_SID", "TWILIO_API_KEY_SID", "TWILIO_API_KEY_SECRET"),
        _twilio,
    ),
    "amplitude": (
        "https://amplitude.com",
        ("AMPLITUDE_API_KEY", "AMPLITUDE_SECRET_KEY"),
        _basic,
    ),
    "mixpanel": (
        "https://data.mixpanel.com",
        (
            "MIXPANEL_SERVICE_ACCOUNT_USERNAME",
            "MIXPANEL_SERVICE_ACCOUNT_SECRET",
            "MIXPANEL_PROJECT_ID",
        ),
        _mixpanel,
    ),
    "activecampaign": (
        "{base}",
        ("ACTIVECAMPAIGN_BASE_URL", "ACTIVECAMPAIGN_API_KEY"),
        _activecampaign,
    ),
    "twitter": (
        "https://api.x.com",
        ("TWITTER_BEARER_TOKEN", "TWITTER_USER_ID"),
        _twitter,
    ),
    "google_ads_transparency": (
        "https://serpapi.com",
        ("SERPAPI_API_KEY", "OPENROUTER_API_KEY"),
        _serpapi_read_by_openrouter,
    ),
    "chatgpt": ("https://openrouter.ai", ("OPENROUTER_API_KEY",), _bearer),
    "gemini": ("https://openrouter.ai", ("OPENROUTER_API_KEY",), _bearer),
    "linkedin_posts": (
        "https://api.brightdata.com",
        ("BRIGHTDATA_API_KEY",),
        _bearer,
    ),
    "google_serp": ("https://serpapi.com", ("SERPAPI_API_KEY",), _serpapi),
    "shopify": (
        "https://{domain}",
        ("SHOPIFY_STORE_DOMAIN", "SHOPIFY_ACCESS_TOKEN"),
        _shopify,
    ),
}

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
            "revision": "2026-07-15",
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
    "google_ads_transparency": ("/serpapi", {}, None, {"api_key": "mock_serpapi_key"}),
    "chatgpt": (
        "/openrouter",
        {"Authorization": "Bearer mock_openrouter_key"},
        None,
        {},
    ),
    "gemini": (
        "/openrouter",
        {"Authorization": "Bearer mock_openrouter_key"},
        None,
        {},
    ),
    "linkedin_posts": (
        "/brightdata",
        {"Authorization": "Bearer mock_brightdata_key"},
        None,
        {},
    ),
    "google_serp": ("/serpapi", {}, None, {"api_key": "mock_serpapi_key"}),
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


_MOCK_VALUES: dict[str, dict] = {
    "twilio": {"account_sid": "mock_account_sid"},
    "google_sheets": {"spreadsheet_id": "mock_spreadsheet_id"},
    "google_analytics": {"property_id": "123456789"},
    "google_ads": {"customer_id": "1234567890"},
    "twitter": {"user_id": "me"},
    "linkedin": {"organization": "urn:li:organization:1"},
    "meta": {"account_ids": ["act_000001", "act_000002", "act_000006", "act_000007"]},
}


def _base_url_override(source: str, names: tuple[str, ...]) -> str:
    name = f"{source.upper()}_BASE_URL"
    return "" if name in names else os.environ.get(name, "")


def _real(source: str) -> Credentials | None:
    if settings.STAND_INS_ONLY:
        return None
    if source not in _REAL:
        return None
    base_url, names, build = _REAL[source]
    given = [os.environ.get(name, "") for name in names]
    missing = [name for name, value in zip(names, given, strict=True) if not value]
    if len(missing) == len(names):
        return None
    if missing:
        raise CredentialsError(
            f"{source}: {', '.join(missing)} unset while the rest of "
            f"{', '.join(names)} is set — set all of them for the real API, "
            "or none for the mock"
        )
    headers, auth, params, values = build(*given)
    return Credentials(
        base_url=_base_url_override(source, names) or base_url.format(**values),
        headers=headers,
        auth=auth,
        params=params,
        values=values,
        real=True,
    )


def credentials_for(source: str) -> Credentials:
    if source not in _MOCK:
        raise KeyError(f"no credentials configured for source {source!r}")
    real = _real(source)
    if real is not None:
        return real
    prefix, headers, auth, params = _MOCK[source]
    return Credentials(
        base_url=f"{settings.MOCK_BASE_URL}{prefix}",
        headers=headers,
        auth=auth,
        params=params,
        values=_MOCK_VALUES.get(source, {}),
    )
