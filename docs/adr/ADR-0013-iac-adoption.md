# ADR-0013: Adopt Bicep for Infrastructure-as-Code

## Status

Proposed

## Date

2026-04-03

## Context

The Quality Governance Platform's Azure infrastructure is currently managed through a combination of Azure Portal point-and-click operations and ad-hoc shell scripts (e.g., `scripts/infra/autoscale_aca.sh`, `scripts/infra/azure_cost_alert.sh`). This approach has several problems:

1. **No reproducibility**: Environments cannot be reliably recreated from source control. Standing up a new staging or DR environment requires manual steps and tribal knowledge.
2. **Configuration drift**: Manual portal changes are not tracked, leading to divergence between environments.
3. **No review process**: Infrastructure changes bypass the PR review workflow that application code benefits from.
4. **Audit gaps**: The governance platform tracks application-level changes via audit trail, but infrastructure changes are invisible.

The platform runs exclusively on Azure (Container Apps, PostgreSQL Flexible Server, Azure Blob Storage, Static Web Apps, Azure Monitor) with no multi-cloud requirement on the roadmap.

## Decision

**Adopt Azure Bicep as the infrastructure-as-code (IaC) tool.**

All new infrastructure will be defined in Bicep modules under `infra/`. Existing shell scripts in `scripts/infra/` will be incrementally migrated to Bicep equivalents. Deployments will be triggered via GitHub Actions using `azure/arm-deploy`.

### Module structure

```
infra/
├── main.bicep              # Orchestrator
├── modules/
│   ├── container-app.bicep
│   ├── postgres.bicep
│   ├── storage.bicep
│   ├── monitoring.bicep
│   └── swa.bicep
└── parameters/
    ├── dev.bicepparam
    ├── staging.bicepparam
    └── prod.bicepparam
```

## Alternatives Considered

| Alternative | Pros | Cons | Verdict |
|-------------|------|------|---------|
| **Terraform** | Multi-cloud, large ecosystem, state management | Requires state backend (extra infra), HCL learning curve, Azure provider lags behind ARM API | Rejected — multi-cloud not needed, state management adds operational burden |
| **Pulumi** | General-purpose languages (Python/TS), strong typing | Requires Pulumi service or self-hosted backend, smaller community for Azure-specific patterns, additional SaaS dependency | Rejected — adds vendor dependency, team more familiar with declarative IaC |
| **ARM templates** | Native Azure, no tooling required | Verbose JSON, poor authoring experience, no modularity without linked templates | Rejected — Bicep compiles to ARM but is far more readable and maintainable |
| **Continue with shell scripts** | No learning curve | All existing problems persist, does not scale | Rejected |

## Consequences

**Positive:**

- Infrastructure changes go through PR review like application code.
- Environments become reproducible — a new staging environment is a parameter file change.
- What-if deployments (`az deployment group what-if`) enable safe preview of changes.
- Bicep is first-party Azure tooling with zero-lag API coverage and no external state to manage.
- Existing team familiarity with Azure Portal translates well to Bicep's resource model.

**Negative / trade-offs:**

- Learning curve for team members unfamiliar with Bicep syntax.
- Migration of existing shell scripts will take several sprints.
- Bicep locks us into Azure — acceptable given current strategy but would require re-evaluation if multi-cloud becomes a requirement.

**Risks:**

- Partial migration may leave some resources managed by scripts and others by Bicep, creating a split-brain period. Mitigated by tracking migration progress and tagging Bicep-managed resources.
- Bicep does not handle all operational tasks (e.g., data migrations, certificate rotation). Shell scripts remain appropriate for those.

## Participants

- Engineering Lead
- Platform / DevOps Engineer
- Security (reviewed for secrets handling)

## Related

- `scripts/infra/` — existing shell-based infrastructure scripts
- [ADR-0004](ADR-0004-ACA-STAGING-INFRASTRUCTURE.md) — Azure Container Apps staging infrastructure
- [ADR-0005](ADR-0005-production-dependencies.md) — production infrastructure dependencies
- [ADR-0006](ADR-0006-environment-and-config-strategy.md) — environment strategy
