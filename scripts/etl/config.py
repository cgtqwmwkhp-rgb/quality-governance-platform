"""
ETL Configuration - Quality Governance Platform
Stage 10: Data Foundation

Environment-aware configuration with field mappings for all entity types.
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional
import os


class Environment(Enum):
    """Deployment environments."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class EntityType(Enum):
    """Governance entity types."""
    INCIDENT = "incident"
    COMPLAINT = "complaint"
    RTA = "rta"


@dataclass
class APIConfig:
    """API connection configuration."""
    base_url: str
    api_version: str = "v1"
    timeout_seconds: int = 30
    max_retries: int = 3
    auth_token: Optional[str] = None

    @property
    def incidents_endpoint(self) -> str:
        return f"{self.base_url}/api/{self.api_version}/incidents"

    @property
    def complaints_endpoint(self) -> str:
        return f"{self.base_url}/api/{self.api_version}/complaints/"

    @property
    def rtas_endpoint(self) -> str:
        return f"{self.base_url}/api/{self.api_version}/rtas/"


@dataclass
class FieldMapping:
    """Maps source column to target API field."""
    source_column: str
    target_field: str
    transformer: Optional[str] = None
    required: bool = False
    default_value: Optional[str] = None


# Field mappings based on actual OpenAPI contract
INCIDENT_MAPPINGS = [
    FieldMapping("external_ref", "external_ref", required=True),
    FieldMapping("title", "title", required=True),
    FieldMapping("description", "description"),
    FieldMapping("incident_type", "incident_type", transformer="map_incident_type"),
    FieldMapping("severity", "severity", transformer="map_severity"),
    FieldMapping("status", "status", transformer="map_status", default_value="reported"),
    FieldMapping("incident_date", "incident_date", transformer="parse_date", required=True),
    FieldMapping("location", "location"),
]

COMPLAINT_MAPPINGS = [
    FieldMapping("external_ref", "external_ref", required=True),
    FieldMapping("title", "title", required=True),
    FieldMapping("description", "description", required=True),
    FieldMapping("complainant_name", "complainant_name", required=True),
    FieldMapping("received_date", "received_date", transformer="parse_date", required=True),
    FieldMapping("status", "status", transformer="map_complaint_status", default_value="received"),
]

RTA_MAPPINGS = [
    FieldMapping("external_ref", "external_ref", required=True),
    FieldMapping("title", "title", required=True),
    FieldMapping("problem_statement", "problem_statement", required=True),
    FieldMapping("root_cause", "root_cause"),
    FieldMapping("corrective_actions", "corrective_actions"),
    FieldMapping("status", "status", transformer="map_rta_status", default_value="draft"),
]


ENVIRONMENT_CONFIGS = {
    Environment.DEVELOPMENT: APIConfig(
        base_url="http://localhost:8001",
        timeout_seconds=10,
    ),
    Environment.STAGING: APIConfig(
        base_url="https://qgp-staging.icytree-89d41650.uksouth.azurecontainerapps.io",
        timeout_seconds=30,
    ),
    Environment.PRODUCTION: APIConfig(
        base_url="https://qgp-prod.icytree-89d41650.uksouth.azurecontainerapps.io",
        timeout_seconds=60,
        max_retries=5,
    ),
}


@dataclass
class ETLConfig:
    """Master ETL configuration."""
    environment: Environment
    api_config: APIConfig
    source_directory: Path
    output_directory: Path
    batch_size: int = 50
    dry_run: bool = False
    validate_only: bool = False
    
    # Entity field mappings
    incident_mappings: List[FieldMapping] = field(default_factory=lambda: INCIDENT_MAPPINGS)
    complaint_mappings: List[FieldMapping] = field(default_factory=lambda: COMPLAINT_MAPPINGS)
    rta_mappings: List[FieldMapping] = field(default_factory=lambda: RTA_MAPPINGS)

    def get_mappings(self, entity_type: EntityType) -> List[FieldMapping]:
        """Get field mappings for entity type."""
        mapping_map = {
            EntityType.INCIDENT: self.incident_mappings,
            EntityType.COMPLAINT: self.complaint_mappings,
            EntityType.RTA: self.rta_mappings,
        }
        return mapping_map.get(entity_type, [])


def get_config(env_name: Optional[str] = None) -> ETLConfig:
    """Get ETL configuration for environment."""
    env_str = env_name or os.getenv("ETL_ENVIRONMENT", "development")

    try:
        environment = Environment(env_str.lower())
    except ValueError:
        raise ValueError(f"Invalid environment: {env_str}")

    api_config = ENVIRONMENT_CONFIGS[environment]
    api_config.auth_token = os.getenv("QGP_API_TOKEN")

    base_path = Path(__file__).parent.parent.parent

    return ETLConfig(
        environment=environment,
        api_config=api_config,
        source_directory=base_path / "data" / "etl_source",
        output_directory=base_path / "data" / "etl_output",
    )
