"""Shared model update utilities for API routes."""

from datetime import datetime, timezone

from pydantic import BaseModel


def apply_updates(
    entity: object,
    schema: BaseModel,
    set_updated_at: bool = True,
    *,
    exclude: set[str] | None = None,
) -> dict:
    """Apply partial updates from a Pydantic schema to a SQLAlchemy model.

    Returns the dict of fields that were actually updated.
    """
    update_data = schema.model_dump(exclude_unset=True, exclude=exclude)
    for key, value in update_data.items():
        setattr(entity, key, value)
    if set_updated_at and hasattr(entity, "updated_at"):
        entity.updated_at = datetime.now(timezone.utc)
    return update_data
