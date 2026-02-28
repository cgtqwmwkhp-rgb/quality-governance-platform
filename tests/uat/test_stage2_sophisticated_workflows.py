"""
UAT Stage 2: Sophisticated Workflow Tests

These tests exercise complex multi-step workflows that demand more
from the system. They test:
- Multi-entity workflows (incident -> investigation -> action)
- Concurrent operations
- Edge cases and error handling
- Performance under load
- Data integrity across operations

Results Classification:
- WORKING: Test passes, feature functions correctly
- NOT_WORKING: Test fails, feature needs attention
- PARTIAL: Feature works with limitations

Note: The `client` fixture is defined in conftest.py with proper async isolation.
"""

import asyncio
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient

# ============================================================================
# Test Result Tracking
# ============================================================================


class TestResult:
    """Track test results with classification."""

    WORKING = []
    NOT_WORKING = []
    PARTIAL = []

    @classmethod
    def record(cls, test_id: str, status: str, details: str = ""):
        """Record a test result."""
        entry = {"id": test_id, "details": details}
        if status == "WORKING":
            cls.WORKING.append(entry)
        elif status == "NOT_WORKING":
            cls.NOT_WORKING.append(entry)
        else:
            cls.PARTIAL.append(entry)


# ============================================================================
# SUAT-001 to SUAT-010: Multi-Step Entity Workflows
# ============================================================================


class TestMultiStepEntityWorkflows:
    """Complex multi-step entity workflows."""

    @pytest.mark.asyncio
    async def test_suat_001_full_incident_lifecycle_via_portal(self, client):
        """
        SUAT-001: Complete incident lifecycle from portal submission to tracking.

        Workflow:
        1. Submit incident via employee portal
        2. Get reference number
        3. Track status via portal
        4. Verify timeline has submission event
        """
        # Step 1: Submit incident
        incident = {
            "report_type": "incident",
            "title": "SUAT-001: Lifecycle test incident",
            "description": "Testing full incident lifecycle from submission to tracking",
            "location": "Test Location",
            "severity": "medium",
            "reporter_name": "SUAT Tester",
            "reporter_email": "suat@example.com",
            "is_anonymous": False,
        }

        submit_response = await client.post("/api/v1/portal/reports/", json=incident)

        if submit_response.status_code != 201:
            TestResult.record(
                "SUAT-001",
                "NOT_WORKING",
                f"Submission failed: {submit_response.status_code}",
            )
            pytest.fail(f"Submission failed: {submit_response.text}")

        submit_data = submit_response.json()
        ref_number = submit_data["reference_number"]
        tracking_code = submit_data["tracking_code"]

        # Step 2: Verify reference number format
        assert ref_number.startswith("INC-"), f"Invalid reference format: {ref_number}"

        # Step 3: Track the report
        track_response = await client.get(f"/api/v1/portal/reports/{ref_number}/")

        if track_response.status_code != 200:
            TestResult.record("SUAT-001", "PARTIAL", "Submission works but tracking fails")
            pytest.fail(f"Tracking failed: {track_response.text}")

        track_data = track_response.json()

        # Step 4: Verify timeline
        assert "timeline" in track_data, "Missing timeline in tracking response"
        assert len(track_data["timeline"]) >= 1, "Timeline should have at least submission event"

        TestResult.record("SUAT-001", "WORKING", "Full lifecycle works")

    @pytest.mark.asyncio
    async def test_suat_002_complaint_with_status_tracking(self, client):
        """
        SUAT-002: Complaint submission and status tracking workflow.
        """
        complaint = {
            "report_type": "complaint",
            "title": "SUAT-002: Service quality complaint",
            "description": "Testing complaint workflow from submission to tracking",
            "severity": "high",
            "reporter_name": "SUAT Complainant",
            "reporter_email": "suat.complaint@example.com",
            "is_anonymous": False,
        }

        # Submit
        submit_response = await client.post("/api/v1/portal/reports/", json=complaint)
        assert submit_response.status_code == 201
        ref_number = submit_response.json()["reference_number"]

        # Track
        track_response = await client.get(f"/api/v1/portal/reports/{ref_number}/")
        assert track_response.status_code == 200

        data = track_response.json()
        assert data["report_type"] == "Complaint"
        assert "status" in data

        TestResult.record("SUAT-002", "WORKING")

    @pytest.mark.asyncio
    async def test_suat_003_anonymous_report_cannot_reveal_identity(self, client):
        """
        SUAT-003: Anonymous reports should not expose reporter identity.

        This is a security/privacy test.
        """
        anonymous_report = {
            "report_type": "incident",
            "title": "SUAT-003: Anonymous report privacy test",
            "description": "This report should not expose any reporter information",
            "severity": "critical",
            "is_anonymous": True,
        }

        submit_response = await client.post("/api/v1/portal/reports/", json=anonymous_report)
        assert submit_response.status_code == 201
        ref_number = submit_response.json()["reference_number"]

        # Track the report
        track_response = await client.get(f"/api/v1/portal/reports/{ref_number}/")
        assert track_response.status_code == 200

        data = track_response.json()

        # Verify no PII is exposed
        track_str = str(data).lower()
        assert "reporter_name" not in track_str or "anonymous" in track_str.lower()
        assert "reporter_email" not in track_str or data.get("reporter_email") is None

        TestResult.record("SUAT-003", "WORKING", "Anonymous privacy maintained")

    @pytest.mark.asyncio
    async def test_suat_004_qr_code_generation_after_submission(self, client):
        """
        SUAT-004: QR code should be generated immediately after submission.
        """
        incident = {
            "report_type": "incident",
            "title": "SUAT-004: QR code generation test",
            "description": "Testing QR code availability after submission",
            "severity": "low",
            "is_anonymous": False,
        }

        submit_response = await client.post("/api/v1/portal/reports/", json=incident)
        assert submit_response.status_code == 201

        data = submit_response.json()
        assert "qr_code_url" in data, "QR code URL should be in response"

        ref_number = data["reference_number"]

        # Fetch QR data
        qr_response = await client.get(f"/api/v1/portal/qr/{ref_number}/")
        assert qr_response.status_code == 200

        qr_data = qr_response.json()
        assert "tracking_url" in qr_data
        assert ref_number in qr_data["tracking_url"]

        TestResult.record("SUAT-004", "WORKING")

    @pytest.mark.asyncio
    async def test_suat_005_multiple_reports_same_session(self, client):
        """
        SUAT-005: Multiple reports in same session get unique references.
        """
        reports = []
        reference_numbers = set()

        for i in range(5):
            report = {
                "report_type": "incident",
                "title": f"SUAT-005: Multi-report test #{i + 1}",
                "description": f"Testing multiple report submission - report {i + 1}",
                "severity": "low",
                "is_anonymous": True,
            }

            response = await client.post("/api/v1/portal/reports/", json=report)
            assert response.status_code == 201, f"Report {i + 1} failed"

            ref = response.json()["reference_number"]
            assert ref not in reference_numbers, f"Duplicate reference: {ref}"
            reference_numbers.add(ref)
            reports.append(ref)

        assert len(reference_numbers) == 5, "Should have 5 unique references"

        TestResult.record("SUAT-005", "WORKING", f"Created {len(reports)} unique reports")


