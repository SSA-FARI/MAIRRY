from pathlib import Path
from uuid import UUID

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPOSITORY_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"
BACKEND_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    app_env: str = "local"
    database_url: str = "postgresql+psycopg://mairry:mairry@localhost:5432/mairry"
    demo_user_id: UUID
    demo_user_login_id: str = Field(min_length=1, max_length=50)
    demo_user_display_name: str = Field(min_length=1, max_length=50)
    demo_user_email: str | None = Field(max_length=255)
    ai_api_key: str = ""
    ai_model: str = ""
    object_storage_endpoint: str = "http://localhost:9000"
    object_storage_bucket: str = "mairry"
    object_storage_access_key: str = "minio"
    object_storage_secret_key: str = "miniosecret"
    max_upload_size_bytes: int = Field(default=10 * 1024 * 1024, gt=0)
    max_pdf_pages: int = Field(default=20, gt=0)
    presigned_url_expiry_seconds: int = Field(default=300, gt=0)
    cors_origins: str = "http://localhost:3000"
    enable_demo_fallback: bool = True
    ai_timeout_seconds: int = Field(default=45, gt=0)

    model_config = SettingsConfigDict(
        env_file=(REPOSITORY_ENV_FILE, BACKEND_ENV_FILE),
        extra="ignore",
        str_strip_whitespace=True,
    )

    @field_validator("demo_user_email", mode="before")
    @classmethod
    def empty_demo_user_email_is_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value


settings = Settings()


def get_settings() -> Settings:
    return settings
