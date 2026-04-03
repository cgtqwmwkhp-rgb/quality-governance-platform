# Documentation Standards (D22)

Guidelines for documentation quality across the Quality Governance Platform.

## Document Categories

| Category | Location | Purpose | Review Cadence |
|----------|----------|---------|----------------|
| Architecture Decision Records | `docs/adr/` | Capture architectural decisions | On creation |
| Runbooks | `docs/runbooks/` | Operational procedures | Quarterly |
| API documentation | `docs/api/` | API design and usage | On API change |
| Infrastructure | `docs/infra/` | Infrastructure configuration and cost | Monthly |
| Evidence | `docs/evidence/` | Compliance and audit evidence | On change |
| Testing | `docs/testing/` | Test strategy and data | On change |
| Security | `docs/security/` | Security policies and reviews | Quarterly |
| SLOs | `docs/slo/` | Service level objectives | Monthly |

## Quality Guidelines

### Structure

- Every document starts with a heading (`# Title`) and a one-sentence summary.
- Use tables for structured data; avoid long prose paragraphs.
- Include a "Related Documents" section with links to related files.
- Use relative links to reference other docs in the repo.

### Content

- **Specific over generic**: Reference exact file paths, function names, and config keys.
- **Evidence over assertion**: Link to CI jobs, config files, or code that proves the claim.
- **Current state over aspirational**: Document what exists, with clear "Planned" labels for future work.
- **No stale content**: If a document references a specific value (e.g., coverage threshold), it must match the actual config.

### ADR Format

ADRs follow the standard template:
1. Title (ADR-NNNN: Descriptive Title)
2. Status (Proposed / Accepted / Deprecated / Superseded)
3. Date
4. Context (why the decision was needed)
5. Decision (what was decided)
6. Consequences (trade-offs and implications)

### Review Process

1. Documentation changes are included in the relevant PR.
2. At least one reviewer must verify documentation accuracy.
3. Runbooks must be validated by executing the procedure in staging.
4. ADRs require team discussion before acceptance.

## Related Documents

- [`docs/adr/`](adr/) — Architecture Decision Records
- [`docs/runbooks/`](runbooks/) — Operational runbooks
- [`scripts/governance/pr_body_template.md`](../scripts/governance/pr_body_template.md) — PR template
