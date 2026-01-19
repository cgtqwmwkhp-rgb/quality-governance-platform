"""Pytest configuration and fixtures."""

import asyncio

# Test database URL (use Postgres if available, fallback to SQLite)
import os
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.core.security import create_access_token, get_password_hash
from src.domain.models.user import Role, User
from src.infrastructure.database import Base, get_db
from src.main import app

TEST_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def test_engine():
    """Create a test database engine."""
    # Configure engine based on database type
    engine_kwargs = {}
    if "sqlite" in TEST_DATABASE_URL:
        engine_kwargs["connect_args"] = {"check_same_thread": False}
        engine_kwargs["poolclass"] = StaticPool

    engine = create_async_engine(TEST_DATABASE_URL, **engine_kwargs)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def test_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    async_session = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def client(test_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create a test client with overridden database dependency."""

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield test_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    # Enable follow_redirects to handle FastAPI's redirect_slashes=True (307 redirects)
    async with AsyncClient(transport=transport, base_url="http://test", follow_redirects=True) as client:
        yield client

    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def test_user(test_session: AsyncSession) -> User:
    """Create a test user."""
    user = User(
        email="test@example.com",
        hashed_password=get_password_hash("testpassword123"),
        first_name="Test",
        last_name="User",
        is_active=True,
        is_superuser=False,
    )
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)
    return user


@pytest_asyncio.fixture(scope="function")
async def test_superuser(test_session: AsyncSession) -> User:
    """Create a test superuser."""
    user = User(
        email="admin@example.com",
        hashed_password=get_password_hash("adminpassword123"),
        first_name="Admin",
        last_name="User",
        is_active=True,
        is_superuser=True,
    )
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)
    return user


@pytest.fixture
def user_token(test_user: User) -> str:
    """Create an access token for the test user."""
    return create_access_token(subject=test_user.id)


@pytest.fixture
def superuser_token(test_superuser: User) -> str:
    """Create an access token for the test superuser."""
    return create_access_token(subject=test_superuser.id)


@pytest.fixture
def auth_headers(user_token: str) -> dict:
    """Create authorization headers for the test user."""
    return {"Authorization": f"Bearer {user_token}"}


@pytest.fixture
def superuser_auth_headers(superuser_token: str) -> dict:
    """Create authorization headers for the test superuser."""
    return {"Authorization": f"Bearer {superuser_token}"}


def generate_test_reference(prefix: str, sequence: int = 1) -> str:
    """Generate a test reference number."""
    from datetime import datetime

    year = datetime.now().year
    return f"{prefix}-{year}-{sequence:04d}"
