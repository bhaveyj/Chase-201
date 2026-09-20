from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit

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
    environment: Literal["development", "test", "production"] = "development"
    google_client_id: str = ""
    google_client_secret: str = ""
    catalog_version: str = "real-players-v2"

    @property
    def secure_cookies(self) -> bool:
        return self.environment == "production"

    @model_validator(mode="after")
    def safe_production(self) -> "Settings":
        if self.database_url.startswith("postgresql://"):
            self.database_url = self.database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        urls = [self.frontend_url, self.api_url, *self.cors_origins]
        if any(
            (parsed := urlsplit(url)).scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.path
            or parsed.query
            or parsed.fragment
            or parsed.username
            or parsed.password
            for url in urls
        ):
            raise ValueError("Frontend, API and CORS URLs must be HTTP(S) origins without paths")
        if "*" in self.cors_origins or self.frontend_url not in self.cors_origins:
            raise ValueError(
                "CORS must explicitly include the frontend origin; wildcards are forbidden"
            )
        if bool(self.google_client_id) != bool(self.google_client_secret):
            raise ValueError("Google OAuth requires both GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET")
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
