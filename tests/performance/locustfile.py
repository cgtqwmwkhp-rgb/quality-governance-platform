"""Performance load testing suite for Quality Governance Platform."""

import json
import os
import random

from locust import HttpUser, between, task, tag


class QualityPlatformUser(HttpUser):
    """Simulates a typical platform user performing common operations."""

    wait_time = between(1, 3)
    host = os.getenv("TARGET_HOST", "http://localhost:8000")

    def on_start(self):
        """Authenticate and get JWT token."""
        response = self.client.post("/api/v1/auth/login", json={
            "email": os.getenv("TEST_USER_EMAIL", "test@example.com"),
            "password": os.getenv("TEST_USER_PASSWORD", "testpassword"),
        })
        if response.status_code == 200:
            data = response.json()
            self.token = data.get("access_token", "")
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            self.token = ""
            self.headers = {}

    @tag("health")
    @task(1)
    def health_check(self):
        """Health endpoint - should be fastest."""
        self.client.get("/healthz")

    @tag("health")
    @task(1)
    def readiness_check(self):
        """Readiness with verbose checks."""
        self.client.get("/readyz?verbose=true")

    @tag("read", "incidents")
    @task(10)
    def list_incidents(self):
        """List incidents - most common read operation."""
        self.client.get(
            "/api/v1/incidents?page=1&page_size=20",
            headers=self.headers,
            name="/api/v1/incidents [LIST]",
        )

    @tag("read", "risks")
    @task(8)
    def list_risks(self):
        """List risks with filtering."""
        self.client.get(
            "/api/v1/risks?page=1&page_size=20",
            headers=self.headers,
            name="/api/v1/risks [LIST]",
        )

    @tag("read", "audits")
    @task(6)
    def list_audits(self):
        """List audit templates."""
        self.client.get(
            "/api/v1/audits?page=1&page_size=20",
            headers=self.headers,
            name="/api/v1/audits [LIST]",
        )

    @tag("read", "dashboard")
    @task(5)
    def executive_dashboard(self):
        """Executive dashboard - complex aggregation query."""
        self.client.get(
            "/api/v1/executive-dashboard/summary",
            headers=self.headers,
            name="/api/v1/executive-dashboard [SUMMARY]",
        )

    @tag("read", "compliance")
    @task(4)
    def compliance_status(self):
        """Compliance automation status."""
        self.client.get(
            "/api/v1/compliance?page=1&page_size=20",
            headers=self.headers,
            name="/api/v1/compliance [LIST]",
        )

    @tag("read", "documents")
    @task(4)
    def list_documents(self):
        """Document control listing."""
        self.client.get(
            "/api/v1/documents?page=1&page_size=20",
            headers=self.headers,
            name="/api/v1/documents [LIST]",
        )

    @tag("read", "capa")
    @task(3)
    def list_capa(self):
        """CAPA actions listing."""
        self.client.get(
            "/api/v1/capa?page=1&page_size=20",
            headers=self.headers,
            name="/api/v1/capa [LIST]",
        )

    @tag("read", "search")
    @task(2)
    def global_search(self):
        """Global search - expensive query."""
        terms = ["safety", "quality", "audit", "risk", "compliance"]
        self.client.get(
            f"/api/v1/search?q={random.choice(terms)}",
            headers=self.headers,
            name="/api/v1/search [QUERY]",
        )

    @tag("write", "incidents")
    @task(2)
    def create_incident(self):
        """Create an incident - write operation."""
        self.client.post(
            "/api/v1/incidents",
            headers=self.headers,
            json={
                "title": f"Load test incident {random.randint(1, 10000)}",
                "description": "Created during performance testing",
                "severity": random.choice(["low", "medium", "high"]),
                "category": "test",
            },
            name="/api/v1/incidents [CREATE]",
        )

    @tag("read", "audit_trail")
    @task(2)
    def audit_trail(self):
        """Audit trail listing."""
        self.client.get(
            "/api/v1/audit-trail?page=1&page_size=20",
            headers=self.headers,
            name="/api/v1/audit-trail [LIST]",
        )


class AdminUser(HttpUser):
    """Simulates an admin user performing management operations."""

    wait_time = between(2, 5)
    weight = 1  # 10% of users
    host = os.getenv("TARGET_HOST", "http://localhost:8000")

    def on_start(self):
        response = self.client.post("/api/v1/auth/login", json={
            "email": os.getenv("ADMIN_EMAIL", "admin@example.com"),
            "password": os.getenv("ADMIN_PASSWORD", "adminpassword"),
        })
        if response.status_code == 200:
            data = response.json()
            self.headers = {"Authorization": f"Bearer {data.get('access_token', '')}"}
        else:
            self.headers = {}

    @tag("admin", "read")
    @task(3)
    def admin_dashboard(self):
        self.client.get(
            "/api/v1/executive-dashboard/summary",
            headers=self.headers,
            name="/api/v1/executive-dashboard [ADMIN]",
        )

    @tag("admin", "read")
    @task(2)
    def telemetry_metrics(self):
        self.client.get(
            "/api/v1/telemetry/metrics",
            headers=self.headers,
            name="/api/v1/telemetry/metrics [ADMIN]",
        )

    @tag("admin", "read")
    @task(1)
    def capa_stats(self):
        self.client.get(
            "/api/v1/capa/stats",
            headers=self.headers,
            name="/api/v1/capa/stats [ADMIN]",
        )
