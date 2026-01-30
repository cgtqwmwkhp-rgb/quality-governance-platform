"""
ETL API Client - Quality Governance Platform
Stage 10: Data Foundation

Authenticated API client for ETL import operations with:
- Retry logic for 5xx and 429 errors
- Idempotency via reference_number (409 CONFLICT = skip)
- Audit trail for all operations
"""

import json
import logging
import os
import ssl
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ImportResult(Enum):
    """Result of an import operation."""

    CREATED = "created"
    SKIPPED_EXISTS = "skipped_exists"  # 409 CONFLICT
    SKIPPED_VALIDATION = "skipped_validation"
    FAILED = "failed"
    RETRIED = "retried"


@dataclass
class ImportRecord:
    """Record of a single import attempt."""

    entity_type: str
    reference_number: str
    result: ImportResult
    status_code: Optional[int] = None
    response_time_ms: float = 0.0
    error_message: Optional[str] = None
    api_id: Optional[int] = None  # ID assigned by API on creation
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_type": self.entity_type,
            "reference_number": self.reference_number,
            "result": self.result.value,
            "status_code": self.status_code,
            "response_time_ms": round(self.response_time_ms, 2),
            "error_message": self.error_message,
            "api_id": self.api_id,
            "timestamp": self.timestamp.isoformat(),
        }


