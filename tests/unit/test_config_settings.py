"""Unit tests for Settings validation in src/core/config.py.

Tests production validation, pepper length, database URL format,
UAT mode properties, and environment detection.
"""

import os
from unittest.mock import patch

import pytest


def _make_settings(**overrides):
    """Create a Settings instance with safe defaults for testing."""
    from src.core.config import Settings

    defaults = {
        "app_env": "development",
        "database_url": "postgresql+asyncpg://user:pass@localhost:5432/testdb",
        "secret_key": "change-me-in-production",
        "jwt_secret_key": "change-me-in-production",
        "pseudonymization_pepper": "change-me-in-production",
    }
    defaults.update(overrides)
    return Settings(**defaults)


# =========================================================================
# Basic property tests
# =========================================================================


class TestEnvironmentDetection:
    def test_is_development_true(self):
        s = _make_settings(app_env="development")
        assert s.is_development is True
        assert s.is_production is False

    def test_is_production_true(self):
        s = _make_settings(
            app_env="production",
            database_url="postgresql+asyncpg://user:pass@prod-db.example.com:5432/db",
            secret_key="a-very-secure-production-key-1234",
            jwt_secret_key="another-secure-jwt-key-5678",
            pseudonymization_pepper="super-secret-pepper-value-1234",
        )
        assert s.is_production is True
        assert s.is_development is False

    def test_unknown_env_is_neither(self):
        s = _make_settings(app_env="staging")
        assert s.is_development is False
        assert s.is_production is False


class TestUATProperties:
    def test_uat_read_only_default(self):
        s = _make_settings()
        assert s.is_uat_read_only is False

    def test_uat_read_only_when_set(self):
        s = _make_settings(uat_mode="READ_ONLY")
        assert s.is_uat_read_only is True

    def test_uat_read_only_case_insensitive(self):
        s = _make_settings(uat_mode="read_only")
        assert s.is_uat_read_only is True

    def test_uat_admin_users_empty(self):
        s = _make_settings(uat_admin_users="")
        assert s.uat_admin_user_list == []

    def test_uat_admin_users_parsed(self):
        s = _make_settings(uat_admin_users="1, 2, 3")
        assert s.uat_admin_user_list == ["1", "2", "3"]

    def test_uat_admin_users_strips_whitespace(self):
        s = _make_settings(uat_admin_users="  alice , bob  ")
        assert s.uat_admin_user_list == ["alice", "bob"]


class TestAzureADAliases:
    def test_azure_ad_client_id_alias(self):
        s = _make_settings(azure_client_id="my-client-id")
        assert s.azure_ad_client_id == "my-client-id"

    def test_azure_ad_tenant_id_alias(self):
        s = _make_settings(azure_tenant_id="my-tenant-id")
        assert s.azure_ad_tenant_id == "my-tenant-id"


# =========================================================================
# Database URL validation
# =========================================================================


class TestDatabaseURLValidation:
    def test_postgresql_url_accepted(self):
        s = _make_settings(database_url="postgresql+asyncpg://u:p@host/db")
        assert s.database_url.startswith("postgresql")

    def test_sqlite_url_accepted(self):
        s = _make_settings(database_url="sqlite:///test.db")
        assert s.database_url.startswith("sqlite")

    def test_invalid_scheme_rejected(self):
        with pytest.raises(ValueError, match="Invalid DATABASE_URL format"):
            _make_settings(database_url="mysql://u:p@host/db")

    def test_empty_url_rejected(self):
        with pytest.raises(ValueError):
            _make_settings(database_url="")


# =========================================================================
# Production validation
# =========================================================================


