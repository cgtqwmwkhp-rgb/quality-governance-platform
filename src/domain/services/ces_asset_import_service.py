"""XLSX dry-run and upsert service for CES Calibrations Equipment Lists."""

from __future__ import annotations

import dataclasses
import io
from typing import Any

from openpyxl import load_workbook
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.exceptions import BadRequestError, ValidationError
from src.domain.models.asset import Asset, AssetType
from src.domain.models.engineer import Engineer
from src.domain.models.location import Location
from src.domain.models.training_matrix import TrainingMatrixNameMap
from src.domain.services.asset_service import AssetService
from src.domain.services.ces_asset_import_parser import cell_text, normalise_ces_row
from src.domain.services.training_matrix_parser import normalize_person_name

EQUIPMENT_LIST_SHEET = "Equipment List"


@dataclasses.dataclass(frozen=True)
class RowIssue:
    row: int
    code: str
    message: str
    field: str | None = None
    severity: str = "error"


@dataclasses.dataclass
class ValidatedCesRow:
    row: int
    action: str
    asset_type_id: int
    asset_number: str
    name: str
    serial_number: str
    status: str
    existing_id: int | None
    make: str | None = None
    model: str | None = None
    owner_user_id: int | None = None
    location_id: int | None = None
    vehicle_reg: str | None = None
    site: str | None = None
    expiry_date: Any = None
    qr_code_data: str | None = None
    metadata_json: dict[str, Any] = dataclasses.field(default_factory=dict)

    def payload(self, *, for_update: bool = False) -> dict[str, Any]:
        data = {
            "asset_type_id": self.asset_type_id,
            "asset_number": self.asset_number,
            "name": self.name,
            "make": self.make,
            "model": self.model,
            "serial_number": self.serial_number,
            "owner_user_id": self.owner_user_id,
            "location_id": self.location_id,
            "vehicle_reg": self.vehicle_reg,
            "site": self.site,
            "expiry_date": self.expiry_date,
            "qr_code_data": self.qr_code_data,
            "status": self.status,
            "metadata_json": self.metadata_json or None,
        }
        if for_update:
            # Serial is the upsert key; preserve existing asset_number on re-import.
            data.pop("asset_number", None)
        return data


@dataclasses.dataclass
class CesImportReport:
    dry_run: bool
    total_rows: int
    valid_rows: int
    error_rows: int
    creates: int
    updates: int
    errors: list[RowIssue] = dataclasses.field(default_factory=list)
    warnings: list[RowIssue] = dataclasses.field(default_factory=list)
    preview: list[dict[str, Any]] = dataclasses.field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.total_rows > 0 and self.error_rows == 0

    def to_dict(self) -> dict[str, Any]:
        def issue(item: RowIssue) -> dict[str, Any]:
            return dataclasses.asdict(item)

        return {
            "dry_run": self.dry_run,
            "total_rows": self.total_rows,
            "valid_rows": self.valid_rows,
            "error_rows": self.error_rows,
            "creates": self.creates,
            "updates": self.updates,
            "ok": self.ok,
            "errors": [issue(item) for item in self.errors],
            "warnings": [issue(item) for item in self.warnings],
            "preview": self.preview,
        }


@dataclasses.dataclass
class CesImportCommitResult:
    created_count: int
    updated_count: int
    created_asset_ids: list[int]
    updated_asset_ids: list[int]
    report: CesImportReport

    def to_dict(self) -> dict[str, Any]:
        return {
            "created_count": self.created_count,
            "updated_count": self.updated_count,
            "created_asset_ids": self.created_asset_ids,
            "updated_asset_ids": self.updated_asset_ids,
            "report": self.report.to_dict(),
        }