class ETLAPIClient:
    """
    Authenticated API client for ETL import operations.

    Features:
    - JWT Bearer token authentication
    - Retry on 5xx and 429 with exponential backoff
    - Idempotency: 409 CONFLICT means record exists (skip)
    - Comprehensive logging and audit trail
    """

    def __init__(
        self,
        base_url: str,
        auth_token: Optional[str] = None,
        timeout_seconds: int = 30,
        max_retries: int = 3,
        initial_retry_delay: float = 1.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.auth_token = auth_token or os.getenv("QGP_API_TOKEN")
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.initial_retry_delay = initial_retry_delay

        # SSL context for HTTPS
        self.ssl_context = ssl.create_default_context()

        # Track all operations
        self.import_records: List[ImportRecord] = []

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with auth token."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "QGP-ETL-Client/1.0",
        }
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        return headers

    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Tuple[int, Optional[Dict[str, Any]], float]:
        """
        Make HTTP request with retry logic.

        Returns: (status_code, response_data, response_time_ms)
        """
        url = f"{self.base_url}{endpoint}"
        headers = self._get_headers()

        request_data = None
        if data:
            request_data = json.dumps(data).encode("utf-8")

        for attempt in range(self.max_retries + 1):
            start_time = time.time()
            try:
                request = urllib.request.Request(
                    url,
                    data=request_data,
                    headers=headers,
                    method=method,
                )

                with urllib.request.urlopen(
                    request,
                    timeout=self.timeout_seconds,
                    context=self.ssl_context,
                ) as response:
                    response_time = (time.time() - start_time) * 1000
                    status_code = response.status
                    response_data = json.loads(response.read().decode("utf-8"))
                    return status_code, response_data, response_time

            except urllib.error.HTTPError as e:
                response_time = (time.time() - start_time) * 1000
                status_code = e.code

                try:
                    error_body = json.loads(e.read().decode("utf-8"))
                except Exception:
                    error_body = {"error": str(e)}

                # 409 CONFLICT = record already exists (idempotent skip)
                if status_code == 409:
                    return status_code, error_body, response_time

                # 4xx errors (except 429) are not retryable
                if 400 <= status_code < 500 and status_code != 429:
                    return status_code, error_body, response_time

                # 429 or 5xx: retry with backoff
                if attempt < self.max_retries:
                    # Check for Retry-After header
                    retry_after = e.headers.get("Retry-After")
                    if retry_after:
                        try:
                            delay = float(retry_after)
                        except ValueError:
                            delay = self.initial_retry_delay * (2**attempt)
                    else:
                        delay = self.initial_retry_delay * (2**attempt)

                    logger.warning(
                        f"Request failed with {status_code}, retrying in {delay}s "
                        f"(attempt {attempt + 1}/{self.max_retries})"
                    )
                    time.sleep(delay)
                    continue

                return status_code, error_body, response_time

            except urllib.error.URLError as e:
                response_time = (time.time() - start_time) * 1000
                if attempt < self.max_retries:
                    delay = self.initial_retry_delay * (2**attempt)
                    logger.warning(f"Connection error, retrying in {delay}s: {e}")
                    time.sleep(delay)
                    continue
                return 0, {"error": str(e)}, response_time

            except Exception as e:
                response_time = (time.time() - start_time) * 1000
                logger.error(f"Unexpected error: {e}")
                return 0, {"error": str(e)}, response_time

        return 0, {"error": "Max retries exceeded"}, 0.0

    def create_incident(self, data: Dict[str, Any]) -> ImportRecord:
        """
        Create an incident via API.

        Uses reference_number for idempotency:
        - 201: Created successfully
        - 409: Already exists (idempotent skip)
        - Other: Error
        """
        reference_number = data.get("reference_number", "UNKNOWN")

        status_code, response, response_time = self._make_request(
            "POST",
            "/api/v1/incidents/",
            data,
        )

        if status_code == 201:
            record = ImportRecord(
                entity_type="incident",
                reference_number=reference_number,
                result=ImportResult.CREATED,
                status_code=status_code,
                response_time_ms=response_time,
                api_id=response.get("id") if response else None,
            )
        elif status_code == 409:
            record = ImportRecord(
                entity_type="incident",
                reference_number=reference_number,
                result=ImportResult.SKIPPED_EXISTS,
                status_code=status_code,
                response_time_ms=response_time,
            )
        else:
            record = ImportRecord(
                entity_type="incident",
                reference_number=reference_number,
                result=ImportResult.FAILED,
                status_code=status_code,
                response_time_ms=response_time,
                error_message=str(response) if response else "Unknown error",
            )

        self.import_records.append(record)
        return record

    def create_complaint(self, data: Dict[str, Any]) -> ImportRecord:
        """Create a complaint via API."""
        reference_number = data.get("reference_number", "UNKNOWN")

        status_code, response, response_time = self._make_request(
            "POST",
            "/api/v1/complaints/",
            data,
        )

        if status_code == 201:
            result = ImportResult.CREATED
            api_id = response.get("id") if response else None
            error_msg = None
        elif status_code == 409:
            result = ImportResult.SKIPPED_EXISTS
            api_id = None
            error_msg = None
        else:
            result = ImportResult.FAILED
            api_id = None
            error_msg = str(response) if response else "Unknown error"

        record = ImportRecord(
            entity_type="complaint",
            reference_number=reference_number,
            result=result,
            status_code=status_code,
            response_time_ms=response_time,
            api_id=api_id,
            error_message=error_msg,
        )
        self.import_records.append(record)
        return record

    def create_rta(self, data: Dict[str, Any]) -> ImportRecord:
        """Create an RTA via API."""
        reference_number = data.get("reference_number", "UNKNOWN")

        status_code, response, response_time = self._make_request(
            "POST",
            "/api/v1/rtas/",
            data,
        )

        if status_code == 201:
            result = ImportResult.CREATED
            api_id = response.get("id") if response else None
            error_msg = None
        elif status_code == 409:
            result = ImportResult.SKIPPED_EXISTS
            api_id = None
            error_msg = None
        else:
            result = ImportResult.FAILED
            api_id = None
            error_msg = str(response) if response else "Unknown error"

        record = ImportRecord(
            entity_type="rta",
            reference_number=reference_number,
            result=result,
            status_code=status_code,
            response_time_ms=response_time,
            api_id=api_id,
            error_message=error_msg,
        )
        self.import_records.append(record)
        return record

    def get_import_summary(self) -> Dict[str, Any]:
        """Get summary of all import operations."""
        summary = {
            "total": len(self.import_records),
            "created": 0,
            "skipped_exists": 0,
            "failed": 0,
            "by_entity": {},
        }

        for record in self.import_records:
            if record.result == ImportResult.CREATED:
                summary["created"] += 1
            elif record.result == ImportResult.SKIPPED_EXISTS:
                summary["skipped_exists"] += 1
            elif record.result == ImportResult.FAILED:
                summary["failed"] += 1

            entity = record.entity_type
            if entity not in summary["by_entity"]:
                summary["by_entity"][entity] = {"created": 0, "skipped": 0, "failed": 0}

            if record.result == ImportResult.CREATED:
                summary["by_entity"][entity]["created"] += 1
            elif record.result == ImportResult.SKIPPED_EXISTS:
                summary["by_entity"][entity]["skipped"] += 1
            else:
                summary["by_entity"][entity]["failed"] += 1

        return summary

    def get_import_records(self) -> List[Dict[str, Any]]:
        """Get all import records as dictionaries."""
        return [r.to_dict() for r in self.import_records]
