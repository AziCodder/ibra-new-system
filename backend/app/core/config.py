from typing import Annotated, Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

_DEFAULT_SECRET = "change-me-to-random-string"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["development", "production"] = "development"
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5433/ibra_orders"
    session_secret: str = _DEFAULT_SECRET
    upload_dir: str = "./uploads"
    telegram_bot_token: str = ""
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]
    trusted_hosts: Annotated[list[str], NoDecode] = []
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"

    # Состояние системы (health-панель в админке). *_base — откуда бэкенд
    # пробит фронт и сам себя (внутренние адреса compose-сети).
    health_check_enabled: bool = True
    health_frontend_base: str = "http://frontend:5173"
    health_self_base: str = "http://localhost:8000"

    # Логи процессов (реальные логи контейнеров, как `docker logs`). Бэкенд
    # читает их через read-only docker-socket-proxy — сам docker.sock в API
    # не монтируется. compose_project пустой = автоопределение своего проекта
    # по метке com.docker.compose.project (чтобы не светить чужие контейнеры).
    logs_viewer_enabled: bool = True
    docker_proxy_url: str = "tcp://docker-socket-proxy:2375"
    compose_project: str = ""

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def cookie_secure(self) -> bool:
        return self.is_production

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> list[str]:
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.startswith("["):
                import json

                return json.loads(stripped)
            return [origin.strip() for origin in stripped.split(",") if origin.strip()]
        return value  # type: ignore[return-value]

    @field_validator("trusted_hosts", mode="before")
    @classmethod
    def parse_trusted_hosts(cls, value: object) -> list[str]:
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.startswith("["):
                import json

                return json.loads(stripped)
            return [host.strip() for host in stripped.split(",") if host.strip()]
        return value  # type: ignore[return-value]

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        if not self.is_production:
            return self

        if self.session_secret == _DEFAULT_SECRET or len(self.session_secret) < 32:
            raise ValueError("SESSION_SECRET must be a random string of at least 32 characters in production")

        if not self.cors_origins:
            raise ValueError("CORS_ORIGINS must list explicit allowed frontend origins in production")

        if any(origin == "*" for origin in self.cors_origins):
            raise ValueError("CORS wildcard (*) is not allowed in production")

        if not self.trusted_hosts:
            raise ValueError("TRUSTED_HOSTS must be set in production (Host header allow-list)")

        return self


settings = Settings()
