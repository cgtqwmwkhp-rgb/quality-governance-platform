"""Behavioral unit tests for domain services.

Tests pure business logic without database dependencies:
- ReferenceNumberService.parse
- Risk score calculation
- Risk level mapping
"""

import pytest


class TestReferenceNumberParsing:
    """ReferenceNumberService.parse must decompose valid refs correctly."""

    def test_valid_incident_reference(self):
        from src.services.reference_number import ReferenceNumberService

        result = ReferenceNumberService.parse("INC-2026-0042")
        assert result == {"prefix": "INC", "year": 2026, "sequence": 42}

    def test_valid_audit_reference(self):
        from src.services.reference_number import ReferenceNumberService

        result = ReferenceNumberService.parse("AUD-2025-0001")
        assert result == {"prefix": "AUD", "year": 2025, "sequence": 1}

    def test_valid_complaint_reference(self):
        from src.services.reference_number import ReferenceNumberService

        result = ReferenceNumberService.parse("CMP-2026-9999")
        assert result == {"prefix": "CMP", "year": 2026, "sequence": 9999}

    def test_invalid_reference_returns_nones(self):
        from src.services.reference_number import ReferenceNumberService

        result = ReferenceNumberService.parse("GARBAGE")
        assert result == {"prefix": None, "year": None, "sequence": None}

    def test_empty_string_returns_nones(self):
        from src.services.reference_number import ReferenceNumberService

        result = ReferenceNumberService.parse("")
        assert result == {"prefix": None, "year": None, "sequence": None}

    def test_partial_reference_returns_nones(self):
        from src.services.reference_number import ReferenceNumberService

        result = ReferenceNumberService.parse("INC-2026")
        assert result["prefix"] == "INC"
        assert result["year"] == 2026
        assert result["sequence"] is None

    def test_prefix_mapping_covers_all_entity_types(self):
        from src.services.reference_number import ReferenceNumberService

        expected_types = {
            "audit_run", "audit_finding", "risk", "incident",
            "rta", "complaint", "policy", "incident_action",
            "rta_action", "complaint_action",
        }
        assert set(ReferenceNumberService.PREFIXES.keys()) == expected_types


class TestRiskScoreCalculation:
    """Risk matrix calculations must be deterministic."""

    def test_score_is_likelihood_times_impact(self):
        from src.api.routes.risks import calculate_risk_level

        score, level, color = calculate_risk_level(3, 4)
        assert score == 12
        assert isinstance(level, str)
        assert isinstance(color, str)

    def test_minimum_score(self):
        from src.api.routes.risks import calculate_risk_level

        score, level, _ = calculate_risk_level(1, 1)
        assert score == 1
        assert level == "very_low"

    def test_maximum_score(self):
        from src.api.routes.risks import calculate_risk_level

        score, level, _ = calculate_risk_level(5, 5)
        assert score == 25
        assert level == "critical"

    def test_matrix_is_symmetric_at_corners(self):
        from src.api.routes.risks import calculate_risk_level

        _, level_1_5, _ = calculate_risk_level(1, 5)
        _, level_5_1, _ = calculate_risk_level(5, 1)
        assert level_1_5 == level_5_1 == "medium"

    def test_all_matrix_cells_return_valid_levels(self):
        from src.api.routes.risks import calculate_risk_level

        valid_levels = {"very_low", "low", "medium", "high", "critical"}
        for likelihood in range(1, 6):
            for impact in range(1, 6):
                score, level, color = calculate_risk_level(likelihood, impact)
                assert level in valid_levels, f"Invalid level '{level}' for ({likelihood}, {impact})"
                assert score == likelihood * impact
                assert color.startswith("#")


class TestRiskScoringServiceLevels:
    """RiskScoringService._calculate_risk_level boundaries."""

    def test_critical_threshold(self):
        from src.services.risk_scoring import RiskScoringService

        svc = RiskScoringService.__new__(RiskScoringService)
        assert svc._calculate_risk_level(20) == "critical"
        assert svc._calculate_risk_level(25) == "critical"

    def test_high_threshold(self):
        from src.services.risk_scoring import RiskScoringService

        svc = RiskScoringService.__new__(RiskScoringService)
        assert svc._calculate_risk_level(15) == "high"
        assert svc._calculate_risk_level(19) == "high"

    def test_medium_threshold(self):
        from src.services.risk_scoring import RiskScoringService

        svc = RiskScoringService.__new__(RiskScoringService)
        assert svc._calculate_risk_level(10) == "medium"
        assert svc._calculate_risk_level(14) == "medium"

    def test_low_threshold(self):
        from src.services.risk_scoring import RiskScoringService

        svc = RiskScoringService.__new__(RiskScoringService)
        assert svc._calculate_risk_level(5) == "low"
        assert svc._calculate_risk_level(9) == "low"

    def test_negligible_threshold(self):
        from src.services.risk_scoring import RiskScoringService

        svc = RiskScoringService.__new__(RiskScoringService)
        assert svc._calculate_risk_level(1) == "negligible"
        assert svc._calculate_risk_level(4) == "negligible"


class TestSecurityTokenUtils:
    """JWT token creation and verification roundtrips."""

    def test_access_token_roundtrip(self):
        from src.core.security import create_access_token, decode_token

        token = create_access_token(subject="42")
        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == "42"
        assert payload["type"] == "access"

    def test_decode_invalid_token_returns_none(self):
        from src.core.security import decode_token

        result = decode_token("not.a.valid.jwt")
        assert result is None

    def test_password_reset_token_roundtrip(self):
        from src.core.security import create_password_reset_token, verify_password_reset_token

        token = create_password_reset_token(user_id=7)
        user_id = verify_password_reset_token(token)
        assert user_id == 7

    def test_password_reset_token_wrong_type_rejected(self):
        from src.core.security import create_access_token, verify_password_reset_token

        access_token = create_access_token(subject="7")
        user_id = verify_password_reset_token(access_token)
        assert user_id is None

    def test_password_hash_roundtrip(self):
        from src.core.security import get_password_hash, verify_password

        hashed = get_password_hash("s3cureP@ss!")
        assert verify_password("s3cureP@ss!", hashed)
        assert not verify_password("wrong-password", hashed)
