"""Application configuration settings."""

import logging
from functools import lru_cache
from typing import List, Optional
from urllib.parse import urlparse

from pydantic import field_validator
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
        if self.is_production and "uat_mode" not in self.model_fields_set:
            self.uat_mode = "READ_ONLY"
        self._validate_production_settings()
        self._log_config_summary()

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

            if self.pseudonymization_pepper in placeholder_keys:
                raise ValueError(
                    "SECURITY ERROR: PSEUDONYMIZATION_PEPPER contains a placeholder value in production! "
                    "GDPR pseudonymization requires a unique, secret pepper. "
                    "Generate one with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
                )

            if self.external_audit_import_enabled and not self.external_audit_import_feature_flag:
                logger.info(
                    "External audit import is enabled in production without a feature-flag key. "
                    "Set EXTERNAL_AUDIT_IMPORT_FEATURE_FLAG for staged rollout if needed."
                )

            mistral_placeholders = {
                *placeholder_keys,
                "mistral-api-key",
                "replace-me",
            }
            if self.mistral_api_key and self.mistral_api_key in mistral_placeholders:
                raise ValueError(
                    "SECURITY ERROR: MISTRAL_API_KEY contains a placeholder value in production! "
                    "Set a real provider credential or disable OCR."
                )

            if self.uat_mode.upper() != "READ_ONLY":
                logger.info(
                    "UAT_MODE is %s in production — write operations are enabled. "
                    "Set UAT_MODE=READ_ONLY to enforce read-only mode if needed.",
                    self.uat_mode,
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

    def _log_config_summary(self) -> None:
        """Emit a non-secret configuration summary at startup for support and audits."""
        parsed = urlparse(self.database_url)
        db_host = parsed.hostname or "(unknown)"
        if parsed.port:
            db_host = f"{db_host}:{parsed.port}"
        db_user = parsed.username or ""
        db_user_masked = f"{db_user}:***" if db_user else "***"

        redis_configured = "yes" if (self.redis_url or "").strip() else "no"
        pams_configured = "yes" if (self.pams_database_url or "").strip() else "no"
        appinsights_configured = "yes" if (self.applicationinsights_connection_string or "").strip() else "no"
        azure_storage_configured = "yes" if (self.azure_storage_connection_string or "").strip() else "no"
        mistral_configured = "yes" if (self.mistral_api_key or "").strip() else "no"
        gemini_configured = "yes" if (self.google_gemini_api_key or "").strip() else "no"

        logger.info("Configuration summary: app_env=%s", self.app_env)
        logger.info(
            "Configuration summary: database_url=%s://%s@%s (password ***)", parsed.scheme, db_user_masked, db_host
        )
        logger.info("Configuration summary: redis_configured=%s", redis_configured)
        logger.info("Configuration summary: pams_configured=%s", pams_configured)
        logger.info("Configuration summary: azure_storage_configured=%s", azure_storage_configured)
        logger.info("Configuration summary: azure_storage_container=%s", self.azure_storage_container_name or "(unset)")
        logger.info("Configuration summary: application_insights_configured=%s", appinsights_configured)
        logger.info("Configuration summary: mistral_configured=%s", mistral_configured)
        logger.info("Configuration summary: gemini_configured=%s", gemini_configured)
        logger.info("Configuration summary: external_audit_import_enabled=%s", self.external_audit_import_enabled)
        logger.info("Configuration summary: cors_origin_count=%s", len(self.cors_origins))

    # Application
    app_name: str = "Quality Governance Platform"
    app_env: str = "development"
    debug: bool = False
    secret_key: str = "change-me-in-production"

    # Database
    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/quality_governance"
    database_echo: bool = False

    # PAMS External Database (read-only MySQL connection for Van Checklists)
    pams_database_url: str = ""
    pams_ssl_ca: str = ""

    # JWT Authentication
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    # Azure AD Authentication (for portal users)
    azure_client_id: str = ""
    azure_tenant_id: str = ""
    azure_ad_jwks_cache_ttl_seconds: int = 3600

    # Azure Blob Storage
    azure_storage_connection_string: str = ""
    azure_storage_container_name: str = "attachments"

    # Default tenant for unauthenticated/public portal intake
    default_tenant_id: Optional[int] = None

    # Email Ingestion
    email_imap_server: str = ""
    email_imap_port: int = 993
    email_username: str = ""
    email_password: str = ""

    # Frontend URL — used for password reset links, email CTAs, etc.
    frontend_url: str = "https://purple-water-03205fa03.6.azurestaticapps.net"

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

    # GDPR / Pseudonymization
    pseudonymization_pepper: str = "change-me-in-production"

    @field_validator("pseudonymization_pepper")
    @classmethod
    def validate_pepper_length(cls, v: str) -> str:
        """Pepper must be at least 16 characters for security."""
        if v and len(v) < 16:
            raise ValueError("PSEUDONYMIZATION_PEPPER must be at least 16 characters")
        return v

    # Application version (used by telemetry)
    app_version: str = "0.1.0"

    # Logging
    log_level: str = "INFO"

    # Redis (optional — used by idempotency middleware when available)
    redis_url: str = ""

    # Celery (optional — background task processing)
    celery_broker_url: str = ""
    celery_result_backend: str = ""

    # External audit OCR / import
    external_audit_import_enabled: bool = True
    external_audit_import_feature_flag: str = "external_audit_import"
    mistral_api_key: str = ""
    mistral_ocr_model: str = "mistral-ocr-latest"
    mistral_api_base_url: str = "https://api.mistral.ai/v1"
    mistral_ocr_timeout_seconds: int = 120
    google_gemini_api_key: str = ""

    # OpenTelemetry / Azure Monitor
    otel_trace_sample_rate: Optional[float] = None
    applicationinsights_connection_string: str = ""

    # UAT Mode for production-safe testing
    # READ_ONLY: Block all non-idempotent operations (default when APP_ENV=production)
    # READ_WRITE: Allow UAT writes (default for non-production, or explicit override)
    uat_mode: str = "READ_WRITE"

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

    @property
    def azure_ad_client_id(self) -> str:
        """Backward-compatible alias used by Azure AD validator."""
        return self.azure_client_id

    @property
    def azure_ad_tenant_id(self) -> str:
        """Backward-compatible alias used by Azure AD validator."""
        return self.azure_tenant_id


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
