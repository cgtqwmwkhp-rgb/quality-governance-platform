"""
Data Validator - Quality Governance Platform
Stage 10: Data Foundation

Validates records against schema and business rules.
Generates structured validation reports.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import re

from .config import FieldMapping, EntityType


class ValidationSeverity(Enum):
    """Validation issue severity."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationIssue:
    """Single validation issue."""
    severity: ValidationSeverity
    field: str
    message: str
    value: Any = None
    row_number: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "severity": self.severity.value,
            "field": self.field,
            "message": self.message,
            "value": str(self.value) if self.value else None,
            "row_number": self.row_number,
        }


@dataclass
class ValidationResult:
    """Validation result for a single record."""
    is_valid: bool
    row_number: int
    issues: List[ValidationIssue] = field(default_factory=list)
    source_data: Optional[Dict[str, Any]] = None

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == ValidationSeverity.ERROR)

    def add_error(self, field_name: str, message: str, value: Any = None) -> None:
        self.issues.append(ValidationIssue(
            severity=ValidationSeverity.ERROR,
            field=field_name,
            message=message,
            value=value,
            row_number=self.row_number,
        ))
        self.is_valid = False

    def add_warning(self, field_name: str, message: str, value: Any = None) -> None:
        self.issues.append(ValidationIssue(
            severity=ValidationSeverity.WARNING,
            field=field_name,
            message=message,
            value=value,
            row_number=self.row_number,
        ))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "row_number": self.row_number,
            "error_count": self.error_count,
            "issues": [i.to_dict() for i in self.issues],
        }


@dataclass
class ValidationReport:
    """Complete validation report."""
    entity_type: str
    source_file: str
    timestamp: datetime
    total_records: int
    valid_records: int
    invalid_records: int
    results: List[ValidationResult] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        if self.total_records == 0:
            return 0.0
        return (self.valid_records / self.total_records) * 100

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_type": self.entity_type,
            "source_file": self.source_file,
            "timestamp": self.timestamp.isoformat(),
            "summary": {
                "total_records": self.total_records,
                "valid_records": self.valid_records,
                "invalid_records": self.invalid_records,
                "success_rate": f"{self.success_rate:.1f}%",
            },
            "results": [r.to_dict() for r in self.results if not r.is_valid],
        }


def validate_record(
    record: Dict[str, Any],
    mappings: List[FieldMapping],
    row_number: int,
) -> ValidationResult:
    """Validate a single record against field mappings."""
    result = ValidationResult(
        is_valid=True,
        row_number=row_number,
        source_data=record,
    )

    # Check required fields
    for mapping in mappings:
        value = record.get(mapping.source_column)

        if mapping.required and (value is None or str(value).strip() == ""):
            result.add_error(
                mapping.source_column,
                "Required field is missing or empty",
                value,
            )

    # Validate date formats
    date_fields = ["incident_date", "received_date", "created_at"]
    for field_name in date_fields:
        if field_name in record:
            value = record[field_name]
            if value and not _is_valid_date(str(value)):
                result.add_warning(field_name, "Invalid date format", value)

    # Validate text lengths
    if "title" in record:
        title = record["title"]
        if title and len(str(title)) > 300:
            result.add_warning("title", "Title exceeds 300 characters", len(str(title)))

    return result


def validate_records(
    records: List[Dict[str, Any]],
    mappings: List[FieldMapping],
    entity_type: EntityType,
    source_file: str,
) -> ValidationReport:
    """Validate all records and generate report."""
    results = []
    valid_count = 0
    invalid_count = 0

    for i, record in enumerate(records):
        result = validate_record(record, mappings, row_number=i + 1)
        results.append(result)

        if result.is_valid:
            valid_count += 1
        else:
            invalid_count += 1

    return ValidationReport(
        entity_type=entity_type.value,
        source_file=source_file,
        timestamp=datetime.utcnow(),
        total_records=len(records),
        valid_records=valid_count,
        invalid_records=invalid_count,
        results=results,
    )


def _is_valid_date(value: str) -> bool:
    """Check if string looks like a valid date."""
    patterns = [
        r'^\d{4}-\d{2}-\d{2}$',
        r'^\d{2}/\d{2}/\d{4}$',
        r'^\d{2}-\d{2}-\d{4}$',
    ]
    return any(re.match(p, value.strip()) for p in patterns)
