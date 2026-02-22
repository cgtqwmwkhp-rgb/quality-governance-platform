"""Investigation Service.

Business logic for investigation creation, prefill, approval, and customer pack generation.
Implements Mapping Contract v1 and Customer Pack Redaction Rules v1.
"""

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.domain.exceptions import (
    AuthorizationError,
    ConflictError,
    NotFoundError,
    StateTransitionError,
    ValidationError,
)
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
from src.infrastructure.cache.redis_cache import invalidate_tenant_cache
from src.infrastructure.monitoring.azure_monitor import track_metric


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class PaginatedResult:
    """Generic paginated result returned by service methods."""

    items: list
    total: int
    page: int
    page_size: int
    pages: int


@dataclass
class SourceRecordItemResult:
    """A single source record with investigation enrichment info."""

    source_id: int
    display_label: str
    reference_number: str
    status: str
    created_at: Optional[datetime]
    investigation_id: Optional[int]
    investigation_reference: Optional[str]


@dataclass
class SourceRecordsResult:
    """Paginated list of source records."""

    items: List[SourceRecordItemResult]
    total: int
    page: int
    page_size: int
    pages: int
    source_type: str


@dataclass
class ClosureValidationResult:
    """Result of closure validation check."""

    status: str  # "OK" or "BLOCKED"
    reason_codes: List[str]
    missing_fields: List[str]
    checked_at_utc: datetime
    investigation_id: int
    investigation_level: Optional[str]


@dataclass
class CustomerPackResult:
    """Result of customer pack generation."""

    pack: InvestigationCustomerPack
    investigation_reference: str


# ---------------------------------------------------------------------------
# Closure validation reason codes
# ---------------------------------------------------------------------------


class ClosureReasonCode:
    """Stable reason codes for closure validation failures."""

    TEMPLATE_NOT_FOUND = "TEMPLATE_NOT_FOUND"
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
    MISSING_REQUIRED_SECTION = "MISSING_REQUIRED_SECTION"
    INVALID_ARRAY_EMPTY = "INVALID_ARRAY_EMPTY"
    LEVEL_NOT_SET = "LEVEL_NOT_SET"
    STATUS_NOT_COMPLETE = "STATUS_NOT_COMPLETE"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

ENTITY_MODEL_MAP: Dict[str, str] = {
    AssignedEntityType.ROAD_TRAFFIC_COLLISION.value: "src.domain.models.rta:RoadTrafficCollision",
    AssignedEntityType.REPORTING_INCIDENT.value: "src.domain.models.incident:Incident",
    AssignedEntityType.COMPLAINT.value: "src.domain.models.complaint:Complaint",
    AssignedEntityType.NEAR_MISS.value: "src.domain.models.near_miss:NearMiss",
}


def _resolve_entity_model(entity_type_value: str) -> Any:
    """Dynamically import and return the SQLAlchemy model class for an entity type."""
    model_path = ENTITY_MODEL_MAP.get(entity_type_value)
    if not model_path:
        raise ValidationError(
            f"Invalid entity type: {entity_type_value}",
            code="INVALID_ENTITY_TYPE",
            details={"entity_type": entity_type_value, "valid_types": list(ENTITY_MODEL_MAP.keys())},
        )
    module_path, class_name = model_path.split(":")
    module = __import__(module_path, fromlist=[class_name])
    return getattr(module, class_name)


async def _paginate_query(
    db: AsyncSession,
    query: Any,
    page: int,
    page_size: int,
) -> PaginatedResult:
    """Execute a query with offset/limit pagination."""
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar_one()

    offset = (page - 1) * page_size
    result = await db.execute(query.offset(offset).limit(page_size))
    items = list(result.scalars().all())

    pages = (total + page_size - 1) // page_size if total > 0 else 0
    return PaginatedResult(items=items, total=total, page=page, page_size=page_size, pages=pages)


def _level_to_str(level: object) -> Optional[str]:
    """Convert an investigation level (enum or str) to a plain string."""
    if level is None:
        return None
    if hasattr(level, "value"):
        return str(level.value)
    return str(level)


# ---------------------------------------------------------------------------
# Status manager
# ---------------------------------------------------------------------------


