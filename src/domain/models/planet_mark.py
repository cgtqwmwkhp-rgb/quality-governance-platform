"""
Planet Mark Carbon Management Models

Planet Mark Business Certification - Carbon footprint measurement and reduction
Aligned with GHG Protocol Corporate Standard

Features:
- Multi-year reporting with historical comparison
- Scope 1, 2, 3 emissions tracking
- All 15 GHG Protocol Scope 3 categories
- Data quality scoring (0-16 scale)
- SMART improvement action tracking
- Certification lifecycle management
- ISO 14001 environmental cross-mapping
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.database import Base


# ============ Enums ============


class EmissionScope(str, Enum):
    SCOPE_1 = "scope_1"  # Direct emissions
    SCOPE_2 = "scope_2"  # Indirect - purchased energy
    SCOPE_3 = "scope_3"  # Value chain


class Scope3Category(str, Enum):
    """GHG Protocol Scope 3 Categories (15 total)"""

    CAT_1 = "cat_1"  # Purchased goods and services
    CAT_2 = "cat_2"  # Capital goods
    CAT_3 = "cat_3"  # Fuel and energy-related activities
    CAT_4 = "cat_4"  # Upstream transportation and distribution
    CAT_5 = "cat_5"  # Waste generated in operations
    CAT_6 = "cat_6"  # Business travel
    CAT_7 = "cat_7"  # Employee commuting
    CAT_8 = "cat_8"  # Upstream leased assets
    CAT_9 = "cat_9"  # Downstream transportation and distribution
    CAT_10 = "cat_10"  # Processing of sold products
    CAT_11 = "cat_11"  # Use of sold products
    CAT_12 = "cat_12"  # End-of-life treatment of sold products
    CAT_13 = "cat_13"  # Downstream leased assets
    CAT_14 = "cat_14"  # Franchises
    CAT_15 = "cat_15"  # Investments


class DataQualityLevel(str, Enum):
    ACTUAL = "actual"  # Metered/verified data (4 points)
    CALCULATED = "calculated"  # Based on actual activity data (3 points)
    ESTIMATED = "estimated"  # Estimates from proxy data (2 points)
    EXTRAPOLATED = "extrapolated"  # Rough estimates (1 point)
    MISSING = "missing"  # No data (0 points)


# ============ Core Models ============


class CarbonReportingYear(Base):
    """Annual Carbon Reporting Period"""

    __tablename__ = "carbon_reporting_year"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Reporting period
    year_label: Mapped[str] = mapped_column(String(20), nullable=False)  # "YE2023", "YE2024"
    year_number: Mapped[int] = mapped_column(Integer, nullable=False)  # 1, 2, 3...
    period_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # Organization context
    organization_name: Mapped[str] = mapped_column(String(255), default="Plantexpand Limited")
    reporting_boundary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sites_included: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)

    # Headcount for per-employee calculations
    average_fte: Mapped[float] = mapped_column(Float, nullable=False, default=0)

    # Baseline comparison
    is_baseline_year: Mapped[bool] = mapped_column(Boolean, default=False)
    baseline_year_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("carbon_reporting_year.id"), nullable=True
    )

    # Total emissions summary
    scope_1_total: Mapped[float] = mapped_column(Float, default=0)  # tCO₂e
    scope_2_location: Mapped[float] = mapped_column(Float, default=0)  # Location-based
    scope_2_market: Mapped[float] = mapped_column(Float, default=0)  # Market-based
    scope_3_total: Mapped[float] = mapped_column(Float, default=0)
    total_emissions: Mapped[float] = mapped_column(Float, default=0)  # Market-based total
    emissions_per_fte: Mapped[float] = mapped_column(Float, default=0)

    # Data quality scores (0-16)
    scope_1_data_quality: Mapped[int] = mapped_column(Integer, default=0)
    scope_2_data_quality: Mapped[int] = mapped_column(Integer, default=0)
    scope_3_data_quality: Mapped[int] = mapped_column(Integer, default=0)
    overall_data_quality: Mapped[int] = mapped_column(Integer, default=0)

    # Certification status
    certification_status: Mapped[str] = mapped_column(String(30), default="draft")
    # draft, submitted, certified, expired
    certificate_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    certification_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    expiry_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Planet Mark assessor
    assessor_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    assessment_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Improvement targets
    reduction_target_percent: Mapped[float] = mapped_column(Float, default=5.0)  # 5% default
    target_emissions_per_fte: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    emission_sources = relationship("EmissionSource", back_populates="reporting_year")
    improvement_actions = relationship("ImprovementAction", back_populates="reporting_year")
    evidence_documents = relationship("CarbonEvidence", back_populates="reporting_year")


class EmissionSource(Base):
    """Individual Emission Source Entry"""

    __tablename__ = "emission_source"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reporting_year_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("carbon_reporting_year.id", ondelete="CASCADE"), nullable=False
    )

    # Source identification
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_category: Mapped[str] = mapped_column(String(100), nullable=False)  # Fleet, Buildings, etc.

    # Scope classification
    scope: Mapped[str] = mapped_column(String(20), nullable=False)  # scope_1, scope_2, scope_3
    scope_3_category: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # cat_1 to cat_15

    # Activity data
    activity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    # e.g., "diesel_litres", "natural_gas_kwh", "electricity_kwh", "waste_tonnes"
    activity_value: Mapped[float] = mapped_column(Float, nullable=False)
    activity_unit: Mapped[str] = mapped_column(String(50), nullable=False)

    # Emission factors
    emission_factor: Mapped[float] = mapped_column(Float, nullable=False)
    emission_factor_unit: Mapped[str] = mapped_column(String(100), nullable=False)
    emission_factor_source: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # e.g., "DEFRA 2023", "IEA 2023"

    # Calculated emissions
    co2e_tonnes: Mapped[float] = mapped_column(Float, nullable=False)
    co2_tonnes: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ch4_tonnes: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    n2o_tonnes: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Data quality
    data_quality_level: Mapped[str] = mapped_column(String(30), nullable=False, default="estimated")
    data_quality_score: Mapped[int] = mapped_column(Integer, default=2)  # 0-4 per source
    data_source: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    data_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Verification
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verified_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    verified_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Breakdown (for detailed sources like fleet)
    sub_sources: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    # e.g., [{"vehicle": "LD24VLP", "litres": 5000, "co2e": 12.5}, ...]

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    reporting_year = relationship("CarbonReportingYear", back_populates="emission_sources")


class Scope3CategoryData(Base):
    """Detailed Scope 3 Category Data"""

    __tablename__ = "scope3_category_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reporting_year_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("carbon_reporting_year.id", ondelete="CASCADE"), nullable=False
    )

    # GHG Protocol Category
    category_number: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-15
    category_name: Mapped[str] = mapped_column(String(100), nullable=False)
    category_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Measurement status
    is_relevant: Mapped[bool] = mapped_column(Boolean, default=True)
    is_measured: Mapped[bool] = mapped_column(Boolean, default=False)
    exclusion_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Emissions
    total_co2e: Mapped[float] = mapped_column(Float, default=0)
    percentage_of_scope3: Mapped[float] = mapped_column(Float, default=0)

    # Data quality
    data_quality_score: Mapped[int] = mapped_column(Integer, default=0)
    calculation_method: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    # spend-based, activity-based, supplier-specific, hybrid

    # Data sources
    data_sources: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    supplier_data_coverage: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # % of spend

    # Improvement recommendations
    improvement_priority: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    improvement_actions: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ImprovementAction(Base):
    """SMART Improvement Actions for Carbon Reduction"""

    __tablename__ = "carbon_improvement_action"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reporting_year_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("carbon_reporting_year.id", ondelete="CASCADE"), nullable=False
    )

    # Action identification
    action_id: Mapped[str] = mapped_column(String(20), nullable=False)  # "ACT-001"
    action_title: Mapped[str] = mapped_column(String(255), nullable=False)

    # SMART criteria
    specific: Mapped[str] = mapped_column(Text, nullable=False)  # What exactly will be done
    measurable: Mapped[str] = mapped_column(Text, nullable=False)  # How success is measured
    achievable_owner: Mapped[str] = mapped_column(String(255), nullable=False)  # Who is responsible
    relevant: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Why this matters
    time_bound: Mapped[datetime] = mapped_column(DateTime, nullable=False)  # Deadline

    # Scheduling
    scheduled_month: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # "Jul 25"
    quarter: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)  # "Q1", "Q2"

    # Target scope
    target_scope: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # scope_1, scope_2, scope_3
    target_source: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # "Fleet", "Gas"
    expected_reduction_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    expected_reduction_tco2e: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Progress tracking
    status: Mapped[str] = mapped_column(String(30), default="planned")
    # planned, in_progress, completed, delayed, cancelled
    progress_percent: Mapped[int] = mapped_column(Integer, default=0)
    actual_completion_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Evidence
    evidence_required: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    evidence_provided: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)

    # Results
    actual_reduction_achieved: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    lessons_learned: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Notifications
    reminder_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    overdue_notified: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    reporting_year = relationship("CarbonReportingYear", back_populates="improvement_actions")


class DataQualityAssessment(Base):
    """Data Quality Assessment and Recommendations"""

    __tablename__ = "data_quality_assessment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reporting_year_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("carbon_reporting_year.id", ondelete="CASCADE"), nullable=False
    )

    # Assessment scope
    scope: Mapped[str] = mapped_column(String(20), nullable=False)  # scope_1, scope_2, scope_3

    # Scoring breakdown (4 criteria, 4 points each = 16 max)
    completeness_score: Mapped[int] = mapped_column(Integer, default=0)  # 0-4
    accuracy_score: Mapped[int] = mapped_column(Integer, default=0)  # 0-4
    consistency_score: Mapped[int] = mapped_column(Integer, default=0)  # 0-4
    transparency_score: Mapped[int] = mapped_column(Integer, default=0)  # 0-4
    total_score: Mapped[int] = mapped_column(Integer, default=0)  # 0-16

    # Assessment details
    completeness_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    accuracy_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    consistency_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    transparency_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Data sources analyzed
    sources_assessed: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    actual_data_percent: Mapped[float] = mapped_column(Float, default=0)  # % from actual reads
    estimated_data_percent: Mapped[float] = mapped_column(Float, default=0)  # % estimated

    # Recommendations
    improvement_recommendations: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    priority_actions: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    target_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    assessed_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    assessed_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CarbonEvidence(Base):
    """Evidence Documents for Certification"""

    __tablename__ = "carbon_evidence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reporting_year_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("carbon_reporting_year.id", ondelete="CASCADE"), nullable=False
    )

    # Document details
    document_name: Mapped[str] = mapped_column(String(255), nullable=False)
    document_type: Mapped[str] = mapped_column(String(100), nullable=False)
    # utility_bill, fuel_card_report, waste_manifest, travel_expense, supplier_invoice, certificate

    # Reference
    evidence_category: Mapped[str] = mapped_column(String(50), nullable=False)
    # scope_1, scope_2, scope_3, improvement_action, certification
    linked_source_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    linked_action_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # File details
    file_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    file_size_kb: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    mime_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Metadata
    period_covered: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    value_documented: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    unit: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Verification
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verified_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    verified_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Notes
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    uploaded_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    reporting_year = relationship("CarbonReportingYear", back_populates="evidence_documents")


class FleetEmissionRecord(Base):
    """Detailed Fleet Fuel Consumption for Scope 1"""

    __tablename__ = "fleet_emission_record"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reporting_year_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("carbon_reporting_year.id", ondelete="CASCADE"), nullable=False
    )

    # Vehicle identification
    vehicle_registration: Mapped[str] = mapped_column(String(20), nullable=False)
    vehicle_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # Van, Car, HGV
    fuel_type: Mapped[str] = mapped_column(String(50), nullable=False)  # Diesel, Petrol, Electric, Hybrid

    # Monthly fuel consumption
    month: Mapped[str] = mapped_column(String(10), nullable=False)  # "2025-07"
    fuel_litres: Mapped[float] = mapped_column(Float, nullable=False)
    fuel_cost: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Mileage (if available from telematics)
    mileage: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    litres_per_100km: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Emissions
    co2e_kg: Mapped[float] = mapped_column(Float, nullable=False)

    # Data source
    data_source: Mapped[str] = mapped_column(String(50), nullable=False)
    # fuel_card, telematics, manual_entry
    fuel_card_provider: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Driver (for eco-driving tracking)
    driver_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class UtilityMeterReading(Base):
    """Utility Meter Readings for Scope 1 & 2"""

    __tablename__ = "utility_meter_reading"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reporting_year_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("carbon_reporting_year.id", ondelete="CASCADE"), nullable=False
    )

    # Meter identification
    meter_reference: Mapped[str] = mapped_column(String(100), nullable=False)
    utility_type: Mapped[str] = mapped_column(String(50), nullable=False)  # electricity, natural_gas
    site_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Reading details
    reading_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    reading_value: Mapped[float] = mapped_column(Float, nullable=False)
    reading_unit: Mapped[str] = mapped_column(String(20), nullable=False)  # kWh, m³

    # Period consumption
    period_start: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    period_end: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    consumption: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Data quality
    reading_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # actual_read, estimated, smart_meter
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)

    # Supplier info (for market-based Scope 2)
    supplier_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    tariff_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_renewable: Mapped[bool] = mapped_column(Boolean, default=False)
    rego_certificate: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SupplierEmissionData(Base):
    """Supplier-Specific Emission Data for Scope 3"""

    __tablename__ = "supplier_emission_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reporting_year_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("carbon_reporting_year.id", ondelete="CASCADE"), nullable=False
    )

    # Supplier identification
    supplier_name: Mapped[str] = mapped_column(String(255), nullable=False)
    supplier_category: Mapped[str] = mapped_column(String(100), nullable=False)
    scope3_category: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-15

    # Spend data
    annual_spend: Mapped[float] = mapped_column(Float, nullable=False)
    spend_currency: Mapped[str] = mapped_column(String(10), default="GBP")

    # Emission data (if supplier provides)
    supplier_reported_co2e: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    emission_intensity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # tCO2e/£

    # Calculated emissions (if using spend-based)
    spend_based_co2e: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    emission_factor_used: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Data quality
    data_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # supplier_specific, average_sector, spend_based
    has_responded_to_survey: Mapped[bool] = mapped_column(Boolean, default=False)

    # Engagement
    engagement_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    last_contact_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ISO14001CrossMapping(Base):
    """Cross-mapping between Planet Mark and ISO 14001"""

    __tablename__ = "planet_mark_iso14001_mapping"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Planet Mark reference
    pm_requirement: Mapped[str] = mapped_column(String(255), nullable=False)
    pm_category: Mapped[str] = mapped_column(String(100), nullable=False)
    # emissions_measurement, improvement_plan, data_quality, certification

    # ISO 14001 reference
    iso14001_clause: Mapped[str] = mapped_column(String(20), nullable=False)
    iso14001_title: Mapped[str] = mapped_column(String(255), nullable=False)

    # Mapping details
    mapping_type: Mapped[str] = mapped_column(String(20), nullable=False)  # direct, partial, related
    alignment_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Evidence sharing
    shared_evidence_types: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
