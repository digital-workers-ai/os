from dataclasses import dataclass, field

from app.config import settings


@dataclass
class Credentials:
    base_url: str
    headers: dict = field(default_factory=dict)


_MOCK: dict[str, tuple[str, dict]] = {
    "hubspot": ("/hubspot", {"Authorization": "Bearer mock_hs_token"}),
}


def credentials_for(source: str) -> Credentials:
    if source not in _MOCK:
        raise KeyError(f"no credentials configured for source {source!r}")
    prefix, headers = _MOCK[source]
    return Credentials(base_url=f"{settings.MOCK_BASE_URL}{prefix}", headers=headers)
