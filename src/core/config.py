"""Application configuration settings."""

import logging
from functools import lru_cache
from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


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
        placeholder_keys = [
            "change-me-in-production",
            "__CHANGE_ME__",
            "changeme",
            "your-secret-key-here",
            "secret",
            "dev-secret",
            "",
        ]

        if not self.is_production:
            if self.secret_key in placeholder_keys:
                logger.warning(
                    "SECRET_KEY is using a placeholder value. "
                    "This is acceptable for development but MUST be changed before deploying to production."
                )
            if self.jwt_secret_key in placeholder_keys:
                logger.warning(
                    "JWT_SECRET_KEY is using a placeholder value. "
                    "This is acceptable for development but MUST be changed before deploying to production."
                )

        if self.is_production:
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

            if len(self.secret_key) < 16:
                raise ValueError(
                    "SECURITY ERROR: SECRET_KEY must be at least 16 characters long in production! "
                    "Generate a secure key with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
                )

            if len(self.jwt_secret_key) < 16:
                raise ValueError(
                    "SECURITY ERROR: JWT_SECRET_KEY must be at least 16 characters long in production! "
                    "Generate a secure key with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
                )

            # Ensure database URL is not localhost/127.0.0.1 (ADR-0002)
            if not self.database_url:
                raise ValueError("CONFIGURATION ERROR: DATABASE_URL must be set in production mode!")

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

    # Build / version
    build_sha: str = "dev"
    build_time: str = "local"
    app_version: str = "1.0.0"

    # Database
    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/quality_governance"
    database_echo: bool = False

    # JWT Authentication
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"  # Fallback; RS256 used when RSA key files are configured
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7
    jwt_private_key_path: str = ""
    jwt_public_key_path: str = ""

    # Azure AD Authentication (for portal users)
    azure_client_id: str = ""
    azure_tenant_id: str = ""

    # Azure Blob Storage
    azure_storage_connection_string: str = ""
    azure_storage_container_name: str = "attachments"

    # Frontend
    frontend_url: str = "https://app-qgp-prod.azurestaticapps.net"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Celery
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # Email (SMTP)
    smtp_host: str = "smtp.office365.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    from_email: str = "noreply@qgp.plantexpand.com"
    from_name: str = "Quality Governance Platform"

    # Email Ingestion
    email_imap_server: str = ""
    email_imap_port: int = 993
    email_username: str = ""
    email_password: str = ""

    # Twilio / SMS
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""

    # VAPID (Push Notifications)
    vapid_private_key: str = ""
    vapid_public_key: str = ""
    vapid_email: str = "admin@plantexpand.com"

    # Field Encryption (PII)
    field_encryption_key: str = ""

    # AI Providers
    ai_provider: str = "openai"
    openai_api_key: str = ""
    openai_model: str = "gpt-4-turbo-preview"
    azure_openai_endpoint: str = ""
    azure_openai_key: str = ""
    azure_openai_deployment: str = ""
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-3-opus-20240229"
    local_model_path: str = ""
    embedding_model: str = "text-embedding-3-small"

    # Monitoring / Telemetry
    applicationinsights_connection_string: str = ""
    otel_trace_sample_rate: Optional[float] = None
    sentry_dsn: str = ""

    # Cache
    cache_recovery_interval: int = 60
    cache_ttl_short: int = 60
    cache_ttl_medium: int = 300
    cache_ttl_long: int = 3600
    cache_ttl_daily: int = 86400
    cache_ttl_session: int = 1800
    cache_ttl_default: int = 300

    # Metrics
    metrics_dir: str = ""

    # Testing (staging only)
    ci_test_secret: str = ""

    # CORS - explicit allowlist for production safety
    # Production SWA origins must be listed explicitly (no wildcards)
    # Regex in main.py serves as fallback for staging/preview environments
    cors_origins: List[str] = [
        # Local development
        "http://localhost:3000",
        "http://localhost:8080",
        "http://localhost:5173",
        # Production Azure Static Web App (custom domain style)
        "https://app-qgp-prod.azurestaticapps.net",
        # Production Azure Static Web App (auto-generated style)
        "https://purple-water-03205fa03.6.azurestaticapps.net",
        # Staging Azure Static Web App (if different)
        # Add staging origin here when deployed
    ]

    # Logging
    log_level: str = "INFO"

    # UAT Mode for production-safe testing
    # READ_ONLY: Block all non-idempotent operations (default for production)
    # READ_WRITE: Allow UAT writes (for staging or with explicit override)
    uat_mode: str = "READ_WRITE"  # Default READ_WRITE, production should set READ_ONLY

    # UAT admin users allowed to perform override writes (comma-separated user IDs)
    uat_admin_users: str = ""

    @property
    def is_uat_read_only(self) -> bool:
        """Check if UAT is in read-only mode (production default)."""
        return self.uat_mode.upper() == "READ_ONLY"

    @property
    def uat_admin_user_list(self) -> list:
        """Get list of UAT admin users allowed to perform writes."""
        if not self.uat_admin_users:
            return []
        return [u.strip() for u in self.uat_admin_users.split(",") if u.strip()]

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
