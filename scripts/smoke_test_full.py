#!/usr/bin/env python3
"""
Comprehensive Smoke Tests for Quality Governance Platform

This script runs smoke tests against the deployed application to verify
that all critical endpoints are working correctly.

Usage:
    python scripts/smoke_test_full.py [--staging | --production]

Default: staging
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from typing import Optional

import httpx

# Environment URLs
ENVIRONMENTS = {
    "staging": {
        "frontend": "https://purple-water-03205fa03-staging.azurestaticapps.net",
        "backend": "https://qgp-staging-plantexpand.azurewebsites.net",
    },
    "production": {
        "frontend": "https://purple-water-03205fa03.6.azurestaticapps.net",
        "backend": "https://app-qgp-prod.azurewebsites.net",
    },
}


class SmokeTestRunner:
    """Runs comprehensive smoke tests against the platform."""

    def __init__(self, environment: str = "staging"):
        self.env = environment
        self.urls = ENVIRONMENTS[environment]
        self.results = []
        self.passed = 0
        self.failed = 0
        self.client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        self.client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.aclose()

    def log(self, message: str, level: str = "info"):
        """Log a message with timestamp."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        prefix = {"info": "   ", "pass": " ✅ ", "fail": " ❌ ", "warn": " ⚠️ "}
        print(f"[{timestamp}]{prefix.get(level, '   ')} {message}")

    async def test(self, name: str, url: str, expected_status: int = 200, method: str = "GET", **kwargs):
        """Run a single test."""
        try:
            if method == "GET":
                response = await self.client.get(url, **kwargs)
            elif method == "POST":
                response = await self.client.post(url, **kwargs)
            elif method == "PATCH":
                response = await self.client.patch(url, **kwargs)
            else:
                response = await self.client.request(method, url, **kwargs)

            if response.status_code == expected_status:
                self.passed += 1
                self.log(f"{name}: {response.status_code}", "pass")
                self.results.append({"name": name, "status": "pass", "code": response.status_code})
                return True
            else:
                self.failed += 1
                self.log(f"{name}: Expected {expected_status}, got {response.status_code}", "fail")
                self.results.append({
                    "name": name,
                    "status": "fail",
                    "expected": expected_status,
                    "actual": response.status_code,
                })
                return False
        except Exception as e:
            self.failed += 1
            self.log(f"{name}: {str(e)}", "fail")
            self.results.append({"name": name, "status": "fail", "error": str(e)})
            return False

    async def run_frontend_tests(self):
        """Run frontend smoke tests."""
        self.log("\n📱 FRONTEND TESTS", "info")
        self.log("=" * 50, "info")

        base = self.urls["frontend"]

        # Core pages
        await self.test("Homepage", f"{base}/")
        await self.test("Portal Main", f"{base}/portal")
        await self.test("Portal Login", f"{base}/portal/login")
        await self.test("Portal Report", f"{base}/portal/report")
        await self.test("Portal Track", f"{base}/portal/track")
        await self.test("Portal Help", f"{base}/portal/help")

        # Report forms
        await self.test("Incident Form", f"{base}/portal/report/incident")
        await self.test("Near Miss Form", f"{base}/portal/report/near-miss")
        await self.test("Complaint Form", f"{base}/portal/report/complaint")
        await self.test("RTA Form", f"{base}/portal/report/rta")

        # Admin pages
        await self.test("Admin Dashboard", f"{base}/admin")
        await self.test("Admin Forms List", f"{base}/admin/forms")
        await self.test("Admin Contracts", f"{base}/admin/contracts")
        await self.test("Admin Settings", f"{base}/admin/settings")

        # Static assets
        await self.test("Manifest JSON", f"{base}/manifest.json")
        await self.test("Service Worker", f"{base}/sw.js")
        await self.test("Icon 192x192", f"{base}/icons/icon-192x192.png")

    async def run_backend_tests(self):
        """Run backend smoke tests."""
        self.log("\n🔧 BACKEND TESTS", "info")
        self.log("=" * 50, "info")

        base = self.urls["backend"]

        # Health endpoints
        await self.test("Root Endpoint", f"{base}/")
        await self.test("Health Check", f"{base}/health")
        await self.test("Liveness Probe", f"{base}/healthz")
        await self.test("Readiness Probe", f"{base}/readyz")

        # API Documentation
        await self.test("OpenAPI Spec", f"{base}/openapi.json")
        await self.test("Swagger UI", f"{base}/docs")
        await self.test("ReDoc", f"{base}/redoc")

    async def run_api_tests(self):
        """Run API endpoint tests."""
        self.log("\n🔌 API ENDPOINT TESTS", "info")
        self.log("=" * 50, "info")

        base = f"{self.urls['backend']}/api/v1"

        # Public endpoints (no auth required)
        await self.test("List Contracts (public)", f"{base}/admin/config/contracts")
        await self.test("List Roles Lookup", f"{base}/admin/config/lookup/roles")
        await self.test("List Medical Assistance Lookup", f"{base}/admin/config/lookup/medical_assistance")

        # Auth endpoints (expect 401/422 without valid credentials)
        await self.test("Login (no creds)", f"{base}/auth/login", expected_status=422, method="POST", json={})
        
        # Protected endpoints (expect 401 without auth)
        await self.test("List Users (protected)", f"{base}/users", expected_status=401)
        await self.test("List Templates (protected)", f"{base}/admin/config/templates", expected_status=401)
        await self.test("List Settings (protected)", f"{base}/admin/config/settings", expected_status=401)

    async def run_all_tests(self):
        """Run all smoke tests."""
        print("\n" + "=" * 60)
        print(f"🚀 SMOKE TESTS - {self.env.upper()} ENVIRONMENT")
        print(f"   Frontend: {self.urls['frontend']}")
        print(f"   Backend:  {self.urls['backend']}")
        print("=" * 60)

        await self.run_frontend_tests()
        await self.run_backend_tests()
        await self.run_api_tests()

        # Summary
        print("\n" + "=" * 60)
        print("📊 SUMMARY")
        print("=" * 60)
        total = self.passed + self.failed
        print(f"   Total Tests: {total}")
        print(f"   Passed:      {self.passed} ✅")
        print(f"   Failed:      {self.failed} ❌")
        print(f"   Success Rate: {(self.passed/total)*100:.1f}%" if total > 0 else "   No tests run")
        print("=" * 60)

        # Write results to JSON
        results_file = f"smoke_test_results_{self.env}.json"
        with open(results_file, "w") as f:
            json.dump({
                "environment": self.env,
                "timestamp": datetime.now().isoformat(),
                "passed": self.passed,
                "failed": self.failed,
                "results": self.results,
            }, f, indent=2)
        print(f"\nResults saved to: {results_file}")

        return self.failed == 0


async def main():
    parser = argparse.ArgumentParser(description="Run smoke tests against the platform")
    parser.add_argument("--staging", action="store_true", help="Test staging environment")
    parser.add_argument("--production", action="store_true", help="Test production environment")
    args = parser.parse_args()

    environment = "production" if args.production else "staging"

    async with SmokeTestRunner(environment) as runner:
        success = await runner.run_all_tests()
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
