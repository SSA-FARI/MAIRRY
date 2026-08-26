from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "local"
    database_url: str = "postgresql+psycopg://mairry:mairry@localhost:5432/mairry"
    demo_user_id: str = "00000000-0000-0000-0000-000000000001"
    ai_api_key: str = ""
    ai_model: str = ""
    object_storage_endpoint: str = "http://localhost:9000"
    object_storage_bucket: str = "mairry"
    object_storage_access_key: str = "minio"
    object_storage_secret_key: str = "miniosecret"
    cors_origins: str = "http://localhost:3000"
    enable_demo_fallback: bool = True

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
