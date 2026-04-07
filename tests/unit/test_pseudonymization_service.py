"""Unit tests for PseudonymizationService (D15 coverage uplift, D07 privacy evidence)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.services.pseudonymization_service import PII_FIELDS, PseudonymizationResult, PseudonymizationService


class TestHashValue:
    """Tests for the internal _hash_value method."""

    def _service(self) -> PseudonymizationService:
        mock_db = AsyncMock()
        with patch("src.domain.services.pseudonymization_service.settings") as m:
            m.pseudonymization_pepper = "test-pepper-secret"
            svc = PseudonymizationService(mock_db)
        return svc

    def test_hash_is_deterministic(self) -> None:
        svc = self._service()
        assert svc._hash_value("alice@example.com") == svc._hash_value("alice@example.com")

    def test_different_values_produce_different_hashes(self) -> None:
        svc = self._service()
        assert svc._hash_value("alice@example.com") != svc._hash_value("bob@example.com")

    def test_hash_length_is_64_chars(self) -> None:
        svc = self._service()
        result = svc._hash_value("test@example.com")
        assert len(result) == 64

    def test_hash_is_hex(self) -> None:
        svc = self._service()
        result = svc._hash_value("test@example.com")
        int(result, 16)  # raises ValueError if not hex

    def test_different_peppers_produce_different_hashes(self) -> None:
        mock_db = AsyncMock()
        with patch("src.domain.services.pseudonymization_service.settings") as m:
            m.pseudonymization_pepper = "pepper-a"
            svc_a = PseudonymizationService(mock_db)
        with patch("src.domain.services.pseudonymization_service.settings") as m:
            m.pseudonymization_pepper = "pepper-b"
            svc_b = PseudonymizationService(mock_db)

        assert svc_a._hash_value("same@value.com") != svc_b._hash_value("same@value.com")


class TestPseudonymizeRecord:
    """Tests for PseudonymizationService.pseudonymize_record."""

    def _service(self, dry_run: bool = False) -> PseudonymizationService:
        mock_db = AsyncMock()
        with patch("src.domain.services.pseudonymization_service.settings") as m:
            m.pseudonymization_pepper = "test-pepper"
            svc = PseudonymizationService(mock_db, dry_run=dry_run)
        return svc

    def test_pii_fields_are_pseudonymized_in_record(self) -> None:
        svc = self._service()
        record = {"id": 1, "email": "alice@example.com", "first_name": "Alice"}

        result = svc.pseudonymize_record(record)

        assert "email" in result.fields_affected
        assert "first_name" in result.fields_affected
        assert record["email"].startswith("ali*** -> ") is False  # pseudonymized in-place
        assert record["email"] != "alice@example.com"

    def test_non_pii_fields_not_touched(self) -> None:
        svc = self._service()
        record = {"id": 42, "email": "x@y.com", "status": "active", "score": 99}

        svc.pseudonymize_record(record)

        assert record["status"] == "active"
        assert record["score"] == 99
        assert record["id"] == 42

    def test_none_fields_are_skipped(self) -> None:
        svc = self._service()
        record = {"id": 1, "email": None, "first_name": "Bob"}

        result = svc.pseudonymize_record(record)

        assert "email" not in result.fields_affected
        assert "first_name" in result.fields_affected

    def test_custom_fields_parameter(self) -> None:
        svc = self._service()
        record = {"email": "x@y.com", "note": "sensitive"}

        result = svc.pseudonymize_record(record, fields=["note"])

        assert "note" in result.fields_affected
        assert "email" not in result.fields_affected

    def test_dry_run_does_not_mutate_record(self) -> None:
        svc = self._service(dry_run=True)
        original_email = "alice@example.com"
        record = {"id": 1, "email": original_email}

        result = svc.pseudonymize_record(record)

        # Dry run: record must NOT be mutated
        assert record["email"] == original_email
        assert result.dry_run is True

    def test_result_has_correct_entity_id(self) -> None:
        svc = self._service()
        record = {"id": 77, "email": "test@test.com"}

        result = svc.pseudonymize_record(record)

        assert result.entity_id == 77

    def test_result_entity_type_is_record(self) -> None:
        svc = self._service()
        record = {"email": "a@b.com"}

        result = svc.pseudonymize_record(record)

        assert result.entity_type == "record"


class TestPseudonymizationResult:
    """Tests for the PseudonymizationResult dataclass."""

    def test_default_fields_affected_is_empty_dict(self) -> None:
        r = PseudonymizationResult(entity_type="user", entity_id=1)
        assert r.fields_affected == {}

    def test_dry_run_defaults_to_false(self) -> None:
        r = PseudonymizationResult(entity_type="user", entity_id=1)
        assert r.dry_run is False

    def test_fields_affected_is_mutable(self) -> None:
        r1 = PseudonymizationResult(entity_type="user", entity_id=1)
        r2 = PseudonymizationResult(entity_type="user", entity_id=2)
        r1.fields_affected["email"] = "hash"
        assert "email" not in r2.fields_affected  # not shared


class TestPiiFieldsConstant:
    """Verify the PII_FIELDS constant meets compliance requirements."""

    def test_email_is_pii_field(self) -> None:
        assert "email" in PII_FIELDS

    def test_name_fields_are_pii(self) -> None:
        assert "first_name" in PII_FIELDS
        assert "last_name" in PII_FIELDS

    def test_phone_is_pii_field(self) -> None:
        assert "phone" in PII_FIELDS
