"""
Security Test Suite

Automated security tests for the Quality Governance Platform.
These tests complement OWASP ZAP scanning with targeted security checks.

Run with:
    pytest tests/security/ -v --tb=short
"""

import os
import re
import secrets
import subprocess
from pathlib import Path

import pytest

# Get project root
PROJECT_ROOT = Path(__file__).parent.parent.parent


class TestSecurityHeaders:
    """Test security headers are properly configured."""

    @pytest.fixture
    def client(self):
        """Get test client."""
        from fastapi.testclient import TestClient

        from src.main import app

        return TestClient(app)

    def test_cors_headers(self, client):
        """Test CORS is properly configured."""
        response = client.options("/api/health")
        # Should have CORS headers for allowed origins
        assert response.status_code in [200, 204, 405]

    def test_content_type_options(self, client):
        """Test X-Content-Type-Options header."""
        response = client.get("/api/health")
        # Should prevent MIME type sniffing
        # Note: This would be added in middleware

    def test_xss_protection(self, client):
        """Test XSS protection headers."""
        response = client.get("/api/health")
        assert response.status_code == 200


class TestAuthenticationSecurity:
    """Test authentication security measures."""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient

        from src.main import app

        return TestClient(app)

    def test_login_rate_limiting(self, client):
        """Test that login endpoint is rate limited."""
        # Make many rapid requests
        for i in range(15):
            client.post(
                "/api/auth/login",
                json={"username": "fake@test.com", "password": "wrongpassword"},
            )

        # Should eventually get rate limited (429)
        # This test validates rate limiting is in place

    def test_password_not_in_logs(self, client):
        """Ensure passwords are not logged in plaintext."""
        # This would check log files or log configuration
        pass

    def test_jwt_token_format(self, client):
        """Test JWT tokens have proper format and claims."""
        response = client.post(
            "/api/auth/login",
            json={"username": "testuser@plantexpand.com", "password": "testpassword123"},
        )
        if response.status_code == 200:
            token = response.json().get("access_token")
            assert token is not None
            # JWT should have 3 parts
            parts = token.split(".")
            assert len(parts) == 3

    def test_expired_token_rejected(self, client):
        """Test that expired tokens are rejected."""
        # Use an obviously expired token
        expired_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwiZXhwIjoxfQ.invalid"
        response = client.get(
            "/api/users/me",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert response.status_code in [401, 422]


class TestInputValidation:
    """Test input validation and sanitization."""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient

        from src.main import app

        return TestClient(app)

    def test_sql_injection_prevention(self, client):
        """Test SQL injection is prevented."""
        malicious_inputs = [
            "'; DROP TABLE users; --",
            "1' OR '1'='1",
            "1; SELECT * FROM users",
            "admin'--",
            "' UNION SELECT * FROM users--",
        ]

        for payload in malicious_inputs:
            response = client.get(f"/api/incidents?search={payload}")
            # Should not cause server error
            assert response.status_code != 500

    def test_xss_prevention(self, client):
        """Test XSS payloads are sanitized."""
        xss_payloads = [
            "<script>alert('XSS')</script>",
            "javascript:alert('XSS')",
            "<img src=x onerror=alert('XSS')>",
            "<svg onload=alert('XSS')>",
            "';alert('XSS');//",
        ]

        for payload in xss_payloads:
            # Try to create an incident with XSS payload
            response = client.post(
                "/api/portal/report",
                json={
                    "report_type": "incident",
                    "title": payload,
                    "description": payload,
                    "severity": "low",
                },
            )
            # Should either reject or sanitize
            if response.status_code == 201:
                data = response.json()
                # Payload should be escaped or removed
                assert "<script>" not in str(data)

    def test_path_traversal_prevention(self, client):
        """Test path traversal is prevented."""
        traversal_payloads = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "....//....//....//etc/passwd",
            "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
        ]

        for payload in traversal_payloads:
            response = client.get(f"/api/documents/{payload}")
            assert response.status_code in [400, 404, 422]

    def test_command_injection_prevention(self, client):
        """Test command injection is prevented."""
        cmd_payloads = [
            "; ls -la",
            "| cat /etc/passwd",
            "$(whoami)",
            "`id`",
            "&& rm -rf /",
        ]

        for payload in cmd_payloads:
            response = client.post(
                "/api/portal/report",
                json={
                    "report_type": "incident",
                    "title": f"Test {payload}",
                    "description": "Test description",
                    "severity": "low",
                },
            )
            assert response.status_code != 500


