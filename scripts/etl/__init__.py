"""
ETL Pipeline Package - Quality Governance Platform
Stage 10: Data Foundation

Contract-driven, idempotent ETL pipeline for governance data migration.
"""

from .api_client import ETLAPIClient, ImportRecord, ImportResult
from .config import EntityType, Environment, ETLConfig, get_config
from .contract_probe import ContractProbe, ContractProbeResult, EnforcementMode, ProbeOutcome, run_contract_probe
from .pipeline import ETLPipeline, PipelineStats
from .transformers import TransformError, get_transformer
from .validator import ValidationReport, ValidationResult, validate_records

__version__ = "1.0.0"
__all__ = [
    # Config
    "ETLConfig",
    "EntityType",
    "Environment",
    "get_config",
    # Contract Probe
    "ContractProbe",
    "ContractProbeResult",
    "EnforcementMode",
    "ProbeOutcome",
    "run_contract_probe",
    # Transformers
    "TransformError",
    "get_transformer",
    # Validator
    "ValidationReport",
    "ValidationResult",
    "validate_records",
    # Pipeline
    "ETLPipeline",
    "PipelineStats",
    # API Client
    "ETLAPIClient",
    "ImportRecord",
    "ImportResult",
]
