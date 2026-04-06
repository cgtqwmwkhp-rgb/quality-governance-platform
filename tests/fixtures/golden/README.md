# Golden Test Fixtures

Frozen reference datasets used for regression and snapshot testing. These fixtures
ensure deterministic, reproducible test results across all environments.

## Rules

1. **Immutability**: Golden fixtures must not change unless a schema migration or deliberate
   data model change requires it. All changes must be reviewed in the PR diff.
2. **Determinism**: No random values, no wall-clock timestamps, no `uuid4()` without fixed seeds.
   All values are explicit constants.
3. **Referenceability**: Tests import fixtures by constant name (e.g., `GOLDEN_INCIDENT`)
   so diffs show exactly which test data changed.
4. **Coverage**: Each core domain entity has a golden fixture representing a realistic,
   fully-populated record suitable for API response comparison and report generation.

## Fixture Files

| File | Domain | Contents |
|------|--------|----------|
| `incident.json` | Incident | Complete incident with actions, severity, SIF flags |
| `risk.json` | Enterprise Risk | Risk with scores, linked audits, linked actions |
| `audit.json` | Audit Run + Findings | Audit run with findings, corrective actions, risk links |
| `capa.json` | CAPA Action | Corrective action with source linkage |
| `complaint.json` | Complaint | Complaint with categorization and SLA timestamps |
| `action.json` | CAPA Action (full) | Fully-populated corrective action with root cause, verification, ISO clause |
| `workflow.json` | Workflow Instance | Approval workflow with three sequential steps and SLA tracking |
| `tenant.json` | Tenant | Multi-tenant org with branding, feature flags, settings, and limits |

## Usage

```python
import json
from pathlib import Path

GOLDEN_DIR = Path(__file__).parent

def load_golden(name: str) -> dict:
    return json.loads((GOLDEN_DIR / f"{name}.json").read_text())
```
