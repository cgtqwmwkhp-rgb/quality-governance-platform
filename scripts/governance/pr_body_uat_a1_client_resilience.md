# Change Ledger (CL-UAT-A1-CLIENT-RESILIENCE)

## 1) Summary
- **Feature / Change name:** Wave A1 frontend reliability (PX-029 / ACT-052)
- **User goal:** Stop false Offline banners and premature request aborts; make create POSTs safer under timeout with Idempotency-Key and maybe-committed messaging.
- **Depends on:** None (FE-only axios client + OfflineIndicator wiring).
- **In scope:** Adaptive timeouts (reads 30s / writes 45s); timeout/abort must not set `connectionStatus=disconnected` while `navigator.onLine`; Idempotency-Key on create POSTs + Actions/CAPA writes; POST timeout classified as maybe-committed (no blind retry copy); unit tests + this ledger.
- **Out of scope:** Backend timeout/proxy changes; redesign OfflineIndicator UI; expanding server idempotency middleware scope.
- **Feature flag / kill switch:** N/A (client reliability hardening).

## 2) Impact Map
- **Frontend:** `frontend/src/api/client.ts`, `client.test.ts`, `OfflineIndicator.tsx` (+ test), `Login.tsx` comment.
- **Backend / APIs / DB:** None.
- **Observability:** Fewer false Offline states; timeout toasts distinguish maybe-committed writes.

## 3) Compatibility & Data Safety
- Additive client behaviour only; existing caller-supplied `Idempotency-Key` preserved.
- Explicit long timeouts (uploads / process jobs) still win over adaptive defaults.
- Backend IdempotencyMiddleware already honors the header when present.

## 4) Acceptance Criteria
- [x] AC-01: Default read timeout is 30s; mutating verbs default to 45s (documented why).
- [x] AC-02: Timeout/abort while `navigator.onLine` does not mark connection disconnected / Offline.
- [x] AC-03: Create POSTs receive an `Idempotency-Key` when the caller did not supply one.
- [x] AC-04: POST (write) timeout UX is maybe-committed — does not encourage blind retry without reconcile.
- [x] AC-05: Focused vitest coverage for timeouts, offline gating, and idempotency helpers.

## 5) Testing Evidence
- [x] Unit: `npx vitest run src/api/client.test.ts src/components/__tests__/OfflineIndicator.test.tsx`
- [ ] CI: PR checks

## 6) Critical Journeys
- [x] CUJ-01: Slow list GET under 30s completes; hung request times out without Offline banner while online.
- [x] CUJ-02: Create Incident/Complaint POST times out → maybe-committed message; retry only after list reconcile (same Idempotency-Key if retried via auth refresh).

## 7) Rollback Plan
- **Owner:** Platform release operator
- **Rollback steps:** Revert this PR / tip SHA; no DB rollback.
- **Trigger:** Elevated false Offline banners, create-POST failures, or timeout regressions.

## 8) Observability & Operations
- **Metrics:** Watch client timeout toast rate; OfflineIndicator false-positive reports.
- **Logs:** Browser network tab — confirm `Idempotency-Key` on create POSTs.
- **Runbook:** If Offline still appears on timeout, verify SWA tip includes this client change and `navigator.onLine` is true.

## 9) Release Plan
- Merge after CI green → SWA staging bake → spot-check create flows and Offline banner under throttled network.

## 10) Evidence Pack
- Focused vitest output attached in PR checks after push.

---

# Gate Checklist
- [x] **Gate 0:** Scope lock, AC, CUJs, Change Ledger complete.
- [x] **Gate 1:** Reuses existing axios client + OfflineIndicator; no second stack.
- [ ] **Gate 2:** CI green.
- [ ] **Gate 3:** Staging verification after SWA bake.
- [x] **Gate 4:** N/A canary (FE client reliability).
- [x] **Gate 5:** Rollback + observability documented.
