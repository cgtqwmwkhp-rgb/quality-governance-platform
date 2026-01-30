"""
ETL Pipeline Package - Quality Governance Platform
Stage 10: Data Foundation

Contract-driven, idempotent ETL pipeline for governance data migration.
"""

from .config import ETLConfig, EntityType, Environment, get_config
from .contract_probe import ContractProbe, ProbeResult
from .transformers import TransformError, get_transformer
from .validator import ValidationReport, ValidationResult, validate_records
from .pipeline import ETLPipeline, PipelineStats

__version__ = "1.0.0"
__all__ = [
    "ETLConfig",
    "EntityType", 
    "Environment",
    "get_config",
    "ContractProbe",
    "ProbeResult",
    "TransformError",
    "get_transformer",
    "ValidationReport",
    "ValidationResult",
    "validate_records",
    "ETLPipeline",
    "PipelineStats",
]
