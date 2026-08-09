# Framework evidence pack fixtures (Library WK-1 / L-47)

Golden JSON for ISO 9001 · UVDB B2 · Planet Mark packs built from **typed CEL-shaped rows**.

| File | Role |
|------|------|
| `*.input-rows.json` | Frozen typed rows (+ export metadata) |
| `*.pack.fixture.json` | Expected pack output from `framework_evidence_pack_builder` |

## Isolation (WI-1 conflict)

These fixtures + `src/domain/services/framework_evidence_pack_builder.py` must **not** edit:

- `src/domain/models/compliance_evidence.py`
- `src/domain/models/standard.py` / clauses
- `alembic/versions/*lib_wi1*`
- `src/api/routes/compliance.py`
- `src/api/routes/governed_knowledge.py`

Wire a CEL → typed-row adapter only after WI-1 (#1687) is **PROD LIVE**.

## Rebuild fixtures

```bash
PYTHONPATH=. python3.11 -c "
from pathlib import Path
import json
from src.domain.services.framework_evidence_pack_builder import (
  build_iso9001_evidence_pack, build_uvdb_b2_evidence_pack, build_planet_mark_evidence_pack,
)
..."
```

Or run: `pytest tests/unit/test_lib_wk1_framework_evidence_packs.py -q`
