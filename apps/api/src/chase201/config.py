from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = (
        "postgresql+asyncpg://chase201:local-development-only@localhost:5432/chase201"
    )
    secret_key: str = "local-development-change-this-secret-before-deploying"
    frontend_url: str = "http://localhost:3000"
    api_url: str = "http://localhost:8000"
    cors_origins: list[str] = ["http://localhost:3000"]
    environment: str = "development"
    google_client_id: str = ""
    google_client_secret: str = ""
    catalog_version: str = "real-players-v2"

    @property
    def secure_cookies(self) -> bool:
        return self.environment == "production"

    @model_validator(mode="after")
    def safe_production(self) -> "Settings":
        if "*" in self.cors_origins or self.frontend_url not in self.cors_origins:
            raise ValueError(
                "CORS must explicitly include the frontend origin; wildcards are forbidden"
            )
        if self.environment == "production":
            if len(self.secret_key) < 32 or self.secret_key.startswith("local-development"):
                raise ValueError(
                    "Production requires a unique SECRET_KEY of at least 32 characters"
                )
            if not all(
                url.startswith("https://")
                for url in [self.frontend_url, self.api_url, *self.cors_origins]
            ):
                raise ValueError("Production requires HTTPS origins")
            if not self.database_url.startswith("postgresql+asyncpg://"):
                raise ValueError("Production requires PostgreSQL")
            if self.catalog_version.startswith("fictional"):
                raise ValueError("Production requires an approved, licensed player catalog")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