class CesAssetImportService:
    """Validate then upsert CES assets by serial number."""

    @staticmethod
    def _duplicate_in_file(
        serial: str,
        equipment_type: str,
        qr: str | None,
        same_file: list[dict[str, Any]],
        row_number: int,
    ) -> RowIssue | None:
        if len(same_file) <= 1:
            return None
        discriminator = (equipment_type.lower(), (qr or "").strip())
        matches = sum(
            (
                str(candidate.get("equipment_type") or "").strip().lower(),
                (candidate.get("qr_code_data") or "").strip(),
            )
            == discriminator
            for candidate in same_file
        )
        if matches <= 1:
            return None
        return RowIssue(
            row_number,
            "AMBIGUOUS_SERIAL",
            f"Serial '{serial}' is repeated in this file without a unique equipment type/QR discriminator",
            "serial_number",
        )

    @staticmethod
    def _match_existing(
        serial: str,
        asset_type: AssetType | None,
        qr: str | None,
        candidates: list[Asset],
        row_number: int,
        claimed_existing: dict[int, int],
    ) -> tuple[Asset | None, list[RowIssue]]:
        issues: list[RowIssue] = []
        matched = list(candidates)
        if asset_type is not None and matched:
            # Always discriminate by equipment type so two CES rows with the same
            # serial but different types cannot both update a single existing asset.
            typed = [asset for asset in matched if asset.asset_type_id == asset_type.id]
            if qr:
                qr_matched = [asset for asset in typed if asset.qr_code_data == qr]
                if qr_matched:
                    typed = qr_matched
            if len(typed) > 1:
                issues.append(
                    RowIssue(
                        row_number,
                        "AMBIGUOUS_SERIAL",
                        (
                            f"Serial '{serial}' matches multiple existing assets; "
                            "equipment type and QR must identify one"
                        ),
                        "serial_number",
                    )
                )
                return None, issues
            matched = typed
        elif len(matched) > 1:
            issues.append(
                RowIssue(
                    row_number,
                    "AMBIGUOUS_SERIAL",
                    (f"Serial '{serial}' matches multiple existing assets; " "equipment type and QR must identify one"),
                    "serial_number",
                )
            )
            return None, issues

        existing = matched[0] if len(matched) == 1 else None
        if existing is not None and existing.id in claimed_existing:
            prior_row = claimed_existing[existing.id]
            # Avoid SQL-ish wording ("update") that trips Bandit B608 on error text.
            message = (
                f"Serial {serial!r} maps to the same register asset ({existing.id}) as "
                f"row {prior_row}; equipment type/QR must identify distinct assets"
            )
            issues.append(RowIssue(row_number, "AMBIGUOUS_SERIAL", message, "serial_number"))
            return None, issues
        return existing, issues

    @staticmethod
    def _resolve_assignment(
        row: dict[str, Any],
        row_number: int,
        location_map: dict[str, Location],
        owner_by_name: dict[str, int | None],
    ) -> tuple[int | None, int | None, list[RowIssue]]:
        warnings: list[RowIssue] = []
        location_id = None
        vehicle_reg = row["vehicle_reg"]
        assignment = row["assignment_text"]
        if not vehicle_reg and assignment:
            location = location_map.get(assignment.lower())
            if location:
                location_id = location.id
            else:
                warnings.append(
                    RowIssue(
                        row_number,
                        "UNMAPPED_LOCATION",
                        f"Location '{assignment}' is not configured; asset will remain unassigned",
                        "location",
                        "warning",
                    )
                )
        owner_user_id = None
        owner_name = row["engineer_name"]
        if owner_name:
            key = normalize_person_name(owner_name).lower()
            if key in owner_by_name and owner_by_name[key] is not None:
                owner_user_id = owner_by_name[key]
            else:
                warnings.append(
                    RowIssue(
                        row_number,
                        "UNMAPPED_OWNER",
                        f"Engineer '{owner_name}' has no uniquely linked user",
                        "location",
                        "warning",
                    )
                )
        return location_id, owner_user_id, warnings

    def __init__(self, db: AsyncSession, *, asset_service: AssetService | None = None) -> None:
        self.db = db
        self.assets = asset_service or AssetService(db)

    @staticmethod
    def parse_workbook(content: bytes) -> list[dict[str, Any]]:
        if not content:
            raise BadRequestError("XLSX file is empty")
        if len(content) > 5 * 1024 * 1024:
            raise BadRequestError("XLSX file exceeds 5 MiB limit")
        try:
            workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        except Exception as exc:  # noqa: BLE001
            raise BadRequestError(f"Unable to read XLSX workbook: {exc}") from exc
        if EQUIPMENT_LIST_SHEET not in workbook.sheetnames:
            raise BadRequestError(f"Workbook missing required sheet '{EQUIPMENT_LIST_SHEET}'")
        sheet = workbook[EQUIPMENT_LIST_SHEET]
        parsed: list[dict[str, Any]] = []
        # CES export columns are fixed: A Location through L Status; I is unused.
        for row_number, values in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
            if not values or all(value is None or cell_text(value) == "" for value in values):
                continue
            padded = tuple(values) + (None,) * max(0, 12 - len(values))
            raw = {
                "__row__": row_number,
                "location": padded[0],
                "equipment_type": padded[1],
                "make": padded[2],
                "model": padded[3],
                "capacity": padded[4],
                "serial_number": padded[5],
                "asset_id": padded[6],
                "qr_code": padded[7],
                "last_inspection": padded[9],
                "next_inspection": padded[10],
                "status": padded[11],
            }
            try:
                parsed.append(normalise_ces_row(raw))
            except ValueError as exc:
                parsed.append({"__row__": row_number, "__parse_error__": str(exc)})
        if not parsed:
            raise BadRequestError("Equipment List sheet contains no data rows")
        return parsed

    async def _lookups(
        self, tenant_id: int, serials: set[str]
    ) -> tuple[dict[str, AssetType], dict[str, Location], dict[str, int | None], dict[str, list[Asset]]]:
        types = (
            (
                await self.db.execute(
                    select(AssetType).where(
                        or_(AssetType.tenant_id == tenant_id, AssetType.tenant_id.is_(None)),
                        AssetType.is_active.is_(True),
                    )
                )
            )
            .scalars()
            .all()
        )
        locations = (
            (
                await self.db.execute(
                    select(Location).where(Location.tenant_id == tenant_id, Location.is_active.is_(True))
                )
            )
            .scalars()
            .all()
        )
        engineers = (
            await self.db.execute(
                select(Engineer.id, Engineer.display_name, Engineer.user_id).where(Engineer.tenant_id == tenant_id)
            )
        ).all()
        maps = (
            await self.db.execute(
                select(TrainingMatrixNameMap.atlas_name, TrainingMatrixNameMap.engineer_id).where(
                    TrainingMatrixNameMap.tenant_id == tenant_id
                )
            )
        ).all()
        engineer_by_id = {int(engineer_id): user_id for engineer_id, _, user_id in engineers}
        owner_by_name: dict[str, int | None] = {}
        ambiguous: set[str] = set()
        for engineer_id, display_name, user_id in engineers:
            if not display_name:
                continue
            key = normalize_person_name(display_name).lower()
            if key in owner_by_name:
                owner_by_name.pop(key, None)
                ambiguous.add(key)
            elif key not in ambiguous:
                owner_by_name[key] = user_id
        for atlas_name, engineer_id in maps:
            key = normalize_person_name(atlas_name).lower()
            if key not in ambiguous and int(engineer_id) in engineer_by_id:
                owner_by_name[key] = engineer_by_id[int(engineer_id)]

        existing_by_serial: dict[str, list[Asset]] = {}
        if serials:
            assets = (
                (
                    await self.db.execute(
                        select(Asset).where(
                            or_(Asset.tenant_id == tenant_id, Asset.tenant_id.is_(None)),
                            Asset.serial_number.in_(serials),
                        )
                    )
                )
                .scalars()
                .all()
            )
            for asset in assets:
                existing_by_serial.setdefault((asset.serial_number or "").strip(), []).append(asset)
        return (
            {asset_type.name.strip().lower(): asset_type for asset_type in types},
            {location.name.strip().lower(): location for location in locations},
            owner_by_name,
            existing_by_serial,
        )

    async def validate_rows(
        self, rows: list[dict[str, Any]], *, tenant_id: int, dry_run: bool
    ) -> tuple[CesImportReport, list[ValidatedCesRow]]:
        serials = {str(row.get("serial_number") or "").strip() for row in rows if row.get("serial_number")}
        type_map, location_map, owner_by_name, existing_by_serial = await self._lookups(tenant_id, serials)
        serial_rows: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            serial = str(row.get("serial_number") or "").strip()
            if serial:
                serial_rows.setdefault(serial, []).append(row)

        errors: list[RowIssue] = []
        warnings: list[RowIssue] = []
        validated: list[ValidatedCesRow] = []
        claimed_existing: dict[int, int] = {}
        creates = updates = 0
        for row in rows:
            row_number = int(row["__row__"])
            row_errors: list[RowIssue] = []
            if "__parse_error__" in row:
                row_errors.append(RowIssue(row_number, "INVALID_ROW", row["__parse_error__"]))
                errors.extend(row_errors)
                continue
            serial = str(row["serial_number"]).strip()
            equipment_type = str(row["equipment_type"]).strip()
            qr = row["qr_code_data"]
            if not serial:
                row_errors.append(RowIssue(row_number, "REQUIRED", "Serial Number is required", "serial_number"))
            asset_type = type_map.get(equipment_type.lower())
            if not equipment_type:
                row_errors.append(RowIssue(row_number, "REQUIRED", "Equipment Type is required", "equipment_type"))
            elif asset_type is None:
                row_errors.append(
                    RowIssue(row_number, "UNKNOWN_TYPE", f"Unknown asset type '{equipment_type}'", "equipment_type")
                )
            if not row["name"]:
                row_errors.append(RowIssue(row_number, "REQUIRED", "Equipment name is required", "equipment_type"))

            duplicate = self._duplicate_in_file(serial, equipment_type, qr, serial_rows.get(serial, []), row_number)
            if duplicate:
                row_errors.append(duplicate)

            existing, match_issues = self._match_existing(
                serial,
                asset_type,
                qr,
                list(existing_by_serial.get(serial, [])),
                row_number,
                claimed_existing,
            )
            row_errors.extend(match_issues)

            location_id, owner_user_id, assignment_warnings = self._resolve_assignment(
                row, row_number, location_map, owner_by_name
            )
            warnings.extend(assignment_warnings)

            if row["not_made_available"]:
                warnings.append(
                    RowIssue(
                        row_number,
                        "NOT_MADE_AVAILABLE",
                        "CES status is Not Made Available; imported as active and flagged in metadata",
                        "status",
                        "warning",
                    )
                )
            if row_errors:
                errors.extend(row_errors)
                continue
            assert asset_type is not None
            action = "update" if existing else "create"
            if existing is not None:
                claimed_existing[existing.id] = row_number
            creates += action == "create"
            updates += action == "update"
            metadata = {
                "ces_location": row["location_raw"],
                "ces_company": row["company"],
                "ces_last_inspection": row["last_inspection"].isoformat() if row["last_inspection"] else None,
                "ces_asset_id": row["asset_id"],
                "ces_not_made_available": row["not_made_available"],
            }
            validated.append(
                ValidatedCesRow(
                    row=row_number,
                    action=action,
                    asset_type_id=asset_type.id,
                    # Asset.number is mandatory. Serial is stable; QR is only a fallback.
                    asset_number=serial or qr or f"CES-{row_number}",
                    name=row["name"][:200],
                    serial_number=serial,
                    status=row["status"],
                    existing_id=existing.id if existing else None,
                    make=row["make"],
                    model=row["model"],
                    owner_user_id=owner_user_id,
                    location_id=location_id,
                    vehicle_reg=row["vehicle_reg"],
                    site=row["assignment_text"],
                    expiry_date=row["expiry_date"],
                    qr_code_data=qr,
                    metadata_json={key: value for key, value in metadata.items() if value is not None},
                )
            )
        preview = [
            {
                "row": item.row,
                "action": item.action,
                "asset_number": item.asset_number,
                "name": item.name,
                "serial_number": item.serial_number,
                "owner_user_id": item.owner_user_id,
                "location_id": item.location_id,
                "vehicle_reg": item.vehicle_reg,
                "status": item.status,
                "not_made_available": item.metadata_json.get("ces_not_made_available", False),
            }
            for item in validated[:50]
        ]
        report = CesImportReport(
            dry_run=dry_run,
            total_rows=len(rows),
            valid_rows=len(validated),
            error_rows=len({issue.row for issue in errors}),
            creates=creates,
            updates=updates,
            errors=errors,
            warnings=warnings,
            preview=preview,
        )
        return report, validated

    async def dry_run(self, content: bytes, *, tenant_id: int) -> CesImportReport:
        report, _ = await self.validate_rows(self.parse_workbook(content), tenant_id=tenant_id, dry_run=True)
        return report

    async def commit(self, content: bytes, *, user_id: int, tenant_id: int) -> CesImportCommitResult:
        report, validated = await self.validate_rows(self.parse_workbook(content), tenant_id=tenant_id, dry_run=False)
        if not report.ok:
            raise ValidationError(
                "CES import validation failed; fix row errors before commit",
                code="CES_ASSET_IMPORT_VALIDATION_FAILED",
                details=report.to_dict(),
            )
        created_ids: list[int] = []
        updated_ids: list[int] = []
        try:
            for item in validated:
                if item.action == "update":
                    assert item.existing_id is not None
                    existing = await self.assets.get_asset(item.existing_id, tenant_id=tenant_id)
                    update_payload = item.payload(for_update=True)
                    # Merge CES metadata keys; do not wipe unrelated asset metadata.
                    prior_meta = dict(existing.metadata_json or {})
                    ces_meta = dict(item.metadata_json or {})
                    update_payload["metadata_json"] = {**prior_meta, **ces_meta} or None
                    asset = await self.assets.update_asset(
                        item.existing_id,
                        update_payload,
                        tenant_id=tenant_id,
                        actor_user_id=user_id,
                        commit=False,
                    )
                    updated_ids.append(asset.id)
                else:
                    asset = await self.assets.create_asset(
                        item.payload(),
                        user_id=user_id,
                        tenant_id=tenant_id,
                        commit=False,
                    )
                    created_ids.append(asset.id)
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            raise
        report.dry_run = False
        return CesImportCommitResult(
            created_count=len(created_ids),
            updated_count=len(updated_ids),
            created_asset_ids=created_ids,
            updated_asset_ids=updated_ids,
            report=report,
        )
