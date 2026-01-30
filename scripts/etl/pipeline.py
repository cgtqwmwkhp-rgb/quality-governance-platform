"""
ETL Pipeline - Quality Governance Platform
Stage 10: Data Foundation

Main orchestration for ETL operations with idempotent imports,
audit trail generation, and contract validation.
"""

import csv
import hashlib
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import EntityType, ETLConfig, get_config
from .contract_probe import ContractProbe, run_contract_probe
from .transformers import TransformError, get_transformer, sanitize_text
from .validator import ValidationReport, validate_records

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class AuditRecord:
    """Audit trail record."""

    timestamp: datetime
    run_id: str
    action: str
    entity_type: str
    row_number: int
    source_hash: str
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "run_id": self.run_id,
            "action": self.action,
            "entity_type": self.entity_type,
            "row_number": self.row_number,
            "source_hash": self.source_hash,
            "details": self.details,
        }


@dataclass
class PipelineStats:
    """Pipeline execution statistics."""

    entity_type: str
    run_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    total_records: int = 0
    valid_records: int = 0
    invalid_records: int = 0
    imported_records: int = 0
    skipped_records: int = 0
    failed_records: int = 0

    def to_dict(self) -> Dict[str, Any]:
        duration = 0.0
        if self.end_time:
            duration = (self.end_time - self.start_time).total_seconds()

        return {
            "entity_type": self.entity_type,
            "run_id": self.run_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": round(duration, 2),
            "total_records": self.total_records,
            "valid_records": self.valid_records,
            "invalid_records": self.invalid_records,
            "imported_records": self.imported_records,
            "skipped_records": self.skipped_records,
            "failed_records": self.failed_records,
        }