class InvestigationStatusManager:
    @staticmethod
    def apply_status_timestamps(investigation: InvestigationRun, new_status: str) -> None:
        if new_status == "in_progress" and not investigation.started_at:
            investigation.started_at = datetime.now(timezone.utc)
        elif new_status == "completed" and not investigation.completed_at:
            investigation.completed_at = datetime.now(timezone.utc)
        elif new_status == "closed" and not investigation.closed_at:
            investigation.closed_at = datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Mapping reason codes (Mapping Contract v1)
# ---------------------------------------------------------------------------


class MappingReasonCode:
    """Reason codes for field mapping (Mapping Contract v1)."""

    SUCCESS = "SUCCESS"
    SOURCE_MISSING_FIELD = "SOURCE_MISSING_FIELD"
    TYPE_MISMATCH = "TYPE_MISMATCH"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    EMPTY_VALUE = "EMPTY_VALUE"
    REDACTED_PII = "REDACTED_PII"
    MAPPING_ERROR = "MAPPING_ERROR"


# ---------------------------------------------------------------------------
# Investigation service
# ---------------------------------------------------------------------------


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

    # ------------------------------------------------------------------
    # Existing methods (preserved)
    # ------------------------------------------------------------------

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
            AssignedEntityType.ROAD_TRAFFIC_COLLISION: (
                "src.domain.models.rta",
                "RoadTrafficCollision",
            ),
            AssignedEntityType.COMPLAINT: ("src.domain.models.complaint", "Complaint"),
            AssignedEntityType.REPORTING_INCIDENT: (
                "src.domain.models.incident",
                "Incident",
            ),
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
        snapshot = {}
        for column in record.__table__.columns:
            value = getattr(record, column.name, None)
            if value is not None:
                if isinstance(value, datetime):
                    value = value.isoformat()
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

        if source_type == AssignedEntityType.NEAR_MISS:
            map_field("reference_number", "section_1_details", "reference_number")
            map_field("event_date", "section_1_details", "incident_date")
            map_field("location", "section_1_details", "location")
            map_field("location_coordinates", "section_1_details", "location_coordinates")
            map_field("description", "section_1_details", "description")
            map_field("persons_involved", "section_1_details", "persons_involved")
            map_field("witness_names", "section_1_details", "witnesses")
            map_field("potential_consequences", "section_1_details", "immediate_harm")
            map_field(
                "preventive_action_suggested",
                "section_2_immediate_actions",
                "actions_taken",
            )

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

            data["sections"]["addendum_complaint"] = {}
            map_field("complaint_type", "addendum_complaint", "complaint_type")
            map_field("complainant_company", "addendum_complaint", "complainant_company")
            map_field("related_reference", "addendum_complaint", "related_reference")
            map_field("customer_satisfied", "addendum_complaint", "customer_satisfaction")
            map_field("compensation_offered", "addendum_complaint", "compensation_offered")

            priority = getattr(record, "priority", None)
            if priority:
                priority_value = priority.value if hasattr(priority, "value") else str(priority)
                level = cls.COMPLAINT_PRIORITY_MAP.get(priority_value, InvestigationLevel.MEDIUM)

        elif source_type == AssignedEntityType.REPORTING_INCIDENT:
            map_field("reference_number", "section_1_details", "reference_number")
            map_field("incident_date", "section_1_details", "incident_date")
            map_field("location", "section_1_details", "location")
            map_field("description", "section_1_details", "description")

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
        redaction_log: List[Dict[str, Any]] = []
        included_assets: List[Dict[str, Any]] = []

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

        source_data: Dict[str, Any] = investigation.data if isinstance(investigation.data, dict) else {}
        for section_id, section_data in source_data.get("sections", {}).items():
            content["sections"][section_id] = {}  # type: ignore[index]  # TYPE-IGNORE: MYPY-1

            if isinstance(section_data, dict):
                for field_id, field_value in section_data.items():
                    redacted = False

                    if audience == CustomerPackAudience.EXTERNAL_CUSTOMER:
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
            elif asset.visibility in (
                EvidenceVisibility.EXTERNAL_ALLOWED,
                EvidenceVisibility.PUBLIC,
            ):
                can_include = True
                if audience == CustomerPackAudience.EXTERNAL_CUSTOMER:
                    if asset.contains_pii or asset.redaction_required:
                        pass

            included_assets.append(
                {
                    "asset_id": asset.id,
                    "title": asset.title,
                    "asset_type": (asset.asset_type.value if asset.asset_type else "other"),
                    "included": can_include,
                    "exclusion_reason": exclusion_reason,
                    "visibility": (asset.visibility.value if asset.visibility else "unknown"),
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

    # ------------------------------------------------------------------
    # New service methods — extracted from route handlers
    # ------------------------------------------------------------------

    @classmethod
    async def get_investigation(
        cls,
        db: AsyncSession,
        investigation_id: int,
        tenant_id: int,
    ) -> InvestigationRun:
        """Fetch an investigation by ID, scoped to tenant.

        Raises NotFoundError if the investigation does not exist or belongs
        to a different tenant.
        """
        stmt = select(InvestigationRun).where(
            InvestigationRun.id == investigation_id,
            InvestigationRun.tenant_id == tenant_id,
        )
        result = await db.execute(stmt)
        investigation = result.scalar_one_or_none()
        if investigation is None:
            raise NotFoundError(
                f"InvestigationRun with ID {investigation_id} not found",
                code="ENTITY_NOT_FOUND",
                details={"entity_id": investigation_id},
            )
        return investigation

    @classmethod
    async def validate_assigned_entity(
        cls,
        db: AsyncSession,
        entity_type: str,
        entity_id: int,
        tenant_id: Optional[int] = None,
    ) -> None:
        """Validate that the assigned entity exists.

        Raises ValidationError for unknown entity types and NotFoundError
        when the referenced entity cannot be found.
        """
        model_class = _resolve_entity_model(entity_type)

        query = select(model_class).where(model_class.id == entity_id)
        if hasattr(model_class, "tenant_id") and tenant_id is not None:
            query = query.where(model_class.tenant_id == tenant_id)
        result = await db.execute(query)
        entity = result.scalar_one_or_none()

        if not entity:
            raise NotFoundError(
                f"{entity_type.replace('_', ' ').title()} with ID {entity_id} not found",
                code="ENTITY_NOT_FOUND",
                details={"entity_type": entity_type, "entity_id": entity_id},
            )

    @classmethod
    async def create_new_investigation(
        cls,
        db: AsyncSession,
        *,
        template_id: int,
        assigned_entity_type: str,
        assigned_entity_id: int,
        title: str,
        description: Optional[str],
        status: str,
        data: Optional[Dict[str, Any]],
        tenant_id: int,
        user_id: int,
    ) -> InvestigationRun:
        """Full creation flow: validate inputs, generate reference, persist."""
        from src.domain.services.reference_number import ReferenceNumberService

        template = await get_or_create_default_template(db, template_id, user_id)

        await cls.validate_assigned_entity(db, assigned_entity_type, assigned_entity_id, tenant_id)

        reference_number = await ReferenceNumberService.generate(db, "investigation", InvestigationRun)

        investigation = InvestigationRun(
            template_id=template_id,
            assigned_entity_type=AssignedEntityType(assigned_entity_type),
            assigned_entity_id=assigned_entity_id,
            title=title,
            description=description,
            status=InvestigationStatus(status),
            data=data,
            reference_number=reference_number,
            tenant_id=tenant_id,
            created_by_id=user_id,
            updated_by_id=user_id,
        )

        db.add(investigation)
        await db.commit()
        await db.refresh(investigation)
        await invalidate_tenant_cache(tenant_id, "investigations")
        track_metric("investigations.started", 1, {"tenant_id": str(tenant_id)})

        return investigation

    @classmethod
    async def list_investigations(
        cls,
        db: AsyncSession,
        *,
        tenant_id: int,
        entity_type: Optional[str] = None,
        entity_id: Optional[int] = None,
        status_filter: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedResult:
        """List investigations with optional filters and pagination."""
        query = (
            select(InvestigationRun)
            .options(
                selectinload(InvestigationRun.template),
                selectinload(InvestigationRun.comments),
                selectinload(InvestigationRun.actions),
            )
            .where(InvestigationRun.tenant_id == tenant_id)
        )

        if entity_type is not None:
            try:
                entity_type_enum = AssignedEntityType(entity_type)
                query = query.where(InvestigationRun.assigned_entity_type == entity_type_enum)
            except ValueError:
                raise ValidationError(
                    f"Invalid entity type: {entity_type}",
                    code="INVALID_ENTITY_TYPE",
                    details={"entity_type": entity_type, "valid_types": [e.value for e in AssignedEntityType]},
                )

        if entity_id is not None:
            query = query.where(InvestigationRun.assigned_entity_id == entity_id)

        if status_filter is not None:
            try:
                status_enum = InvestigationStatus(status_filter)
                query = query.where(InvestigationRun.status == status_enum)
            except ValueError:
                raise ValidationError(
                    f"Invalid status: {status_filter}",
                    code="INVALID_STATUS",
                    details={"status": status_filter, "valid_statuses": [s.value for s in InvestigationStatus]},
                )

        query = query.order_by(InvestigationRun.created_at.desc(), InvestigationRun.id.asc())
        return await _paginate_query(db, query, page, page_size)

    @classmethod
    async def list_source_records(
        cls,
        db: AsyncSession,
        *,
        source_type: str,
        tenant_id: int,
        search_query: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> SourceRecordsResult:
        """List source records available for investigation creation."""
        try:
            source_type_enum = AssignedEntityType(source_type)
        except ValueError:
            raise ValidationError(
                f"Invalid source type: {source_type}",
                code="INVALID_SOURCE_TYPE",
                details={"valid_types": [e.value for e in AssignedEntityType]},
            )

        model_class = _resolve_entity_model(source_type)

        base_query = select(model_class)
        if hasattr(model_class, "tenant_id"):
            base_query = base_query.where(model_class.tenant_id == tenant_id)

        if search_query:
            search_term = f"%{search_query}%"
            search_conditions = []
            if hasattr(model_class, "title"):
                search_conditions.append(model_class.title.ilike(search_term))
            if hasattr(model_class, "reference_number"):
                search_conditions.append(model_class.reference_number.ilike(search_term))
            if hasattr(model_class, "description"):
                search_conditions.append(model_class.description.ilike(search_term))
            if search_conditions:
                base_query = base_query.where(or_(*search_conditions))

        base_query = base_query.order_by(model_class.created_at.desc(), model_class.id.asc())
        paginated = await _paginate_query(db, base_query, page, page_size)
        records = list(paginated.items)

        source_ids = [r.id for r in records]
        inv_query = select(InvestigationRun).where(
            InvestigationRun.assigned_entity_type == source_type_enum,
            InvestigationRun.assigned_entity_id.in_(source_ids),
        )
        inv_result = await db.execute(inv_query)
        existing_investigations = {inv.assigned_entity_id: inv for inv in inv_result.scalars().all()}

        items: List[SourceRecordItemResult] = []
        for record in records:
            ref_num = getattr(record, "reference_number", f"REF-{record.id}")
            record_status = getattr(record, "status", "unknown")
            if hasattr(record_status, "value"):
                record_status = record_status.value
            created_date = record.created_at.strftime("%Y-%m-%d") if record.created_at else "Unknown"
            display_label = f"{ref_num} — {record_status.upper()} — {created_date}"
            existing_inv = existing_investigations.get(record.id)

            items.append(
                SourceRecordItemResult(
                    source_id=record.id,
                    display_label=display_label,
                    reference_number=ref_num,
                    status=record_status,
                    created_at=record.created_at,
                    investigation_id=int(existing_inv.id) if existing_inv else None,
                    investigation_reference=str(existing_inv.reference_number) if existing_inv else None,
                )
            )

        return SourceRecordsResult(
            items=items,
            total=paginated.total,
            page=paginated.page,
            page_size=paginated.page_size,
            pages=paginated.pages,
            source_type=source_type,
        )

    @classmethod
    async def update_investigation(
        cls,
        db: AsyncSession,
        *,
        investigation_id: int,
        updates: Dict[str, Any],
        tenant_id: int,
        user_id: int,
    ) -> InvestigationRun:
        """Apply a partial update to an investigation.

        ``updates`` is expected to come from ``schema.model_dump(exclude_unset=True)``.
        """
        investigation = await cls.get_investigation(db, investigation_id, tenant_id)

        new_status = updates.pop("status", None)
        if new_status is not None:
            investigation.status = InvestigationStatus(new_status)
            InvestigationStatusManager.apply_status_timestamps(investigation, new_status)

        for key, value in updates.items():
            setattr(investigation, key, value)

        investigation.updated_by_id = user_id
        investigation.updated_at = datetime.now(timezone.utc)

        await db.commit()
        await db.refresh(investigation)
        await invalidate_tenant_cache(tenant_id, "investigations")

        return investigation

    @classmethod
    async def autosave(
        cls,
        db: AsyncSession,
        *,
        investigation_id: int,
        data: Dict[str, Any],
        version: int,
        tenant_id: int,
        user_id: int,
    ) -> InvestigationRun:
        """Autosave investigation data with optimistic locking.

        Raises ConflictError on version mismatch.
        """
        investigation = await cls.get_investigation(db, investigation_id, tenant_id)

        if investigation.version != version:
            raise ConflictError(
                "Investigation was modified by another user",
                code="VERSION_CONFLICT",
                details={"expected_version": version, "current_version": investigation.version},
            )

        old_data = investigation.data

        investigation.data = data  # type: ignore[assignment]  # TYPE-IGNORE: SQLALCHEMY-1
        investigation.version += 1  # type: ignore[assignment]  # TYPE-IGNORE: SQLALCHEMY-1
        investigation.updated_by_id = user_id

        await cls.create_revision_event(
            db=db,
            investigation=investigation,
            event_type="DATA_UPDATED",
            actor_id=user_id,
            old_value=old_data,
            new_value=data,
        )

        await db.commit()
        await db.refresh(investigation)

        return investigation

    @classmethod
    async def add_comment(
        cls,
        db: AsyncSession,
        *,
        investigation_id: int,
        body: str,
        section_id: Optional[str],
        field_id: Optional[str],
        parent_comment_id: Optional[int],
        tenant_id: int,
        user_id: int,
    ) -> InvestigationComment:
        """Add an internal comment to an investigation.

        Raises NotFoundError if investigation or parent comment not found.
        """
        investigation = await cls.get_investigation(db, investigation_id, tenant_id)

        if parent_comment_id:
            parent_query = select(InvestigationComment).where(
                InvestigationComment.id == parent_comment_id,
                InvestigationComment.investigation_id == investigation_id,
                InvestigationComment.deleted_at.is_(None),
            )
            parent_result = await db.execute(parent_query)
            parent_comment = parent_result.scalar_one_or_none()
            if not parent_comment:
                raise NotFoundError(
                    f"Parent comment {parent_comment_id} not found",
                    code="PARENT_COMMENT_NOT_FOUND",
                )

        comment = InvestigationComment(
            investigation_id=investigation_id,
            content=body,
            section_id=section_id,
            field_id=field_id,
            parent_comment_id=parent_comment_id,
            author_id=user_id,
        )

        db.add(comment)

        await cls.create_revision_event(
            db=db,
            investigation=investigation,
            event_type="COMMENT_ADDED",
            actor_id=user_id,
            metadata={
                "section_id": section_id,
                "field_id": field_id,
                "is_reply": parent_comment_id is not None,
            },
        )

        await db.commit()
        await db.refresh(comment)

        return comment

    @classmethod
    async def approve_or_reject(
        cls,
        db: AsyncSession,
        *,
        investigation_id: int,
        approved: bool,
        rejection_reason: Optional[str],
        tenant_id: int,
        user_id: int,
    ) -> InvestigationRun:
        """Approve or reject an investigation.

        Raises StateTransitionError if current status disallows the operation
        and ValidationError if rejection_reason is missing on reject.
        """
        investigation = await cls.get_investigation(db, investigation_id, tenant_id)

        if investigation.status not in (InvestigationStatus.UNDER_REVIEW, InvestigationStatus.IN_PROGRESS):
            raise StateTransitionError(
                f"Cannot approve investigation in status {investigation.status.value}",
            )

        old_status = investigation.status

        if approved:
            investigation.status = InvestigationStatus.COMPLETED  # type: ignore[assignment]  # TYPE-IGNORE: SQLALCHEMY-1
            investigation.approved_at = datetime.now(timezone.utc)  # type: ignore[assignment]  # TYPE-IGNORE: SQLALCHEMY-1
            investigation.approved_by_id = user_id  # type: ignore[assignment]  # TYPE-IGNORE: SQLALCHEMY-1
            investigation.completed_at = datetime.now(timezone.utc)  # type: ignore[assignment]  # TYPE-IGNORE: SQLALCHEMY-1
            investigation.rejection_reason = None  # type: ignore[assignment]  # TYPE-IGNORE: SQLALCHEMY-1
            event_type = "APPROVED"
        else:
            if not rejection_reason:
                raise ValidationError(
                    "Rejection reason is required",
                    code="REJECTION_REASON_REQUIRED",
                )
            investigation.status = InvestigationStatus.IN_PROGRESS
            investigation.rejection_reason = rejection_reason
            event_type = "REJECTED"

        investigation.updated_by_id = user_id
        investigation.version += 1

        await cls.create_revision_event(
            db=db,
            investigation=investigation,
            event_type=event_type,
            actor_id=user_id,
            old_value={"status": old_status.value},
            new_value={"status": investigation.status.value},
            metadata={"rejection_reason": rejection_reason} if not approved else None,
        )

        await db.commit()
        await db.refresh(investigation)

        return investigation

    @classmethod
    async def create_from_record(
        cls,
        db: AsyncSession,
        *,
        source_type: str,
        source_id: int,
        title: str,
        template_id: int,
        tenant_id: int,
        user_id: int,
    ) -> InvestigationRun:
        """Create an investigation from a source record with deterministic prefill.

        Performs duplicate check, source snapshot, field mapping, evidence linking,
        and revision event creation.

        Raises ConflictError if an investigation already exists for this source,
        and NotFoundError if the source record is not found.
        """
        from src.domain.services.reference_number import ReferenceNumberService

        source_type_enum = AssignedEntityType(source_type)

        existing_query = select(InvestigationRun).where(
            InvestigationRun.tenant_id == tenant_id,
            InvestigationRun.assigned_entity_type == source_type_enum,
            InvestigationRun.assigned_entity_id == source_id,
        )
        existing_result = await db.execute(existing_query)
        existing_investigation = existing_result.scalar_one_or_none()

        if existing_investigation:
            raise ConflictError(
                f"An investigation already exists for this {source_type.replace('_', ' ')}",
                code="INV_ALREADY_EXISTS",
                details={
                    "existing_investigation_id": existing_investigation.id,
                    "existing_reference_number": existing_investigation.reference_number,
                    "source_type": source_type,
                    "source_id": source_id,
                },
            )

        record, error = await cls.get_source_record(db, source_type_enum, source_id)
        if error:
            raise NotFoundError(
                error,
                code="SOURCE_NOT_FOUND",
                details={"source_type": source_type, "source_id": source_id},
            )

        source_snapshot = cls.create_source_snapshot(record, source_type_enum)
        data, mapping_log, level = cls.map_source_to_investigation(record, source_type_enum)
        template = await get_or_create_default_template(db, template_id, user_id)
        reference_number = await ReferenceNumberService.generate(db, "investigation", InvestigationRun)

        investigation = InvestigationRun(
            template_id=template.id,
            assigned_entity_type=source_type_enum,
            assigned_entity_id=source_id,
            title=title,
            status=InvestigationStatus.DRAFT,
            level=level,
            data=data,
            source_schema_version="1.0",
            source_snapshot=source_snapshot,
            mapping_log=mapping_log,
            version=1,
            reference_number=reference_number,
            tenant_id=tenant_id,
            created_by_id=user_id,
            updated_by_id=user_id,
        )

        db.add(investigation)
        await db.commit()
        await db.refresh(investigation)

        await cls.create_revision_event(
            db=db,
            investigation=investigation,
            event_type="CREATED",
            actor_id=user_id,
            metadata={
                "source_type": source_type,
                "source_id": source_id,
                "mapping_log_count": len(mapping_log),
            },
        )

        evidence_assets = await cls.get_source_evidence_assets(db, source_type_enum, source_id)
        for asset in evidence_assets:
            asset.linked_investigation_id = investigation.id

        await db.commit()
        await db.refresh(investigation)

        return investigation

    @classmethod
    async def generate_pack_for_investigation(
        cls,
        db: AsyncSession,
        *,
        investigation_id: int,
        audience: str,
        tenant_id: int,
        user_id: int,
    ) -> CustomerPackResult:
        """Generate a customer pack with audience-specific redaction.

        Raises ValidationError for invalid audience values.
        """
        try:
            audience_enum = CustomerPackAudience(audience)
        except ValueError:
            raise ValidationError(
                f"Invalid audience: {audience}",
                code="INVALID_AUDIENCE",
                details={"valid_audiences": [e.value for e in CustomerPackAudience]},
            )

        investigation = await cls.get_investigation(db, investigation_id, tenant_id)

        assets_query = select(EvidenceAsset).where(
            EvidenceAsset.linked_investigation_id == investigation_id,
            EvidenceAsset.deleted_at.is_(None),
        )
        assets_result = await db.execute(assets_query)
        evidence_assets = list(assets_result.scalars().all())

        content, redaction_log, included_assets = cls.generate_customer_pack(
            investigation=investigation,
            audience=audience_enum,
            evidence_assets=evidence_assets,
            generated_by_id=user_id,
            generated_by_role=None,
        )

        pack = cls.create_customer_pack_entity(
            investigation_id=investigation_id,
            audience=audience_enum,
            content=content,
            redaction_log=redaction_log,
            included_assets=included_assets,
            generated_by_id=user_id,
        )

        db.add(pack)

        await cls.create_revision_event(
            db=db,
            investigation=investigation,
            event_type="PACK_GENERATED",
            actor_id=user_id,
            metadata={
                "pack_uuid": pack.pack_uuid,
                "audience": audience,
                "redaction_count": len(redaction_log),
                "assets_included": sum(1 for a in included_assets if a["included"]),
                "assets_excluded": sum(1 for a in included_assets if not a["included"]),
            },
        )

        await db.commit()
        await db.refresh(pack)

        return CustomerPackResult(
            pack=pack,
            investigation_reference=investigation.reference_number,
        )

    @classmethod
    async def get_timeline(
        cls,
        db: AsyncSession,
        *,
        investigation_id: int,
        tenant_id: int,
        event_type: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedResult:
        """Get paginated timeline of revision events for an investigation."""
        await cls.get_investigation(db, investigation_id, tenant_id)

        query = select(InvestigationRevisionEvent).where(
            InvestigationRevisionEvent.investigation_id == investigation_id,
        )

        if event_type:
            query = query.where(InvestigationRevisionEvent.event_type == event_type)

        query = query.order_by(
            desc(InvestigationRevisionEvent.created_at),
            desc(InvestigationRevisionEvent.id),
        )

        return await _paginate_query(db, query, page, page_size)

    @classmethod
    async def get_comments_list(
        cls,
        db: AsyncSession,
        *,
        investigation_id: int,
        tenant_id: int,
        include_deleted: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedResult:
        """Get paginated comments for an investigation.

        Caller is responsible for authorizing *include_deleted* before
        invoking this method.
        """
        await cls.get_investigation(db, investigation_id, tenant_id)

        query = select(InvestigationComment).where(
            InvestigationComment.investigation_id == investigation_id,
        )

        if not include_deleted:
            query = query.where(InvestigationComment.deleted_at.is_(None))

        query = query.order_by(
            desc(InvestigationComment.created_at),
            desc(InvestigationComment.id),
        )

        return await _paginate_query(db, query, page, page_size)

    @classmethod
    async def get_packs_list(
        cls,
        db: AsyncSession,
        *,
        investigation_id: int,
        tenant_id: int,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedResult:
        """Get paginated customer packs for an investigation."""
        await cls.get_investigation(db, investigation_id, tenant_id)

        query = select(InvestigationCustomerPack).where(
            InvestigationCustomerPack.investigation_id == investigation_id,
        )

        query = query.order_by(
            desc(InvestigationCustomerPack.created_at),
            desc(InvestigationCustomerPack.id),
        )

        return await _paginate_query(db, query, page, page_size)

    @classmethod
    async def validate_closure(
        cls,
        db: AsyncSession,
        *,
        investigation_id: int,
        tenant_id: int,
    ) -> ClosureValidationResult:
        """Validate whether an investigation can be closed.

        Performs deterministic, template-driven validation.
        """
        checked_at = datetime.now(timezone.utc)
        investigation = await cls.get_investigation(db, investigation_id, tenant_id)

        reason_codes: List[str] = []
        missing_fields: List[str] = []

        template_query = select(InvestigationTemplate).where(
            InvestigationTemplate.id == investigation.template_id,
        )
        template_result = await db.execute(template_query)
        template = template_result.scalar_one_or_none()

        level_str = _level_to_str(investigation.level)

        if not template:
            return ClosureValidationResult(
                status="BLOCKED",
                reason_codes=[ClosureReasonCode.TEMPLATE_NOT_FOUND],
                missing_fields=[],
                checked_at_utc=checked_at,
                investigation_id=investigation_id,
                investigation_level=level_str,
            )

        if not investigation.level:
            reason_codes.append(ClosureReasonCode.LEVEL_NOT_SET)

        data: dict = dict(investigation.data) if investigation.data else {}

        level_section_counts = {
            "low": 3,
            "medium": 4,
            "high": 6,
        }
        max_sections = level_section_counts.get(level_str or "high", 6)

        structure: dict = dict(template.structure) if template.structure else {}
        sections = structure.get("sections", [])

        for i, section in enumerate(sections):
            if i >= max_sections:
                break

            section_id = section.get("id", f"section_{i}")
            section_data = data.get(section_id, {})

            if section_id not in data:
                fields = section.get("fields", [])
                has_required = any(f.get("required", False) for f in fields)
                if has_required:
                    reason_codes.append(ClosureReasonCode.MISSING_REQUIRED_SECTION)
                    missing_fields.append(section_id)
                continue

            fields = section.get("fields", [])
            for field in fields:
                field_id = field.get("id")
                is_required = field.get("required", False)
                field_type = field.get("type", "text")

                if not is_required:
                    continue

                field_path = f"{section_id}.{field_id}"
                field_value = section_data.get(field_id)

                if field_value is None:
                    reason_codes.append(ClosureReasonCode.MISSING_REQUIRED_FIELD)
                    missing_fields.append(field_path)
                elif field_type == "text" and isinstance(field_value, str) and not field_value.strip():
                    reason_codes.append(ClosureReasonCode.MISSING_REQUIRED_FIELD)
                    missing_fields.append(field_path)
                elif field_type == "array" and isinstance(field_value, list) and len(field_value) == 0:
                    reason_codes.append(ClosureReasonCode.INVALID_ARRAY_EMPTY)
                    missing_fields.append(field_path)

        unique_reason_codes = list(dict.fromkeys(reason_codes))
        closure_status = "OK" if not unique_reason_codes else "BLOCKED"

        return ClosureValidationResult(
            status=closure_status,
            reason_codes=unique_reason_codes,
            missing_fields=missing_fields,
            checked_at_utc=checked_at,
            investigation_id=investigation_id,
            investigation_level=level_str,
        )

    @staticmethod
    def user_can_access_investigation(user: Any, investigation: InvestigationRun) -> bool:
        """Check if user has access to an investigation.

        Access is granted if the user is a superuser, has global view
        permission, or is directly involved with the investigation.
        """
        if user.is_superuser:
            return True
        if user.has_permission("investigations:view_all"):
            return True
        if investigation.assigned_to_user_id == user.id:
            return True
        if investigation.reviewer_user_id == user.id:
            return True
        if investigation.approved_by_id == user.id:
            return True
        return False


# ---------------------------------------------------------------------------
# Standalone helpers (kept for backward compatibility)
# ---------------------------------------------------------------------------


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
    result = await db.execute(select(InvestigationTemplate).where(InvestigationTemplate.id == template_id))
    template = result.scalar_one_or_none()

    if template:
        return template

    if template_id != 1:
        raise NotFoundError(
            f"Investigation template with ID {template_id} not found",
            code="TEMPLATE_NOT_FOUND",
            details={"template_id": template_id},
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
                        {
                            "id": "contributing_factors",
                            "type": "array",
                            "required": False,
                        },
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
