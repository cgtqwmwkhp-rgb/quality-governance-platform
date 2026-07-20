"""Unified assurance certificate shelf — expiry-driven readiness aggregation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.compliance_automation import Certificate
from src.domain.models.document import Document
from src.domain.models.planet_mark import CarbonReportingYear
from src.domain.models.uvdb_achilles import UVDBAudit

DEFAULT_DUE_SOON_DAYS = 30


def _to_iso(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value else None


def _aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def compute_readiness_status(
    expiry_date: Optional[datetime],
    *,
    due_soon_days: int = DEFAULT_DUE_SOON_DAYS,
    now: Optional[datetime] = None,
) -> str:
    """Return valid | due_soon | expired | unknown from an expiry timestamp."""
    if expiry_date is None:
        return "unknown"
    reference = now or datetime.now(timezone.utc)
    expiry = _aware(expiry_date)
    if expiry < reference:
        return "expired"
    if expiry <= reference + timedelta(days=due_soon_days):
        return "due_soon"
    return "valid"


def _build_item(
    *,
    shelf_key: str,
    name: str,
    scheme: str,
    source: str,
    expiry_date: Optional[datetime],
    due_soon_days: int,
    issuing_body: Optional[str] = None,
    reference_number: Optional[str] = None,
    detail_path: Optional[str] = None,
    library_path: Optional[str] = None,
    external_url: Optional[str] = None,
    is_external_sor: bool = False,
    is_critical: bool = False,
    metadata: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    readiness = compute_readiness_status(expiry_date, due_soon_days=due_soon_days)
    return {
        "shelf_key": shelf_key,
        "name": name,
        "scheme": scheme,
        "source": source,
        "issuing_body": issuing_body,
        "reference_number": reference_number,
        "expiry_date": _to_iso(expiry_date),
        "readiness_status": readiness,
        "is_critical": is_critical,
        "is_external_sor": is_external_sor,
        "detail_path": detail_path,
        "library_path": library_path,
        "external_url": external_url,
        "metadata": metadata or {},
    }


class AssuranceCertShelfService:
    """Aggregate assurance certificates from register, schemes, and Library masters."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_shelf(
        self,
        *,
        tenant_id: int,
        scheme: Optional[str] = None,
        readiness_status: Optional[str] = None,
        due_soon_days: int = DEFAULT_DUE_SOON_DAYS,
    ) -> dict[str, Any]:
        items: list[dict[str, Any]] = []
        items.extend(await self._from_register(tenant_id=tenant_id, due_soon_days=due_soon_days))
        items.extend(await self._from_planet_mark(tenant_id=tenant_id, due_soon_days=due_soon_days))
        items.extend(await self._from_uvdb(tenant_id=tenant_id, due_soon_days=due_soon_days))
        items.extend(await self._from_library_documents(tenant_id=tenant_id, due_soon_days=due_soon_days))

        if scheme:
            items = [item for item in items if item["scheme"] == scheme]
        if readiness_status:
            items = [item for item in items if item["readiness_status"] == readiness_status]

        items.sort(key=lambda item: (item.get("expiry_date") or "9999-12-31", item["name"].lower()))
        summary = self._build_summary(items)
        return {
            "items": items,
            "total": len(items),
            "summary": summary,
            "due_soon_days": due_soon_days,
        }

    async def _from_register(self, *, tenant_id: int, due_soon_days: int) -> list[dict[str, Any]]:
        result = await self.db.execute(
            select(Certificate).where(or_(Certificate.tenant_id == tenant_id, Certificate.tenant_id.is_(None)))
        )
        items: list[dict[str, Any]] = []
        for certificate in result.scalars().all():
            library_path = None
            external_url = certificate.document_url
            if external_url and external_url.startswith("/documents/"):
                library_path = external_url
                external_url = None
            items.append(
                _build_item(
                    shelf_key=f"register:{certificate.id}",
                    name=certificate.name,
                    scheme="register",
                    source="compliance_register",
                    expiry_date=certificate.expiry_date,
                    due_soon_days=due_soon_days,
                    issuing_body=certificate.issuing_body,
                    reference_number=certificate.reference_number,
                    detail_path="/compliance-automation",
                    library_path=library_path,
                    external_url=external_url,
                    is_external_sor=bool(external_url),
                    is_critical=certificate.is_critical,
                    metadata={
                        "certificate_type": certificate.certificate_type,
                        "entity_type": certificate.entity_type,
                        "entity_name": certificate.entity_name,
                        "primary_evidence_asset_id": certificate.primary_evidence_asset_id,
                    },
                )
            )
        return items

    async def _from_planet_mark(self, *, tenant_id: int, due_soon_days: int) -> list[dict[str, Any]]:
        result = await self.db.execute(
            select(CarbonReportingYear).where(
                or_(CarbonReportingYear.tenant_id == tenant_id, CarbonReportingYear.tenant_id.is_(None)),
                CarbonReportingYear.expiry_date.is_not(None),
            )
        )
        items: list[dict[str, Any]] = []
        for year in result.scalars().all():
            items.append(
                _build_item(
                    shelf_key=f"planet_mark:{year.id}",
                    name=f"Planet Mark {year.year_label}",
                    scheme="planet_mark",
                    source="planet_mark",
                    expiry_date=year.expiry_date,
                    due_soon_days=due_soon_days,
                    issuing_body=year.certifying_body,
                    reference_number=year.certificate_number,
                    detail_path="/planet-mark",
                    is_external_sor=True,
                    metadata={
                        "year_id": year.id,
                        "year_label": year.year_label,
                        "certification_status": year.certification_status,
                    },
                )
            )
        return items

    async def _from_uvdb(self, *, tenant_id: int, due_soon_days: int) -> list[dict[str, Any]]:
        result = await self.db.execute(
            select(UVDBAudit).where(or_(UVDBAudit.tenant_id == tenant_id, UVDBAudit.tenant_id.is_(None)))
        )
        items: list[dict[str, Any]] = []
        for audit in result.scalars().all():
            expiry_date = audit.expiry_date or audit.next_audit_due
            if expiry_date is None:
                continue
            items.append(
                _build_item(
                    shelf_key=f"uvdb:{audit.id}",
                    name=f"UVDB {audit.audit_reference}",
                    scheme="uvdb_achilles",
                    source="uvdb_achilles",
                    expiry_date=expiry_date,
                    due_soon_days=due_soon_days,
                    issuing_body=audit.auditor_organization or "Achilles UVDB",
                    reference_number=audit.audit_reference,
                    detail_path="/uvdb",
                    is_external_sor=True,
                    metadata={
                        "audit_id": audit.id,
                        "company_name": audit.company_name,
                        "audit_type": audit.audit_type,
                        "status": audit.status,
                        "expiry_date": _to_iso(audit.expiry_date),
                        "next_audit_due": _to_iso(audit.next_audit_due),
                    },
                )
            )
        return items

    async def _from_library_documents(self, *, tenant_id: int, due_soon_days: int) -> list[dict[str, Any]]:
        result = await self.db.execute(
            select(Document).where(
                Document.tenant_id == tenant_id,
                Document.expiry_date.is_not(None),
                Document.is_active == True,  # noqa: E712
            )
        )
        items: list[dict[str, Any]] = []
        for document in result.scalars().all():
            items.append(
                _build_item(
                    shelf_key=f"library:{document.id}",
                    name=document.title,
                    scheme="library",
                    source="governance_library",
                    expiry_date=document.expiry_date,
                    due_soon_days=due_soon_days,
                    reference_number=document.pel_doc_ref or document.reference_number,
                    detail_path=f"/documents/{document.id}",
                    library_path=f"/documents/{document.id}",
                    is_external_sor=False,
                    is_critical=document.is_statutory,
                    metadata={
                        "document_id": document.id,
                        "is_statutory": document.is_statutory,
                    },
                )
            )
        return items

    @staticmethod
    def _build_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
        valid = due_soon = expired = unknown = 0
        by_scheme: dict[str, int] = {}
        for item in items:
            status = item["readiness_status"]
            if status == "valid":
                valid += 1
            elif status == "due_soon":
                due_soon += 1
            elif status == "expired":
                expired += 1
            else:
                unknown += 1
            scheme = str(item["scheme"])
            by_scheme[scheme] = by_scheme.get(scheme, 0) + 1
        return {
            "valid": valid,
            "due_soon": due_soon,
            "expired": expired,
            "unknown": unknown,
            "by_scheme": by_scheme,
        }
