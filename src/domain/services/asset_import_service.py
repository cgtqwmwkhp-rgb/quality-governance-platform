"""CSV bulk import for engineer / safety tools (AM-IMPORT).

Dry-run validates every row and returns a structured validation report.
Commit re-validates then persists assets via AssetService (location XOR vehicle).
"""

from __future__ import annotations

import csv
import dataclasses
import io
import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.exceptions import BadRequestError, ValidationError
from src.domain.models.asset import Asset, AssetStatus, AssetType
from src.domain.models.location import Location
from src.domain.models.user import User
from src.domain.services.asset_service import AssetService

# Canonical CSV headers (aliases normalised before validation).
REQUIRED_FIELDS = frozenset({"asset_number", "name", "type"})
OPTIONAL_FIELDS = frozenset(
    {
        "make",
        "model",
        "serial",
        "owner_email",
        "owner_user_id",
        "location_name",
        "vehicle_reg",
        "expiry_date",
        "status",
    }
)
HEADER_ALIASES: dict[str, str] = {
    "asset_number": "asset_number",
    "asset no": "asset_number",
    "asset_no": "asset_number",
    "name": "name",
    "type": "type",
    "asset_type": "type",
    "asset_type_name": "type",
    "make": "make",
    "model": "model",
    "serial": "serial",
    "serial_number": "serial",
    "owner_email": "owner_email",
    "owner_user_id": "owner_user_id",
    "owner_id": "owner_user_id",
    "location_name": "location_name",
    "location": "location_name",
    "vehicle_reg": "vehicle_reg",
    "vehicle": "vehicle_reg",
    "expiry_date": "expiry_date",
    "expiry": "expiry_date",
    "status": "status",
}

_DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S%z",
    "%d/%m/%Y",
    "%d-%m-%Y",
)


@dataclasses.dataclass(frozen=True)
class RowError:
    """Single row-level validation failure."""

    row: int
    code: str
    message: str
    field: str | None = None


@dataclasses.dataclass
class ValidatedImportRow:
    """Normalised payload ready for AssetService.create_asset."""

    row: int
    asset_number: str
    name: str
    asset_type_id: int
    make: str | None = None
    model: str | None = None
    serial_number: str | None = None
    owner_user_id: int | None = None
    location_id: int | None = None
    vehicle_reg: str | None = None
    expiry_date: datetime | None = None
    status: str = AssetStatus.ACTIVE.value

    def to_create_dict(self) -> dict[str, Any]:
        return {
            "asset_type_id": self.asset_type_id,
            "asset_number": self.asset_number,
            "name": self.name,
            "make": self.make,
            "model": self.model,
            "serial_number": self.serial_number,
            "owner_user_id": self.owner_user_id,
            "location_id": self.location_id,
            "vehicle_reg": self.vehicle_reg,
            "expiry_date": self.expiry_date,
            "status": self.status,
        }


@dataclasses.dataclass
class ImportValidationReport:
    """Dry-run / pre-commit validation summary."""

    dry_run: bool
    total_rows: int
    valid_rows: int
    error_rows: int
    errors: list[RowError]
    preview: list[dict[str, Any]] = dataclasses.field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.error_rows == 0 and self.total_rows > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "dry_run": self.dry_run,
            "total_rows": self.total_rows,
            "valid_rows": self.valid_rows,
            "error_rows": self.error_rows,
            "ok": self.ok,
            "errors": [
                {
                    "row": e.row,
                    "code": e.code,
                    "message": e.message,
                    "field": e.field,
                }
                for e in self.errors
            ],
            "preview": self.preview,
        }


@dataclasses.dataclass
class ImportCommitResult:
    """Outcome of a successful commit."""

    created_count: int
    created_asset_ids: list[int]
    report: ImportValidationReport

    def to_dict(self) -> dict[str, Any]:
        return {
            "created_count": self.created_count,
            "created_asset_ids": self.created_asset_ids,
            "report": self.report.to_dict(),
        }


