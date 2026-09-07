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
    # TODO(wedding_plan 도메인 병합 후 제거): wedding_plans/wedding_plan_members가 생기기 전까지
    # documents.wedding_plan_id/uploaded_by_member_id에 사용하는 고정값. models.py의 FK TODO 참고.
    demo_wedding_plan_id: UUID = UUID("00000000-0000-0000-0000-000000000002")
    demo_member_id: UUID = UUID("00000000-0000-0000-0000-000000000003")
    ai_api_key: str = ""
    ai_model: str = ""
    ai_base_url: str = "https://gms.ssafy.io/gmsapi/api.openai.com/v1"
    object_storage_endpoint: str = "http://localhost:9000"
    # Docker Compose 안에서는 backend가 컨테이너 내부 호스트(예: minio:9000)로 object_storage_endpoint를
    # 쓰지만, presigned URL은 브라우저가 직접 열어야 하므로 host에 노출된 이 주소로 서명해야 한다.
    object_storage_public_endpoint: str = "http://localhost:9000"
    object_storage_bucket: str = "mairry"
    object_storage_access_key: str = "minio"
    object_storage_secret_key: str = "miniosecret"
    max_upload_size_bytes: int = Field(default=10 * 1024 * 1024, gt=0)
    max_pdf_pages: int = Field(default=20, gt=0)
    presigned_url_expiry_seconds: int = Field(default=300, gt=0)
    cors_origins: str = "http://localhost:3000"
    enable_demo_fallback: bool = True
    ai_timeout_seconds: int = Field(default=45, gt=0)
    rag_enabled: bool = True
    rag_search_top_k: int = Field(default=5, ge=1, le=20)
    rag_max_context_chunks: int = Field(default=6, ge=1, le=20)
    rag_chunk_size: int = Field(default=900, ge=200, le=4_000)
    rag_chunk_overlap: int = Field(default=120, ge=0, le=1_000)
    rag_score_threshold: float = Field(default=0.12, ge=0, le=1)
    rag_history_limit: int = Field(default=8, ge=0, le=30)
    embedding_model_name: str = "text-embedding-3-small"
    embedding_version: str = "v1"
    embedding_dimensions: int = Field(default=1536, gt=0)
    embedding_batch_size: int = Field(default=64, ge=1, le=2048)
    rag_seed_ingest_on_startup: bool = True

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
