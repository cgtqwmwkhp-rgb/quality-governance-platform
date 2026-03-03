"""
Performance Testing Suite using Locust

Run with:
    locust -f tests/performance/locustfile.py --host=http://localhost:8000

For headless mode:
    locust -f tests/performance/locustfile.py --host=http://localhost:8000 \
           --headless -u 100 -r 10 --run-time 5m
"""

import json
import random
import string
from datetime import datetime, timedelta

from locust import HttpUser, between, task


def random_string(length: int = 10) -> str:
    """Generate random string for test data."""
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


class QGPUser(HttpUser):
    """Simulated user for load testing the Quality Governance Platform."""

    wait_time = between(1, 3)  # Wait 1-3 seconds between tasks
    token: str = None

    def on_start(self):
        """Login and get auth token at start of user session."""
        response = self.client.post(
            "/api/auth/login",
            json={
                "username": "testuser@plantexpand.com",
                "password": "testpassword123",
            },
        )
        if response.status_code == 200:
            self.token = response.json().get("access_token")
        else:
            # Use a dummy token for unauthenticated testing
            self.token = None

    @property
    def auth_headers(self) -> dict:
        """Get authorization headers."""
        if self.token:
            return {"Authorization": f"Bearer {self.token}"}
        return {}

    # ========================================================================
    # Dashboard & Health
    # ========================================================================

    @task(10)
    def health_check(self):
        """Check API health endpoint."""
        self.client.get("/health")

    @task(5)
    def get_dashboard(self):
        """Load main dashboard data."""
        with self.client.get(
            "/api/incidents?page=1&per_page=10",
            headers=self.auth_headers,
            catch_response=True,
        ) as response:
            if response.status_code == 401:
                response.success()  # Expected for unauthorized

    # ========================================================================
    # Incidents Module
    # ========================================================================

    @task(8)
    def list_incidents(self):
        """List incidents with pagination."""
        page = random.randint(1, 5)
        self.client.get(
            f"/api/incidents?page={page}&per_page=20",
            headers=self.auth_headers,
            name="/api/incidents?page=[n]",
        )

    @task(3)
    def create_incident(self):
        """Create a new incident."""
        incident_data = {
            "title": f"Load Test Incident {random_string(8)}",
            "description": f"This is a test incident created during load testing at {datetime.now().isoformat()}",
            "severity": random.choice(["low", "medium", "high", "critical"]),
            "incident_type": random.choice(["safety", "environmental", "quality", "security"]),
            "location": f"Test Location {random.randint(1, 100)}",
        }
        self.client.post(
            "/api/incidents",
            json=incident_data,
            headers=self.auth_headers,
        )

    @task(2)
    def get_incident_detail(self):
        """Get incident details."""
        incident_id = random.randint(1, 100)
        with self.client.get(
            f"/api/incidents/{incident_id}",
            headers=self.auth_headers,
            name="/api/incidents/[id]",
            catch_response=True,
        ) as response:
            if response.status_code == 404:
                response.success()  # Expected for non-existent

    # ========================================================================
    # Audits Module
    # ========================================================================

    @task(5)
    def list_audits(self):
        """List audits."""
        self.client.get(
            "/api/audits/runs?page=1&per_page=20",
            headers=self.auth_headers,
        )

    @task(3)
    def list_audit_templates(self):
        """List audit templates."""
        self.client.get(
            "/api/audit-templates?page=1&per_page=20",
            headers=self.auth_headers,
        )

    @task(2)
    def get_audit_findings(self):
        """Get audit findings."""
        self.client.get(
            "/api/audits/findings?page=1&per_page=50",
            headers=self.auth_headers,
        )

    # ========================================================================
    # Risks Module
    # ========================================================================

    @task(4)
    def list_risks(self):
        """List risks."""
        self.client.get(
            "/api/risks?page=1&per_page=20",
            headers=self.auth_headers,
        )

    @task(2)
    def get_risk_heatmap(self):
        """Get risk heat map data."""
        self.client.get(
            "/api/risk-register/heat-map",
            headers=self.auth_headers,
        )

    # ========================================================================
    # Compliance Module
    # ========================================================================

    @task(4)
    def list_standards(self):
        """List compliance standards."""
        self.client.get(
            "/api/standards",
            headers=self.auth_headers,
        )

    @task(2)
    def get_compliance_evidence(self):
        """Get compliance evidence."""
        self.client.get(
            "/api/compliance/evidence?page=1&per_page=50",
            headers=self.auth_headers,
        )

    # ========================================================================
    # Employee Portal
    # ========================================================================

    @task(6)
    def portal_stats(self):
        """Get portal statistics."""
        self.client.get("/api/portal/stats")

    @task(4)
    def submit_quick_report(self):
        """Submit a quick report via portal."""
        report_data = {
            "report_type": random.choice(["incident", "complaint"]),
            "title": f"Test Report {random_string(8)}",
            "description": "This is a test report submitted during load testing.",
            "severity": random.choice(["low", "medium", "high"]),
            "is_anonymous": random.choice([True, False]),
        }
        self.client.post(
            "/api/portal/report",
            json=report_data,
            name="/api/portal/report",
        )

    @task(3)
    def track_report(self):
        """Track a report status."""
        ref = f"INC-{datetime.now().year}-{random.randint(1, 9999):04d}"
        tracking_code = random_string(12)
        with self.client.get(
            f"/api/portal/track/{ref}?tracking_code={tracking_code}",
            name="/api/portal/track/[ref]",
            catch_response=True,
        ) as response:
            if response.status_code == 404:
                response.success()  # Expected for non-existent

    # ========================================================================
    # Search & Analytics
    # ========================================================================

    @task(3)
    def global_search(self):
        """Perform global search."""
        query = random.choice(["safety", "incident", "audit", "risk", "compliance"])
        self.client.get(
            f"/api/search?q={query}",
            headers=self.auth_headers,
            name="/api/search?q=[query]",
        )

    @task(2)
    def get_analytics(self):
        """Get analytics data."""
        self.client.get(
            "/api/analytics/summary",
            headers=self.auth_headers,
        )


