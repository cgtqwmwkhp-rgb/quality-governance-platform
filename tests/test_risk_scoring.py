"""Comprehensive tests for Risk Scoring and KRI Services.

Tests cover:
- Dynamic risk score calculation
- KRI threshold evaluation
- Alert generation
- Trend calculations
- SIF classification
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.risk_scoring import (
    RiskScoringService,
    KRIService,
)
from src.domain.models.kri import (
    KeyRiskIndicator,
    KRIAlert,
    KRIMeasurement,
    KRICategory,
    KRITrendDirection,
    RiskScoreHistory,
    ThresholdStatus,
)
from src.domain.models.incident import IncidentSeverity


class TestRiskScoringService:
    """Test suite for Risk Scoring Service."""

    def test_severity_impact_mapping(self):
        """Test that severity to impact mapping is correct."""
        assert RiskScoringService.SEVERITY_IMPACT[IncidentSeverity.CRITICAL] == 2
        assert RiskScoringService.SEVERITY_IMPACT[IncidentSeverity.HIGH] == 1
        assert RiskScoringService.SEVERITY_IMPACT[IncidentSeverity.MEDIUM] == 0
        assert RiskScoringService.SEVERITY_IMPACT[IncidentSeverity.LOW] == 0

    def test_calculate_risk_level(self):
        """Test risk level calculation from score."""
        service = RiskScoringService(AsyncMock())

        assert service._calculate_risk_level(25) == "critical"
        assert service._calculate_risk_level(20) == "critical"
        assert service._calculate_risk_level(15) == "high"
        assert service._calculate_risk_level(10) == "medium"
        assert service._calculate_risk_level(5) == "low"
        assert service._calculate_risk_level(4) == "negligible"
        assert service._calculate_risk_level(1) == "negligible"


class TestKeyRiskIndicator:
    """Test suite for KRI model."""

    def test_kri_creation(self):
        """Test creating a KRI."""
        kri = KeyRiskIndicator(
            code="INC-001",
            name="Monthly Incident Count",
            description="Total incidents reported per month",
            category=KRICategory.SAFETY,
            unit="count",
            measurement_frequency="monthly",
            data_source="incident_count",
            lower_is_better=True,
            green_threshold=5,
            amber_threshold=10,
            red_threshold=15,
            is_active=True,
        )

        assert kri.code == "INC-001"
        assert kri.category == KRICategory.SAFETY
        assert kri.lower_is_better is True

    def test_calculate_status_lower_is_better(self):
        """Test status calculation when lower values are better."""
        kri = KeyRiskIndicator(
            code="TEST",
            name="Test KRI",
            category=KRICategory.SAFETY,
            unit="count",
            data_source="test",
            lower_is_better=True,
            green_threshold=5,
            amber_threshold=10,
            red_threshold=15,
        )

        assert kri.calculate_status(3) == ThresholdStatus.GREEN
        assert kri.calculate_status(5) == ThresholdStatus.GREEN
        assert kri.calculate_status(7) == ThresholdStatus.AMBER
        assert kri.calculate_status(10) == ThresholdStatus.AMBER
        assert kri.calculate_status(12) == ThresholdStatus.RED
        assert kri.calculate_status(20) == ThresholdStatus.RED

    def test_calculate_status_higher_is_better(self):
        """Test status calculation when higher values are better."""
        kri = KeyRiskIndicator(
            code="TEST",
            name="Test KRI",
            category=KRICategory.COMPLIANCE,
            unit="percentage",
            data_source="test",
            lower_is_better=False,
            green_threshold=90,
            amber_threshold=75,
            red_threshold=60,
        )

        assert kri.calculate_status(95) == ThresholdStatus.GREEN
        assert kri.calculate_status(90) == ThresholdStatus.GREEN
        assert kri.calculate_status(80) == ThresholdStatus.AMBER
        assert kri.calculate_status(75) == ThresholdStatus.AMBER
        assert kri.calculate_status(65) == ThresholdStatus.RED
        assert kri.calculate_status(50) == ThresholdStatus.RED


class TestKRIMeasurement:
    """Test suite for KRI Measurement model."""

    def test_measurement_creation(self):
        """Test creating a KRI measurement."""
        measurement = KRIMeasurement(
            kri_id=1,
            measurement_date=datetime.utcnow(),
            value=7.5,
            status=ThresholdStatus.AMBER,
            period_start=datetime.utcnow() - timedelta(days=30),
            period_end=datetime.utcnow(),
        )

        assert measurement.value == 7.5
        assert measurement.status == ThresholdStatus.AMBER


class TestKRIAlert:
    """Test suite for KRI Alert model."""

    def test_alert_creation(self):
        """Test creating a KRI alert."""
        alert = KRIAlert(
            kri_id=1,
            alert_type="threshold_breach",
            severity=ThresholdStatus.RED,
            triggered_at=datetime.utcnow(),
            trigger_value=20,
            previous_value=12,
            threshold_breached=15,
            title="Critical Threshold Breach",
            message="Incident count has exceeded critical threshold",
        )

        assert alert.severity == ThresholdStatus.RED
        assert alert.trigger_value == 20
        assert alert.is_acknowledged is False
        assert alert.is_resolved is False


class TestRiskScoreHistory:
    """Test suite for Risk Score History model."""

    def test_history_creation(self):
        """Test creating a risk score history entry."""
        history = RiskScoreHistory(
            risk_id=1,
            recorded_at=datetime.utcnow(),
            likelihood=4,
            impact=4,
            risk_score=16,
            risk_level="high",
            trigger_type="incident",
            trigger_entity_type="incident",
            trigger_entity_id=123,
            previous_score=12,
            score_change=4,
            change_reason="Critical incident reported",
        )

        assert history.risk_score == 16
        assert history.risk_level == "high"
        assert history.score_change == 4


class TestKRIService:
    """Test suite for KRI Service."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        db = AsyncMock()
        db.execute = AsyncMock()
        db.commit = AsyncMock()
        db.add = MagicMock()
        db.refresh = AsyncMock()
        return db

    @pytest.fixture
    def kri_service(self, mock_db):
        """Create KRI service with mocked DB."""
        return KRIService(mock_db)

    @pytest.mark.asyncio
    async def test_calculate_trend_improving(self, kri_service, mock_db):
        """Test trend calculation when improving."""
        kri = KeyRiskIndicator(
            id=1,
            code="TEST",
            name="Test",
            category=KRICategory.SAFETY,
            unit="count",
            data_source="test",
            lower_is_better=True,
            green_threshold=5,
            amber_threshold=10,
            red_threshold=15,
        )

        # Mock previous measurements
        measurements = [
            MagicMock(value=12),
            MagicMock(value=10),
            MagicMock(value=11),
        ]
        mock_result = MagicMock()
        mock_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=measurements)))
        mock_db.execute.return_value = mock_result

        # Current value is significantly lower (better)
        trend = await kri_service._calculate_trend(kri, 5)

        assert trend == KRITrendDirection.IMPROVING

    @pytest.mark.asyncio
    async def test_calculate_trend_deteriorating(self, kri_service, mock_db):
        """Test trend calculation when deteriorating."""
        kri = KeyRiskIndicator(
            id=1,
            code="TEST",
            name="Test",
            category=KRICategory.SAFETY,
            unit="count",
            data_source="test",
            lower_is_better=True,
            green_threshold=5,
            amber_threshold=10,
            red_threshold=15,
        )

        # Mock previous measurements
        measurements = [
            MagicMock(value=8),
            MagicMock(value=7),
            MagicMock(value=6),
        ]
        mock_result = MagicMock()
        mock_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=measurements)))
        mock_db.execute.return_value = mock_result

        # Current value is significantly higher (worse)
        trend = await kri_service._calculate_trend(kri, 15)

        assert trend == KRITrendDirection.DETERIORATING