class ETLPipeline:
    """
    Main ETL pipeline orchestrator.

    Supports:
    - Contract validation before operations
    - Validate-only mode
    - Dry-run mode
    - Full import with idempotency
    """

    def __init__(self, config: ETLConfig):
        self.config = config
        self.run_id = str(uuid.uuid4())[:8]
        self.audit_records: List[AuditRecord] = []

        # Ensure output directory exists
        self.config.output_directory.mkdir(parents=True, exist_ok=True)

    def _compute_hash(self, data: Dict[str, Any]) -> str:
        """Compute SHA-256 hash of record."""
        content = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _add_audit(
        self,
        action: str,
        entity_type: EntityType,
        row_number: int,
        source_data: Dict[str, Any],
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add audit record."""
        self.audit_records.append(
            AuditRecord(
                timestamp=datetime.utcnow(),
                run_id=self.run_id,
                action=action,
                entity_type=entity_type.value,
                row_number=row_number,
                source_hash=self._compute_hash(source_data),
                details=details or {},
            )
        )

    def read_csv(self, file_path: Path) -> List[Dict[str, Any]]:
        """Read CSV file."""
        records = []

        with open(file_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                records.append(dict(row))

        logger.info(f"Read {len(records)} records from {file_path.name}")
        return records

    def transform_record(
        self,
        source_row: Dict[str, Any],
        entity_type: EntityType,
    ) -> Dict[str, Any]:
        """Transform source record to API schema."""
        mappings = self.config.get_mappings(entity_type)
        result = {}

        for mapping in mappings:
            source_value = source_row.get(mapping.source_column)

            if source_value is None or str(source_value).strip() == "":
                if mapping.default_value is not None:
                    result[mapping.target_field] = mapping.default_value
                continue

            if mapping.transformer:
                transformer = get_transformer(mapping.transformer)
                result[mapping.target_field] = transformer(source_value, mapping.source_column)
            else:
                result[mapping.target_field] = sanitize_text(source_value)

        return result

    def validate_contracts(self) -> bool:
        """Validate API contracts before import."""
        logger.info(f"Validating contracts for {self.config.environment.value}")

        probe_result = run_contract_probe(self.config.environment.value)

        # Save probe result
        probe_path = self.config.output_directory / f"contract_probe_{self.run_id}.json"
        with open(probe_path, "w") as f:
            json.dump(probe_result.to_dict(), f, indent=2)

        logger.info(f"Contract probe saved: {probe_path}")

        if not probe_result.all_passed:
            logger.error("Contract validation FAILED")
            for endpoint in probe_result.endpoints:
                if not endpoint.success:
                    logger.error(f"  {endpoint.endpoint}: {endpoint.errors}")
            return False

        logger.info("Contract validation PASSED")
        return True

    def run_validate_only(
        self,
        source_file: Path,
        entity_type: EntityType,
    ) -> ValidationReport:
        """Run validation only, no import."""
        logger.info(f"Running validate-only for {entity_type.value}")

        records = self.read_csv(source_file)
        mappings = self.config.get_mappings(entity_type)

        report = validate_records(
            records=records,
            mappings=mappings,
            entity_type=entity_type,
            source_file=source_file.name,
        )

        # Save validation report
        report_path = self.config.output_directory / f"validation_{entity_type.value}_{self.run_id}.json"
        with open(report_path, "w") as f:
            json.dump(report.to_dict(), f, indent=2)

        logger.info(f"Validation report saved: {report_path}")
        logger.info(f"Results: {report.valid_records} valid, {report.invalid_records} invalid")

        return report

    def run_dry_run(
        self,
        source_file: Path,
        entity_type: EntityType,
    ) -> PipelineStats:
        """Run validation and transformation, no API calls."""
        logger.info(f"Running dry-run for {entity_type.value}")

        stats = PipelineStats(
            entity_type=entity_type.value,
            run_id=self.run_id,
            start_time=datetime.utcnow(),
        )

        records = self.read_csv(source_file)
        stats.total_records = len(records)

        mappings = self.config.get_mappings(entity_type)
        report = validate_records(records, mappings, entity_type, source_file.name)

        stats.valid_records = report.valid_records
        stats.invalid_records = report.invalid_records

        # Transform valid records
        for result in report.results:
            if result.is_valid:
                try:
                    transformed = self.transform_record(result.source_data, entity_type)
                    self._add_audit(
                        "dry_run_transform",
                        entity_type,
                        result.row_number,
                        result.source_data,
                        {"transformed_keys": list(transformed.keys())},
                    )
                except TransformError as e:
                    stats.failed_records += 1
                    self._add_audit(
                        "transform_error",
                        entity_type,
                        result.row_number,
                        result.source_data,
                        {"error": str(e)},
                    )

        stats.end_time = datetime.utcnow()

        # Save stats and audit
        self._save_outputs(stats)

        return stats

    def run_import(
        self,
        source_file: Path,
        entity_type: EntityType,
        batch_size: int = 50,
    ) -> PipelineStats:
        """
        Run full import with API calls.

        Idempotency: Uses reference_number (mapped from external_ref).
        - 201 Created: Record imported
        - 409 Conflict: Record already exists (skip)
        - Other: Error (tracked in failed_records)
        """
        from .api_client import ETLAPIClient, ImportResult

        logger.info(f"Running import for {entity_type.value}")
        logger.info(f"Target: {self.config.api_config.base_url}")

        stats = PipelineStats(
            entity_type=entity_type.value,
            run_id=self.run_id,
            start_time=datetime.utcnow(),
        )

        # Initialize API client
        api_client = ETLAPIClient(
            base_url=self.config.api_config.base_url,
            auth_token=self.config.api_config.auth_token,
            timeout_seconds=self.config.api_config.timeout_seconds,
            max_retries=self.config.api_config.max_retries,
        )

        # Read and validate
        records = self.read_csv(source_file)
        stats.total_records = len(records)

        mappings = self.config.get_mappings(entity_type)
        report = validate_records(records, mappings, entity_type, source_file.name)

        stats.valid_records = report.valid_records
        stats.invalid_records = report.invalid_records

        # Import valid records
        for i, result in enumerate(report.results):
            if not result.is_valid:
                stats.skipped_records += 1
                self._add_audit(
                    "import_skipped_validation",
                    entity_type,
                    result.row_number,
                    result.source_data,
                    {"errors": result.errors},
                )
                continue

            try:
                # Transform record
                transformed = self.transform_record(result.source_data, entity_type)

                # Map external_ref to reference_number for API
                if "external_ref" in transformed:
                    transformed["reference_number"] = transformed.pop("external_ref")

                # Add required fields that may be missing
                if entity_type == EntityType.INCIDENT:
                    # Ensure incident_date is present
                    if "incident_date" not in transformed:
                        from datetime import datetime as dt

                        transformed["incident_date"] = dt.utcnow().isoformat()
                    import_result = api_client.create_incident(transformed)
                elif entity_type == EntityType.COMPLAINT:
                    import_result = api_client.create_complaint(transformed)
                elif entity_type == EntityType.RTA:
                    import_result = api_client.create_rta(transformed)
                else:
                    raise ValueError(f"Unknown entity type: {entity_type}")

                # Track result
                if import_result.result == ImportResult.CREATED:
                    stats.imported_records += 1
                    self._add_audit(
                        "import_created",
                        entity_type,
                        result.row_number,
                        result.source_data,
                        {
                            "reference_number": import_result.reference_number,
                            "api_id": import_result.api_id,
                            "response_time_ms": import_result.response_time_ms,
                        },
                    )
                elif import_result.result == ImportResult.SKIPPED_EXISTS:
                    stats.skipped_records += 1
                    self._add_audit(
                        "import_skipped_exists",
                        entity_type,
                        result.row_number,
                        result.source_data,
                        {
                            "reference_number": import_result.reference_number,
                            "reason": "409 CONFLICT - record already exists",
                        },
                    )
                else:
                    stats.failed_records += 1
                    self._add_audit(
                        "import_failed",
                        entity_type,
                        result.row_number,
                        result.source_data,
                        {
                            "reference_number": import_result.reference_number,
                            "status_code": import_result.status_code,
                            "error": import_result.error_message,
                        },
                    )

            except Exception as e:
                stats.failed_records += 1
                self._add_audit(
                    "import_error",
                    entity_type,
                    result.row_number,
                    result.source_data,
                    {"error": str(e)},
                )
                logger.error(f"Import error for row {result.row_number}: {e}")

            # Log progress for large batches
            if (i + 1) % batch_size == 0:
                logger.info(f"Progress: {i + 1}/{stats.total_records} records processed")

        stats.end_time = datetime.utcnow()

        # Save outputs including import summary
        self._save_outputs(stats)

        # Save import summary
        summary_path = self.config.output_directory / f"import_summary_{self.run_id}.json"
        with open(summary_path, "w") as f:
            json.dump(
                {
                    "run_id": self.run_id,
                    "entity_type": entity_type.value,
                    "stats": stats.to_dict(),
                    "api_summary": api_client.get_import_summary(),
                    "import_records": api_client.get_import_records(),
                },
                f,
                indent=2,
            )
        logger.info(f"Import summary saved: {summary_path}")

        # Log summary
        logger.info(
            f"Import complete: {stats.imported_records} created, "
            f"{stats.skipped_records} skipped, {stats.failed_records} failed"
        )

        return stats

    def _save_outputs(self, stats: PipelineStats) -> None:
        """Save stats and audit trail."""
        # Stats
        stats_path = self.config.output_directory / f"stats_{stats.entity_type}_{self.run_id}.json"
        with open(stats_path, "w") as f:
            json.dump(stats.to_dict(), f, indent=2)

        # Audit trail
        audit_path = self.config.output_directory / f"audit_{self.run_id}.json"
        with open(audit_path, "w") as f:
            json.dump([r.to_dict() for r in self.audit_records], f, indent=2)

        logger.info(f"Stats saved: {stats_path}")
        logger.info(f"Audit trail saved: {audit_path}")


def main():
    """CLI entry point."""
    import argparse
    import os

    parser = argparse.ArgumentParser(description="Quality Governance Platform ETL")
    parser.add_argument("--environment", choices=["development", "staging", "production"], default="staging")
    parser.add_argument("--validate-only", action="store_true", help="Only validate, no transforms")
    parser.add_argument("--dry-run", action="store_true", help="Validate and transform, no API calls")
    parser.add_argument("--import", dest="do_import", action="store_true", help="Full import with API calls")
    parser.add_argument("--probe-contracts", action="store_true", help="Only probe API contracts")
    parser.add_argument("--source", type=str, help="Source CSV file")
    parser.add_argument("--entity-type", choices=["incident", "complaint", "rta"], help="Entity type")
    parser.add_argument("--batch-size", type=int, default=50, help="Batch size for progress logging")

    args = parser.parse_args()

    # Safety check: --import requires explicit staging (not production)
    if args.do_import and args.environment == "production":
        print("ERROR: --import is not allowed for production environment")
        print("Use staging environment for ETL imports")
        return 1

    config = get_config(args.environment)
    config.validate_only = args.validate_only
    config.dry_run = args.dry_run

    # Get auth token from environment
    config.api_config.auth_token = os.getenv("QGP_API_TOKEN")

    pipeline = ETLPipeline(config)

    if args.probe_contracts:
        success = pipeline.validate_contracts()
        return 0 if success else 1

    if args.source and args.entity_type:
        entity_type = EntityType(args.entity_type)
        source_path = Path(args.source)

        if args.validate_only:
            report = pipeline.run_validate_only(source_path, entity_type)
            return 0 if report.invalid_records == 0 else 1
        elif args.dry_run:
            stats = pipeline.run_dry_run(source_path, entity_type)
            return 0 if stats.failed_records == 0 else 1
        elif args.do_import:
            # Require auth token for import
            if not config.api_config.auth_token:
                print("ERROR: QGP_API_TOKEN environment variable required for import")
                return 1
            stats = pipeline.run_import(source_path, entity_type, args.batch_size)
            return 0 if stats.failed_records == 0 else 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
