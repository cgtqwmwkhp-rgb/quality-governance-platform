"""Unit contracts for the canonical API error vocabulary."""

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from src.api.middleware.error_handler import register_exception_handlers


def _client() -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/entities/{entity_id}")
    async def get_entity(entity_id: int) -> None:
        raise HTTPException(status_code=404, detail="Entity not found")

    return TestClient(app)


def test_error_class_is_a_value_identical_legacy_alias() -> None:
    response = _client().get("/entities/42")

    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "ENTITY_NOT_FOUND"
    assert error["error_class"] == error["code"]


def test_unmatched_route_uses_route_not_found_not_entity_not_found() -> None:
    response = _client().get("/missing-route")

    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "ROUTE_NOT_FOUND"
    assert error["error_class"] == "ROUTE_NOT_FOUND"
    assert error["details"] == {"path": "/missing-route"}
