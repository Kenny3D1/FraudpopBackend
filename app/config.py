from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str
    REDIS_URL: str
    REMIX_URL: str
    INTERNAL_SHARED_SECRET: str
    

    JWT_SECRET: str
    ENCRYPTION_KEY: str
    VAULT_PEPPER: str

    SHOPIFY_API_KEY: str | None = None
    SHOPIFY_API_SECRET: str | None = None
    SHOPIFY_WEBHOOK_SECRET: str
    APP_BASE_URL: str = "http://localhost:8000"
    ENV: str = "dev"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
