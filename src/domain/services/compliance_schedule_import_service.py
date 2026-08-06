"""CSV bulk import for Compliance Schedule catalogue activations (Wave 3).

Dry-run validates every row and returns a structured report.
Commit re-validates then activates via ComplianceScheduleService.activate_catalogue_template
so location/owner/duplicate/inactive-template guards stay single-sourced.

Location is required: org-wide activations do not cover a site (coverage gaps).
"""

from __future__ import annotations

import csv
import dataclasses
import io
from datetime import date, datetime, timezone
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.exceptions import BadRequestError, ConflictError, NotFoundError, ValidationError
from src.domain.models.location import Location
from src.domain.services.compliance_schedule_service import ComplianceScheduleService

MAX_ROWS = 500
REQUIRED_HEADERS = frozenset({"template_key"})
OPTIONAL_HEADERS = frozenset(
    {
        "location_id",
        "location_name",
        "next_due_date",
        "last_completed_at",
        "owner_id",
    }
)
HEADER_ALIASES: dict[str, str] = {
    "template_key": "template_key",
    "template": "template_key",
    "catalogue_key": "template_key",
    "location_id": "location_id",
    "location": "location_name",
    "location_name": "location_name",
    "next_due_date": "next_due_date",
    "due_date": "next_due_date",
    "last_completed_at": "last_completed_at",
    "completed_at": "last_completed_at",
    "owner_id": "owner_id",
    "owner": "owner_id",
}

_DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y")
_DT_FORMATS = (
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%d %H:%M:%S",
)


@dataclasses.dataclass(frozen=True)
class RowError:
    row: int
    code: str
    message: str
    field: str | None = None


@dataclasses.dataclass
class ValidatedImportRow:
    row: int
    template_key: str
    location_id: int
    location_name: str
    title: str
    next_due_date: Optional[date] = None
    last_completed_at: Optional[datetime] = None
    owner_id: Optional[int] = None


@dataclasses.dataclass
class ImportValidationReport:
    dry_run: bool
    total_rows: int
    valid_rows: int
    error_rows: int
    creates: int
    skips: int
    ok: bool
    errors: list[RowError]
    preview: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "dry_run": self.dry_run,
            "total_rows": self.total_rows,
            "valid_rows": self.valid_rows,
            "error_rows": self.error_rows,
            "creates": self.creates,
            "skips": self.skips,
            "ok": self.ok,
            "errors": [{"row": e.row, "code": e.code, "message": e.message, "field": e.field} for e in self.errors],
            "preview": self.preview,
        }


@dataclasses.dataclass
class ImportCommitResult:
    created_count: int
    created_requirement_ids: list[int]
    report: ImportValidationReport

    def to_dict(self) -> dict[str, Any]:
        return {
            "created_count": self.created_count,
            "created_requirement_ids": self.created_requirement_ids,
            "report": self.report.to_dict(),
        }


def _norm_header(raw: str) -> str:
    key = (raw or "").strip().lower().replace("-", "_")
    key = " ".join(key.split())
    return HEADER_ALIASES.get(key, HEADER_ALIASES.get(key.replace(" ", "_"), key.replace(" ", "_")))


def _parse_date(value: str) -> date:
    text = value.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unparseable date: {value!r}")


