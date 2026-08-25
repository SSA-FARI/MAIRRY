from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "local"
    database_url: str = (
        "postgresql+psycopg://mairry:mairry@localhost:5432/mairry"
    )
    demo_user_id: str = "00000000-0000-0000-0000-000000000001"
    ai_api_key: str = ""
    ai_model: str = ""
    enable_demo_fallback: bool = True

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
