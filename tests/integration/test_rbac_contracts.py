import pytest
from httpx import AsyncClient

from src.domain.models.policy import DocumentStatus, DocumentType


@pytest.mark.asyncio
async def test_create_policy_with_permission(client: AsyncClient, superuser_auth_headers: dict):
    """Verify that a user with the correct permission can create a policy."""
    policy_data = {
        "title": "Test Policy",
        "description": "Test Description",
        "document_type": "policy",
        "status": "draft",
    }
    response = await client.post("/api/v1/policies", json=policy_data, headers=superuser_auth_headers)
    print(response.json())
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_create_policy_without_permission(client: AsyncClient, auth_headers: dict):
    """Verify that a user without the correct permission cannot create a policy."""
    policy_data = {
        "title": "Test Policy",
        "description": "Test Description",
        "document_type": "policy",
        "status": "draft",
    }
    response = await client.post("/api/v1/policies", json=policy_data, headers=auth_headers)
    assert response.status_code == 403
    data = response.json()
    assert data["message"] == "The user does not have the required permission"