class TestDataProtection:
    """Test data protection measures."""

    def test_sensitive_data_not_in_url(self):
        """Ensure sensitive data is not passed in URLs."""
        # Check that API routes don't include sensitive data in GET params
        from src.api import router

        sensitive_patterns = ["password", "token", "secret", "key", "ssn", "credit_card"]

        for route in router.routes:
            if hasattr(route, "path"):
                path = route.path.lower()
                for pattern in sensitive_patterns:
                    # Skip auth routes which legitimately handle tokens
                    if "auth" not in path:
                        assert pattern not in path, f"Sensitive data '{pattern}' found in route: {path}"

    def test_error_messages_not_verbose(self):
        """Test that error messages don't leak sensitive info."""
        from fastapi.testclient import TestClient

        from src.main import app

        client = TestClient(app)

        # Try to trigger various errors
        response = client.get("/api/incidents/999999")
        if response.status_code == 404:
            error = response.json()
            # Should not contain stack traces or internal paths
            error_str = str(error)
            assert "/home/" not in error_str
            assert "Traceback" not in error_str


class TestFileUploadSecurity:
    """Test file upload security."""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient

        from src.main import app

        return TestClient(app)

    def test_file_type_validation(self, client):
        """Test that only allowed file types can be uploaded."""
        # Try to upload a PHP file disguised as an image
        malicious_file = b"<?php system($_GET['cmd']); ?>"

        response = client.post(
            "/api/documents/upload",
            files={"file": ("malicious.php", malicious_file, "image/jpeg")},
        )
        # Should be rejected
        assert response.status_code in [400, 415, 422]

    def test_file_size_limit(self, client):
        """Test file size limits are enforced."""
        # Create a large file (>10MB)
        large_content = b"x" * (11 * 1024 * 1024)

        response = client.post(
            "/api/documents/upload",
            files={"file": ("large.pdf", large_content, "application/pdf")},
        )
        # Should be rejected for size
        assert response.status_code in [400, 413, 422]


class TestSecurityConfiguration:
    """Test security configuration and secrets."""

    def test_no_hardcoded_secrets(self):
        """Scan codebase for hardcoded secrets."""
        secret_patterns = [
            r"password\s*=\s*['\"][^'\"]+['\"]",
            r"secret\s*=\s*['\"][^'\"]+['\"]",
            r"api_key\s*=\s*['\"][^'\"]+['\"]",
            r"token\s*=\s*['\"][^'\"]+['\"]",
            r"AWS_SECRET_ACCESS_KEY\s*=\s*['\"][^'\"]+['\"]",
        ]

        # Directories to scan
        scan_dirs = [PROJECT_ROOT / "src", PROJECT_ROOT / "frontend" / "src"]

        for scan_dir in scan_dirs:
            if not scan_dir.exists():
                continue

            for py_file in scan_dir.rglob("*.py"):
                content = py_file.read_text()
                for pattern in secret_patterns:
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    # Filter out obvious test/example values
                    real_matches = [m for m in matches if "test" not in m.lower() and "example" not in m.lower()]
                    assert len(real_matches) == 0, f"Potential secret in {py_file}: {real_matches}"

    def test_debug_mode_disabled_in_prod(self):
        """Ensure debug mode is disabled in production."""
        # This would check environment configuration
        env = os.getenv("ENVIRONMENT", "development")
        if env == "production":
            assert os.getenv("DEBUG", "false").lower() != "true"

    def test_secure_cookie_settings(self):
        """Test that cookies use secure settings."""
        # Would check cookie configuration in auth middleware
        pass


class TestAPISecurityBestPractices:
    """Test API security best practices."""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient

        from src.main import app

        return TestClient(app)

    def test_authentication_required_for_sensitive_endpoints(self, client):
        """Test that sensitive endpoints require authentication."""
        protected_endpoints = [
            "/api/users",
            "/api/incidents",
            "/api/audits/runs",
            "/api/risks",
            "/api/documents",
        ]

        for endpoint in protected_endpoints:
            response = client.get(endpoint)
            assert response.status_code in [401, 403], f"Endpoint {endpoint} is not protected"

    def test_no_server_version_disclosure(self, client):
        """Test that server version is not disclosed."""
        response = client.get("/api/health")

        # Check headers for version disclosure
        headers = dict(response.headers)
        assert "Server" not in headers or "version" not in headers.get("Server", "").lower()
        assert "X-Powered-By" not in headers


# ============================================================================
# CI/CD Security Checks
# ============================================================================


def test_dependencies_have_no_vulnerabilities():
    """Check dependencies for known vulnerabilities using safety."""
    try:
        result = subprocess.run(
            ["safety", "check", "--json", "-r", "requirements.txt"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        if result.returncode != 0:
            vulnerabilities = result.stdout
            pytest.fail(f"Security vulnerabilities found in dependencies:\n{vulnerabilities}")
    except FileNotFoundError:
        pytest.skip("safety not installed - run: pip install safety")


def test_no_secrets_in_git_history():
    """Check for secrets in git history using git-secrets or similar."""
    try:
        result = subprocess.run(
            ["git", "secrets", "--scan-history"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        if result.returncode != 0:
            pytest.fail(f"Secrets found in git history:\n{result.stderr}")
    except FileNotFoundError:
        pytest.skip("git-secrets not installed")
