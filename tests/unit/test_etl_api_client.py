"""
Unit tests for ETL API Client.

Tests:
- Create success (201)
- Idempotent skip on existing record (409)
- Retry on 5xx errors
- Retry on 429 with Retry-After
- No retry on 4xx errors (except 429)
"""

import json
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.etl.api_client import ETLAPIClient, ImportRecord, ImportResult


class TestETLAPIClient(unittest.TestCase):
    """Tests for ETLAPIClient."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = ETLAPIClient(
            base_url="https://test-api.example.com",
            auth_token="test-token",
            timeout_seconds=10,
            max_retries=2,
            initial_retry_delay=0.01,  # Fast retries for tests
        )

    def _mock_response(self, status_code: int, data: dict):
        """Create a mock urllib response."""
        response = MagicMock()
        response.status = status_code
        response.read.return_value = json.dumps(data).encode()
        return response

    def _mock_http_error(self, status_code: int, data: dict, headers: dict = None):
        """Create a mock HTTPError."""
        error = urllib.error.HTTPError(
            url="https://test-api.example.com/api/v1/incidents/",
            code=status_code,
            msg="Error",
            hdrs=headers or {},
            fp=MagicMock(),
        )
        error.read = MagicMock(return_value=json.dumps(data).encode())
        error.headers = headers or {}
        return error

    @patch("urllib.request.urlopen")
    def test_create_incident_success(self, mock_urlopen):
        """Test successful incident creation (201)."""
        mock_urlopen.return_value.__enter__.return_value = self._mock_response(
            201, {"id": 123, "reference_number": "SAMPLE-INC-001"}
        )

        result = self.client.create_incident(
            {
                "reference_number": "SAMPLE-INC-001",
                "title": "Test Incident",
                "description": "Test description",
            }
        )

        self.assertEqual(result.result, ImportResult.CREATED)
        self.assertEqual(result.status_code, 201)
        self.assertEqual(result.api_id, 123)
        self.assertIsNone(result.error_message)

    @patch("urllib.request.urlopen")
    def test_create_incident_idempotent_skip(self, mock_urlopen):
        """Test idempotent skip on existing record (409)."""
        mock_urlopen.side_effect = self._mock_http_error(
            409, {"detail": "Incident with reference number SAMPLE-INC-001 already exists"}
        )

        result = self.client.create_incident(
            {
                "reference_number": "SAMPLE-INC-001",
                "title": "Test Incident",
            }
        )

        self.assertEqual(result.result, ImportResult.SKIPPED_EXISTS)
        self.assertEqual(result.status_code, 409)
        self.assertIsNone(result.api_id)

    @patch("urllib.request.urlopen")
    def test_create_incident_auth_error(self, mock_urlopen):
        """Test auth error (401) - no retry."""
        mock_urlopen.side_effect = self._mock_http_error(401, {"detail": "Not authenticated"})

        result = self.client.create_incident(
            {
                "reference_number": "SAMPLE-INC-001",
                "title": "Test Incident",
            }
        )

        self.assertEqual(result.result, ImportResult.FAILED)
        self.assertEqual(result.status_code, 401)
        # Should not retry on 401
        self.assertEqual(mock_urlopen.call_count, 1)

    @patch("urllib.request.urlopen")
    def test_retry_on_500_error(self, mock_urlopen):
        """Test retry on 500 error."""
        # First call fails with 500, second succeeds
        mock_urlopen.side_effect = [
            self._mock_http_error(500, {"detail": "Internal error"}),
            MagicMock(
                __enter__=MagicMock(
                    return_value=self._mock_response(201, {"id": 456, "reference_number": "SAMPLE-INC-002"})
                )
            ),
        ]

        result = self.client.create_incident(
            {
                "reference_number": "SAMPLE-INC-002",
                "title": "Test Incident",
            }
        )

        self.assertEqual(result.result, ImportResult.CREATED)
        self.assertEqual(mock_urlopen.call_count, 2)

    @patch("urllib.request.urlopen")
    def test_retry_on_429_with_retry_after(self, mock_urlopen):
        """Test retry on 429 with Retry-After header."""
        error_429 = self._mock_http_error(429, {"detail": "Rate limited"}, headers={"Retry-After": "0.01"})

        mock_urlopen.side_effect = [
            error_429,
            MagicMock(
                __enter__=MagicMock(
                    return_value=self._mock_response(201, {"id": 789, "reference_number": "SAMPLE-INC-003"})
                )
            ),
        ]

        result = self.client.create_incident(
            {
                "reference_number": "SAMPLE-INC-003",
                "title": "Test Incident",
            }
        )

        self.assertEqual(result.result, ImportResult.CREATED)
        self.assertEqual(mock_urlopen.call_count, 2)

    @patch("urllib.request.urlopen")
    def test_no_retry_on_400_error(self, mock_urlopen):
        """Test no retry on 400 error (bad request)."""
        mock_urlopen.side_effect = self._mock_http_error(400, {"detail": "Validation error"})

        result = self.client.create_incident(
            {
                "reference_number": "SAMPLE-INC-004",
                "title": "",  # Invalid
            }
        )

        self.assertEqual(result.result, ImportResult.FAILED)
        self.assertEqual(result.status_code, 400)
        # Should not retry on 400
        self.assertEqual(mock_urlopen.call_count, 1)

    def test_import_summary(self):
        """Test import summary generation."""
        # Add some mock records
        self.client.import_records = [
            ImportRecord(
                entity_type="incident",
                reference_number="INC-001",
                result=ImportResult.CREATED,
                status_code=201,
            ),
            ImportRecord(
                entity_type="incident",
                reference_number="INC-002",
                result=ImportResult.SKIPPED_EXISTS,
                status_code=409,
            ),
            ImportRecord(
                entity_type="complaint",
                reference_number="COMP-001",
                result=ImportResult.CREATED,
                status_code=201,
            ),
            ImportRecord(
                entity_type="rta",
                reference_number="RTA-001",
                result=ImportResult.FAILED,
                status_code=500,
            ),
        ]

        summary = self.client.get_import_summary()

        self.assertEqual(summary["total"], 4)
        self.assertEqual(summary["created"], 2)
        self.assertEqual(summary["skipped_exists"], 1)
        self.assertEqual(summary["failed"], 1)
        self.assertEqual(summary["by_entity"]["incident"]["created"], 1)
        self.assertEqual(summary["by_entity"]["incident"]["skipped"], 1)

    def test_auth_header_included(self):
        """Test that auth header is included in requests."""
        headers = self.client._get_headers()

        self.assertIn("Authorization", headers)
        self.assertEqual(headers["Authorization"], "Bearer test-token")
        self.assertEqual(headers["Content-Type"], "application/json")


class TestImportRecord(unittest.TestCase):
    """Tests for ImportRecord dataclass."""

    def test_to_dict(self):
        """Test ImportRecord serialization."""
        record = ImportRecord(
            entity_type="incident",
            reference_number="INC-001",
            result=ImportResult.CREATED,
            status_code=201,
            response_time_ms=123.456,
            api_id=42,
        )

        data = record.to_dict()

        self.assertEqual(data["entity_type"], "incident")
        self.assertEqual(data["reference_number"], "INC-001")
        self.assertEqual(data["result"], "created")
        self.assertEqual(data["status_code"], 201)
        self.assertEqual(data["response_time_ms"], 123.46)  # Rounded
        self.assertEqual(data["api_id"], 42)


if __name__ == "__main__":
    unittest.main()
