# Change Ledger (CL-PX-427-CERTIFICATES-POST)

> **Start gate:** #1792 LIVE @ `6ce348983c8b`. `STACK_MAX=1`. Merge ≠ LIVE.
> David lock 2026-08-19: T6 PX-427 (W0 UAT LIVE-05 — a dated 9001 certificate
> must move the framework countdown). Last W0 UAT tip. Entra flag stays false.
> Exceptions cap 200. No invented CHAS / SSIP / PM / UVDB EXACT.

## 1) Summary
- **Feature / Change name:** PX-427 add `POST /compliance-automation/certificates` and an Add path on Monitoring and the shelf
- **User goal:** File a dated ISO 9001 certificate through the product and see the standards-matrix framework countdown leave "No dated cert". LIVE-05 could not be attempted at all: the register shipped three read routes and no writer, so `POST` answered **405**, and the only route to a dated row was a hand-written SQL insert — which the brief forbade and which would have proved nothing about the product.
- **In scope:** Align `CertificateCreate` to the `Certificate` columns and require the dates. Add the writer (`create_certificate`) with server-side `tenant_id` stamping and naive-UTC date normalisation. Add the `POST` route under `audit:create`. One `CertificateFormDialog` used from both register surfaces (Monitoring Certificates tab and the assurance cert shelf). i18n keys. Unit + vitest cover. Contract artefacts patched at the two affected nodes.
- **Out of scope:** Any SQL insert of a certificate. Editing or deleting a certificate (no `PATCH`/`DELETE` added). Uploading the certificate PDF (`primary_evidence_asset_id` / `document_url` stay server-side / Library-owned). Recomputing or storing `status`. Backfilling existing rows. Reminder scheduling. Touching the Library master, UVDB or Planet Mark systems of record on the shelf. Any `FF_*` flip. Any EXACT share.
- **Feature flag / kill switch:** None. Revert this PR; the route disappears and the register returns to read-only.

## 2) Impact Map (what changed)

| ID | Surface | Before | After |
|---|---|---|---|
| PX-427-01 | `POST /api/v1/compliance-automation/certificates` | No route — FastAPI answered **405** on the existing `GET` path | 201 with the stored row, under `require_permission("audit:create")` (the permission every other writer in this router already uses) |
| PX-427-02 | `CertificateCreate` field names | `issued_by` / `issued_date` — match **no** column and no caller; wiring the schema up as written would have dropped the issuer and the issue date on every write | `issuing_body` / `issue_date`, plus `entity_name`, `is_critical`, `reminder_days`, `notes` — every field names a real `certificates` column |
| PX-427-03 | `CertificateCreate` date requirement | `Optional`, while both columns are `NOT NULL` | `issue_date` and `expiry_date` required; `expiry_date` earlier than `issue_date` is a 422 |
| PX-427-04 | `CertificateCreate.extra` | `forbid` | Unchanged — `additionalProperties: false` in the published contract |
| PX-427-05 | Date binding | n/a (no writer) | `_as_naive_utc` **converts** an offset to UTC then drops the tzinfo. Same failure class as PX-424 / `_as_capa_naive`: asyncpg refuses an aware datetime on `TIMESTAMP WITHOUT TIME ZONE` |
| PX-427-06 | `tenant_id` | n/a | Stamped from the caller's session, never accepted as body data. Not decorative: every read in this service and in `AssuranceCertShelfService` matches `tenant_id IS NULL` **as well as** the caller's tenant, so a NULL row would be visible to every tenant on the deployment |
| PX-427-07 | `entity_id` | Required `string` on the client type, `NOT NULL` on the column | Optional in the body; the server supplies the tenant's own id for an organisation-level accreditation. The browser has no tenant id to send, and there is no row inside the tenant for a company certificate to point at |
| PX-427-08 | POST vs GET row shape | n/a | `_certificate_row` is shared by the list read and the writer, so what POST reports back cannot drift from what the next GET shows |
| PX-427-09 | Monitoring → Certificates tab | Read-only; header offered only "Open certificate shelf"; empty state offered nothing | Primary **Add certificate**, plus a CTA in the empty state. "Open certificate shelf" demoted to an outline link so the two do not compete |
| PX-427-10 | Assurance cert shelf panel | Read-only; header offered only Refresh | **Add certificate** alongside Refresh; saving reloads the shelf |
| PX-427-11 | `complianceAutomationApi.addCertificate` | Zero call sites, and typed `entity_id` as required | Called from `CertificateFormDialog`; type matches the shipped schema |

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Purely additive at the API surface. One new operation on an existing path; no existing route, response or schema changes shape. `CertificateCreate` was referenced by no route before this PR, so renaming its fields cannot break a caller — it was unreachable. The one frontend client type that named the old shape had zero call sites.
- **Breaking changes:** None reachable. `addCertificate`'s `entity_id` went from required to optional, which only widens what compiles.
- **Migration plan:** None. `certificates` already exists with every column this writer sets; no DDL.
- **Backfill:** None. Existing undated or absent certificates stay as they are — the operator files a real certificate through the form. Back-dating rows would invent assurance cover, which is the specific thing LIVE-05 is trying to measure honestly.
- **`status` is deliberately not derived on write.** The column default (`valid`) stands. Nothing in the codebase recomputes `status` afterwards, so a verdict stamped at create time would be a snapshot that silently goes stale; every reader that matters grades from `expiry_date` on each read (the Monitoring `loadData` overrides the stored value per row, the shelf derives readiness, and the framework countdown reads the expiry). Storing a fresher lie was the alternative and it loses.
- **Rollback strategy:** Revert merge; redeploy prior tip. Certificates filed while this was LIVE stay on the register and keep being read by the three GET routes; only the writer disappears.
- **Contract baseline:** `openapi-baseline.json` and `docs/contracts/openapi.json` patched at exactly two nodes — the new `post` operation and the `CertificateCreate` component — rather than regenerated. The committed artefacts carry pre-existing drift against `app.openapi()` (eleven unrelated paths, including alignment import, cell-aggregate and the exact/near-share surfaces, plus ~16 schemas); a full regeneration was attempted first and produced **1397 lines** of change belonging to other work, so it was reverted. This follows the PX-425a/b precedent. `test_openapi_baseline_matches_contracts_artifact` passes (the two files remain byte-identical) and `check_openapi_compatibility.py` reports **PASSED — no breaking changes**.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Certificate on the expiry register | Reachable only by hand-written SQL; `POST` was 405 | Reachable through the product, from either register surface |
| Framework countdown (LIVE-05) | "No dated cert" with no in-product way to change it | A dated `iso9001` certificate sets the 9001 countdown; unit asserts `due_soon` / `days_remaining` / `next_expiry` through the real shelf composer |
| Attribution honesty | n/a | A PAT/equipment certificate still paints **no** framework column and reports `unmatched_on_shelf`; asserted, not assumed |
| Tenant isolation | n/a | `tenant_id` stamped server-side; asserted. A NULL row would be cross-tenant visible because the reads match `IS NULL` |
| Timezone honesty | n/a | `+01:00` is converted, not dropped; asserted. Dropping it would move the recorded expiry an hour and shift the countdown a day at the boundary |
| extra=forbid honesty | Unknown fields 422 (unreachable schema) | Unchanged and now reachable; the dead `issued_by` / `issued_date` names are rejected, asserted |
| Invented CHAS / SSIP / PM / UVDB EXACT | Unchanged | Unchanged. Nothing writes to the Planet Mark, UVDB or Library systems of record; no EXACT share |
| Entra attestation flag | `ENTRA_ATTESTATION_ENABLED` false | Unchanged |
| Exceptions cap 200 | 200-row page | Unchanged |
| Evidence linkage | n/a | `primary_evidence_asset_id` / `document_url` are **not** client-settable, so a filed certificate cannot claim a PDF it has not got |

