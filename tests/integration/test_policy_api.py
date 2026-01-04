"""Integration tests for Policy Library API."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from src.domain.models.policy import DocumentStatus, DocumentType, Policy
from src.domain.models.user import User


@pytest.mark.asyncio
async def test_create_policy(client: AsyncClient, test_user: User, auth_headers: dict):
    """Test creating a new policy."""
    policy_data = {
        "title": "Test Policy",
        "description": "This is a test policy",
        "document_type": "policy",
        "status": "draft",
    }

    response = await client.post(
        "/api/v1/policies",
        json=policy_data,
        headers=auth_headers,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Test Policy"
    assert data["description"] == "This is a test policy"
    assert data["document_type"] == "policy"
    assert data["status"] == "draft"
    assert "id" in data
    assert "reference_number" in data
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_get_policy_by_id(client: AsyncClient, test_user: User, auth_headers: dict, test_session):
    """Test getting a policy by ID."""
    # Create a policy directly in the database
    policy = Policy(
        title="Test Policy",
        description="Test description",
        document_type=DocumentType.POLICY,
        status=DocumentStatus.DRAFT,
        reference_number="POL-2026-TEST-001",
        created_by_id=test_user.id,
        updated_by_id=test_user.id,
    )
    test_session.add(policy)
    await test_session.commit()
    await test_session.refresh(policy)

    # Get the policy via API
    response = await client.get(
        f"/api/v1/policies/{policy.id}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == policy.id
    assert data["title"] == "Test Policy"
    assert data["description"] == "Test description"


@pytest.mark.asyncio
async def test_get_policy_not_found(client: AsyncClient, auth_headers: dict):
    """Test getting a non-existent policy returns 404."""
    response = await client.get(
        "/api/v1/policies/99999",
        headers=auth_headers,
    )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_list_policies_deterministic_ordering(
    client: AsyncClient,
    test_user: User,
    auth_headers: dict,
    test_session,
):
    """Test that list policies returns results in deterministic order."""
    # Create multiple policies with slight time differences
    import asyncio

    policies = []
    for i in range(5):
        policy = Policy(
            title=f"Policy {i}",
            description=f"Description {i}",
            document_type=DocumentType.POLICY,
            status=DocumentStatus.DRAFT,
            reference_number=f"POL-2026-TEST-{i:03d}",
            created_by_id=test_user.id,
            updated_by_id=test_user.id,
        )
        test_session.add(policy)
        await test_session.commit()
        await test_session.refresh(policy)
        policies.append(policy)
        await asyncio.sleep(0.01)  # Small delay to ensure different timestamps

    # Get the list via API
    response = await client.get(
        "/api/v1/policies",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 5

    # Verify ordering: newest first (created_at DESC), then by id ASC
    items = data["items"]
    assert len(items) >= 5

    # The most recently created policy should be first
    assert items[0]["title"] == "Policy 4"

    # Verify deterministic ordering by checking that results are consistent
    response2 = await client.get(
        "/api/v1/policies",
        headers=auth_headers,
    )
    data2 = response2.json()

    # Same order on repeated calls
    assert [item["id"] for item in items] == [item["id"] for item in data2["items"]]


@pytest.mark.asyncio
async def test_list_policies_pagination(
    client: AsyncClient,
    test_user: User,
    auth_headers: dict,
    test_session,
):
    """Test pagination in list policies."""
    # Create 10 policies
    for i in range(10):
        policy = Policy(
            title=f"Policy {i}",
            document_type=DocumentType.POLICY,
            status=DocumentStatus.DRAFT,
            reference_number=f"POL-2026-PAG-{i:03d}",
            created_by_id=test_user.id,
            updated_by_id=test_user.id,
        )
        test_session.add(policy)
    await test_session.commit()

    # Get first page
    response = await client.get(
        "/api/v1/policies?page=1&page_size=5",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 5
    assert data["page"] == 1
    assert data["page_size"] == 5
    assert data["total"] >= 10

    # Get second page
    response2 = await client.get(
        "/api/v1/policies?page=2&page_size=5",
        headers=auth_headers,
    )

    assert response2.status_code == 200
    data2 = response2.json()
    assert len(data2["items"]) == 5
    assert data2["page"] == 2

    # Verify no overlap between pages
    page1_ids = {item["id"] for item in data["items"]}
    page2_ids = {item["id"] for item in data2["items"]}
    assert page1_ids.isdisjoint(page2_ids)


@pytest.mark.asyncio
async def test_update_policy(client: AsyncClient, test_user: User, auth_headers: dict, test_session):
    """Test updating a policy."""
    # Create a policy
    policy = Policy(
        title="Original Title",
        description="Original description",
        document_type=DocumentType.POLICY,
        status=DocumentStatus.DRAFT,
        reference_number="POL-2026-UPD-001",
        created_by_id=test_user.id,
        updated_by_id=test_user.id,
    )
    test_session.add(policy)
    await test_session.commit()
    await test_session.refresh(policy)

    # Update the policy
    update_data = {
        "title": "Updated Title",
        "status": "approved",
    }

    response = await client.put(
        f"/api/v1/policies/{policy.id}",
        json=update_data,
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated Title"
    assert data["status"] == "approved"
    assert data["description"] == "Original description"  # Unchanged


@pytest.mark.asyncio
async def test_update_policy_not_found(client: AsyncClient, auth_headers: dict):
    """Test updating a non-existent policy returns 404."""
    update_data = {"title": "Updated Title"}

    response = await client.put(
        "/api/v1/policies/99999",
        json=update_data,
        headers=auth_headers,
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_policy(client: AsyncClient, test_user: User, auth_headers: dict, test_session):
    """Test deleting a policy."""
    # Create a policy
    policy = Policy(
        title="Policy to Delete",
        document_type=DocumentType.POLICY,
        status=DocumentStatus.DRAFT,
        reference_number="POL-2026-DEL-001",
        created_by_id=test_user.id,
        updated_by_id=test_user.id,
    )
    test_session.add(policy)
    await test_session.commit()
    await test_session.refresh(policy)
    policy_id = policy.id

    # Delete the policy
    response = await client.delete(
        f"/api/v1/policies/{policy_id}",
        headers=auth_headers,
    )

    assert response.status_code == 204

    # Verify it's deleted
    result = await test_session.execute(select(Policy).where(Policy.id == policy_id))
    deleted_policy = result.scalar_one_or_none()
    assert deleted_policy is None


@pytest.mark.asyncio
async def test_delete_policy_not_found(client: AsyncClient, auth_headers: dict):
    """Test deleting a non-existent policy returns 404."""
    response = await client.delete(
        "/api/v1/policies/99999",
        headers=auth_headers,
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_full_crud_flow(client: AsyncClient, test_user: User, auth_headers: dict, test_session):
    """Test the full CRUD flow: create -> get -> list -> update -> delete."""
    # 1. Create
    create_data = {
        "title": "CRUD Test Policy",
        "description": "Testing full CRUD flow",
        "document_type": "policy",
        "status": "draft",
    }

    create_response = await client.post(
        "/api/v1/policies",
        json=create_data,
        headers=auth_headers,
    )
    assert create_response.status_code == 201
    policy_id = create_response.json()["id"]

    # 2. Get
    get_response = await client.get(
        f"/api/v1/policies/{policy_id}",
        headers=auth_headers,
    )
    assert get_response.status_code == 200
    assert get_response.json()["title"] == "CRUD Test Policy"

    # 3. List
    list_response = await client.get(
        "/api/v1/policies",
        headers=auth_headers,
    )
    assert list_response.status_code == 200
    assert any(item["id"] == policy_id for item in list_response.json()["items"])

    # 4. Update
    update_data = {"title": "Updated CRUD Test Policy"}
    update_response = await client.put(
        f"/api/v1/policies/{policy_id}",
        json=update_data,
        headers=auth_headers,
    )
    assert update_response.status_code == 200
    assert update_response.json()["title"] == "Updated CRUD Test Policy"

    # 5. Delete
    delete_response = await client.delete(
        f"/api/v1/policies/{policy_id}",
        headers=auth_headers,
    )
    assert delete_response.status_code == 204

    # 6. Verify deletion (Hard Delete)
    get_after_delete = await client.get(
        f"/api/v1/policies/{policy_id}",
        headers=auth_headers,
    )
    assert get_after_delete.status_code == 404

    # Verify it's gone from the database
    from sqlalchemy import select

    from src.domain.models.policy import Policy

    db_check = await test_session.execute(select(Policy).where(Policy.id == policy_id))
    assert db_check.scalar_one_or_none() is None
