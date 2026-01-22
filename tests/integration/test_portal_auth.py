"""
Portal Authentication Tests

Tests for the portal authentication flow including:
- Token exchange endpoint
- My-reports endpoint with proper auth
- Email enumeration prevention
- Read-your-writes guarantee for report creation
"""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from src.core.security import create_access_token
from src.domain.models.user import User
from src.infrastructure.database import async_session_maker
from src.main import app


class TestPortalAuth:
    """Tests for portal authentication endpoints."""

    @pytest.fixture
    async def client(self):
        """Async HTTP client for portal auth tests."""
        from src.infrastructure.database import engine

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
        await engine.dispose()

    @pytest.mark.asyncio
    async def test_token_exchange_requires_valid_token(self, client):
        """Token exchange should reject invalid Azure AD tokens."""
        response = await client.post(
            "/api/v1/auth/token-exchange",
            json={"id_token": "invalid-token"},
        )
        # Should reject with 401 (invalid token)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_token_exchange_requires_token(self, client):
        """Token exchange should require id_token field."""
        response = await client.post(
            "/api/v1/auth/token-exchange",
            json={},
        )
        # Should reject with 422 (validation error)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_my_reports_requires_auth(self, client):
        """My-reports endpoint should require authentication."""
        response = await client.get("/api/v1/portal/my-reports/")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_my_reports_rejects_invalid_token(self, client):
        """My-reports should reject invalid tokens."""
        response = await client.get(
            "/api/v1/portal/my-reports/",
            headers={"Authorization": "Bearer invalid-token"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_portal_reports_still_public(self, client):
        """Portal report submission should still be public."""
        response = await client.post(
            "/api/v1/portal/reports/",
            json={
                "report_type": "incident",
                "title": "Test incident for auth verification",
                "description": "This is a test incident to verify auth works",
                "severity": "low",
                "is_anonymous": True,
            },
        )
        # Portal submission is public
        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_incidents_list_requires_auth(self, client):
        """Incidents list should require authentication."""
        response = await client.get("/api/v1/incidents/")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_incidents_list_with_email_filter_requires_auth(self, client):
        """
        Incidents list with email filter should require auth.
        This prevents email enumeration attacks.
        """
        response = await client.get("/api/v1/incidents/?reporter_email=test@example.com")
        assert response.status_code == 401


class TestEmailEnumerationPrevention:
    """Tests to ensure email enumeration is prevented."""

    @pytest.fixture
    async def client(self):
        """Async HTTP client."""
        from src.infrastructure.database import engine

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
        await engine.dispose()

    @pytest.mark.asyncio
    async def test_cannot_enumerate_incidents_by_email(self, client):
        """Users cannot enumerate incidents by guessing emails."""
        # Without auth, should get 401
        response = await client.get("/api/v1/incidents/?reporter_email=victim@example.com")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_cannot_enumerate_complaints_by_email(self, client):
        """Users cannot enumerate complaints by guessing emails."""
        response = await client.get("/api/v1/complaints/?complainant_email=victim@example.com")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_cannot_enumerate_rtas_by_email(self, client):
        """Users cannot enumerate RTAs by guessing emails."""
        response = await client.get("/api/v1/rtas/?reporter_email=victim@example.com")
        assert response.status_code == 401


class TestReadYourWritesGuarantee:
    """
    Tests for read-your-writes guarantee.
    
    When a user creates a report, it MUST be immediately visible in
    their "My Reports" list without requiring a refresh or delay.
    """

    @pytest.fixture
    async def client(self):
        """Async HTTP client."""
        from src.infrastructure.database import engine

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
        await engine.dispose()

    @pytest.fixture
    async def test_user_with_token(self):
        """Create a test user and return (user, token) tuple."""
        test_email = "read-your-writes-test@example.com"
        
        async with async_session_maker() as session:
            # Check if user exists
            result = await session.execute(
                select(User).where(User.email == test_email)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                # Create test user
                user = User(
                    email=test_email,
                    first_name="Test",
                    last_name="User",
                    hashed_password="not-used",
                    is_active=True,
                )
                session.add(user)
                await session.commit()
                await session.refresh(user)
            
            # Generate platform token for this user
            token = create_access_token(subject=user.id)
            
            return user, token

    @pytest.mark.asyncio
    async def test_created_incident_appears_in_my_reports(self, client, test_user_with_token):
        """
        CRITICAL: A report created via portal MUST immediately appear in My Reports.
        
        This test verifies the read-your-writes guarantee that was broken when
        reporter_email was not being set on incident creation.
        """
        user, token = test_user_with_token
        
        # Step 1: Create incident with reporter_email
        create_response = await client.post(
            "/api/v1/portal/reports/",
            json={
                "report_type": "incident",
                "title": "Read-your-writes test incident",
                "description": "This incident should appear in My Reports immediately",
                "severity": "low",
                "is_anonymous": False,
                "reporter_email": user.email,
                "reporter_name": f"{user.first_name} {user.last_name}",
            },
        )
        
        assert create_response.status_code == 201, f"Create failed: {create_response.text}"
        created = create_response.json()
        reference_number = created["reference_number"]
        assert reference_number.startswith("INC-"), f"Expected INC- prefix: {reference_number}"
        
        # Step 2: IMMEDIATELY fetch My Reports (same request session)
        my_reports_response = await client.get(
            "/api/v1/portal/my-reports/",
            headers={"Authorization": f"Bearer {token}"},
        )
        
        assert my_reports_response.status_code == 200, f"My Reports failed: {my_reports_response.text}"
        my_reports = my_reports_response.json()
        
        # Step 3: Verify the created incident appears in the list
        reference_numbers = [r["reference_number"] for r in my_reports["items"]]
        assert reference_number in reference_numbers, (
            f"CRITICAL: Created report {reference_number} not found in My Reports! "
            f"Found: {reference_numbers}. This is a read-your-writes violation."
        )

    @pytest.mark.asyncio
    async def test_anonymous_report_not_in_my_reports(self, client, test_user_with_token):
        """Anonymous reports should NOT appear in My Reports (no identity linkage)."""
        user, token = test_user_with_token
        
        # Create anonymous incident
        create_response = await client.post(
            "/api/v1/portal/reports/",
            json={
                "report_type": "incident",
                "title": "Anonymous test incident",
                "description": "This should NOT appear in My Reports",
                "severity": "low",
                "is_anonymous": True,
            },
        )
        
        assert create_response.status_code == 201
        created = create_response.json()
        reference_number = created["reference_number"]
        
        # Fetch My Reports
        my_reports_response = await client.get(
            "/api/v1/portal/my-reports/",
            headers={"Authorization": f"Bearer {token}"},
        )
        
        assert my_reports_response.status_code == 200
        my_reports = my_reports_response.json()
        
        # Verify anonymous report does NOT appear (correct behavior)
        reference_numbers = [r["reference_number"] for r in my_reports["items"]]
        assert reference_number not in reference_numbers, (
            f"Anonymous report {reference_number} should NOT appear in My Reports"
        )

    @pytest.mark.asyncio
    async def test_other_user_cannot_see_my_reports(self, client, test_user_with_token):
        """Reports should only be visible to the user who created them."""
        user, token = test_user_with_token
        
        # Create incident as user
        create_response = await client.post(
            "/api/v1/portal/reports/",
            json={
                "report_type": "incident",
                "title": "Private test incident",
                "description": "Only the reporter should see this",
                "severity": "medium",
                "is_anonymous": False,
                "reporter_email": user.email,
            },
        )
        
        assert create_response.status_code == 201
        reference_number = create_response.json()["reference_number"]
        
        # Create a different user and token
        async with async_session_maker() as session:
            other_user = User(
                email="other-user@example.com",
                first_name="Other",
                last_name="User",
                hashed_password="not-used",
                is_active=True,
            )
            session.add(other_user)
            await session.commit()
            await session.refresh(other_user)
            other_token = create_access_token(subject=other_user.id)
        
        # Other user fetches their My Reports
        other_reports_response = await client.get(
            "/api/v1/portal/my-reports/",
            headers={"Authorization": f"Bearer {other_token}"},
        )
        
        assert other_reports_response.status_code == 200
        other_reports = other_reports_response.json()
        
        # Verify other user cannot see this report
        other_reference_numbers = [r["reference_number"] for r in other_reports["items"]]
        assert reference_number not in other_reference_numbers, (
            f"SECURITY: Report {reference_number} visible to wrong user!"
        )
