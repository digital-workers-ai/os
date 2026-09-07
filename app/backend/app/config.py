import os

from pydantic_settings import BaseSettings

ANTHROPIC_CREDENTIAL_ENV = "ANTHROPIC_API_KEY"
LLM_FLAGS = ("ENRICHMENT_ENABLED", "COACHING_ENABLED", "CONVERSATION_ENABLED")
CREDENTIALS = {
    ANTHROPIC_CREDENTIAL_ENV: LLM_FLAGS,
    "OPENAI_API_KEY": ("EMBEDDINGS_ENABLED",),
    "ZEROENTROPY_API_KEY": ("RERANK_ENABLED",),
}


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://os:os@localhost:5442/os"
    SYNC_RUN_RETENTION_DAYS: int = 30
    ENGINE_RUN_RETENTION: int = 200
    MOCK_BASE_URL: str = "http://localhost:8192"
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
    CONVERSATION_MAX_TOOL_RESULT_CHARS: int = 12_000
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

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()


class StartupError(RuntimeError):
    pass


def has_credential(
    env: dict | None = None, name: str = ANTHROPIC_CREDENTIAL_ENV
) -> bool:
    env = os.environ if env is None else env
    return bool(env.get(name))


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
