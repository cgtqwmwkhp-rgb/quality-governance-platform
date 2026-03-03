"""
Health Endpoint Stability Tests

Stage 3 Regression Guard: Verify health tests are deterministic and stable
across repeated runs. This catches async event loop issues that manifest
as flaky failures (GOVPLAT-ASYNC-001).

Run with: pytest tests/integration/test_health_stability.py -v
"""

import pytest
from httpx import AsyncClient


class TestHealthEndpointStability:
    """Regression guards for health endpoint stability."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("run_number", range(10))
    async def test_health_repeated_runs(self, client: AsyncClient, run_number: int):
        """Health check should be stable across 10 repeated runs.

        This test guards against GOVPLAT-ASYNC-001: Event loop contamination
        between sync and async fixtures causing flaky failures.
        """
        response = await client.get("/health")

        assert (
            response.status_code == 200
        ), f"Run {run_number}: Expected 200, got {response.status_code}"
        data = response.json()
        assert data["status"] == "healthy", f"Run {run_number}: Expected healthy status"
        assert "request_id" in data, f"Run {run_number}: Missing request_id"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("run_number", range(10))
    async def test_healthz_repeated_runs(self, client: AsyncClient, run_number: int):
        """Liveness probe should be stable across 10 repeated runs."""
        response = await client.get("/healthz")

        assert (
            response.status_code == 200
        ), f"Run {run_number}: Expected 200, got {response.status_code}"
        data = response.json()
        assert data["status"] == "ok", f"Run {run_number}: Expected ok status"

    @pytest.mark.asyncio
    async def test_no_pending_tasks_after_health_check(self, client: AsyncClient):
        """Verify no async tasks are left pending after health checks.

        This guards against resource leaks that could cause flaky tests.
        """
        import asyncio

        # Run multiple health checks
        for _ in range(5):
            response = await client.get("/health")
            assert response.status_code == 200

        # Check for pending tasks (excluding the current task)
        loop = asyncio.get_running_loop()
        all_tasks = asyncio.all_tasks(loop)
        current_task = asyncio.current_task(loop)

        pending = [t for t in all_tasks if t is not current_task and not t.done()]

        # Filter out known pytest-asyncio infrastructure tasks
        suspicious_pending = [
            t
            for t in pending
            if "pytest" not in str(t.get_coro()) and "anyio" not in str(t.get_coro())
        ]

        assert len(suspicious_pending) == 0, (
            f"Found {len(suspicious_pending)} suspicious pending tasks after health checks: "
            f"{[str(t.get_coro()) for t in suspicious_pending]}"
        )
