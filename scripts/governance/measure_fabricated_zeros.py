"""Measure C-7 and C-53 against a real PostgreSQL with a genuinely drifted schema.

Run before and after the fix and diff the output. Prints the raw response bodies
rather than assertions, because the point of the exercise is to see what a
director's dashboard would actually have shown.

    DATABASE_URL=postgresql+asyncpg://... python scripts/governance/measure_fabricated_zeros.py

Requires PostgreSQL: the drift depends on DROP COLUMN aborting the surrounding
transaction, which SQLite does not do. See tests/integration/_fabricated_zero_scratch.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

os.environ.setdefault("TESTING", "1")

from httpx import ASGITransport, AsyncClient  # noqa: E402

from tests.integration.conftest import _generate_test_jwt  # noqa: E402
from tests.integration._fabricated_zero_scratch import (  # noqa: E402
    AUDIT_RUNS_STATUS,
    CAPA_ACTIONS_TENANT,
    TENANT_ID,
    USER_ID,
    DriftedDatabase,
    drop_drifted_database,
    make_drifted_engine,
)


async def _scratch():
    import src.domain.models  # noqa: F401
    from src.infrastructure.database import Base

    engine, name = await make_drifted_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    scratch = DriftedDatabase(engine)
    await scratch.seed_tenant_and_user()
    return scratch, engine, name


async def _client(scratch):
    from src.infrastructure.database import get_db
    from src.main import app

    async def _get_db():
        async with scratch.sessions() as session:
            yield session

    app.dependency_overrides[get_db] = _get_db
    token = _generate_test_jwt(user_id=str(USER_ID), tenant_id=TENANT_ID, role="admin")
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    )


def _show(label: str, response) -> None:
    print(f"\n--- {label}")
    print(f"    HTTP {response.status_code}")
    print("    " + json.dumps(response.json(), indent=2, default=str).replace("\n", "\n    "))


async def scenario_c7() -> None:
    print("=" * 78)
    print("C-7  /analytics/kpis audits tile, audit_runs.status dropped")
    print("=" * 78)
    scratch, engine, name = await _scratch()
    try:
        seeded = await scratch.seed_audit_runs(completed=2, in_progress=1)
        print(f"\nSeeded {seeded} audit runs (2 completed @ 90%, 1 in progress).")

        async with await _client(scratch) as client:
            body = (await client.get("/api/v1/analytics/kpis")).json()
            print(f"\nBefore drift, audits tile: {json.dumps(body['audits'], default=str)}")

        await scratch.drop_column(*AUDIT_RUNS_STATUS)
        print(f"\nDropped {AUDIT_RUNS_STATUS[0]}.{AUDIT_RUNS_STATUS[1]}.")
        print(f"    column still present? {await scratch.has_column(*AUDIT_RUNS_STATUS)}")
        print("    NB: `SELECT count(*) FROM audit_runs WHERE tenant_id=1` still succeeds —")
        print("        the total was readable. Only the status-filtered counts fail.")

        async with await _client(scratch) as client:
            _show("GET /api/v1/analytics/kpis", await client.get("/api/v1/analytics/kpis"))
    finally:
        await engine.dispose()
        await drop_drifted_database(name)


async def scenario_c53_empty() -> None:
    print("\n" + "=" * 78)
    print("C-53(b)  /actions/ with only CAPA rows, capa_actions.tenant_id dropped")
    print("=" * 78)
    scratch, engine, name = await _scratch()
    try:
        seeded = await scratch.seed_capa_actions(2)
        print(f"\nSeeded {seeded} CAPA actions and nothing else.")

        await scratch.drop_column(*CAPA_ACTIONS_TENANT)
        print(f"Dropped {CAPA_ACTIONS_TENANT[0]}.{CAPA_ACTIONS_TENANT[1]}.")

        async with await _client(scratch) as client:
            _show("GET /api/v1/actions/", await client.get("/api/v1/actions/"))
    finally:
        await engine.dispose()
        await drop_drifted_database(name)


async def scenario_c53_partial() -> None:
    print("\n" + "=" * 78)
    print("C-53(a)  /actions/ with CAPA + incident rows, capa_actions.tenant_id dropped")
    print("=" * 78)
    scratch, engine, name = await _scratch()
    try:
        capas = await scratch.seed_capa_actions(2)
        incidents = await scratch.seed_incident_actions(3)
        print(f"\nSeeded {capas} CAPA actions and {incidents} incident actions.")
        print(f"True register size: {capas + incidents}.")

        await scratch.drop_column(*CAPA_ACTIONS_TENANT)
        print(f"Dropped {CAPA_ACTIONS_TENANT[0]}.{CAPA_ACTIONS_TENANT[1]}.")

        async with await _client(scratch) as client:
            response = await client.get("/api/v1/actions/")
            body = response.json()
            print(f"\n--- GET /api/v1/actions/\n    HTTP {response.status_code}")
            print(f"    total .................. {body.get('total')}   (true value: {capas + incidents})")
            print(f"    items returned ......... {len(body.get('items') or [])}")
            print(f"    sources_complete ....... {body.get('sources_complete', '<field absent>')}")
            print(f"    unavailable_sources .... {body.get('unavailable_sources', '<field absent>')}")
    finally:
        await engine.dispose()
        await drop_drifted_database(name)


async def main() -> None:
    if not os.environ.get("DATABASE_URL", "").startswith("postgresql"):
        raise SystemExit("set DATABASE_URL to a throwaway PostgreSQL first")
    await scenario_c7()
    await scenario_c53_empty()
    await scenario_c53_partial()


if __name__ == "__main__":
    asyncio.run(main())