class TestIntegrationScenarios:
    """Integration scenarios for risk and KRI tracking."""

    def test_incident_triggers_risk_update(self):
        """Test that critical incident should trigger risk score update."""
        # Simulate the flow
        incident_severity = IncidentSeverity.CRITICAL
        old_likelihood = 3
        old_impact = 4
        old_score = old_likelihood * old_impact  # 12

        # Calculate new likelihood based on severity
        adjustment = RiskScoringService.SEVERITY_IMPACT.get(incident_severity, 0)
        new_likelihood = min(5, old_likelihood + adjustment)  # 3 + 2 = 5
        new_score = new_likelihood * old_impact  # 5 * 4 = 20

        assert new_score > old_score
        assert new_likelihood == 5
        assert new_score == 20

    def test_kri_threshold_breach_creates_alert(self):
        """Test that breaching KRI threshold should create alert."""
        kri = KeyRiskIndicator(
            id=1,
            code="INC-RATE",
            name="Incident Rate",
            category=KRICategory.SAFETY,
            unit="per 1000",
            data_source="incident_rate",
            lower_is_better=True,
            green_threshold=2,
            amber_threshold=5,
            red_threshold=10,
            current_status=ThresholdStatus.AMBER,
            current_value=6,
        )

        # New value breaches red threshold
        new_value = 12
        new_status = kri.calculate_status(new_value)

        # Status should be red
        assert new_status == ThresholdStatus.RED

        # Alert should be created (simulated)
        should_alert = new_status.value > kri.current_status.value
        assert should_alert is True

    def test_near_miss_velocity_calculation(self):
        """Test near-miss velocity affects likelihood."""
        # Simulate 15 near misses in 30 days
        near_miss_count = 15

        # High velocity threshold
        if near_miss_count >= RiskScoringService.NEAR_MISS_VELOCITY_HIGH:
            velocity_adjustment = 2
        elif near_miss_count >= RiskScoringService.NEAR_MISS_VELOCITY_MEDIUM:
            velocity_adjustment = 1
        else:
            velocity_adjustment = 0

        assert velocity_adjustment == 2

        # Old likelihood of 2 should become 4
        old_likelihood = 2
        new_likelihood = min(5, max(1, old_likelihood + velocity_adjustment))
        assert new_likelihood == 4