## 4) Acceptance Criteria (AC)
- [x] AC-01: `POST /api/v1/compliance-automation/certificates` exists and answers **201** with the stored row (`status_code=201` on the route; published in both contract artefacts).
- [x] AC-02: Every `CertificateCreate` field is a column on `certificates` — asserted against `Certificate.__table__.columns` rather than a hand-copied list, so a rename breaks the test instead of silently reintroducing a field that writes nowhere. `issued_by` / `issued_date` are rejected. Unknown fields still 422 under `extra="forbid"`.
- [x] AC-03: The writer stamps `tenant_id`, stores naive **UTC** (converting `+01:00` rather than discarding it), leaves `status` unset, and defaults `entity_id` to the tenant's own id only when the caller sends none.
- [x] AC-04: What POST returns is what the next GET lists — both build the row through `_certificate_row`, asserted by feeding the created object through `get_certificates`.
- [x] AC-05: A dated ISO 9001 certificate, taken from the writer through the real `AssuranceCertShelfService` composer, sets the 9001 framework countdown (`due_soon`, 19 days, `2027-08-01`) and leaves 14001 at `none`. A PAT certificate paints nothing. This is the LIVE-05 observable.
- [x] AC-06: **Add certificate** is reachable from the Monitoring Certificates tab (header and empty state) and from the assurance cert shelf; the payload carries the column names, omits blank optional fields rather than sending empty strings, and sends no `entity_id`.
- [x] AC-07: Contract artefacts describe the shipped schema; `check_openapi_compatibility.py` **PASSED**, no breaking change; baseline and contract stay identical.
- [ ] AC-08: Hosted CI green; STG+PROD SUCCESS (Build and Deploy not skipped); SHA match → LIVE.
- [ ] AC-09: After LIVE, file the real 9001 certificate on prod and snapshot the matrix countdown **before** claiming LIVE-05 closed.

