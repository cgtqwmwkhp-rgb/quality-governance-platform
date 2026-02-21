"""Shared query filter utilities for common patterns across routes."""

from sqlalchemy import Select, or_
from sqlalchemy.orm import InstrumentedAttribute


def apply_search_filter(
    query: Select,
    search: str | None,
    *fields: InstrumentedAttribute,
) -> Select:
    """Apply a case-insensitive search filter across multiple fields.

    Usage:
        query = apply_search_filter(query, search_term, Model.name, Model.description)
    """
    if not search:
        return query
    pattern = f"%{search}%"
    return query.where(or_(*(field.ilike(pattern) for field in fields)))


def apply_status_filter(
    query: Select,
    status_value: str | None,
    field: InstrumentedAttribute,
) -> Select:
    """Apply an exact status filter."""
    if status_value is None:
        return query
    return query.where(field == status_value)


def apply_date_range_filter(
    query: Select,
    start_date=None,
    end_date=None,
    field: InstrumentedAttribute = None,
) -> Select:
    """Apply a date range filter on a field."""
    if field is None:
        return query
    if start_date:
        query = query.where(field >= start_date)
    if end_date:
        query = query.where(field <= end_date)
    return query
