from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://os:os@localhost:5442/os_v0"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
