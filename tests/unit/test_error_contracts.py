
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_http_exception_handler(client: AsyncClient, auth_headers: dict):
    """Verify that HTTPException is caught and returns a canonical error response."""
    response = await client.get("/api/v1/policies/99999", headers=auth_headers)

    assert response.status_code == 404
    data = response.json()
    assert data["error_code"] == "404"
    assert data["message"] == "Policy with id 99999 not found"
    assert "request_id" in data


@pytest.mark.asyncio
async def test_validation_exception_handler(client: AsyncClient, auth_headers: dict):
    """Verify that RequestValidationError is caught and returns a canonical error response."""
    # Send invalid data (missing required 'title' field)
    invalid_policy_data = {"description": "This is a test policy"}

    response = await client.post("/api/v1/policies", json=invalid_policy_data, headers=auth_headers)

    assert response.status_code == 422
    data = response.json()
    assert data["error_code"] == "VALIDATION_ERROR"
    assert data["message"] == "Input validation failed"
    assert "request_id" in data
    assert isinstance(data["details"], list)
    assert len(data["details"]) > 0
    assert data["details"][0]["loc"] == ["body", "title"]
    assert data["details"][0]["msg"] == "Field required"
