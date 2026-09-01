import os

from pydantic_settings import BaseSettings

ANTHROPIC_CREDENTIAL_ENV = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")
LLM_FLAGS = ("ENRICHMENT_ENABLED",)


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://os:os@localhost:5442/os_v0"
    SYNC_RUN_RETENTION_DAYS: int = 30
    ENGINE_RUN_RETENTION: int = 200
    MOCK_BASE_URL: str = "http://localhost:8192"
    CONNECTOR_MAX_PAGES: int = 500
    ER_BUCKET_CAP: int = 50
    ER_ONE_RECORD_PER_SOURCE: bool = True
    CONNECTOR_MAX_BYTES: int = 50 * 1024 * 1024
    ENRICHMENT_ENABLED: bool = False

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()


class StartupError(RuntimeError):
    pass


def has_credential(env: dict | None = None) -> bool:
    env = os.environ if env is None else env
    return any(env.get(name) for name in ANTHROPIC_CREDENTIAL_ENV)


def validate_startup(env: dict | None = None) -> None:
    on = sorted(name for name in LLM_FLAGS if getattr(settings, name))
    if on and not has_credential(env):
        raise StartupError(
            f"{', '.join(on)} on and no Anthropic credential is present "
            f"({' or '.join(ANTHROPIC_CREDENTIAL_ENV)}). The layer would "
            "produce nothing, which is indistinguishable from having nothing "
            "to produce. Set a credential, or switch it off."
        )