## 5) Testing Evidence (link to runs)
- [x] Unit (local, focused): `tests/unit/test_certificates_create_px_427.py` — **16 passed**.
- [x] Unit (local, regression): full `tests/unit` — **7063 passed, 11 pre-existing skips, 0 failed**.
- [x] Contract (local): full `tests/contract` — **441 passed, 68 skipped, 59 xfailed, 0 failed**, including the OpenAPI-driven write-contract guards, which pick the new operation up automatically.
- [x] Contract artefacts (local): `tests/unit/test_gt_openapi_list_routes.py`, `test_gt_api_honesty_contract.py`, `test_copilot_openapi_exclusion.py`, `test_audit_contract_freeze.py` — 22 passed. `check_openapi_compatibility.py` PASSED.
- [x] Frontend (local, focused): `frontend/src/pages/__tests__/certificateFormDialog.test.tsx` — **10 passed**.
- [x] Frontend (local, regression): full `vitest run` — **3007 passed across 424 files, 0 failed**. `tsc --noEmit` clean. `eslint --max-warnings 0` clean on touched files.
- [x] i18n (local): `npm run i18n:check` — 4524 keys validated; Welsh coverage 91.0%, above the 80% gate.
- [x] Format (local): `isort` + `black` + `flake8` clean on all four touched Python files.
- [ ] Hosted CI — pending PR checks.

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Monitoring → Certificates → **Add certificate** → name, type `iso9001`, issue and expiry dates → 201, dialog closes, register reloads, success toast (vitest asserts the exact payload).
- [x] CUJ-02: Assurance cert shelf → **Add certificate** → same dialog, shelf reloads on save (vitest).
- [x] CUJ-03: Filing a dated 9001 certificate makes the standards-matrix 9001 countdown report a real expiry instead of "No dated cert" (unit, through the shelf composer).
- [x] CUJ-04: Submitting with a missing date, or an expiry before the issue date, is refused in the form **and** by the schema — the operator does not have to submit to find out (vitest + unit).
- [x] CUJ-05: An API failure leaves the typed work on screen with the server's message, rather than closing the dialog (vitest).
- [ ] CUJ-06: LIVE-05 on prod — file the real certificate and read the countdown, after this image is LIVE.

## 7) Observability & Ops
- No new signals. The failure direction is under-claiming: a certificate whose name and type mention no standard paints no framework column and is reported as `unmatched_on_shelf`, rather than being attributed to a framework it does not prove.
- A `tenant_id`-less session is refused with a 400 before the write, not an `assert` — `python -O` strips asserts, and a NULL `tenant_id` on this table reads back as visible to every tenant.
- `status` is not written, so no background job needs to keep it honest; the readers grade from `expiry_date`.
- **Unchanged, pre-existing, stated so it is not mistaken for something this PR fixed:** the register's GET serialises these columns with `datetime.isoformat()` and no `Z`, so a browser reads them as local time. The framework countdown is computed server-side in UTC and is unaffected; the Monitoring list's own expired/expiring bucketing can be off by the browser's offset (≤1h against a 30-day window). Adding a suffix would change an existing published response and belongs in its own change.
- Rollback: revert. Rows filed while LIVE remain readable through the three GET routes.

## 8) Release Plan (Local → Staging → Canary → Prod)
1. Merge after required CI green (`STACK_MAX=1`).
2. Staging: Monitoring → Certificates → Add certificate with a dated 9001 entry; confirm 201, the row in the GET list, and the countdown on the standards matrix. `/api/v1/health` SHA = tip.
3. Promote PROD; Production **Build and Deploy SUCCESS (not skipped)**; STG=PROD=MAIN SHA.
4. After LIVE, run LIVE-05 on prod and snapshot the countdown before claiming W0 UAT closure. Do not mix follow-on register work (edit/delete, PDF attach) into this PR.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** `POST /certificates` 500s (in particular an asyncpg timezone bind error); a filed certificate does not appear in the GET list; a row is written with a NULL `tenant_id` or is visible from another tenant; the countdown moves for a certificate that names no framework; unknown body fields accepted.
- **Rollback steps:** Revert merge; redeploy prior tip via governed Staging → Production; re-verify the ACA image SHA.
- **Owner:** Platform release operator / Standards Governance conveyor.

## 10) Evidence Pack (links)
- Branch: `fix/px-427-certificates-post`
- Ledger: `scripts/governance/pr_body_px_427_certificates_post.md`
- Predecessor: PX-425a/b builder clause tokens (`scripts/governance/pr_body_px_425ab_builder_clause_tokens.md`) — #1792, LIVE @ `6ce348983c8b`
- Date-normalisation precedent: PX-424 / `_as_capa_naive`
- UAT: W0 Operator Proofs 2026-08-18/19 LIVE-05

# Gate checklist
- [x] **Gate 0:** Scope lock + AC + Change Ledger
- [x] **Gate 1:** Focused unit + vitest tests (run locally before PR)
- [ ] **Gate 2:** CI green on tip
- [ ] **Gate 3:** STG tip verify
- [ ] **Gate 4:** PROD tip verify
- [ ] **Gate 5:** LIVE SHA match; LIVE-05 snapshotted on prod before W0 closure