class AdminUser(HttpUser):
    """Simulated admin user for testing admin-specific operations."""

    wait_time = between(2, 5)
    weight = 1  # Less common than regular users
    token: str = None

    def on_start(self):
        """Login as admin."""
        response = self.client.post(
            "/api/auth/login",
            json={
                "username": "admin@plantexpand.com",
                "password": "adminpassword123",
            },
        )
        if response.status_code == 200:
            self.token = response.json().get("access_token")

    @property
    def auth_headers(self) -> dict:
        if self.token:
            return {"Authorization": f"Bearer {self.token}"}
        return {}

    @task(3)
    def list_users(self):
        """List all users."""
        self.client.get(
            "/api/users?page=1&per_page=50",
            headers=self.auth_headers,
        )

    @task(2)
    def get_audit_trail(self):
        """Get audit trail logs."""
        self.client.get(
            "/api/audit-trail?page=1&per_page=100",
            headers=self.auth_headers,
        )

    @task(2)
    def get_workflow_stats(self):
        """Get workflow statistics."""
        self.client.get(
            "/api/workflows/stats",
            headers=self.auth_headers,
        )

    @task(1)
    def generate_report(self):
        """Generate analytics report."""
        self.client.post(
            "/api/analytics/reports/generate",
            json={
                "report_type": "incident_summary",
                "date_from": (datetime.now() - timedelta(days=30)).isoformat(),
                "date_to": datetime.now().isoformat(),
            },
            headers=self.auth_headers,
        )


class PortalUser(HttpUser):
    """Simulated employee portal user (mobile/field worker)."""

    wait_time = between(3, 8)  # Slower, mobile users
    weight = 3  # More common than regular users

    @task(10)
    def view_portal_home(self):
        """View portal home page."""
        self.client.get("/portal")

    @task(8)
    def submit_incident(self):
        """Submit an incident report."""
        data = {
            "report_type": "incident",
            "title": f"Field Incident {random_string(6)}",
            "description": "Incident reported from mobile device during load test.",
            "severity": random.choice(["low", "medium", "high"]),
            "location": f"Site {random.randint(1, 50)}",
            "is_anonymous": False,
            "reporter_name": f"Test User {random.randint(1, 100)}",
        }
        self.client.post("/api/portal/report", json=data)

    @task(5)
    def track_my_reports(self):
        """Track submitted reports."""
        self.client.get("/api/portal/my-reports")

    @task(3)
    def sos_emergency(self):
        """Trigger SOS (simulated)."""
        self.client.get("/portal/sos")

    @task(2)
    def view_help(self):
        """View help page."""
        self.client.get("/portal/help")


# ============================================================================
# Performance Test Configuration
# ============================================================================

"""
Recommended test scenarios:

1. Smoke Test (Quick validation):
   locust -f locustfile.py --headless -u 5 -r 1 --run-time 1m

2. Load Test (Normal load):
   locust -f locustfile.py --headless -u 50 -r 5 --run-time 10m

3. Stress Test (Find breaking point):
   locust -f locustfile.py --headless -u 200 -r 20 --run-time 15m

4. Spike Test (Sudden traffic spike):
   locust -f locustfile.py --headless -u 500 -r 100 --run-time 5m

5. Endurance Test (Long-running):
   locust -f locustfile.py --headless -u 100 -r 10 --run-time 2h

Expected thresholds for production:
- 95th percentile response time < 500ms
- Error rate < 1%
- Throughput > 100 requests/second
"""
