from dataclasses import dataclass, field

from app.config import settings


@dataclass
class Credentials:
    base_url: str
    headers: dict = field(default_factory=dict)


_MOCK: dict[str, tuple[str, dict]] = {
    "hubspot": ("/hubspot", {"Authorization": "Bearer mock_hs_token"}),
    "stripe": ("/stripe", {"Authorization": "Bearer mock_stripe_key"}),
    "zendesk": ("/zendesk/api/v2", {"Authorization": "Bearer mock_zendesk_token"}),
    "intercom": (
        "/intercom",
        {
            "Authorization": "Bearer mock_intercom_token",
            "Accept": "application/json",
            "intercom-version": "2.10",
        },
    ),
    "klaviyo": (
        "/klaviyo",
        {
            "Authorization": "Klaviyo-API-Key mock_klaviyo_key",
            "revision": "2024-10-15",
        },
    ),
    "calendly": ("/calendly", {"Authorization": "Bearer mock_calendly_token"}),
    "sendgrid": ("/sendgrid", {"Authorization": "Bearer mock_sendgrid_key"}),
    "customerio": ("/customerio", {"Authorization": "Bearer mock_cio_token"}),
}


def credentials_for(source: str) -> Credentials:
    if source not in _MOCK:
        raise KeyError(f"no credentials configured for source {source!r}")
    prefix, headers = _MOCK[source]
    return Credentials(base_url=f"{settings.MOCK_BASE_URL}{prefix}", headers=headers)
