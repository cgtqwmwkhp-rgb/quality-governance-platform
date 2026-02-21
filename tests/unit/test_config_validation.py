"""Tests for configuration validation."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from src.core.config import Settings  # noqa: E402


class TestConfigValidation:
    def test_default_settings_load(self):
        """Settings can be created with defaults."""
        s = Settings(
            database_url="sqlite+aiosqlite:///test.db",
            secret_key="test-secret-key-minimum-16-chars",
            jwt_secret_key="test-jwt-secret-minimum-16",
        )
        assert s.app_name is not None
        assert s.app_env is not None

    def test_production_rejects_placeholder_secret(self):
        """Production mode rejects placeholder secrets."""
        with pytest.raises(Exception):
            Settings(
                app_env="production",
                database_url="postgresql+asyncpg://user:pass@db/qgp",
                secret_key="change-me-in-production",
                jwt_secret_key="test-jwt-secret-minimum-16",
            )

    def test_production_rejects_localhost_db(self):
        """Production mode rejects localhost database URLs."""
        with pytest.raises(Exception):
            Settings(
                app_env="production",
                database_url="postgresql+asyncpg://user:pass@localhost/qgp",
                secret_key="real-production-secret-key-here",
                jwt_secret_key="real-jwt-secret-key-here-16",
            )

    def test_production_rejects_short_secret(self):
        """Production mode rejects secrets shorter than 16 chars."""
        with pytest.raises(Exception):
            Settings(
                app_env="production",
                database_url="postgresql+asyncpg://user:pass@prod-db/qgp",
                secret_key="short",
                jwt_secret_key="real-jwt-secret-key-here-16",
            )

    def test_cors_origins_type(self):
        """CORS origins should be a list."""
        s = Settings(
            database_url="sqlite+aiosqlite:///test.db",
            secret_key="test-secret-key-minimum-16-chars",
            jwt_secret_key="test-jwt-secret-minimum-16",
        )
        assert isinstance(s.cors_origins, list)

    def test_new_settings_have_defaults(self):
        """Newly added settings all have sensible defaults."""
        s = Settings(
            database_url="sqlite+aiosqlite:///test.db",
            secret_key="test-secret-key-minimum-16-chars",
            jwt_secret_key="test-jwt-secret-minimum-16",
        )
        assert s.frontend_url == "https://app-qgp-prod.azurestaticapps.net"
        assert s.redis_url == "redis://localhost:6379/0"
        assert s.celery_broker_url == "redis://localhost:6379/1"
        assert s.build_sha == "dev"
        assert s.build_time == "local"
        assert s.app_version == "1.0.0"
        assert s.anthropic_api_key == ""
        assert s.smtp_host == "smtp.office365.com"

    def test_production_accepts_valid_config(self):
        """Production mode accepts a fully valid configuration."""
        s = Settings(
            app_env="production",
            database_url="postgresql+asyncpg://user:pass@prod-db.internal/qgp",
            secret_key="a-very-secure-production-key-here",
            jwt_secret_key="another-secure-jwt-key-here-1",
        )
        assert s.is_production is True
        assert s.is_development is False

    def test_development_accepts_placeholder_with_warning(self):
        """Development mode allows placeholder secrets (with warning)."""
        s = Settings(
            app_env="development",
            database_url="sqlite+aiosqlite:///test.db",
            secret_key="change-me-in-production",
            jwt_secret_key="change-me-in-production",
        )
        assert s.is_development is True

    def test_invalid_database_url_format(self):
        """Rejects database URLs that don't start with postgresql or sqlite."""
        with pytest.raises(Exception):
            Settings(
                database_url="mysql://user:pass@localhost/qgp",
                secret_key="test-secret-key-minimum-16-chars",
                jwt_secret_key="test-jwt-secret-minimum-16",
            )

    def test_production_rejects_short_jwt_secret(self):
        """Production mode rejects JWT secrets shorter than 16 chars."""
        with pytest.raises(Exception):
            Settings(
                app_env="production",
                database_url="postgresql+asyncpg://user:pass@prod-db/qgp",
                secret_key="real-production-secret-key-here",
                jwt_secret_key="short",
            )

    def test_uat_mode_defaults(self):
        """UAT mode defaults are correct."""
        s = Settings(
            database_url="sqlite+aiosqlite:///test.db",
            secret_key="test-secret-key-minimum-16-chars",
            jwt_secret_key="test-jwt-secret-minimum-16",
        )
        assert s.uat_mode == "READ_WRITE"
        assert s.is_uat_read_only is False

    def test_cache_ttl_defaults(self):
        """Cache TTL settings have expected defaults."""
        s = Settings(
            database_url="sqlite+aiosqlite:///test.db",
            secret_key="test-secret-key-minimum-16-chars",
            jwt_secret_key="test-jwt-secret-minimum-16",
        )
        assert s.cache_ttl_short == 60
        assert s.cache_ttl_medium == 300
        assert s.cache_ttl_long == 3600
        assert s.cache_ttl_daily == 86400
        assert s.cache_ttl_default == 300