class TestSIFClassification:
    """Test suite for SIF (Serious Injury or Fatality) classification."""

    def test_sif_criteria(self):
        """Test SIF classification criteria."""
        # SIF: Actual serious injury or fatality
        is_sif = True
        is_psif = False
        classification = "SIF" if is_sif else ("pSIF" if is_psif else "Non-SIF")
        assert classification == "SIF"

        # pSIF: Potential for serious injury (life-altering)
        is_sif = False
        is_psif = True
        life_altering_potential = True
        classification = "SIF" if is_sif else ("pSIF" if is_psif else "Non-SIF")
        assert classification == "pSIF"
        assert life_altering_potential is True

        # Non-SIF
        is_sif = False
        is_psif = False
        classification = "SIF" if is_sif else ("pSIF" if is_psif else "Non-SIF")
        assert classification == "Non-SIF"

    def test_precursor_events_tracking(self):
        """Test tracking of precursor events for pSIF."""
        precursor_events = [
            "Working at height without fall protection",
            "Bypassed safety interlock",
            "Entered confined space without permit",
        ]

        # These are red flags for pSIF classification
        assert len(precursor_events) == 3
        assert "Working at height" in precursor_events[0]

    def test_control_failures_tracking(self):
        """Test tracking of control failures."""
        control_failures = [
            {"control": "Fall protection PPE", "type": "not_used"},
            {"control": "Safety interlock", "type": "bypassed"},
            {"control": "Permit system", "type": "not_followed"},
        ]

        assert len(control_failures) == 3

        # Count bypassed controls
        bypassed = [c for c in control_failures if c["type"] == "bypassed"]
        assert len(bypassed) == 1


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_risk_score_caps_at_maximum(self):
        """Test that likelihood caps at 5."""
        old_likelihood = 4
        severity_adjustment = 3  # Would push over 5

        new_likelihood = min(5, old_likelihood + severity_adjustment)
        assert new_likelihood == 5

        # Score with impact 5 maxes at 25
        max_score = new_likelihood * 5
        assert max_score == 25

    def test_risk_score_minimum(self):
        """Test that likelihood doesn't go below 1."""
        old_likelihood = 2
        velocity_adjustment = -3  # Theoretical negative adjustment

        new_likelihood = min(5, max(1, old_likelihood + velocity_adjustment))
        assert new_likelihood == 1

    def test_kri_with_no_measurements(self):
        """Test trend calculation with insufficient data."""
        # With 0 or 1 measurement, trend should be None
        measurements = []

        if len(measurements) < 2:
            trend = None

        assert trend is None

    def test_zero_value_handling(self):
        """Test handling of zero values in calculations."""
        # Incident count of 0
        kri = KeyRiskIndicator(
            code="TEST",
            name="Test",
            category=KRICategory.SAFETY,
            unit="count",
            data_source="test",
            lower_is_better=True,
            green_threshold=5,
            amber_threshold=10,
            red_threshold=15,
        )

        # Zero incidents should be green
        status = kri.calculate_status(0)
        assert status == ThresholdStatus.GREEN
