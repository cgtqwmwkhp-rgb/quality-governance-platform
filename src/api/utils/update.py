"""Shared model update utilities for API routes."""

from datetime import datetime

from pydantic import BaseModel


def apply_updates(entity: object, schema: BaseModel, set_updated_at: bool = True) -> dict:
    """Apply partial updates from a Pydantic schema to a SQLAlchemy model.
    
    Returns the dict of fields that were actually updated.
    """
    update_data = schema.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(entity, key, value)
    if set_updated_at and hasattr(entity, "updated_at"):
        entity.updated_at = datetime.utcnow()
    return update_data