def _parse_datetime(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+0000"
    for fmt in _DT_FORMATS:
        try:
            parsed = datetime.strptime(text, fmt)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            continue
    # Date-only completed_at → start of that UTC day
    try:
        return datetime.combine(_parse_date(value), datetime.min.time(), tzinfo=timezone.utc)
    except ValueError as exc:
        raise ValueError(f"Unparseable datetime: {value!r}") from exc


def _parse_csv(content: bytes) -> list[dict[str, str]]:
    if not content or not content.strip():
        raise BadRequestError("CSV file is empty")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise BadRequestError("CSV must be UTF-8") from exc
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise BadRequestError("CSV has no header row")
    mapped = [_norm_header(h) for h in reader.fieldnames if h is not None]
    if "template_key" not in mapped:
        raise BadRequestError("CSV must include a template_key column")
    rows: list[dict[str, str]] = []
    for raw in reader:
        if raw is None:
            continue
        normalised: dict[str, str] = {}
        for header, value in raw.items():
            if header is None:
                continue
            key = _norm_header(header)
            if key in REQUIRED_HEADERS or key in OPTIONAL_HEADERS:
                normalised[key] = (value or "").strip()
        # Skip blank lines
        if not any(normalised.values()):
            continue
        rows.append(normalised)
    if len(rows) > MAX_ROWS:
        raise BadRequestError(f"CSV exceeds {MAX_ROWS} data rows")
    return rows


class ComplianceScheduleImportService:
    """Validate and commit catalogue-activate CSV imports."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.cs = ComplianceScheduleService(db)

    async def dry_run(self, content: bytes, *, tenant_id: int, default_owner_id: int) -> ImportValidationReport:
        rows = _parse_csv(content)
        report, _ = await self._validate(rows, tenant_id=tenant_id, default_owner_id=default_owner_id, dry_run=True)
        return report

    async def commit(
        self,
        content: bytes,
        *,
        tenant_id: int,
        user_id: int,
        default_owner_id: Optional[int] = None,
    ) -> ImportCommitResult:
        rows = _parse_csv(content)
        owner_default = default_owner_id if default_owner_id is not None else user_id
        report, validated = await self._validate(
            rows, tenant_id=tenant_id, default_owner_id=owner_default, dry_run=False
        )
        if not report.ok:
            raise ValidationError(
                "Compliance Schedule import has row errors",
                code="VALIDATION_ERROR",
                details=report.to_dict(),
            )
        created_ids: list[int] = []
        for item in validated:
            requirement = await self.cs.activate_catalogue_template(
                item.template_key,
                tenant_id=tenant_id,
                user_id=user_id,
                location_id=item.location_id,
                next_due_date=item.next_due_date,
                last_completed_at=item.last_completed_at,
                owner_id=item.owner_id,
            )
            created_ids.append(requirement.id)
        report.dry_run = False
        return ImportCommitResult(
            created_count=len(created_ids),
            created_requirement_ids=created_ids,
            report=report,
        )

    async def _validate(
        self,
        rows: list[dict[str, str]],
        *,
        tenant_id: int,
        default_owner_id: int,
        dry_run: bool,
    ) -> tuple[ImportValidationReport, list[ValidatedImportRow]]:
        errors: list[RowError] = []
        validated: list[ValidatedImportRow] = []
        preview: list[dict[str, Any]] = []
        seen_keys: set[tuple[str, int]] = set()

        for index, raw in enumerate(rows, start=2):  # header is row 1
            item, row_errors = await self._validate_row(
                index,
                raw,
                tenant_id=tenant_id,
                default_owner_id=default_owner_id,
                seen_keys=seen_keys,
            )
            if row_errors:
                errors.extend(row_errors)
                continue
            assert item is not None
            validated.append(item)
            preview.append(
                {
                    "row": item.row,
                    "action": "create",
                    "template_key": item.template_key,
                    "location_id": item.location_id,
                    "location_name": item.location_name,
                    "title": item.title,
                    "next_due_date": item.next_due_date.isoformat() if item.next_due_date else None,
                    "owner_id": item.owner_id,
                }
            )

        report = ImportValidationReport(
            dry_run=dry_run,
            total_rows=len(rows),
            valid_rows=len(validated),
            error_rows=len({e.row for e in errors}),
            creates=len(validated),
            skips=0,
            ok=len(errors) == 0 and len(rows) > 0,
            errors=errors,
            preview=preview,
        )
        if len(rows) == 0:
            report.ok = False
            report.errors.append(RowError(1, "REQUIRED", "CSV has no data rows", None))
            report.error_rows = 1
        return report, validated

    async def _validate_row(
        self,
        index: int,
        raw: dict[str, str],
        *,
        tenant_id: int,
        default_owner_id: int,
        seen_keys: set[tuple[str, int]],
    ) -> tuple[Optional[ValidatedImportRow], list[RowError]]:
        row_errors: list[RowError] = []
        template_key = (raw.get("template_key") or "").strip()
        location_id_raw = (raw.get("location_id") or "").strip()
        location_name_raw = (raw.get("location_name") or "").strip()

        if not template_key:
            row_errors.append(RowError(index, "REQUIRED", "template_key is required", "template_key"))
        row_errors.extend(self._location_required_errors(index, location_id_raw, location_name_raw))

        template = await self._resolve_template(index, template_key, row_errors)
        location_id, location_name = await self._resolve_location(
            index, location_id_raw, location_name_raw, tenant_id=tenant_id, row_errors=row_errors
        )
        next_due = self._resolve_due(index, (raw.get("next_due_date") or "").strip(), row_errors)
        last_completed = self._resolve_completed(index, (raw.get("last_completed_at") or "").strip(), row_errors)
        owner_id = await self._resolve_owner(
            index,
            (raw.get("owner_id") or "").strip(),
            tenant_id=tenant_id,
            default_owner_id=default_owner_id,
            row_errors=row_errors,
        )

        if template is not None and location_id is not None and not row_errors:
            await self._check_duplicates(
                index,
                template_key,
                template.id,
                location_id,
                tenant_id=tenant_id,
                seen_keys=seen_keys,
                row_errors=row_errors,
            )

        if row_errors or template is None or location_id is None:
            return None, row_errors

        return (
            ValidatedImportRow(
                row=index,
                template_key=template_key,
                location_id=location_id,
                location_name=location_name,
                title=template.title,
                next_due_date=next_due,
                last_completed_at=last_completed,
                owner_id=owner_id,
            ),
            [],
        )

    @staticmethod
    def _location_required_errors(index: int, location_id_raw: str, location_name_raw: str) -> list[RowError]:
        errors: list[RowError] = []
        if location_id_raw and location_name_raw:
            errors.append(
                RowError(
                    index,
                    "LOCATION_XOR",
                    "Provide location_id or location_name, not both",
                    "location_id",
                )
            )
        if not location_id_raw and not location_name_raw:
            errors.append(
                RowError(
                    index,
                    "REQUIRED",
                    "location_id or location_name is required (org-wide rows are not allowed)",
                    "location_id",
                )
            )
        return errors

    async def _resolve_template(self, index: int, template_key: str, row_errors: list[RowError]) -> Any:
        if not template_key or any(e.field == "template_key" for e in row_errors):
            return None
        try:
            return await self.cs._get_template_by_key(template_key)
        except NotFoundError:
            row_errors.append(
                RowError(
                    index,
                    "TEMPLATE_NOT_FOUND",
                    f"Catalogue template '{template_key}' not found or inactive",
                    "template_key",
                )
            )
            return None

    async def _resolve_location(
        self,
        index: int,
        location_id_raw: str,
        location_name_raw: str,
        *,
        tenant_id: int,
        row_errors: list[RowError],
    ) -> tuple[Optional[int], str]:
        if any(e.code == "LOCATION_XOR" for e in row_errors):
            return None, ""
        if location_id_raw:
            try:
                location_id = int(location_id_raw)
            except ValueError:
                row_errors.append(
                    RowError(index, "LOCATION_NOT_FOUND", "location_id must be an integer", "location_id")
                )
                return None, ""
            loc = await self._get_location_by_id(location_id, tenant_id=tenant_id)
            if loc is None:
                row_errors.append(
                    RowError(index, "LOCATION_NOT_FOUND", f"Location {location_id} not found", "location_id")
                )
                return None, ""
            return location_id, loc.name or ""
        if location_name_raw:
            matches = await self._find_locations_by_name(location_name_raw, tenant_id=tenant_id)
            if len(matches) == 0:
                row_errors.append(
                    RowError(
                        index,
                        "LOCATION_NOT_FOUND",
                        f"Location name {location_name_raw!r} not found",
                        "location_name",
                    )
                )
                return None, ""
            if len(matches) > 1:
                row_errors.append(
                    RowError(
                        index,
                        "AMBIGUOUS_LOCATION",
                        f"Location name {location_name_raw!r} matches {len(matches)} locations",
                        "location_name",
                    )
                )
                return None, ""
            return matches[0].id, matches[0].name or location_name_raw
        return None, ""

    @staticmethod
    def _resolve_due(index: int, due_raw: str, row_errors: list[RowError]) -> Optional[date]:
        if not due_raw:
            return None
        try:
            return _parse_date(due_raw)
        except ValueError:
            row_errors.append(RowError(index, "INVALID_DATE", f"Invalid next_due_date: {due_raw}", "next_due_date"))
            return None

    @staticmethod
    def _resolve_completed(index: int, completed_raw: str, row_errors: list[RowError]) -> Optional[datetime]:
        if not completed_raw:
            return None
        try:
            return _parse_datetime(completed_raw)
        except ValueError:
            row_errors.append(
                RowError(
                    index,
                    "INVALID_DATE",
                    f"Invalid last_completed_at: {completed_raw}",
                    "last_completed_at",
                )
            )
            return None

    async def _resolve_owner(
        self,
        index: int,
        owner_raw: str,
        *,
        tenant_id: int,
        default_owner_id: int,
        row_errors: list[RowError],
    ) -> Optional[int]:
        if not owner_raw:
            return default_owner_id
        try:
            owner_id = int(owner_raw)
        except ValueError:
            row_errors.append(RowError(index, "OWNER_NOT_FOUND", "owner_id must be an integer", "owner_id"))
            return None
        try:
            await self.cs._assert_owner_in_tenant(owner_id, tenant_id=tenant_id)
        except NotFoundError:
            row_errors.append(RowError(index, "OWNER_NOT_FOUND", f"User {owner_id} not found", "owner_id"))
            return None
        return owner_id

    async def _check_duplicates(
        self,
        index: int,
        template_key: str,
        template_id: int,
        location_id: int,
        *,
        tenant_id: int,
        seen_keys: set[tuple[str, int]],
        row_errors: list[RowError],
    ) -> None:
        pair = (template_key, location_id)
        if pair in seen_keys:
            row_errors.append(
                RowError(
                    index,
                    "DUPLICATE_IN_FILE",
                    f"Duplicate {template_key} for location {location_id} in this file",
                    "template_key",
                )
            )
            return
        seen_keys.add(pair)
        try:
            await self.cs._assert_template_not_already_active(
                template_id,
                tenant_id=tenant_id,
                location_id=location_id,
            )
        except ConflictError as exc:
            row_errors.append(RowError(index, "DUPLICATE_ENTITY", str(exc), "template_key"))

    async def _get_location_by_id(self, location_id: int, *, tenant_id: int) -> Optional[Location]:
        result = await self.db.execute(
            select(Location).where(Location.id == location_id, Location.tenant_id == tenant_id)
        )
        return result.scalar_one_or_none()

    async def _find_locations_by_name(self, name: str, *, tenant_id: int) -> list[Location]:
        result = await self.db.execute(
            select(Location).where(
                Location.tenant_id == tenant_id,
                func.lower(Location.name) == name.strip().lower(),
            )
        )
        return list(result.scalars().all())
