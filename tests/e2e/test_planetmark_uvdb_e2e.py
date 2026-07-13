"""
Planet Mark / UVDB E2E (Wave C) — former module-wide skip removed.

The legacy suite was skipped for AsyncSession/DB issues. The working harness
now lives outside ``tests/e2e/conftest.py`` autouse seeding:

- ``tests/unit/test_planetmark_uvdb_route_harness.py`` (pytest)
- ``scripts/smoke/uvdb_downstream_e2e.py`` (no DB)

HTTP contract coverage remains in ``tests/integration/test_planetmark_uvdb_api.py``.

This file is intentionally free of ``test_*`` callables so collection does not
trigger the e2e autouse seed; the unit harness is the executable replacement.
"""

from __future__ import annotations

WAVE_C_UVDB_ROUTE_HARNESS = "tests.unit.test_planetmark_uvdb_route_harness"
WAVE_C_UVDB_SMOKE = "scripts/smoke/uvdb_downstream_e2e.py"
