from typing import TYPE_CHECKING, Annotated, Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

if TYPE_CHECKING:
    from app.services.s3 import S3Config

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
    # Where the links inside Telegram notifications point. Production sets this
    # to the public address of the app; the default only suits local runs.
    public_base_url: str = "http://localhost:5173"
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

    # Хранилище вложений. "local" — папка на диске (разработка, тесты),
    # "s3" — два независимых S3: основной (HostKey) + зеркало (Storj).
    # Файл считается сохранённым, когда его принял основной бакет; зеркало
    # догоняется фоновой задачей, если было недоступно.
    storage_backend: Literal["local", "s3"] = "local"
    s3_prefix: str = "files/"

    s3_primary_label: str = "S3 основной"
    s3_primary_endpoint: str = ""
    s3_primary_region: str = ""
    s3_primary_bucket: str = ""
    s3_primary_access_key: str = ""
    s3_primary_secret_key: str = ""

    s3_mirror_label: str = "S3 зеркало"
    s3_mirror_endpoint: str = ""
    s3_mirror_region: str = ""
    s3_mirror_bucket: str = ""
    s3_mirror_access_key: str = ""
    s3_mirror_secret_key: str = ""

    # Резервное копирование. Часовые копии живут ограниченный срок,
    # суточные — постоянные и чисткой не затрагиваются.
    backup_enabled: bool = True
    backup_dir: str = "./backups"
    backup_prefix: str = "backups/"
    backup_hourly_retention_days: int = 7
    backup_timezone: str = "Europe/Moscow"
    backup_hourly_minute: int = 5
    backup_daily_hour: int = 3
    backup_daily_minute: int = 15
    # Ночная проверка: свежий дамп разворачивается в отдельную базу.
    backup_verify_enabled: bool = True
    backup_verify_database: str = "ibra_backup_verify"
    # Как часто фоновый воркер сверяет содержимое двух S3-бакетов.
    storage_sync_interval_minutes: int = 15

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def s3_primary_config(self) -> "S3Config":
        from app.services.s3 import S3Config

        return S3Config(
            name="primary",
            label=self.s3_primary_label,
            endpoint_url=self.s3_primary_endpoint,
            region=self.s3_primary_region,
            access_key=self.s3_primary_access_key,
            secret_key=self.s3_primary_secret_key,
            bucket=self.s3_primary_bucket,
            prefix=self.s3_prefix,
        )

    @property
    def s3_mirror_config(self) -> "S3Config":
        from app.services.s3 import S3Config

        return S3Config(
            name="mirror",
            label=self.s3_mirror_label,
            endpoint_url=self.s3_mirror_endpoint,
            region=self.s3_mirror_region,
            access_key=self.s3_mirror_access_key,
            secret_key=self.s3_mirror_secret_key,
            bucket=self.s3_mirror_bucket,
            prefix=self.s3_prefix,
        )

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

    @model_validator(mode="after")
    def validate_storage(self) -> "Settings":
        """Режим s3 без реквизитов основного бакета — гарантированная потеря
        файлов при первой же загрузке, поэтому падаем на старте, а не в бою."""
        if self.storage_backend != "s3":
            return self

        missing = [
            name
            for name, value in (
                ("S3_PRIMARY_ENDPOINT", self.s3_primary_endpoint),
                ("S3_PRIMARY_BUCKET", self.s3_primary_bucket),
                ("S3_PRIMARY_ACCESS_KEY", self.s3_primary_access_key),
                ("S3_PRIMARY_SECRET_KEY", self.s3_primary_secret_key),
            )
            if not value
        ]
        if missing:
            raise ValueError(
                "STORAGE_BACKEND=s3 requires " + ", ".join(missing)
            )
        return self


settings = Settings()
