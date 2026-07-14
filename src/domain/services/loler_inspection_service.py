"""Read-focused inspection history for LOLER-managed safety assets."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.loler import LOLERExamination


@dataclass(frozen=True)
class InspectionHistoryItem:
    """A certificate-oriented view of one LOLER examination."""

    id: int
    reference_number: str | None
    examination_type: str
    examination_date: datetime
    next_due_date: datetime | None
    safe_to_operate: bool
    competent_person_name: str
    status: str


@dataclass(frozen=True)
class InspectionHistory:
    """Inspection records and the derived compliance status for one asset."""

    asset_id: int
    next_due_date: datetime | None
    status: str
    items: list[InspectionHistoryItem]


def inspection_status(
    *,
    next_due_date: datetime | None,
    safe_to_operate: bool = True,
    now: datetime | None = None,
) -> str:
    """Return a stable status suitable for asset-date and history surfaces."""

    if not safe_to_operate:
        return "unsafe"
    if next_due_date is None:
        return "review_required"

    reference = now or datetime.now(timezone.utc)
    due = next_due_date
    if due.tzinfo is None:
        due = due.replace(tzinfo=timezone.utc)
    if due < reference:
        return "overdue"
    if due <= reference + timedelta(days=30):
        return "due_soon"
    return "compliant"


class LOLERInspectionService:
    """Queries tenant-scoped LOLER examination history without mutations."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_asset_history(self, *, asset_id: int, tenant_id: int) -> InspectionHistory:
        """Return latest-first certificate history and the current asset status."""

        result = await self.db.execute(
            select(LOLERExamination)
            .where(
                LOLERExamination.asset_id == asset_id,
                or_(
                    LOLERExamination.tenant_id == tenant_id,
                    LOLERExamination.tenant_id.is_(None),
                ),
            )
            .order_by(LOLERExamination.examination_date.desc())
        )
        examinations = list(result.scalars().all())
        items = [
            InspectionHistoryItem(
                id=examination.id,
                reference_number=examination.reference_number,
                examination_type=examination.examination_type.value,
                examination_date=examination.examination_date,
                next_due_date=examination.next_examination_due,
                safe_to_operate=examination.safe_to_operate,
                competent_person_name=examination.competent_person_name,
                status=inspection_status(
                    next_due_date=examination.next_examination_due,
                    safe_to_operate=examination.safe_to_operate,
                ),
            )
            for examination in examinations
        ]
        latest = items[0] if items else None
        return InspectionHistory(
            asset_id=asset_id,
            next_due_date=latest.next_due_date if latest else None,
            status=latest.status if latest else "not_recorded",
            items=items,
        )
