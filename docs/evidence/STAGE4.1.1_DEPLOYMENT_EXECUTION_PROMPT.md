ROLE
You are the lead engineer executing the Stage 4.1.1 deployment. You must follow the gated deployment plan with precision, provide evidence for each step, and ensure zero downtime.

TASK
Execute Stage 4.1.1 deployment in two phases: D0 (external rehearsal) and D2 (staging deployment).

CONTEXT
Stage 4.1.1 PR #28 has been merged to main. The post-merge smoke plan was successful. Now we proceed with the gated deployment plan.

PHASE 0 — D0 GATE 1: EXTERNAL REHEARSAL (DRY-RUN)
1) **Objective**: Verify deployment scripts and rollback procedures without touching live infrastructure.
2) **Environment**: Use a local Docker environment that mirrors production.
3) **Steps**:
   a) Pull latest `main` branch.
   b) Build Docker images (`api`, `worker`, `migrations`).
   c) Run migrations against a clean, local Postgres DB.
   d) Start API and worker services.
   e) Run the full post-merge smoke plan against the local environment.
   f) Execute rollback drill: run `alembic downgrade` to previous migration.
   g) Verify rollback was successful.
4) **Evidence**: Provide command logs and pass/fail status for each step.

GATE 0 (HARD STOP)
Stop unless D0 rehearsal is 100% successful.

PHASE 1 — D2 STAGING DEPLOYMENT
1) **Objective**: Deploy to Azure staging environment and verify.
2) **Environment**: Azure App Service (staging slot) + Azure Database for PostgreSQL.
3. **Steps**:
   a) **Pre-flight check**: Confirm staging environment is healthy.
   b) **Deploy**: Trigger Azure DevOps pipeline to deploy `main` branch to staging slot.
   c) **Migrations**: Run Alembic migrations against staging DB.
   d) **Verification**: Run the full post-merge smoke plan against the staging URL.
   e) **Rollback Drill**: Swap back to the previous deployment slot.
   f) **Verify Rollback**: Confirm the old version is running.
   g) **Re-deploy**: Swap back to the new version.
4) **Evidence**: Provide Azure DevOps pipeline URL, smoke test results, and pass/fail status for each step.

GATE 1 (HARD STOP)
Stop unless D2 deployment, verification, and rollback drill are 100% successful.

FINAL STOP CONDITION
Stop only when:
- D0 rehearsal is complete and successful
- D2 staging deployment is complete, verified, and rollback drill is successful

CONSTRAINTS
- No production changes
- Follow runbooks exactly
- Document every command and result

FORMAT (MANDATORY OUTPUT)
For each phase:
1) Environment details
2) Command logs for each step
3) Pass/fail status for each step
4. Evidence (screenshots, logs, URLs)
5) Gate Met: YES/NO
