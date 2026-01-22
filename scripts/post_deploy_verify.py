#!/usr/bin/env python3
"""
Post-Deployment Production Verification Script

Stage 4 Security Governance: Automated production verification after deployments.

This script runs critical checks against production to verify:
1. Health endpoints respond correctly
2. Authentication is required for protected endpoints
3. Security headers are present
4. Rate limiting is active
5. No unauthenticated access to sensitive data

Usage:
    python scripts/post_deploy_verify.py --url https://app-qgp-prod.azurewebsites.net

Exit codes:
    0: All checks passed
    1: One or more checks failed
"""

import argparse
import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import requests


@dataclass
class CheckResult:
    """Result of a verification check."""

    name: str
    passed: bool
    message: str
    response_time_ms: Optional[float] = None
    request_id: Optional[str] = None


class ProductionVerifier:
    """Verifies production deployment is healthy and secure."""

    def __init__(self, base_url: str, timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.results: list[CheckResult] = []

    def _make_request(
        self,
        method: str,
        path: str,
        headers: Optional[dict] = None,
        json_data: Optional[dict] = None,
    ) -> tuple[requests.Response, float]:
        """Make a request and return response with timing."""
        url = f"{self.base_url}{path}"
        start = time.time()

        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            json=json_data,
            timeout=self.timeout,
            allow_redirects=False,
        )

        elapsed_ms = (time.time() - start) * 1000
        return response, elapsed_ms

    def check_health_endpoint(self) -> CheckResult:
        """Verify health endpoint responds."""
        try:
            response, elapsed = self._make_request("GET", "/healthz")
            request_id = response.headers.get("x-request-id")

            if response.status_code == 200:
                data = response.json()
                if data.get("status") in ["ok", "healthy"]:
                    return CheckResult(
                        name="Health Endpoint",
                        passed=True,
                        message=f"Healthy (status={data.get('status')})",
                        response_time_ms=elapsed,
                        request_id=request_id,
                    )

            return CheckResult(
                name="Health Endpoint",
                passed=False,
                message=f"Unexpected response: {response.status_code}",
                response_time_ms=elapsed,
                request_id=request_id,
            )
        except Exception as e:
            return CheckResult(
                name="Health Endpoint",
                passed=False,
                message=f"Error: {e}",
            )

    def check_readiness_endpoint(self) -> CheckResult:
        """Verify readiness endpoint responds."""
        try:
            response, elapsed = self._make_request("GET", "/readyz")
            request_id = response.headers.get("x-request-id")

            # 200 = ready, 503 = not ready (acceptable, means endpoint works)
            if response.status_code in [200, 503]:
                data = response.json()
                status = data.get("status", "unknown")
                return CheckResult(
                    name="Readiness Endpoint",
                    passed=True,
                    message=f"Responding (status={status})",
                    response_time_ms=elapsed,
                    request_id=request_id,
                )

            return CheckResult(
                name="Readiness Endpoint",
                passed=False,
                message=f"Unexpected response: {response.status_code}",
                response_time_ms=elapsed,
                request_id=request_id,
            )
        except Exception as e:
            return CheckResult(
                name="Readiness Endpoint",
                passed=False,
                message=f"Error: {e}",
            )

    def check_auth_required_incidents(self) -> CheckResult:
        """Verify incidents endpoint requires authentication."""
        try:
            response, elapsed = self._make_request("GET", "/api/v1/incidents/")
            request_id = response.headers.get("x-request-id")

            if response.status_code == 401:
                return CheckResult(
                    name="Auth Required (Incidents)",
                    passed=True,
                    message="Correctly requires authentication",
                    response_time_ms=elapsed,
                    request_id=request_id,
                )

            return CheckResult(
                name="Auth Required (Incidents)",
                passed=False,
                message=f"SECURITY ISSUE: Got {response.status_code}, expected 401",
                response_time_ms=elapsed,
                request_id=request_id,
            )
        except Exception as e:
            return CheckResult(
                name="Auth Required (Incidents)",
                passed=False,
                message=f"Error: {e}",
            )

    def check_auth_required_incidents_with_email(self) -> CheckResult:
        """Verify incidents with email filter requires authentication (CVE fix)."""
        try:
            response, elapsed = self._make_request("GET", "/api/v1/incidents/?reporter_email=test@example.com")
            request_id = response.headers.get("x-request-id")

            if response.status_code == 401:
                return CheckResult(
                    name="Auth Required (Incidents + Email Filter)",
                    passed=True,
                    message="CVE fix verified - requires authentication",
                    response_time_ms=elapsed,
                    request_id=request_id,
                )

            return CheckResult(
                name="Auth Required (Incidents + Email Filter)",
                passed=False,
                message=f"CRITICAL SECURITY ISSUE: Got {response.status_code}, expected 401",
                response_time_ms=elapsed,
                request_id=request_id,
            )
        except Exception as e:
            return CheckResult(
                name="Auth Required (Incidents + Email Filter)",
                passed=False,
                message=f"Error: {e}",
            )

    def check_auth_required_complaints_with_email(self) -> CheckResult:
        """Verify complaints with email filter requires authentication."""
        try:
            response, elapsed = self._make_request("GET", "/api/v1/complaints/?complainant_email=test@example.com")
            request_id = response.headers.get("x-request-id")

            if response.status_code == 401:
                return CheckResult(
                    name="Auth Required (Complaints + Email Filter)",
                    passed=True,
                    message="CVE fix verified - requires authentication",
                    response_time_ms=elapsed,
                    request_id=request_id,
                )

            return CheckResult(
                name="Auth Required (Complaints + Email Filter)",
                passed=False,
                message=f"CRITICAL SECURITY ISSUE: Got {response.status_code}, expected 401",
                response_time_ms=elapsed,
                request_id=request_id,
            )
        except Exception as e:
            return CheckResult(
                name="Auth Required (Complaints + Email Filter)",
                passed=False,
                message=f"Error: {e}",
            )

    def check_auth_required_rtas_with_email(self) -> CheckResult:
        """Verify RTAs with email filter requires authentication."""
        try:
            response, elapsed = self._make_request("GET", "/api/v1/rtas/?reporter_email=test@example.com")
            request_id = response.headers.get("x-request-id")

            if response.status_code == 401:
                return CheckResult(
                    name="Auth Required (RTAs + Email Filter)",
                    passed=True,
                    message="CVE fix verified - requires authentication",
                    response_time_ms=elapsed,
                    request_id=request_id,
                )

            return CheckResult(
                name="Auth Required (RTAs + Email Filter)",
                passed=False,
                message=f"CRITICAL SECURITY ISSUE: Got {response.status_code}, expected 401",
                response_time_ms=elapsed,
                request_id=request_id,
            )
        except Exception as e:
            return CheckResult(
                name="Auth Required (RTAs + Email Filter)",
                passed=False,
                message=f"Error: {e}",
            )

    def check_security_headers(self) -> CheckResult:
        """Verify security headers are present."""
        try:
            response, elapsed = self._make_request("GET", "/healthz")
            request_id = response.headers.get("x-request-id")

            required_headers = [
                "x-content-type-options",
                "x-frame-options",
                "x-xss-protection",
            ]

            missing = [h for h in required_headers if h not in response.headers]

            if not missing:
                return CheckResult(
                    name="Security Headers",
                    passed=True,
                    message="All required headers present",
                    response_time_ms=elapsed,
                    request_id=request_id,
                )

            return CheckResult(
                name="Security Headers",
                passed=False,
                message=f"Missing headers: {missing}",
                response_time_ms=elapsed,
                request_id=request_id,
            )
        except Exception as e:
            return CheckResult(
                name="Security Headers",
                passed=False,
                message=f"Error: {e}",
            )

    def check_rate_limit_headers(self) -> CheckResult:
        """Verify rate limit headers are present."""
        try:
            response, elapsed = self._make_request("GET", "/api/v1/incidents/")
            request_id = response.headers.get("x-request-id")

            rate_headers = [
                "x-ratelimit-limit",
                "x-ratelimit-remaining",
            ]

            present = [h for h in rate_headers if h in response.headers]

            if len(present) >= 1:
                limit = response.headers.get("x-ratelimit-limit", "N/A")
                return CheckResult(
                    name="Rate Limiting",
                    passed=True,
                    message=f"Active (limit={limit})",
                    response_time_ms=elapsed,
                    request_id=request_id,
                )

            return CheckResult(
                name="Rate Limiting",
                passed=False,
                message="Rate limit headers not found",
                response_time_ms=elapsed,
                request_id=request_id,
            )
        except Exception as e:
            return CheckResult(
                name="Rate Limiting",
                passed=False,
                message=f"Error: {e}",
            )

    def check_openapi_accessible(self) -> CheckResult:
        """Verify OpenAPI spec is accessible."""
        try:
            response, elapsed = self._make_request("GET", "/openapi.json")
            request_id = response.headers.get("x-request-id")

            if response.status_code == 200:
                spec = response.json()
                if "openapi" in spec and "paths" in spec:
                    return CheckResult(
                        name="OpenAPI Spec",
                        passed=True,
                        message=f"Accessible (version={spec.get('openapi')})",
                        response_time_ms=elapsed,
                        request_id=request_id,
                    )

            return CheckResult(
                name="OpenAPI Spec",
                passed=False,
                message=f"Unexpected response: {response.status_code}",
                response_time_ms=elapsed,
                request_id=request_id,
            )
        except Exception as e:
            return CheckResult(
                name="OpenAPI Spec",
                passed=False,
                message=f"Error: {e}",
            )

    def run_all_checks(self) -> bool:
        """Run all verification checks."""
        print(f"\n{'=' * 60}")
        print(f"POST-DEPLOYMENT VERIFICATION")
        print(f"Target: {self.base_url}")
        print(f"Time: {datetime.utcnow().isoformat()}Z")
        print(f"{'=' * 60}\n")

        checks = [
            self.check_health_endpoint,
            self.check_readiness_endpoint,
            self.check_auth_required_incidents,
            self.check_auth_required_incidents_with_email,
            self.check_auth_required_complaints_with_email,
            self.check_auth_required_rtas_with_email,
            self.check_security_headers,
            self.check_rate_limit_headers,
            self.check_openapi_accessible,
        ]

        for check_func in checks:
            result = check_func()
            self.results.append(result)

            status = "✅ PASS" if result.passed else "❌ FAIL"
            timing = f" ({result.response_time_ms:.0f}ms)" if result.response_time_ms else ""

            print(f"{status} | {result.name}{timing}")
            print(f"       {result.message}")
            if result.request_id:
                print(f"       request_id: {result.request_id}")
            print()

        # Summary
        passed = sum(1 for r in self.results if r.passed)
        total = len(self.results)
        all_passed = passed == total

        print(f"{'=' * 60}")
        print(f"SUMMARY: {passed}/{total} checks passed")
        print(f"{'=' * 60}")

        if all_passed:
            print("\n✅ DEPLOYMENT VERIFIED - All checks passed\n")
        else:
            print("\n❌ DEPLOYMENT ISSUES DETECTED - Review failed checks\n")
            failed = [r for r in self.results if not r.passed]
            for r in failed:
                print(f"  - {r.name}: {r.message}")

        return all_passed


def main():
    parser = argparse.ArgumentParser(description="Post-deployment production verification")
    parser.add_argument(
        "--url",
        default="https://app-qgp-prod.azurewebsites.net",
        help="Production URL to verify",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Request timeout in seconds",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )

    args = parser.parse_args()

    verifier = ProductionVerifier(args.url, args.timeout)
    all_passed = verifier.run_all_checks()

    if args.json:
        results_json = [
            {
                "name": r.name,
                "passed": r.passed,
                "message": r.message,
                "response_time_ms": r.response_time_ms,
                "request_id": r.request_id,
            }
            for r in verifier.results
        ]
        print(json.dumps(results_json, indent=2))

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
