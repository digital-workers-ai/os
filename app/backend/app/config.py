import os
from datetime import datetime
from urllib.parse import urlsplit

from pydantic import field_validator
from pydantic_settings import BaseSettings

ANTHROPIC_CREDENTIAL_ENV = "ANTHROPIC_API_KEY"
EMBEDDINGS_CREDENTIAL_ENV = "OPENAI_API_KEY"
RERANK_CREDENTIAL_ENV = "ZEROENTROPY_API_KEY"
GOOGLE_CLIENT_ID_ENV = "GOOGLE_CLIENT_ID"
GOOGLE_CLIENT_SECRET_ENV = "GOOGLE_CLIENT_SECRET"
AUTH_SIGNING_KEY_ENV = "AUTH_JWT_SIGNING_KEY"
LLM_FLAGS = ("ENRICHMENT_ENABLED", "COACHING_ENABLED", "CONVERSATION_ENABLED")
CREDENTIALS = {
    ANTHROPIC_CREDENTIAL_ENV: (*LLM_FLAGS, "STUDIO_ENABLED"),
    EMBEDDINGS_CREDENTIAL_ENV: ("EMBEDDINGS_ENABLED", "STUDIO_ENABLED"),
    RERANK_CREDENTIAL_ENV: ("RERANK_ENABLED",),
    GOOGLE_CLIENT_ID_ENV: ("AUTH_ENABLED",),
    GOOGLE_CLIENT_SECRET_ENV: ("AUTH_ENABLED",),
    AUTH_SIGNING_KEY_ENV: ("AUTH_ENABLED",),
}
LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://os:os@localhost:5442/os"
    SYNC_RUN_RETENTION_DAYS: int = 30
    ENGINE_RUN_RETENTION: int = 200
    MOCK_BASE_URL: str = "http://localhost:8192"
    STAND_INS_ONLY: bool = False
    CONNECTOR_MAX_PAGES: int = 500
    ER_BUCKET_CAP: int = 50
    ER_ONE_RECORD_PER_SOURCE: bool = True
    CONNECTOR_MAX_BYTES: int = 50 * 1024 * 1024
    ENRICHMENT_ENABLED: bool = False
    ENRICHMENT_MODEL: str = "claude-sonnet-5"
    ENRICHMENT_MAX_TOKENS: int = 8000
    ENRICHMENT_MAX_CALLS_PER_RUN: int = 200
    ENRICHMENT_CONCURRENCY: int = 4
    COACHING_ENABLED: bool = False
    COACHING_MODEL: str = "claude-sonnet-5"
    COACHING_MAX_TOKENS: int = 8000
    CONVERSATION_ENABLED: bool = False
    CONVERSATION_MODEL: str = "claude-sonnet-5"
    CONVERSATION_MAX_TOKENS: int = 8000
    CONVERSATION_MAX_TURNS: int = 8
    CONVERSATION_MAX_TOOL_RESULT_CHARS: int = 16_000
    CONVERSATION_MAX_HISTORY_TURNS: int = 12
    CONVERSATION_MAX_TURN_CHARS: int = 4_000
    EMBEDDINGS_ENABLED: bool = False
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMS: int = 1536
    EMBEDDING_BATCH: int = 100
    EMBEDDINGS_MAX_CALLS_PER_RUN: int = 200
    RERANK_ENABLED: bool = False
    RERANK_MODEL: str = "zerank-2"
    RERANK_TOP: int = 20
    SEARCH_CHUNK_CHARS: int = 1200
    STUDIO_ENABLED: bool = False
    STUDIO_MODEL: str = "claude-opus-5"
    STUDIO_MAX_TOKENS: int = 8000
    STUDIO_MAX_TURNS: int = 16
    PAINT_MODEL: str = "gpt-image-2"
    MEDIA_DIR: str = "/media"
    RENDER_URL: str = "http://localhost:8200"
    MARKETER_DAILY: bool = False
    MARKETER_HOUR: int = 6
    AUTH_ENABLED: bool = False
    PUBLIC_URL: str = "http://localhost:8092"
    AUTH_ALLOWED_EMAILS: str = ""
    CLOCK_PINNED_AT: datetime | None = None

    model_config = {"env_file": ".env", "extra": "ignore"}

    @field_validator("PUBLIC_URL")
    @classmethod
    def public_url_has_no_trailing_slash(cls, value: str) -> str:
        return value.rstrip("/")

    @field_validator("CLOCK_PINNED_AT")
    @classmethod
    def pin_carries_a_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError(
                "CLOCK_PINNED_AT must carry a timezone, e.g. 2026-09-04T12:00:00Z"
            )
        return value


settings = Settings()


class StartupError(RuntimeError):
    pass


def has_credential(
    env: dict | None = None, name: str = ANTHROPIC_CREDENTIAL_ENV
) -> bool:
    env = os.environ if env is None else env
    return bool(env.get(name))


def allowed_emails() -> frozenset[str]:
    return frozenset(
        email.strip().lower()
        for email in settings.AUTH_ALLOWED_EMAILS.split(",")
        if email.strip()
    )


def validate_startup(env: dict | None = None) -> None:
    for credential, flags in CREDENTIALS.items():
        on = sorted(name for name in flags if getattr(settings, name))
        if on and not has_credential(env, credential):
            raise StartupError(
                f"{', '.join(on)} on and no credential is present "
                f"({credential}). The layer would "
                "produce nothing, which is indistinguishable from having nothing "
                "to produce. Set a credential, or switch it off."
            )
    if settings.AUTH_ENABLED:
        validate_auth()


def validate_auth() -> None:
    if not allowed_emails():
        raise StartupError(
            "AUTH_ENABLED on and AUTH_ALLOWED_EMAILS names nobody. Every sign-in "
            "would be refused, which is indistinguishable from the endpoint being "
            "down. Name the addresses allowed in, or switch it off."
        )
    public = urlsplit(settings.PUBLIC_URL)
    if public.scheme != "https" and public.hostname not in LOOPBACK_HOSTS:
        raise StartupError(
            f"AUTH_ENABLED on and PUBLIC_URL is {settings.PUBLIC_URL}. Over plain "
            "http on a public host the consent cookie would travel in the clear. "
            "Serve it over https, or keep it on localhost."
        )
