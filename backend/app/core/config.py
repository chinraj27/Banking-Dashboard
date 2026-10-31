from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Banking Products Dashboard API"
    # Empty MONGO_URL / REDIS_URL switch to in-memory fallbacks (used by the tests).
    database_url: str = "sqlite:///./dev.db"
    mongo_url: str = ""
    mongo_db: str = "banking_logs"
    redis_url: str = ""

    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 60

    cors_origins: str = "http://localhost,http://localhost:5173"
    seed_demo_data: bool = True
    cache_ttl_seconds: int = 60

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
