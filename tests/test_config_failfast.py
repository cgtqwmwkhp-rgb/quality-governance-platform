"""
ADR-0002 Fail-Fast Proof

This test proves that production mode fails fast for unsafe configurations
without attempting a database connection.
"""

import os
from unittest.mock import patch

import pytest

from src.core.config import Settings


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
                "SECRET_KEY": "a" * 64,  # Non-placeholder value
                "JWT_SECRET_KEY": "b" * 64,  # Non-placeholder value
                "DATABASE_URL": "postgresql://user:pass@localhost:5432/db",
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
                "SECRET_KEY": "a" * 64,  # Non-placeholder value
                "JWT_SECRET_KEY": "b" * 64,  # Non-placeholder value
                "DATABASE_URL": "postgresql://user:pass@127.0.0.1:5432/db",
            },
        ):
            with pytest.raises(ValueError) as exc_info:
                Settings()

            assert "DATABASE_URL" in str(exc_info.value)
            assert "127.0.0.1" in str(exc_info.value) or "localhost" in str(exc_info.value).lower()

    def test_production_with_valid_config_passes(self):
        """APP_ENV=production + valid config must pass validation."""
        with patch.dict(
            os.environ,
            {
                "APP_ENV": "production",
                "SECRET_KEY": "a" * 64,  # Non-placeholder value
                "JWT_SECRET_KEY": "b" * 64,  # Non-placeholder value
                "DATABASE_URL": "postgresql://user:pass@prod-db.example.com:5432/db",
            },
        ):
            # This should not raise an exception
            config = Settings()
            assert config.app_env == "production"
            assert config.secret_key == "a" * 64
            assert "prod-db.example.com" in config.database_url

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
            # This should not raise an exception in development
            config = Settings()
            assert config.app_env == "development"

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
            # This should not raise an exception in development
            config = Settings()
            assert config.app_env == "development"