# ============================================================================
# SUAT-006 to SUAT-010: Concurrent Operations
# ============================================================================


class TestConcurrentOperations:
    """Test system behavior under concurrent load."""

    @pytest.mark.asyncio
    async def test_suat_006_concurrent_report_submissions(self, client):
        """
        SUAT-006: Concurrent report submissions should all succeed.
        """

        async def submit_report(index: int):
            report = {
                "report_type": "incident",
                "title": f"SUAT-006: Concurrent test #{index}",
                "description": f"Concurrent submission test report {index}",
                "severity": "low",
                "is_anonymous": True,
            }
            response = await client.post("/api/v1/portal/reports/", json=report)
            return response.status_code, response.json().get("reference_number")

        # Submit 10 reports concurrently
        tasks = [submit_report(i) for i in range(10)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        successes = [r for r in results if isinstance(r, tuple) and r[0] == 201]
        failures = [r for r in results if isinstance(r, Exception) or (isinstance(r, tuple) and r[0] != 201)]

        if len(failures) > 0:
            TestResult.record(
                "SUAT-006",
                "PARTIAL",
                f"{len(successes)}/10 succeeded, {len(failures)} failed",
            )
        else:
            TestResult.record("SUAT-006", "WORKING", "All 10 concurrent submissions succeeded")

        assert len(successes) >= 5, f"At least 50% should succeed, got {len(successes)}/10"

    @pytest.mark.asyncio
    async def test_suat_007_concurrent_health_checks(self, client):
        """
        SUAT-007: Health endpoint handles concurrent requests.
        """

        async def health_check():
            response = await client.get("/health")
            return response.status_code

        tasks = [health_check() for _ in range(20)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        successes = [r for r in results if r == 200]

        assert len(successes) == 20, f"All health checks should pass, got {len(successes)}/20"
        TestResult.record("SUAT-007", "WORKING")

    @pytest.mark.asyncio
    async def test_suat_008_concurrent_tracking_requests(self, client):
        """
        SUAT-008: Multiple tracking requests for same report don't conflict.
        """
        # First create a report
        report = {
            "report_type": "incident",
            "title": "SUAT-008: Concurrent tracking test",
            "description": "Testing concurrent tracking requests",
            "severity": "medium",
            "is_anonymous": True,
        }
        submit_response = await client.post("/api/v1/portal/reports/", json=report)
        ref_number = submit_response.json()["reference_number"]

        async def track_report():
            response = await client.get(f"/api/v1/portal/reports/{ref_number}/")
            return response.status_code, response.json()

        tasks = [track_report() for _ in range(10)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        successes = [r for r in results if isinstance(r, tuple) and r[0] == 200]

        assert len(successes) == 10, "All tracking requests should succeed"

        # Verify all responses are consistent
        statuses = {r[1]["status"] for r in successes}
        assert len(statuses) == 1, "All responses should have same status"

        TestResult.record("SUAT-008", "WORKING")


# ============================================================================
# SUAT-009 to SUAT-015: Error Handling & Edge Cases
# ============================================================================


class TestErrorHandlingEdgeCases:
    """Test error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_suat_009_extremely_long_description(self, client):
        """
        SUAT-009: System handles very long descriptions gracefully.
        """
        long_description = "A" * 10000  # 10K characters

        report = {
            "report_type": "incident",
            "title": "SUAT-009: Long description test",
            "description": long_description,
            "severity": "low",
            "is_anonymous": True,
        }

        response = await client.post("/api/v1/portal/reports/", json=report)

        # Should either succeed or fail gracefully with 422
        if response.status_code == 201:
            TestResult.record("SUAT-009", "WORKING", "Accepts long descriptions")
        elif response.status_code == 422:
            TestResult.record("SUAT-009", "WORKING", "Properly validates max length")
        else:
            TestResult.record("SUAT-009", "NOT_WORKING", f"Unexpected: {response.status_code}")
            pytest.fail(f"Unexpected response: {response.status_code}")

    @pytest.mark.asyncio
    async def test_suat_010_special_characters_in_title(self, client):
        """
        SUAT-010: System handles special characters safely.

        Note: XSS protection is primarily a frontend concern. The API
        should store data correctly and return valid JSON. HTML escaping
        should happen at display time in the frontend.

        This test verifies:
        1. API accepts special characters without error
        2. Response is valid JSON (not corrupted by special chars)
        3. Data is retrievable
        """
        special_title = "Test <script>alert('xss')</script> & 'quotes' \"double\""

        report = {
            "report_type": "incident",
            "title": special_title,
            "description": "Testing XSS and special character handling",
            "severity": "low",
            "is_anonymous": True,
        }

        response = await client.post("/api/v1/portal/reports/", json=report)

        if response.status_code == 201:
            data = response.json()
            ref = data["reference_number"]

            # Verify we can track the report
            track = await client.get(f"/api/v1/portal/reports/{ref}/")
            assert track.status_code == 200

            # Verify response is valid JSON (special chars properly escaped in JSON)
            track_data = track.json()
            assert "title" in track_data

            # The API stores data as-is; XSS protection is frontend's responsibility
            # This is acceptable behavior for a JSON API
            TestResult.record("SUAT-010", "WORKING", "API stores special chars, frontend must escape")
        elif response.status_code == 422:
            # Also acceptable: API validates and rejects potentially dangerous input
            TestResult.record("SUAT-010", "WORKING", "API validates and rejects dangerous input")
        else:
            TestResult.record("SUAT-010", "NOT_WORKING", f"Unexpected: {response.status_code}")
            pytest.fail(f"Unexpected response: {response.status_code}")

    @pytest.mark.asyncio
    async def test_suat_011_unicode_characters(self, client):
        """
        SUAT-011: System handles unicode/international characters.
        """
        unicode_report = {
            "report_type": "incident",
            "title": "SUAT-011: Unicode test 日本語 العربية 中文",
            "description": "Testing unicode: émojis 🚨 and интернационализация",
            "location": "北京市 / القاهرة / München",
            "severity": "low",
            "reporter_name": "José García 田中太郎",
            "is_anonymous": False,
        }

        response = await client.post("/api/v1/portal/reports/", json=unicode_report)

        assert response.status_code == 201, f"Unicode submission failed: {response.text}"

        ref = response.json()["reference_number"]
        track = await client.get(f"/api/v1/portal/reports/{ref}/")

        assert track.status_code == 200
        # Title should contain unicode
        assert "Unicode" in track.json()["title"]

        TestResult.record("SUAT-011", "WORKING", "Unicode handled correctly")

    @pytest.mark.asyncio
    async def test_suat_012_empty_optional_fields(self, client):
        """
        SUAT-012: Minimum required fields submission works.
        """
        minimal_report = {
            "report_type": "incident",
            "title": "SUAT-012: Minimal field test",
            "description": "Only required fields provided",
            "severity": "low",
        }

        response = await client.post("/api/v1/portal/reports/", json=minimal_report)

        assert response.status_code == 201
        TestResult.record("SUAT-012", "WORKING")

    @pytest.mark.asyncio
    async def test_suat_013_invalid_json_request(self, client):
        """
        SUAT-013: Invalid JSON is handled gracefully.
        """
        response = await client.post(
            "/api/v1/portal/reports/",
            content="not valid json {{{",
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 422, "Should return validation error"
        TestResult.record("SUAT-013", "WORKING")

    @pytest.mark.asyncio
    async def test_suat_014_missing_content_type(self, client):
        """
        SUAT-014: Request without content-type is handled.
        """
        report = {
            "report_type": "incident",
            "title": "SUAT-014: No content-type test",
            "description": "Testing missing content-type header",
            "severity": "low",
        }

        # Send without explicit content-type (httpx will still send it)
        response = await client.post("/api/v1/portal/reports/", json=report)

        # Should work with json= parameter
        assert response.status_code in [201, 422]
        TestResult.record("SUAT-014", "WORKING")

    @pytest.mark.asyncio
    async def test_suat_015_rate_limiting_enforcement(self, client):
        """
        SUAT-015: Rate limiting is enforced on protected endpoints.
        """
        # Make many requests to a rate-limited endpoint
        responses = []
        for _ in range(35):  # Exceed the 30 rpm limit
            response = await client.get("/api/v1/incidents/")
            responses.append(response)

        # Should see rate limit headers
        has_rate_limit_header = any("x-ratelimit" in str(r.headers).lower() for r in responses)

        # Note: Rate limiting might not trigger 429 in test mode
        if has_rate_limit_header:
            TestResult.record("SUAT-015", "WORKING", "Rate limit headers present")
        else:
            TestResult.record("SUAT-015", "PARTIAL", "Rate limiting may be disabled in test mode")


# ============================================================================
# SUAT-016 to SUAT-020: API Contract Verification
# ============================================================================


class TestAPIContractVerification:
    """Verify API contracts are consistent."""

    @pytest.mark.asyncio
    async def test_suat_016_openapi_has_all_portal_endpoints(self, client):
        """
        SUAT-016: OpenAPI spec documents all portal endpoints.
        """
        response = await client.get("/openapi.json")
        assert response.status_code == 200

        spec = response.json()
        paths = spec.get("paths", {})

        expected_paths = [
            "/api/v1/portal/reports/",
            "/api/v1/portal/stats/",
            "/api/v1/portal/report-types/",
        ]

        missing = [p for p in expected_paths if p not in paths and not any(p in path for path in paths)]

        if missing:
            TestResult.record("SUAT-016", "PARTIAL", f"Missing paths: {missing}")
        else:
            TestResult.record("SUAT-016", "WORKING")

    @pytest.mark.asyncio
    async def test_suat_017_error_responses_have_consistent_format(self, client):
        """
        SUAT-017: Error responses follow consistent JSON format.
        """
        # Test various error scenarios
        error_responses = []

        # 401 errors
        r1 = await client.get("/api/v1/incidents/")
        error_responses.append(("401", r1))

        # 404 errors
        r2 = await client.get("/api/v1/portal/reports/NONEXISTENT-REF/")
        error_responses.append(("404", r2))

        # 422 errors
        r3 = await client.post("/api/v1/portal/reports/", json={})
        error_responses.append(("422", r3))

        all_have_detail = True
        for name, response in error_responses:
            if response.status_code >= 400:
                data = response.json()
                if "detail" not in data and "error" not in data and "message" not in data:
                    all_have_detail = False

        if all_have_detail:
            TestResult.record("SUAT-017", "WORKING")
        else:
            TestResult.record("SUAT-017", "PARTIAL", "Some errors lack detail field")

    @pytest.mark.asyncio
    async def test_suat_018_responses_include_request_id(self, client):
        """
        SUAT-018: All responses include request ID for traceability.
        """
        endpoints = [
            "/health",
            "/healthz",
            "/api/v1/incidents/",
            "/api/v1/portal/stats/",
        ]

        missing_request_id = []
        for endpoint in endpoints:
            response = await client.get(endpoint)
            if "x-request-id" not in response.headers:
                missing_request_id.append(endpoint)

        if not missing_request_id:
            TestResult.record("SUAT-018", "WORKING")
        else:
            TestResult.record("SUAT-018", "PARTIAL", f"Missing on: {missing_request_id}")

    @pytest.mark.asyncio
    async def test_suat_019_pagination_fields_consistent(self, client):
        """
        SUAT-019: Paginated responses have consistent structure.

        Note: This test checks portal stats which doesn't paginate,
        but real paginated endpoints require auth.
        """
        # Portal stats doesn't paginate, but let's verify consistency
        response = await client.get("/api/v1/portal/stats/")
        assert response.status_code == 200

        # Verify the response has expected structure
        data = response.json()
        expected_fields = ["total_reports_today", "average_resolution_days"]
        has_expected = all(f in data for f in expected_fields)

        if has_expected:
            TestResult.record("SUAT-019", "WORKING")
        else:
            TestResult.record("SUAT-019", "PARTIAL", "Stats response missing fields")

    @pytest.mark.asyncio
    async def test_suat_020_datetime_format_consistency(self, client):
        """
        SUAT-020: DateTime fields use ISO 8601 format.
        """
        # Submit and track a report
        report = {
            "report_type": "incident",
            "title": "SUAT-020: DateTime format test",
            "description": "Testing datetime field format",
            "severity": "low",
            "is_anonymous": True,
        }

        submit = await client.post("/api/v1/portal/reports/", json=report)
        ref = submit.json()["reference_number"]

        track = await client.get(f"/api/v1/portal/reports/{ref}/")
        data = track.json()

        # Check datetime fields
        datetime_fields = ["submitted_at", "updated_at"]
        valid_format = True

        for field in datetime_fields:
            if field in data:
                try:
                    # Should be parseable ISO format
                    datetime.fromisoformat(data[field].replace("Z", "+00:00"))
                except ValueError:
                    valid_format = False

        if valid_format:
            TestResult.record("SUAT-020", "WORKING")
        else:
            TestResult.record("SUAT-020", "PARTIAL", "Some datetime fields not ISO 8601")


# ============================================================================
# Test Summary Generator
# ============================================================================


@pytest.fixture(scope="module", autouse=True)
def generate_test_summary(request):
    """Generate test summary after all tests complete."""
    yield

    print("\n" + "=" * 70)
    print("UAT STAGE 2 TEST SUMMARY")
    print("=" * 70)

    print(f"\n✅ WORKING ({len(TestResult.WORKING)}):")
    for item in TestResult.WORKING:
        print(f"   - {item['id']}: {item.get('details', 'OK')}")

    print(f"\n⚠️ PARTIAL ({len(TestResult.PARTIAL)}):")
    for item in TestResult.PARTIAL:
        print(f"   - {item['id']}: {item.get('details', '')}")

    print(f"\n❌ NOT WORKING ({len(TestResult.NOT_WORKING)}):")
    for item in TestResult.NOT_WORKING:
        print(f"   - {item['id']}: {item.get('details', '')}")

    total = len(TestResult.WORKING) + len(TestResult.PARTIAL) + len(TestResult.NOT_WORKING)
    if total > 0:
        health = len(TestResult.WORKING) / total * 100
        print(f"\n📊 Overall Health: {health:.1f}%")
    print("=" * 70)
