from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5433/ibra_orders"
    session_secret: str = "change-me-to-random-string"
    upload_dir: str = "./uploads"
    telegram_bot_token: str = ""
    cors_origins: list[str] = ["http://localhost:5173"]


settings = Settings()
