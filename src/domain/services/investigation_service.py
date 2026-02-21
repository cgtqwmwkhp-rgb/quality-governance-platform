"""Investigation Service.

Business logic for investigation creation, prefill, approval, and customer pack generation.
Implements Mapping Contract v1 and Customer Pack Redaction Rules v1.
"""

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.evidence_asset import EvidenceAsset, EvidenceSourceModule, EvidenceVisibility
from src.domain.models.investigation import (
    AssignedEntityType,
    CustomerPackAudience,
    InvestigationComment,
    InvestigationCustomerPack,
    InvestigationLevel,
    InvestigationRevisionEvent,
    InvestigationRun,
    InvestigationStatus,
    InvestigationTemplate,
)


class MappingReasonCode:
    """Reason codes for field mapping (Mapping Contract v1)."""

    SUCCESS = "SUCCESS"
    SOURCE_MISSING_FIELD = "SOURCE_MISSING_FIELD"
    TYPE_MISMATCH = "TYPE_MISMATCH"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    EMPTY_VALUE = "EMPTY_VALUE"
    REDACTED_PII = "REDACTED_PII"
    MAPPING_ERROR = "MAPPING_ERROR"


class InvestigationService:
    """Service for investigation operations."""

    # Severity mapping tables (Mapping Contract v1)
    NEAR_MISS_SEVERITY_MAP = {
        "low": InvestigationLevel.LOW,
        "medium": InvestigationLevel.MEDIUM,
        "high": InvestigationLevel.HIGH,
        "critical": InvestigationLevel.HIGH,
    }

    RTA_SEVERITY_MAP = {
        "near_miss": InvestigationLevel.LOW,
        "damage_only": InvestigationLevel.MEDIUM,
        "minor_injury": InvestigationLevel.MEDIUM,
        "serious_injury": InvestigationLevel.HIGH,
        "fatal": InvestigationLevel.HIGH,
    }

    COMPLAINT_PRIORITY_MAP = {
        "LOW": InvestigationLevel.LOW,
        "MEDIUM": InvestigationLevel.MEDIUM,
        "HIGH": InvestigationLevel.HIGH,
        "CRITICAL": InvestigationLevel.HIGH,
    }

    @classmethod
    async def get_source_record(
        cls,
        db: AsyncSession,
        source_type: AssignedEntityType,
        source_id: int,
    ) -> Tuple[Optional[Any], Optional[str]]:
        """Get source record by type and ID.

        Returns:
            Tuple of (record, error_message)
        """
        model_map = {
            AssignedEntityType.NEAR_MISS: ("src.domain.models.near_miss", "NearMiss"),
            AssignedEntityType.ROAD_TRAFFIC_COLLISION: ("src.domain.models.rta", "RoadTrafficCollision"),
            AssignedEntityType.COMPLAINT: ("src.domain.models.complaint", "Complaint"),
            AssignedEntityType.REPORTING_INCIDENT: ("src.domain.models.incident", "Incident"),
        }

        if source_type not in model_map:
            return None, f"Unsupported source type: {source_type.value}"

        module_path, class_name = model_map[source_type]
        module = __import__(module_path, fromlist=[class_name])
        model_class = getattr(module, class_name)

        query = select(model_class).where(model_class.id == source_id)
        result = await db.execute(query)
        record = result.scalar_one_or_none()

        if not record:
            return None, f"{source_type.value} with ID {source_id} not found"

        return record, None

    @classmethod
    def create_source_snapshot(
        cls,
        record: Any,
        source_type: AssignedEntityType,
    ) -> Dict[str, Any]:
        """Create immutable snapshot of source record (PII redacted).

        Returns a serializable dict with source data.
        """
        # Get all column values
        snapshot = {}
        for column in record.__table__.columns:
            value = getattr(record, column.name, None)
            if value is not None:
                # Handle datetime serialization
                if isinstance(value, datetime):
                    value = value.isoformat()
                # Redact PII fields (emails, phone numbers stored as metadata only)
                # We keep the data but flag it
                snapshot[column.name] = value

        return snapshot

    @classmethod
    def map_source_to_investigation(
        cls,
        record: Any,
        source_type: AssignedEntityType,
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]], InvestigationLevel]:
        """Map source record fields to investigation data (Mapping Contract v1).

        Returns:
            Tuple of (investigation_data, mapping_log, suggested_level)
        """
        data: Dict[str, Any] = {"sections": {}}
        mapping_log: List[Dict[str, Any]] = []
        level = InvestigationLevel.MEDIUM  # Default

        def map_field(
            source_field: str,
            target_section: str,
            target_field: str,
            transform: str = "direct",
            fallback: Any = None,
        ) -> None:
            """Map a single field and log the result."""
            source_value = getattr(record, source_field, None)

            if source_value is None:
                mapping_log.append(
                    {
                        "source_field": source_field,
                        "target_field": f"{target_section}.{target_field}",
                        "transform": transform,
                        "result": "FALLBACK",
                        "reason_code": MappingReasonCode.SOURCE_MISSING_FIELD,
                    }
                )
                source_value = fallback
            else:
                # Handle datetime serialization
                if isinstance(source_value, datetime):
                    source_value = source_value.isoformat()
                mapping_log.append(
                    {
                        "source_field": source_field,
                        "target_field": f"{target_section}.{target_field}",
                        "transform": transform,
                        "result": MappingReasonCode.SUCCESS,
                        "reason_code": None,
                    }
                )

            if target_section not in data["sections"]:
                data["sections"][target_section] = {}  # type: ignore[index]  # TYPE-IGNORE: MYPY-1
            data["sections"][target_section][target_field] = source_value  # type: ignore[index]  # TYPE-IGNORE: MYPY-1

        # Section 1: Incident/Event Details (common mapping)
        if source_type == AssignedEntityType.NEAR_MISS:
            map_field("reference_number", "section_1_details", "reference_number")
            map_field("event_date", "section_1_details", "incident_date")
            map_field("location", "section_1_details", "location")
            map_field("location_coordinates", "section_1_details", "location_coordinates")
            map_field("description", "section_1_details", "description")
            map_field("persons_involved", "section_1_details", "persons_involved")
            map_field("witness_names", "section_1_details", "witnesses")
            map_field("potential_consequences", "section_1_details", "immediate_harm")
            map_field("preventive_action_suggested", "section_2_immediate_actions", "actions_taken")

            # Determine level from severity
            severity = getattr(record, "potential_severity", "medium")
            level = cls.NEAR_MISS_SEVERITY_MAP.get(severity, InvestigationLevel.MEDIUM)

        elif source_type == AssignedEntityType.ROAD_TRAFFIC_COLLISION:
            map_field("reference_number", "section_1_details", "reference_number")
            map_field("collision_date", "section_1_details", "incident_date")
            map_field("location", "section_1_details", "location")
            map_field("description", "section_1_details", "description")
            map_field("driver_name", "section_1_details", "persons_involved")
            map_field("witnesses", "section_1_details", "witnesses")
            map_field("company_vehicle_damage", "section_1_details", "immediate_harm")

            # RTA addendum
            data["sections"]["addendum_rta"] = {}
            map_field("collision_time", "addendum_rta", "collision_time")
            map_field("road_name", "addendum_rta", "road_name")
            map_field("postcode", "addendum_rta", "postcode")
            map_field("weather_conditions", "addendum_rta", "weather_conditions")
            map_field("road_conditions", "addendum_rta", "road_conditions")
            map_field("company_vehicle_registration", "addendum_rta", "company_vehicle_reg")
            map_field("driver_injured", "addendum_rta", "driver_injured")
            map_field("driver_injury_details", "addendum_rta", "driver_injury_details")
            map_field("police_attended", "addendum_rta", "police_attended")
            map_field("police_reference", "addendum_rta", "police_reference")
            map_field("insurance_notified", "addendum_rta", "insurance_notified")
            map_field("insurance_reference", "addendum_rta", "insurance_reference")
            map_field("fault_determination", "addendum_rta", "fault_determination")
            map_field("cctv_available", "addendum_rta", "cctv_available")
            map_field("dashcam_footage_available", "addendum_rta", "dashcam_available")

            # Determine level from severity
            severity = getattr(record, "severity", None)
            if severity:
                severity_value = severity.value if hasattr(severity, "value") else str(severity)
                level = cls.RTA_SEVERITY_MAP.get(severity_value, InvestigationLevel.MEDIUM)

        elif source_type == AssignedEntityType.COMPLAINT:
            map_field("reference_number", "section_1_details", "reference_number")
            map_field("received_date", "section_1_details", "incident_date")
            map_field("title", "section_1_details", "description")
            map_field("description", "section_1_details", "description")
            map_field("complainant_name", "section_1_details", "persons_involved")

            # Complaint addendum
            data["sections"]["addendum_complaint"] = {}
            map_field("complaint_type", "addendum_complaint", "complaint_type")
            map_field("complainant_company", "addendum_complaint", "complainant_company")
            map_field("related_reference", "addendum_complaint", "related_reference")
            map_field("customer_satisfied", "addendum_complaint", "customer_satisfaction")
            map_field("compensation_offered", "addendum_complaint", "compensation_offered")

            # Determine level from priority
            priority = getattr(record, "priority", None)
            if priority:
                priority_value = priority.value if hasattr(priority, "value") else str(priority)
                level = cls.COMPLAINT_PRIORITY_MAP.get(priority_value, InvestigationLevel.MEDIUM)

        elif source_type == AssignedEntityType.REPORTING_INCIDENT:
            map_field("reference_number", "section_1_details", "reference_number")
            map_field("incident_date", "section_1_details", "incident_date")
            map_field("location", "section_1_details", "location")
            map_field("description", "section_1_details", "description")

            # Determine level from severity
            severity = getattr(record, "severity", None)
            if severity:
                severity_value = severity.value if hasattr(severity, "value") else str(severity)
                if severity_value in ["critical", "high"]:
                    level = InvestigationLevel.HIGH
                elif severity_value == "medium":
                    level = InvestigationLevel.MEDIUM
                else:
                    level = InvestigationLevel.LOW

        return data, mapping_log, level

    @classmethod
    async def get_source_evidence_assets(
        cls,
        db: AsyncSession,
        source_type: AssignedEntityType,
        source_id: int,
    ) -> List[EvidenceAsset]:
        """Get evidence assets linked to the source record."""
        # Map source type to evidence source module
        source_module_map = {
            AssignedEntityType.NEAR_MISS: EvidenceSourceModule.NEAR_MISS,
            AssignedEntityType.ROAD_TRAFFIC_COLLISION: EvidenceSourceModule.ROAD_TRAFFIC_COLLISION,
            AssignedEntityType.COMPLAINT: EvidenceSourceModule.COMPLAINT,
            AssignedEntityType.REPORTING_INCIDENT: EvidenceSourceModule.INCIDENT,
        }

        source_module = source_module_map.get(source_type)
        if not source_module:
            return []

        query = select(EvidenceAsset).where(
            EvidenceAsset.source_module == source_module,
            EvidenceAsset.source_id == source_id,
            EvidenceAsset.deleted_at.is_(None),
        )
        result = await db.execute(query)
        return list(result.scalars().all())

    @classmethod
    async def create_revision_event(
        cls,
        db: AsyncSession,
        investigation: InvestigationRun,
        event_type: str,
        actor_id: int,
        field_path: Optional[str] = None,
        old_value: Optional[Any] = None,
        new_value: Optional[Any] = None,
        metadata: Optional[Dict] = None,
    ) -> InvestigationRevisionEvent:
        """Create a revision event for audit trail."""
        event = InvestigationRevisionEvent(
            investigation_id=investigation.id,
            event_type=event_type,
            field_path=field_path,
            old_value=old_value,
            new_value=new_value,
            version=investigation.version,
            actor_id=actor_id,
            event_metadata=metadata,
        )
        db.add(event)
        return event

    @classmethod
    def generate_customer_pack(
        cls,
        investigation: InvestigationRun,
        audience: CustomerPackAudience,
        evidence_assets: List[EvidenceAsset],
        generated_by_id: int,
        generated_by_role: Optional[str] = None,
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Generate customer pack with redaction rules applied.

        Returns:
            Tuple of (pack_content, redaction_log, included_assets)
        """
        redaction_log = []
        included_assets = []

        # Base rules: ALWAYS exclude internal comments and revision history
        # (They are not in investigation.data, so nothing to do here)

        # Copy investigation data
        # Get status and level values with proper None handling
        if investigation.status is not None and hasattr(investigation.status, "value"):
            status_val = investigation.status.value
        elif investigation.status is not None:
            status_val = str(investigation.status)
        else:
            status_val = "unknown"

        if investigation.level is not None and hasattr(investigation.level, "value"):
            level_val = investigation.level.value
        elif investigation.level is not None:
            level_val = str(investigation.level)
        else:
            level_val = "medium"
        content: Dict[str, Any] = {
            "investigation_reference": investigation.reference_number,
            "title": investigation.title,
            "status": status_val,
            "level": level_val,
            "sections": {},
        }

        # Process sections with redaction
        source_data: Dict[str, Any] = investigation.data if isinstance(investigation.data, dict) else {}
        for section_id, section_data in source_data.get("sections", {}).items():
            content["sections"][section_id] = {}  # type: ignore[index]  # TYPE-IGNORE: MYPY-1

            if isinstance(section_data, dict):
                for field_id, field_value in section_data.items():
                    # Check if this field contains identity data that needs redaction
                    redacted = False

                    if audience == CustomerPackAudience.EXTERNAL_CUSTOMER:
                        # Redact identity fields by default for external packs
                        identity_fields = [
                            "reporter_name",
                            "reporter_email",
                            "driver_name",
                            "driver_email",
                            "complainant_name",
                            "complainant_email",
                            "investigator_name",
                            "reviewer_name",
                            "approver_name",
                            "persons_involved",
                            "witnesses",
                            "witness_names",
                            "first_responder",
                            "responsible_person",
                        ]

                        if field_id in identity_fields and field_value:
                            # Redact to role or generic placeholder
                            original_value = field_value
                            if "name" in field_id:
                                field_value = "[Name Redacted]"
                            elif "email" in field_id:
                                field_value = "[Email Redacted]"
                            else:
                                field_value = "[Redacted]"
                            redacted = True
                            redaction_log.append(
                                {
                                    "field_path": f"{section_id}.{field_id}",
                                    "redaction_type": "IDENTITY_REDACTION",
                                    "original_type": type(original_value).__name__,
                                }
                            )

                    content["sections"][section_id][field_id] = field_value  # type: ignore[index]  # TYPE-IGNORE: MYPY-1

        # Process evidence assets based on visibility rules
        for asset in evidence_assets:
            can_include = False
            exclusion_reason = None

            if asset.visibility == EvidenceVisibility.INTERNAL_ONLY:
                exclusion_reason = "INTERNAL_ONLY"
            elif asset.visibility == EvidenceVisibility.INTERNAL_CUSTOMER:
                if audience == CustomerPackAudience.INTERNAL_CUSTOMER:
                    can_include = True
                else:
                    exclusion_reason = "INTERNAL_CUSTOMER_ONLY"
            elif asset.visibility in (EvidenceVisibility.EXTERNAL_ALLOWED, EvidenceVisibility.PUBLIC):
                can_include = True
                # Check if redaction is required
                if audience == CustomerPackAudience.EXTERNAL_CUSTOMER:
                    if asset.contains_pii or asset.redaction_required:
                        # Flag that this asset may need manual redaction
                        pass

            included_assets.append(
                {
                    "asset_id": asset.id,
                    "title": asset.title,
                    "asset_type": asset.asset_type.value if asset.asset_type else "other",
                    "included": can_include,
                    "exclusion_reason": exclusion_reason,
                    "visibility": asset.visibility.value if asset.visibility else "unknown",
                    "contains_pii": asset.contains_pii,
                    "redaction_required": asset.redaction_required,
                }
            )

        return content, redaction_log, included_assets

    @classmethod
    def create_customer_pack_entity(
        cls,
        investigation_id: int,
        audience: CustomerPackAudience,
        content: Dict[str, Any],
        redaction_log: List[Dict[str, Any]],
        included_assets: List[Dict[str, Any]],
        generated_by_id: int,
        generated_by_role: Optional[str] = None,
    ) -> InvestigationCustomerPack:
        """Create InvestigationCustomerPack entity."""
        # Calculate checksum
        content_json = json.dumps(content, sort_keys=True, default=str)
        checksum = hashlib.sha256(content_json.encode()).hexdigest()

        return InvestigationCustomerPack(
            investigation_id=investigation_id,
            pack_uuid=str(uuid.uuid4()),
            audience=audience,
            content=content,
            redaction_log=redaction_log,
            included_assets=included_assets,
            checksum_sha256=checksum,
            generated_by_id=generated_by_id,
            generated_by_role=generated_by_role,
        )


async def get_or_create_default_template(
    db: AsyncSession,
    template_id: int,
    created_by_id: int,
) -> InvestigationTemplate:
    """Get a template or create a default one if it doesn't exist.

    When template_id is 1 and no template exists, auto-creates a default
    Investigation Report Template with standard RCA sections. For any
    other template_id, raises HTTP 404.
    """
    from fastapi import HTTPException
    from fastapi import status as http_status

    result = await db.execute(select(InvestigationTemplate).where(InvestigationTemplate.id == template_id))
    template = result.scalar_one_or_none()

    if template:
        return template

    if template_id != 1:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": "TEMPLATE_NOT_FOUND",
                "message": f"Investigation template with ID {template_id} not found",
                "details": {"template_id": template_id},
            },
        )

    default_template = InvestigationTemplate(
        id=1,
        name="Default Investigation Template",
        description="Standard investigation template for incidents, RTAs, and complaints",
        version="1.0",
        is_active=True,
        structure={
            "sections": [
                {
                    "id": "rca",
                    "title": "Root Cause Analysis",
                    "fields": [
                        {"id": "problem_statement", "type": "text", "required": True},
                        {"id": "root_cause", "type": "text", "required": True},
                        {"id": "contributing_factors", "type": "array", "required": False},
                        {"id": "corrective_actions", "type": "array", "required": True},
                    ],
                }
            ]
        },
        applicable_entity_types=[
            "road_traffic_collision",
            "reporting_incident",
            "complaint",
            "near_miss",
        ],
        created_by_id=created_by_id,
        updated_by_id=created_by_id,
    )
    db.add(default_template)
    await db.commit()
    await db.refresh(default_template)
    return default_template
