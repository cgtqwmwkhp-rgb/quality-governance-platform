"""
Login Reliability Smoke Tests (P0)

Ensures the login flow handles all error cases gracefully.
NO-PII: Tests use generic test credentials only.
"""

import pytest
import httpx
import time


# Use staging URL by default, can be overridden
API_BASE_URL = "https://app-qgp-staging.azurewebsites.net"


class TestLoginReliability:
    """P0 login reliability tests - these must never be skipped."""

    @pytest.fixture
    def client(self):
        """Create a test HTTP client with reasonable timeout."""
        return httpx.Client(base_url=API_BASE_URL, timeout=30.0)

    def test_login_invalid_credentials_returns_401(self, client):
        """Invalid credentials should return 401, not hang."""
        start = time.time()
        
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "invalid@test.example", "password": "wrongpassword123"}
        )
        
        elapsed = time.time() - start
        
        # Must respond within 20 seconds (well under frontend timeout)
        assert elapsed < 20, f"Login took {elapsed:.1f}s - too slow!"
        
        # Must return 401 for invalid credentials
        assert response.status_code == 401
        
        # Response must have error structure
        data = response.json()
        assert "message" in data or "detail" in data or "error" in data

    def test_login_empty_credentials_returns_422(self, client):
        """Empty credentials should return 422 validation error."""
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "", "password": ""}
        )
        
        # 422 for validation error
        assert response.status_code in [400, 422]

    def test_login_malformed_json_returns_422(self, client):
        """Malformed JSON should return 422, not crash."""
        response = client.post(
            "/api/v1/auth/login",
            content="not valid json",
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code in [400, 422]

    def test_login_endpoint_responds_under_timeout(self, client):
        """Login endpoint must respond within acceptable time."""
        start = time.time()
        
        try:
            response = client.post(
                "/api/v1/auth/login",
                json={"email": "timing-test@example.com", "password": "test123"}
            )
            elapsed = time.time() - start
        except httpx.TimeoutException:
            elapsed = time.time() - start
            pytest.fail(f"Login timed out after {elapsed:.1f}s")
        
        # Response time should be reasonable
        # Note: Current observed time is ~7s which is high but acceptable
        assert elapsed < 15, f"Login took {elapsed:.1f}s - exceeds threshold!"

    def test_health_endpoints_fast(self, client):
        """Health endpoints should respond quickly."""
        for endpoint in ["/healthz", "/readyz"]:
            start = time.time()
            response = client.get(endpoint)
            elapsed = time.time() - start
            
            assert response.status_code == 200
            assert elapsed < 2, f"{endpoint} took {elapsed:.1f}s - too slow!"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