class TestProductionValidation:
    def _production_defaults(self, **overrides):
        defaults = {
            "app_env": "production",
            "database_url": "postgresql+asyncpg://user:pass@prod-db.example.com:5432/db",
            "secret_key": "a-very-secure-production-key-1234",
            "jwt_secret_key": "another-secure-jwt-key-5678",
            "pseudonymization_pepper": "super-secret-pepper-value-1234",
        }
        defaults.update(overrides)
        return defaults

    def test_placeholder_secret_key_rejected_in_production(self):
        with pytest.raises(ValueError, match="SECRET_KEY"):
            _make_settings(**self._production_defaults(secret_key="change-me-in-production"))

    def test_placeholder_jwt_secret_rejected_in_production(self):
        with pytest.raises(ValueError, match="JWT_SECRET_KEY"):
            _make_settings(**self._production_defaults(jwt_secret_key="change-me-in-production"))

    def test_placeholder_pepper_rejected_in_production(self):
        with pytest.raises(ValueError, match="PSEUDONYMIZATION_PEPPER"):
            _make_settings(**self._production_defaults(pseudonymization_pepper="change-me-in-production"))

    def test_localhost_db_rejected_in_production(self):
        with pytest.raises(ValueError, match="localhost"):
            _make_settings(**self._production_defaults(database_url="postgresql+asyncpg://user:pass@localhost:5432/db"))

    def test_127_0_0_1_db_rejected_in_production(self):
        with pytest.raises(ValueError, match="127.0.0.1"):
            _make_settings(**self._production_defaults(database_url="postgresql+asyncpg://user:pass@127.0.0.1:5432/db"))

    def test_valid_production_config_passes(self):
        s = _make_settings(**self._production_defaults())
        assert s.is_production is True

    def test_production_sets_uat_mode_read_only_by_default(self):
        s = _make_settings(**self._production_defaults())
        assert s.uat_mode == "READ_ONLY"

    def test_production_explicit_uat_mode_preserved(self):
        s = _make_settings(**self._production_defaults(uat_mode="READ_WRITE"))
        assert s.uat_mode == "READ_WRITE"

    def test_placeholder_mistral_key_rejected_in_production(self):
        with pytest.raises(ValueError, match="MISTRAL_API_KEY"):
            _make_settings(**self._production_defaults(mistral_api_key="replace-me"))

    def test_placeholder_gemini_key_rejected_in_production(self):
        with pytest.raises(ValueError, match="GOOGLE_GEMINI_API_KEY"):
            _make_settings(**self._production_defaults(google_gemini_api_key="replace-me"))

    def test_missing_database_url_in_production(self):
        with pytest.raises(ValueError, match="DATABASE_URL"):
            _make_settings(**self._production_defaults(database_url=""))

    def test_real_api_keys_accepted_in_production(self):
        s = _make_settings(
            **self._production_defaults(
                mistral_api_key="real-mistral-key-value-here",
                google_gemini_api_key="real-gemini-key-value-here",
            )
        )
        assert s.mistral_api_key == "real-mistral-key-value-here"


# =========================================================================
# Pepper length validation
# =========================================================================


class TestPepperValidation:
    def test_short_pepper_rejected(self):
        with pytest.raises(ValueError, match="16 characters"):
            _make_settings(pseudonymization_pepper="short")

    def test_16_char_pepper_accepted(self):
        s = _make_settings(pseudonymization_pepper="a" * 16)
        assert len(s.pseudonymization_pepper) == 16

    def test_long_pepper_accepted(self):
        s = _make_settings(pseudonymization_pepper="a" * 64)
        assert len(s.pseudonymization_pepper) == 64


# =========================================================================
# Default values
# =========================================================================


class TestDefaults:
    def test_debug_defaults_false(self):
        s = _make_settings()
        assert s.debug is False

    def test_jwt_algorithm_default(self):
        s = _make_settings()
        assert s.jwt_algorithm == "HS256"

    def test_cors_origins_includes_localhost(self):
        s = _make_settings()
        assert any("localhost" in o for o in s.cors_origins)

    def test_app_name_default(self):
        s = _make_settings()
        assert s.app_name == "Quality Governance Platform"

    def test_redis_url_default_empty(self):
        s = _make_settings()
        assert s.redis_url == ""

    def test_log_level_default(self):
        s = _make_settings()
        assert s.log_level == "INFO"