class AssetImportService:
    """Parse, validate, and optionally commit CSV tool imports."""

    def __init__(self, db: AsyncSession, *, asset_service: AssetService | None = None) -> None:
        self.db = db
        self.assets = asset_service or AssetService(db)

    # ------------------------------------------------------------------
    # CSV parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _decode(content: str | bytes) -> str:
        if isinstance(content, bytes):
            for encoding in ("utf-8-sig", "utf-8", "latin-1"):
                try:
                    return content.decode(encoding)
                except UnicodeDecodeError:
                    continue
            raise BadRequestError("Unable to decode CSV file as text")
        return content

    @classmethod
    def parse_csv(cls, content: str | bytes) -> list[dict[str, str]]:
        """Parse CSV into a list of normalised row dicts (header aliases applied)."""
        text = cls._decode(content).strip()
        if not text:
            raise BadRequestError("CSV file is empty")

        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames:
            raise BadRequestError("CSV file has no header row")

        normalised_headers: list[str | None] = []
        seen: set[str] = set()
        for raw in reader.fieldnames:
            key = (raw or "").strip().lower()
            canonical = HEADER_ALIASES.get(key)
            if canonical is None:
                normalised_headers.append(None)
                continue
            if canonical in seen:
                raise BadRequestError(f"Duplicate CSV column for field '{canonical}'")
            seen.add(canonical)
            normalised_headers.append(canonical)

        missing = REQUIRED_FIELDS - seen
        if missing:
            raise BadRequestError("CSV missing required column(s): " + ", ".join(sorted(missing)))

        rows: list[dict[str, str]] = []
        for raw_row in reader:
            if raw_row is None:
                continue
            # Skip completely blank lines
            if all(not (v or "").strip() for v in raw_row.values()):
                continue
            normalised: dict[str, str] = {}
            for raw_key, value in raw_row.items():
                key = (raw_key or "").strip().lower()
                canonical = HEADER_ALIASES.get(key)
                if canonical is None:
                    continue
                normalised[canonical] = (value or "").strip()
            rows.append(normalised)

        if not rows:
            raise BadRequestError("CSV contains no data rows")
        return rows

    # ------------------------------------------------------------------
    # Field helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_expiry(value: str) -> datetime:
        text = value.strip()
        if not text:
            raise ValueError("empty date")
        # ISO with Z
        iso = text.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(iso)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            pass
        for fmt in _DATE_FORMATS:
            try:
                dt = datetime.strptime(text, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                continue
        raise ValueError(f"unrecognised date format: {value!r}")

    @staticmethod
    def _parse_owner_user_id(value: str) -> int:
        if not re.fullmatch(r"\d+", value.strip()):
            raise ValueError("owner_user_id must be an integer")
        return int(value.strip())

    # ------------------------------------------------------------------
    # Lookups
    # ------------------------------------------------------------------

    async def _load_asset_types(self, tenant_id: int) -> dict[str, AssetType]:
        result = await self.db.execute(
            select(AssetType).where(
                or_(AssetType.tenant_id == tenant_id, AssetType.tenant_id.is_(None)),
                AssetType.is_active.is_(True),
            )
        )
        types = list(result.scalars().all())
        return {t.name.strip().lower(): t for t in types}

    async def _load_locations(self, tenant_id: int) -> dict[str, Location]:
        result = await self.db.execute(
            select(Location).where(
                Location.tenant_id == tenant_id,
                Location.is_active.is_(True),
            )
        )
        locations = list(result.scalars().all())
        return {loc.name.strip().lower(): loc for loc in locations}

    async def _load_users_by_email(self, emails: set[str], tenant_id: int) -> dict[str, User]:
        if not emails:
            return {}
        lowered = {e.lower() for e in emails}
        result = await self.db.execute(
            select(User).where(
                User.tenant_id == tenant_id,
                User.email.in_(lowered),
            )
        )
        users = list(result.scalars().all())
        # Also try case-insensitive match if DB collation is case-sensitive
        by_email = {u.email.lower(): u for u in users}
        missing = lowered - set(by_email)
        if missing:
            result2 = await self.db.execute(select(User).where(User.tenant_id == tenant_id))
            for u in result2.scalars().all():
                if u.email.lower() in missing:
                    by_email[u.email.lower()] = u
        return by_email

    async def _load_users_by_id(self, ids: set[int], tenant_id: int) -> dict[int, User]:
        if not ids:
            return {}
        result = await self.db.execute(select(User).where(User.tenant_id == tenant_id, User.id.in_(ids)))
        return {u.id: u for u in result.scalars().all()}

    async def _existing_asset_numbers(self, numbers: set[str], tenant_id: int) -> set[str]:
        if not numbers:
            return set()
        result = await self.db.execute(
            select(Asset.asset_number).where(
                or_(Asset.tenant_id == tenant_id, Asset.tenant_id.is_(None)),
                Asset.asset_number.in_(numbers),
            )
        )
        return {row[0] for row in result.all()}

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_required_fields(
        *,
        row_number: int,
        asset_number: str,
        name: str,
        type_name: str,
        type_map: dict[str, AssetType],
        errors: list[RowError],
    ) -> AssetType | None:
        if not asset_number:
            errors.append(
                RowError(
                    row=row_number,
                    field="asset_number",
                    code="REQUIRED",
                    message="asset_number is required",
                )
            )
        if not name:
            errors.append(RowError(row=row_number, field="name", code="REQUIRED", message="name is required"))
        if not type_name:
            errors.append(
                RowError(
                    row=row_number,
                    field="type",
                    code="REQUIRED",
                    message="type (asset type name) is required",
                )
            )

        asset_type = type_map.get(type_name.lower()) if type_name else None
        if type_name and asset_type is None:
            errors.append(
                RowError(
                    row=row_number,
                    field="type",
                    code="UNKNOWN_TYPE",
                    message=f"Unknown asset type '{type_name}'",
                )
            )
        return asset_type

    @staticmethod
    def _validate_asset_number(
        *,
        row_number: int,
        asset_number: str,
        seen_in_file: dict[str, int],
        existing_numbers: set[str],
        errors: list[RowError],
    ) -> None:
        if not asset_number:
            return
        if asset_number in seen_in_file:
            errors.append(
                RowError(
                    row=row_number,
                    field="asset_number",
                    code="DUPLICATE_IN_FILE",
                    message=(f"Duplicate asset_number '{asset_number}' " f"(also on row {seen_in_file[asset_number]})"),
                )
            )
        else:
            seen_in_file[asset_number] = row_number
        if asset_number in existing_numbers:
            errors.append(
                RowError(
                    row=row_number,
                    field="asset_number",
                    code="DUPLICATE_EXISTING",
                    message=f"asset_number '{asset_number}' already exists",
                )
            )

    def _resolve_owner(
        self,
        *,
        row_number: int,
        owner_email: str,
        owner_user_id_raw: str,
        users_by_email: dict[str, User],
        users_by_id: dict[int, User],
        errors: list[RowError],
    ) -> int | None:
        if owner_email and owner_user_id_raw:
            errors.append(
                RowError(
                    row=row_number,
                    field="owner_email",
                    code="OWNER_AMBIGUOUS",
                    message="Provide owner_email or owner_user_id, not both",
                )
            )
            return None
        if owner_email:
            user = users_by_email.get(owner_email.lower())
            if user is None:
                errors.append(
                    RowError(
                        row=row_number,
                        field="owner_email",
                        code="UNKNOWN_OWNER",
                        message=f"No user with email '{owner_email}' in tenant",
                    )
                )
                return None
            return user.id
        if owner_user_id_raw:
            try:
                parsed_id = self._parse_owner_user_id(owner_user_id_raw)
            except ValueError as exc:
                errors.append(
                    RowError(
                        row=row_number,
                        field="owner_user_id",
                        code="INVALID_OWNER_ID",
                        message=str(exc),
                    )
                )
                return None
            if parsed_id not in users_by_id:
                errors.append(
                    RowError(
                        row=row_number,
                        field="owner_user_id",
                        code="UNKNOWN_OWNER",
                        message=f"No user with id {parsed_id} in tenant",
                    )
                )
                return None
            return parsed_id
        return None

    @staticmethod
    def _resolve_assignment(
        *,
        row_number: int,
        location_name: str,
        vehicle_reg: str | None,
        location_map: dict[str, Location],
        errors: list[RowError],
    ) -> int | None:
        if location_name and vehicle_reg:
            errors.append(
                RowError(
                    row=row_number,
                    field="location_name",
                    code="ASSIGNMENT_XOR",
                    message="Set location_name or vehicle_reg, not both",
                )
            )
            return None
        if location_name:
            location = location_map.get(location_name.lower())
            if location is None:
                errors.append(
                    RowError(
                        row=row_number,
                        field="location_name",
                        code="UNKNOWN_LOCATION",
                        message=f"Unknown location '{location_name}'",
                    )
                )
                return None
            return location.id
        return None

    def _parse_status_and_expiry(
        self,
        *,
        row_number: int,
        status_raw: str,
        expiry_raw: str,
        errors: list[RowError],
    ) -> tuple[str, datetime | None]:
        try:
            status = AssetStatus(status_raw.lower()).value
        except ValueError:
            errors.append(
                RowError(
                    row=row_number,
                    field="status",
                    code="INVALID_STATUS",
                    message=f"Invalid status '{status_raw}'. Allowed: {', '.join(s.value for s in AssetStatus)}",
                )
            )
            status = AssetStatus.ACTIVE.value

        expiry_date: datetime | None = None
        if expiry_raw:
            try:
                expiry_date = self._parse_expiry(expiry_raw)
            except ValueError as exc:
                errors.append(
                    RowError(
                        row=row_number,
                        field="expiry_date",
                        code="INVALID_DATE",
                        message=str(exc),
                    )
                )
        return status, expiry_date

    async def validate_rows(
        self,
        rows: list[dict[str, str]],
        *,
        tenant_id: int,
        dry_run: bool = True,
    ) -> tuple[ImportValidationReport, list[ValidatedImportRow]]:
        type_map = await self._load_asset_types(tenant_id)
        location_map = await self._load_locations(tenant_id)

        emails: set[str] = set()
        owner_ids: set[int] = set()
        asset_numbers: list[str] = []
        for row in rows:
            if row.get("owner_email"):
                emails.add(row["owner_email"].lower())
            if row.get("owner_user_id"):
                try:
                    owner_ids.add(self._parse_owner_user_id(row["owner_user_id"]))
                except ValueError:
                    pass
            if row.get("asset_number"):
                asset_numbers.append(row["asset_number"])

        users_by_email = await self._load_users_by_email(emails, tenant_id)
        users_by_id = await self._load_users_by_id(owner_ids, tenant_id)
        existing_numbers = await self._existing_asset_numbers(set(asset_numbers), tenant_id)

        errors: list[RowError] = []
        validated: list[ValidatedImportRow] = []
        seen_in_file: dict[str, int] = {}

        for idx, row in enumerate(rows, start=2):  # row 1 = header
            row_errors: list[RowError] = []

            asset_number = (row.get("asset_number") or "").strip()
            name = (row.get("name") or "").strip()
            type_name = (row.get("type") or "").strip()

            owner_email = (row.get("owner_email") or "").strip()
            owner_user_id_raw = (row.get("owner_user_id") or "").strip()
            location_name = (row.get("location_name") or "").strip()
            vehicle_reg = (row.get("vehicle_reg") or "").strip() or None
            status_raw = (row.get("status") or "").strip() or AssetStatus.ACTIVE.value
            expiry_raw = (row.get("expiry_date") or "").strip()
            asset_type = self._validate_required_fields(
                row_number=idx,
                asset_number=asset_number,
                name=name,
                type_name=type_name,
                type_map=type_map,
                errors=row_errors,
            )
            self._validate_asset_number(
                row_number=idx,
                asset_number=asset_number,
                seen_in_file=seen_in_file,
                existing_numbers=existing_numbers,
                errors=row_errors,
            )
            owner_user_id = self._resolve_owner(
                row_number=idx,
                owner_email=owner_email,
                owner_user_id_raw=owner_user_id_raw,
                users_by_email=users_by_email,
                users_by_id=users_by_id,
                errors=row_errors,
            )
            location_id = self._resolve_assignment(
                row_number=idx,
                location_name=location_name,
                vehicle_reg=vehicle_reg,
                location_map=location_map,
                errors=row_errors,
            )
            status, expiry_date = self._parse_status_and_expiry(
                row_number=idx,
                status_raw=status_raw,
                expiry_raw=expiry_raw,
                errors=row_errors,
            )

            if row_errors:
                errors.extend(row_errors)
                continue

            assert asset_type is not None  # guarded above
            validated.append(
                ValidatedImportRow(
                    row=idx,
                    asset_number=asset_number,
                    name=name,
                    asset_type_id=asset_type.id,
                    make=(row.get("make") or "").strip() or None,
                    model=(row.get("model") or "").strip() or None,
                    serial_number=(row.get("serial") or "").strip() or None,
                    owner_user_id=owner_user_id,
                    location_id=location_id,
                    vehicle_reg=vehicle_reg,
                    expiry_date=expiry_date,
                    status=status,
                )
            )

        error_row_nums = {e.row for e in errors}
        preview = [
            {
                "row": v.row,
                "asset_number": v.asset_number,
                "name": v.name,
                "asset_type_id": v.asset_type_id,
                "make": v.make,
                "model": v.model,
                "serial_number": v.serial_number,
                "owner_user_id": v.owner_user_id,
                "location_id": v.location_id,
                "vehicle_reg": v.vehicle_reg,
                "expiry_date": v.expiry_date.isoformat() if v.expiry_date else None,
                "status": v.status,
            }
            for v in validated[:50]
        ]
        report = ImportValidationReport(
            dry_run=dry_run,
            total_rows=len(rows),
            valid_rows=len(validated),
            error_rows=len(error_row_nums),
            errors=errors,
            preview=preview,
        )
        return report, validated

    async def dry_run(self, content: str | bytes, *, tenant_id: int) -> ImportValidationReport:
        rows = self.parse_csv(content)
        report, _ = await self.validate_rows(rows, tenant_id=tenant_id, dry_run=True)
        return report

    async def commit(
        self,
        content: str | bytes,
        *,
        user_id: int,
        tenant_id: int,
    ) -> ImportCommitResult:
        rows = self.parse_csv(content)
        report, validated = await self.validate_rows(rows, tenant_id=tenant_id, dry_run=False)
        if not report.ok:
            raise ValidationError(
                "CSV import validation failed; fix row errors before commit",
                code="ASSET_IMPORT_VALIDATION_FAILED",
                details=report.to_dict(),
            )

        created_ids: list[int] = []
        for item in validated:
            asset = await self.assets.create_asset(
                item.to_create_dict(),
                user_id=user_id,
                tenant_id=tenant_id,
            )
            created_ids.append(asset.id)

        return ImportCommitResult(
            created_count=len(created_ids),
            created_asset_ids=created_ids,
            report=ImportValidationReport(
                dry_run=False,
                total_rows=report.total_rows,
                valid_rows=report.valid_rows,
                error_rows=0,
                errors=[],
                preview=report.preview,
            ),
        )
