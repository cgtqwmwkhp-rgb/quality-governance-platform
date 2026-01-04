"""Application configuration settings."""

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    def __init__(self, **kwargs):
        """Initialize settings with validation."""
        super().__init__(**kwargs)
        self._validate_production_settings()

    def _validate_production_settings(self) -> None:
        """Validate critical settings, especially for production."""
        if self.is_production:
            # Check for placeholder secret keys (ADR-0002)
            placeholder_keys = [
                "change-me-in-production",
                "__CHANGE_ME__",
                "changeme",
                "your-secret-key-here",
                "secret",
                "dev-secret",
            ]
            if self.secret_key in placeholder_keys:
                raise ValueError(
                    "SECURITY ERROR: SECRET_KEY contains a placeholder value in production! "
                    "Generate a secure key with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
                )

            if self.jwt_secret_key in placeholder_keys:
                raise ValueError(
                    "SECURITY ERROR: JWT_SECRET_KEY contains a placeholder value in production! "
                    "Generate a secure key with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
                )

            # Ensure database URL is not localhost/127.0.0.1 (ADR-0002)
            if not self.database_url:
                raise ValueError(
                    "CONFIGURATION ERROR: DATABASE_URL must be set in production mode!"
                )
            
            if "localhost" in self.database_url.lower() or "127.0.0.1" in self.database_url:
                raise ValueError(
                    "CONFIGURATION ERROR: DATABASE_URL must not use localhost or 127.0.0.1 in production mode! "
                    "Use a production database hostname."
                )

        # Always validate database URL format
        if not self.database_url.startswith(("postgresql", "sqlite")):
            raise ValueError(
                f"CONFIGURATION ERROR: Invalid DATABASE_URL format: {self.database_url}. "
                "Must start with 'postgresql' or 'sqlite'."
            )

    # Application
    app_name: str = "Quality Governance Platform"
    app_env: str = "development"
    debug: bool = False
    secret_key: str = "change-me-in-production"

    # Database
    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/quality_governance"
    database_echo: bool = False

    # JWT Authentication
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    # Azure Blob Storage
    azure_storage_connection_string: str = ""
    azure_storage_container_name: str = "attachments"

    # Email Ingestion
    email_imap_server: str = ""
    email_imap_port: int = 993
    email_username: str = ""
    email_password: str = ""

    # CORS
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:8080"]

    # Logging
    log_level: str = "INFO"

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.app_env == "development"

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
