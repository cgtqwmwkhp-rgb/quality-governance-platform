"""Promote investigation lessons text onto the linked case record."""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.complaint import Complaint
from src.domain.models.incident import Incident
from src.domain.models.near_miss import NearMiss
from src.domain.models.rta import RoadTrafficCollision


def extract_lessons_text(data: Optional[dict[str, Any]]) -> Optional[str]:
    """Pull lessons narrative from investigation.data (section_7 or summary)."""
    if not isinstance(data, dict):
        return None
    sections = data.get("sections")
    if isinstance(sections, dict):
        for key in ("section_7_lessons", "section_7_management_system_review", "lessons_learned", "lessons_learnt"):
            block = sections.get(key)
            if isinstance(block, dict):
                for field in ("content", "notes", "text", "summary", "value"):
                    val = block.get(field)
                    if isinstance(val, str) and val.strip():
                        return val.strip()
            elif isinstance(block, str) and block.strip():
                return block.strip()
    for field in ("lessons_learnt", "lessons_learned", "conclusion", "findings"):
        val = data.get(field)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


async def promote_lessons_to_case(
    db: AsyncSession,
    *,
    entity_type: Optional[str],
    entity_id: Optional[int],
    lessons_text: str,
    overwrite: bool = False,
) -> bool:
    """Write lessons onto the case when empty (or overwrite=True). Returns True if updated."""
    if not entity_type or not entity_id or not lessons_text.strip():
        return False
    text = lessons_text.strip()
    model_map = {
        "incident": Incident,
        "reporting_incident": Incident,
        "near_miss": NearMiss,
        "rta": RoadTrafficCollision,
        "road_traffic_collision": RoadTrafficCollision,
        "complaint": Complaint,
    }
    model = model_map.get(str(entity_type).lower())
    if model is None:
        return False
    row = (await db.execute(select(model).where(model.id == entity_id))).scalar_one_or_none()
    if row is None:
        return False
    existing = getattr(row, "lessons_learnt", None)
    if existing and str(existing).strip() and not overwrite:
        return False
    row.lessons_learnt = text
    await db.flush()
    return True
