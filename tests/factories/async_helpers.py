"""
Async DB helpers for factory-boy factories.

Usage in async integration tests:

    from tests.factories.async_helpers import create_async

    async def test_something(db_session):
        user = await create_async(db_session, UserFactory, email="custom@example.com")
        incident = await create_async(db_session, IncidentFactory, reporter_id=user.id)
"""

from typing import TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


async def create_async(session: AsyncSession, factory_class, **overrides):
    """Build a factory instance and persist it via an async session."""
    instance = factory_class.build(**overrides)
    session.add(instance)
    await session.flush()
    await session.refresh(instance)
    return instance


async def create_batch_async(session: AsyncSession, factory_class, size: int, **overrides):
    """Build and persist multiple instances."""
    instances = factory_class.build_batch(size, **overrides)
    session.add_all(instances)
    await session.flush()
    for inst in instances:
        await session.refresh(inst)
    return instances
