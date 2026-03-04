"""Tests for configuration validation and environment sync."""

import os
from pathlib import Path

import pytest


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


class TestConfigValidation:
    """Validate that configuration is properly loaded and validated."""

    def test_required_env_vars_documented(self):
        """All required env vars should be documented in .env.example."""
        env_example_path = _project_root() / ".env.example"
        if not env_example_path.exists():
            pytest.skip(".env.example not found")
        content = env_example_path.read_text()
        required_vars = ["DATABASE_URL", "SECRET_KEY", "CORS_ORIGINS"]
        for var in required_vars:
            assert var in content, f"{var} missing from .env.example"

    def test_config_defaults_are_safe(self):
        """Default config values should be safe for production (debug=False)."""
        config_path = _project_root() / "src" / "core" / "config.py"
        if not config_path.exists():
            pytest.skip("config.py not found")
        source = config_path.read_text()
        assert "debug: bool = False" in source, "DEBUG should default to False for production safety"

    def test_pseudonymization_pepper_minimum_length(self):
        """Pepper must be at least 16 characters (validator in config)."""
        config_path = _project_root() / "src" / "core" / "config.py"
        if not config_path.exists():
            pytest.skip("config.py not found")
        source = config_path.read_text()
        assert "validate_pepper_length" in source, "Pepper length validator missing"
        assert "len(v) < 16" in source or "16 characters" in source, "Minimum pepper length (16) not enforced"

    def test_database_url_not_hardcoded(self):
        """Database URL should come from env, not be hardcoded."""
        config_path = _project_root() / "src" / "core" / "config.py"
        if not config_path.exists():
            pytest.skip("config.py not found")
        source = config_path.read_text()
        assert "postgresql://user:password@" not in source, "Hardcoded DB credentials found"

    def test_secret_key_not_default_in_env(self):
        """SECRET_KEY should not use a default value in production."""
        env_path = _project_root() / ".env"
        if not env_path.exists():
            pytest.skip(".env not found")
        content = env_path.read_text()
        if "SECRET_KEY" in content:
            assert "change-me" not in content.lower(), "Default SECRET_KEY in .env"
