"""Dry-run / commit import for H&S Excel Incident Model workbook."""

from __future__ import annotations

from datetime import timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.complaint import Complaint, ComplaintStatus, ComplaintType
from src.domain.models.incident import Incident, IncidentStatus, IncidentType
from src.domain.models.near_miss import NearMiss
from src.domain.models.rta import RoadTrafficCollision, RTASeverity, RTAStatus
from src.domain.services.hs_excel_import_parser import SOURCE_FORM_ID, parse_hs_workbook
from src.domain.services.reference_number import ReferenceNumberService


class HsExcelImportService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def dry_run(self, content: bytes, *, tenant_id: int) -> dict[str, Any]:
        parsed = parse_hs_workbook(content)
        counts = {"incident": 0, "near_miss": 0, "complaint": 0, "rta": 0, "skip_existing": 0}
        planned: list[dict[str, Any]] = []
        for row in parsed["incident_log"]:
            exists = await self._exists(tenant_id, row["external_key"], row["module"])
            if exists:
                counts["skip_existing"] += 1
                planned.append({**row, "action": "skip_existing", "event_date": row["event_date"].isoformat()})
                continue
            counts[row["module"]] += 1
            planned.append({**row, "action": "create", "event_date": row["event_date"].isoformat()})
        for row in parsed["rta_log"]:
            exists = await self._exists(tenant_id, row["external_key"], "rta")
            if exists:
                counts["skip_existing"] += 1
                planned.append({**row, "action": "skip_existing", "event_date": row["event_date"].isoformat()})
                continue
            counts["rta"] += 1
            planned.append({**row, "action": "create", "event_date": row["event_date"].isoformat()})
        return {
            "counts": counts,
            "warnings": parsed["warnings"],
            "rows": planned[:200],
            "total_rows": len(planned),
        }

    async def commit(self, content: bytes, *, tenant_id: int, user_id: Optional[int]) -> dict[str, Any]:
        report = await self.dry_run(content, tenant_id=tenant_id)
        parsed = parse_hs_workbook(content)
        created = {"incident": 0, "near_miss": 0, "complaint": 0, "rta": 0, "skipped": 0}
        for row in parsed["incident_log"]:
            if await self._exists(tenant_id, row["external_key"], row["module"]):
                created["skipped"] += 1
                continue
            await self._create_from_incident_log(row, tenant_id=tenant_id, user_id=user_id)
            created[row["module"]] += 1
        for row in parsed["rta_log"]:
            if await self._exists(tenant_id, row["external_key"], "rta"):
                created["skipped"] += 1
                continue
            await self._create_rta(row, tenant_id=tenant_id, user_id=user_id)
            created["rta"] += 1
        await self.db.commit()
        return {"created": created, "warnings": report["warnings"]}

    async def _exists(self, tenant_id: int, key: str, module: str) -> bool:
        if module == "incident":
            incident_rows = (
                await self.db.execute(
                    select(Incident).where(Incident.tenant_id == tenant_id, Incident.source_form_id == SOURCE_FORM_ID)
                )
            ).scalars()
            for incident in incident_rows:
                submission = incident.reporter_submission or {}
                if submission.get("external_key") == key:
                    return True
            return False
        if module == "near_miss":
            ref = f"HSXL-{key.replace('excel:', '').replace(':', '-').upper()}"
            found = await self.db.execute(
                select(NearMiss.id).where(NearMiss.tenant_id == tenant_id, NearMiss.reference_number == ref)
            )
            return found.scalar_one_or_none() is not None
        if module == "complaint":
            found = await self.db.execute(
                select(Complaint.id).where(Complaint.tenant_id == tenant_id, Complaint.external_ref == key)
            )
            return found.scalar_one_or_none() is not None
        if module == "rta":
            rta_rows = (
                await self.db.execute(
                    select(RoadTrafficCollision).where(
                        RoadTrafficCollision.tenant_id == tenant_id,
                        RoadTrafficCollision.source_form_id == SOURCE_FORM_ID,
                    )
                )
            ).scalars()
            for rta in rta_rows:
                submission = rta.reporter_submission or {}
                if submission.get("external_key") == key:
                    return True
            return False
        return False

    async def _create_from_incident_log(self, row: dict[str, Any], *, tenant_id: int, user_id: Optional[int]) -> None:
        module = row["module"]
        if module == "incident":
            await self._create_incident(row, tenant_id=tenant_id, user_id=user_id)
        elif module == "near_miss":
            await self._create_near_miss(row, tenant_id=tenant_id, user_id=user_id)
        elif module == "complaint":
            await self._create_complaint(row, tenant_id=tenant_id, user_id=user_id)
        elif module == "rta":
            await self._create_rta_from_incident_log(row, tenant_id=tenant_id, user_id=user_id)

    async def _create_incident(self, row: dict[str, Any], *, tenant_id: int, user_id: Optional[int]) -> None:
        from src.domain.services.contract_resolve import resolve_contract_id_by_code

        ref = await ReferenceNumberService.generate(self.db, "incident", Incident)
        body_parts = [row["body_part"]] if row.get("body_part") else None
        is_injury = bool(row.get("is_injury")) or bool(body_parts)
        contract_id = await resolve_contract_id_by_code(self.db, tenant_id=tenant_id, code=row.get("customer"))
        incident = Incident(
            tenant_id=tenant_id,
            reference_number=ref,
            title=(row["description"][:280] if row["description"] else "Imported injury"),
            description=row["description"],
            incident_type=IncidentType.INJURY if is_injury else IncidentType.OTHER,
            status=IncidentStatus.CLOSED if row["closed"] else IncidentStatus.REPORTED,
            incident_date=row["event_date"],
            reported_date=row["event_date"],
            location=row.get("role_location") or None,
            department=row.get("customer") or None,
            contract_id=contract_id,
            reporter_name=row["reporter"],
            people_involved=row.get("person_involved") or None,
            first_aid_given=bool(row.get("medical_assistance")),
            medical_assistance=("first-aider" if row.get("medical_assistance") else "none"),
            # Excel Emergency Services? is on RTA Log; Incident Log has no typed list.
            emergency_services=None,
            emergency_services_called=False,
            is_injury=is_injury,
            body_parts=body_parts,
            is_lti=bool(row.get("is_lti")),
            is_minor_injury=bool(row.get("is_minor_injury")),
            is_riddor_reportable=row.get("is_riddor"),
            # Injury Log "HiPo Near Miss?" maps to pSIF on injury incidents only.
            # Near-miss rows use NearMiss.is_hipo — see _create_near_miss.
            is_psif=bool(row.get("is_hipo")),
            source_type="api",
            source_form_id=SOURCE_FORM_ID,
            lessons_learnt=row.get("notes") or None,
            reporter_submission={
                "external_key": row["external_key"],
                "notes": row.get("notes"),
                "raw_type": row.get("raw_type"),
                "customer": row.get("customer"),
                "medical_assistance": ("first-aider" if row.get("medical_assistance") else "none"),
            },
            created_by_id=user_id,
            updated_by_id=user_id,
            closed_at=row["event_date"] if row["closed"] else None,
        )
        self.db.add(incident)

    async def _create_near_miss(self, row: dict[str, Any], *, tenant_id: int, user_id: Optional[int]) -> None:
        ref = f"HSXL-{row['external_key'].replace('excel:', '').replace(':', '-').upper()}"
        near_miss = NearMiss(
            tenant_id=tenant_id,
            reference_number=ref,
            reporter_name=row["reporter"],
            contract=row.get("customer") or "Unknown",
            location=row.get("role_location") or "Unknown",
            event_date=row["event_date"],
            description=row["description"],
            persons_involved=row.get("person_involved") or None,
            status="CLOSED" if row["closed"] else "REPORTED",
            source_form_id=SOURCE_FORM_ID,
            potential_consequences=row.get("notes") or None,
            lessons_learnt=row.get("notes") or None,
            is_hipo=bool(row.get("is_hipo")),
            created_by_id=user_id,
            updated_by_id=user_id,
            closed_at=row["event_date"] if row["closed"] else None,
        )
        self.db.add(near_miss)

    async def _create_complaint(self, row: dict[str, Any], *, tenant_id: int, user_id: Optional[int]) -> None:
        ref = await ReferenceNumberService.generate(self.db, "complaint", Complaint)
        complaint = Complaint(
            tenant_id=tenant_id,
            reference_number=ref,
            external_ref=row["external_key"],
            title=(row["description"][:280] if row["description"] else "Imported complaint"),
            description=row["description"] or row.get("notes") or "Imported from H&S Excel",
            complaint_type=ComplaintType.OTHER,
            status=ComplaintStatus.CLOSED if row["closed"] else ComplaintStatus.RECEIVED,
            received_date=row["event_date"],
            complainant_name=row["reporter"],
            complainant_company=row.get("customer") or None,
            source_type="api",
            source_form_id=SOURCE_FORM_ID,
            lessons_learnt=row.get("notes") or None,
            created_by_id=user_id,
            updated_by_id=user_id,
            closed_at=row["event_date"] if row["closed"] else None,
        )
        self.db.add(complaint)

    async def _create_rta_from_incident_log(
        self, row: dict[str, Any], *, tenant_id: int, user_id: Optional[int]
    ) -> None:
        await self._create_rta(
            {
                "external_key": row["external_key"],
                "event_date": row["event_date"],
                "employee": row.get("person_involved") or row["reporter"],
                "vehicle_reg": None,
                "time": None,
                "location": row.get("role_location") or "Unknown",
                "collision_type": None,
                "damage": row["description"],
                "drivable": None,
                "weather": None,
                "road_conditions": None,
                "emergency_services": None,
                "employee_injured": row.get("is_injury"),
                "is_lti": row.get("is_lti"),
                "is_riddor": row.get("is_riddor"),
                "notes": row.get("notes"),
                "closed": row.get("closed", False),
            },
            tenant_id=tenant_id,
            user_id=user_id,
        )

    async def _create_rta(self, row: dict[str, Any], *, tenant_id: int, user_id: Optional[int]) -> None:
        from src.domain.services.rta_injury_fields import (
            derive_third_party_injured,
            seed_third_parties_for_injury,
        )

        ref = await ReferenceNumberService.generate(self.db, "rta", RoadTrafficCollision)
        closed = bool(row.get("closed"))
        event_date = row["event_date"]
        if event_date.tzinfo is None:
            event_date = event_date.replace(tzinfo=timezone.utc)
        # Excel column is third_party_injury (Y/N); platform field is third_party_injured.
        tp_injured = bool(row.get("third_party_injury")) if row.get("third_party_injury") is not None else None
        if tp_injured is None and row.get("third_party_injured") is not None:
            tp_injured = bool(row.get("third_party_injured"))
        third_parties = seed_third_parties_for_injury(None, injured=bool(tp_injured))
        rta = RoadTrafficCollision(
            tenant_id=tenant_id,
            reference_number=ref,
            title=f"RTA — {row.get('employee') or 'Unknown'} — {row.get('vehicle_reg') or 'no reg'}",
            description=row.get("damage") or row.get("notes") or "Imported RTA",
            severity=RTASeverity.MINOR_INJURY if row.get("employee_injured") else RTASeverity.DAMAGE_ONLY,
            status=RTAStatus.CLOSED if closed else RTAStatus.REPORTED,
            collision_date=event_date,
            collision_time=row.get("time") or None,
            reported_date=event_date,
            location=row.get("location") or "Unknown",
            weather_conditions=row.get("weather") or None,
            road_conditions=row.get("road_conditions") or None,
            company_vehicle_registration=row.get("vehicle_reg") or None,
            company_vehicle_damage=row.get("damage") or None,
            driver_name=row.get("employee") or None,
            driver_injured=bool(row.get("employee_injured")),
            third_party_injured=derive_third_party_injured(third_parties, explicit=tp_injured),
            third_parties=third_parties,
            police_attended=bool(row.get("emergency_services")),
            collision_type=row.get("collision_type"),
            vehicle_drivable=row.get("drivable"),
            is_lti=bool(row.get("is_lti")),
            is_riddor_reportable=row.get("is_riddor"),
            source_form_id=SOURCE_FORM_ID,
            lessons_learnt=row.get("notes") or None,
            reporter_submission={"external_key": row["external_key"], "notes": row.get("notes")},
            created_by_id=user_id,
            updated_by_id=user_id,
            closed_at=event_date if closed else None,
        )
        self.db.add(rta)
