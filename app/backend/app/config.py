from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://os:os@localhost:5442/os_v0"
    SYNC_RUN_RETENTION_DAYS: int = 30
    MOCK_BASE_URL: str = "http://localhost:8192"
    CONNECTOR_MAX_PAGES: int = 500
    CONNECTOR_MAX_BYTES: int = 50 * 1024 * 1024

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
