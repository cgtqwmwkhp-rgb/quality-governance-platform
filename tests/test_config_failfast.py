"""
ADR-0002 Fail-Fast Proof

This test proves that production mode fails fast for unsafe configurations
without attempting a database connection.
"""

import os
from unittest.mock import patch

import pytest

from src.core.config import Settings

_PROD_SECRETS = {
    "SECRET_KEY": "a" * 64,
    "JWT_SECRET_KEY": "b" * 64,
    "PSEUDONYMIZATION_PEPPER": "c" * 32,
}

_PROD_REDIS_CELERY = {
    "REDIS_URL": "rediss://:secret@redis-prod.example.com:6380/0",
    "CELERY_BROKER_URL": "rediss://:secret@redis-prod.example.com:6380/0",
    "CELERY_RESULT_BACKEND": "rediss://:secret@redis-prod.example.com:6380/1",
}


class TestProductionFailFast:
    """Test that production mode fails fast for unsafe configurations."""

    def test_production_with_placeholder_secret_key_fails(self):
        """APP_ENV=production + placeholder SECRET_KEY must fail fast."""
        with patch.dict(
            os.environ,
            {
                "APP_ENV": "production",
                "SECRET_KEY": "your-secret-key-here",  # Placeholder value
                "DATABASE_URL": "postgresql://user:pass@prod-db:5432/db",
                **_PROD_REDIS_CELERY,
            },
        ):
            with pytest.raises(ValueError) as exc_info:
                Settings()

            assert "SECRET_KEY" in str(exc_info.value)
            assert "placeholder" in str(exc_info.value).lower() or "production" in str(exc_info.value).lower()

    def test_production_with_localhost_database_fails(self):
        """APP_ENV=production + localhost DATABASE_URL must fail fast."""
        with patch.dict(
            os.environ,
            {
                "APP_ENV": "production",
                **_PROD_SECRETS,
                "DATABASE_URL": "postgresql://user:pass@localhost:5432/db",
                **_PROD_REDIS_CELERY,
            },
        ):
            with pytest.raises(ValueError) as exc_info:
                Settings()

            assert "DATABASE_URL" in str(exc_info.value)
            assert "localhost" in str(exc_info.value).lower() or "production" in str(exc_info.value).lower()

    def test_production_with_127_0_0_1_database_fails(self):
        """APP_ENV=production + 127.0.0.1 DATABASE_URL must fail fast."""
        with patch.dict(
            os.environ,
            {
                "APP_ENV": "production",
                **_PROD_SECRETS,
                "DATABASE_URL": "postgresql://user:pass@127.0.0.1:5432/db",
                **_PROD_REDIS_CELERY,
            },
        ):
            with pytest.raises(ValueError) as exc_info:
                Settings()

            assert "DATABASE_URL" in str(exc_info.value)
            assert "127.0.0.1" in str(exc_info.value) or "localhost" in str(exc_info.value).lower()

    def test_production_missing_redis_url_fails(self):
        """APP_ENV=production without REDIS_URL must fail fast (rate-limit/idempotency)."""
        env = {
            "APP_ENV": "production",
            **_PROD_SECRETS,
            "DATABASE_URL": "postgresql://user:pass@prod-db.example.com:5432/db",
            "CELERY_BROKER_URL": "rediss://:secret@redis-prod.example.com:6380/0",
        }
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop("REDIS_URL", None)
            with pytest.raises(ValueError) as exc_info:
                Settings(_env_file=None)

            assert "REDIS_URL" in str(exc_info.value)

    def test_production_localhost_redis_url_fails(self):
        """APP_ENV=production + localhost REDIS_URL must fail fast."""
        with patch.dict(
            os.environ,
            {
                "APP_ENV": "production",
                **_PROD_SECRETS,
                "DATABASE_URL": "postgresql://user:pass@prod-db.example.com:5432/db",
                "REDIS_URL": "redis://localhost:6379/0",
                "CELERY_BROKER_URL": "rediss://:secret@redis-prod.example.com:6380/0",
            },
        ):
            with pytest.raises(ValueError) as exc_info:
                Settings()

            assert "REDIS_URL" in str(exc_info.value)
            assert "localhost" in str(exc_info.value).lower()

    def test_production_empty_celery_broker_fails(self):
        """APP_ENV=production without CELERY_BROKER_URL must fail fast."""
        env = {
            "APP_ENV": "production",
            **_PROD_SECRETS,
            "DATABASE_URL": "postgresql://user:pass@prod-db.example.com:5432/db",
            "REDIS_URL": "rediss://:secret@redis-prod.example.com:6380/0",
        }
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop("CELERY_BROKER_URL", None)
            os.environ.pop("CELERY_RESULT_BACKEND", None)
            with pytest.raises(ValueError) as exc_info:
                Settings(_env_file=None)

            assert "CELERY_BROKER_URL" in str(exc_info.value)

    def test_production_localhost_celery_broker_fails(self):
        """APP_ENV=production + localhost CELERY_BROKER_URL must fail fast."""
        with patch.dict(
            os.environ,
            {
                "APP_ENV": "production",
                **_PROD_SECRETS,
                "DATABASE_URL": "postgresql://user:pass@prod-db.example.com:5432/db",
                "REDIS_URL": "rediss://:secret@redis-prod.example.com:6380/0",
                "CELERY_BROKER_URL": "redis://localhost:6379/0",
            },
        ):
            with pytest.raises(ValueError) as exc_info:
                Settings()

            assert "CELERY_BROKER_URL" in str(exc_info.value)
            assert "localhost" in str(exc_info.value).lower()

    def test_staging_with_imports_requires_redis(self):
        """APP_ENV=staging + external audit import enabled requires Redis/Celery."""
        env = {
            "APP_ENV": "staging",
            **_PROD_SECRETS,
            "DATABASE_URL": "postgresql://user:pass@staging-db.example.com:5432/db",
            "EXTERNAL_AUDIT_IMPORT_ENABLED": "true",
        }
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop("REDIS_URL", None)
            os.environ.pop("CELERY_BROKER_URL", None)
            with pytest.raises(ValueError) as exc_info:
                Settings(_env_file=None)

            assert "REDIS_URL" in str(exc_info.value) or "CELERY_BROKER_URL" in str(exc_info.value)

    def test_production_with_valid_config_passes(self):
        """APP_ENV=production + valid config must pass validation."""
        with patch.dict(
            os.environ,
            {
                "APP_ENV": "production",
                **_PROD_SECRETS,
                "DATABASE_URL": "postgresql://user:pass@prod-db.example.com:5432/db",
                "AZURE_STORAGE_CONNECTION_STRING": (
                    "DefaultEndpointsProtocol=https;AccountName=test;"
                    "AccountKey=test123==;EndpointSuffix=core.windows.net"
                ),
                **_PROD_REDIS_CELERY,
            },
        ):
            config = Settings()
            assert config.app_env == "production"
            assert config.secret_key == "a" * 64
            assert "prod-db.example.com" in config.database_url
            assert config.is_redis_required is True

    def test_development_with_placeholder_secret_key_passes(self):
        """APP_ENV=development + placeholder SECRET_KEY is allowed."""
        with patch.dict(
            os.environ,
            {
                "APP_ENV": "development",
                "SECRET_KEY": "your-secret-key-here",  # Placeholder value
                "DATABASE_URL": "sqlite:///./test.db",
            },
        ):
            config = Settings()
            assert config.app_env == "development"
            assert config.is_redis_required is False

    def test_development_with_localhost_database_passes(self):
        """APP_ENV=development + localhost DATABASE_URL is allowed."""
        with patch.dict(
            os.environ,
            {
                "APP_ENV": "development",
                "SECRET_KEY": "dev-secret",
                "DATABASE_URL": "postgresql://user:pass@localhost:5432/db",
            },
        ):
            config = Settings()
            assert config.app_env == "development"
