# Test Data & Fixtures Strategy (D16)

This document defines how automated tests obtain data: factories, golden baselines, determinism, property-based coverage, masking, and boundary datasets.

## Factory discipline

- **Single source**: All persisted test entities are created through [factory_boy](https://factoryboy.readthedocs.io/) factories.
- **Location**: Shared factories live in `tests/factories/core.py` (domain-specific splits may extend submodules, but the eighteen canonical factories are registered and imported from this module).
- **Determinism**: Factories use fixed sequences, explicit attributes, and `FIXED_EPOCH` (see below)—never `Faker`, `random`, or non-seeded variability.
- **Eighteen deterministic factories** (canonical set):

  | # | Factory | Primary model / aggregate |
  |---|---------|---------------------------|
  | 1 | `UserFactory` | Platform user account |
  | 2 | `TenantFactory` | Tenant / org |
  | 3 | `IncidentFactory` | Incident record |
  | 4 | `RiskFactory` | Risk register entry |
  | 5 | `RTAFactory` | Right-to-access / RTA workflow entity |
  | 6 | `ComplaintFactory` | Complaint case |
  | 7 | `AuditRunFactory` | Audit run container |
  | 8 | `AuditTemplateFactory` | Audit template definition |
  | 9 | `AuditFindingFactory` | Individual audit finding |
  | 10 | `ActionFactory` | Corrective / follow-up action |
  | 11 | `IncidentActionFactory` | Incident-linked action |
  | 12 | `NearMissFactory` | Near-miss report |
  | 13 | `PolicyFactory` | Policy document |
  | 14 | `RTAActionFactory` | RTA-linked action |
  | 15 | `InvestigationFactory` | Investigation run |
  | 16 | `EnterpriseRiskFactory` | Enterprise risk register entry |
  | 17 | `EvidenceAssetFactory` | Evidence / attachment metadata |
  | 18 | `ExternalAuditImportJobFactory` | External audit import job |

Tests must not construct ORM rows with bare `Model.objects.create(...)` except in factory implementation code.

## Golden datasets

Regression and snapshot tests use **frozen** dictionaries (or equivalent fixtures) exported next to factories and as JSON files in `tests/fixtures/golden/`:

| Source | Purpose |
|--------|---------|
| `tests/factories/core.py::GOLDEN_INCIDENT` | Baseline incident dict for in-code tests |
| `tests/factories/core.py::GOLDEN_RISK` | Baseline risk scores, statuses, and filter facets |
| `tests/factories/core.py::GOLDEN_RTA` | Baseline RTA lifecycle fields and transition guards |
| `tests/factories/core.py::GOLDEN_COMPLAINT` | Baseline complaint categorization and SLA timestamps |
| `tests/fixtures/golden/incident.json` | Full incident payload with actions for API response comparison |
| `tests/fixtures/golden/risk.json` | Enterprise Risk with linked audits/actions |
| `tests/fixtures/golden/audit.json` | Audit run with findings, corrective actions, risk links |
| `tests/fixtures/golden/capa.json` | CAPA action with source linkage |
| `tests/fixtures/golden/complaint.json` | Complaint with categorization and SLA timestamps |

Golden data is updated only deliberately (e.g. schema change PR) and referenced in tests by constant name or file path so diffs stay reviewable.

## Deterministic timestamps

- **Fixed epoch**: `FIXED_EPOCH = datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc)` — timezone-aware UTC datetime.
- **`uuid.uuid4()` policy**: Prohibited in test assertions. Permitted inside factory `LazyFunction` calls (e.g. `AuditTemplateFactory`) where deterministic UUIDs are not required for test correctness.
- All factories default `created_at`, `updated_at`, due dates, and SLA anchors relative to `FIXED_EPOCH` via `factory.LazyFunction` or explicit kwargs—not “now”.
- **Prohibited in tests**: `Faker`, `random.*`, wall-clock–dependent assertions.

## Property-based testing plan (Hypothesis)

Use the [Hypothesis](https://hypothesis.readthedocs.io/) library for boundary and edge exploration **on top of** golden and factory-backed examples—not as a replacement for them.

| Area | Properties / strategies | Notes |
|------|---------------------------|--------|
| **Reference number generation** | Strings constrained to min/max length; allowed charset (e.g. alphanumeric, hyphen); optional prefix/suffix; rejection of empty and over-max | Assert format validators and DB constraints agree; no collisions under sequential factory IDs |
| **Status transitions** | Valid transition pairs vs invalid jumps; terminal states; idempotent “no-op” transitions | Model / FSM rules must match API; invalid transitions return 4xx with stable error codes |
| **Date range queries** | Empty range, identical start/end (single day), span > 1 year, inclusive boundaries, open-ended start or end where supported | SQL must return stable ordering; timezone UTC; no off-by-one on date-only filters |
| **Pagination** | `page=0`, `page=-1`, `page_size=0`, `page_size=10000`, plus valid minimums | API should coerce or reject consistently; never 500; caps applied with documented max |

Run these in CI with a fixed `derandomize` / seed configuration so failures reproduce locally.

## Data masking (PII)

- Test PII (names, emails, phones, addresses, free-text) must come from **factory sequences** (e.g. `factory.Sequence(lambda n: f"user{n}@example.test")`), not real people or production-like dumps.
- Domains should use reserved suffixes (`example.test`, `invalid`) where applicable.
- No live third-party identifiers (real OAuth subjects, payment tokens, etc.) in fixtures or VCR cassettes.

## Boundary datasets by domain entity

Use the following **edge-case matrix** in parameterized tests. “Min string” is the shortest allowed non-null value; “max string” is at the documented limit; “overlong” expects validation or DB error.

### Incident

| Edge case | Specification | Expected behaviour |
|-----------|---------------|--------------------|
| Min string | Title/description at minimum length (1 char if allowed) | Accepted |
| Max string | Title/description at max length | Accepted |
| Overlong | Title/description max+1 | Validation error or DB error, never truncate silently |
| Special characters | `<>\"'&;` in free text | Escaped safely in API/HTML; stored verbatim in DB where allowed |
| Unicode | Emoji, RTL text, combining characters | Normalization policy documented; no corruption |
| Null vs empty | Nullable optional fields: `None` vs `""` | Distinct semantics; filters match correctly |

### Risk

| Edge case | Specification | Expected behaviour |
|-----------|---------------|--------------------|
| Min string | Shortest allowed title / control reference | Accepted |
| Max string | Narrative at limit | Accepted |
| Overlong | Narrative over limit | Rejected with clear error |
| Special characters | CSV/formula injection strings (`=cmd\|`) | No formula execution in exports |
| Unicode | Mixed scripts in risk title | Sorting and search stable |
| Null vs empty | Optional rationale | Query and report treat null/empty per spec |

### RTA

| Edge case | Specification | Expected behaviour |
|-----------|---------------|--------------------|
| Min string | Shortest case reference | Accepted |
| Max string | Correspondence body at limit | Accepted |
| Overlong | Attachment name / notes over limit | Rejected |
| Special characters | Path-like strings in filenames | Sanitized for storage keys |
| Unicode | Requester name in non-Latin scripts | Display and PDF/export correct |
| Null vs empty | Optional deadline | Workflow uses default or blocked state per rules |

### Complaint

| Edge case | Specification | Expected behaviour |
|-----------|---------------|--------------------|
| Min string | Minimum complaint summary | Accepted |
| Max string | Longest allowed narrative | Accepted |
| Overlong | Narrative max+1 | Rejected |
| Special characters | PII-like patterns in text (fake emails) | Still synthetic; redaction rules tested |
| Unicode | Accented names, CJK | Search tokenization documented |
| Null vs empty | Optional contact fields | Channel rules enforced |

### User (account)

| Edge case | Specification | Expected behaviour |
|-----------|---------------|--------------------|
| Min string | Shortest allowed display name | Accepted |
| Max string | Email local-part + domain at limits | Accepted per RFC subset |
| Overlong | Username/email over limit | Rejected |
| Special characters | `+` and `.` in email, quotes | Normalization rules consistent |
| Unicode | IDN email (if supported) or rejected | Explicit policy |
| Null vs empty | Required vs optional profile fields | Auth and profile APIs aligned |

### Organization (tenant)

| Edge case | Specification | Expected behaviour |
|-----------|---------------|--------------------|
| Min string | Shortest org name | Accepted |
| Max string | Org name at limit | Accepted |
| Overlong | Name max+1 | Rejected |
| Special characters | `&` in legal name | Stored and escaped in exports |
| Unicode | Org name with diacritics | Unique constraints use correct collation |
| Null vs empty | Optional billing reference | Nullable semantics clear |

### Audit (container)

| Edge case | Specification | Expected behaviour |
|-----------|---------------|--------------------|
| Min string | Shortest audit title | Accepted |
| Max string | Description at limit | Accepted |
| Overlong | Title over limit | Rejected |
| Special characters | HTML in rich text (if any) | Sanitized on output |
| Unicode | Section titles multilingual | Ordering deterministic |
| Null vs empty | Optional scope fields | Filters correct |

### Evidence / document metadata

| Edge case | Specification | Expected behaviour |
|-----------|---------------|--------------------|
| Min string | Shortest filename | Accepted |
| Max string | Filename at filesystem/API limit | Accepted |
| Overlong | Filename over limit | Rejected before upload |
| Special characters | `/`, `\`, `..` in names | Rejected or normalized |
| Unicode | Non-ASCII filenames | Stored and served with correct encoding |
| Null vs empty | Optional description | Distinct from “no file” |

---

**Review cadence**: Revisit this document when adding new domains, changing reference formats, or altering pagination/date-filter contracts.
