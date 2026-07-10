import { expect, test, type Page, type Route } from "@playwright/test";

/**
 * External Audit Import Review — Reset + Promote critical journey.
 *
 * Runs against staging SWA with API responses mocked so the gate does not
 * depend on live OCR/import fixtures. Auth uses a non-expired unsigned JWT
 * in localStorage (client only checks exp + shape).
 */

const E2E_JWT =
  "eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJzdWIiOiJlMmUiLCJleHAiOjE4MTUxODgxNTUsInJvbGUiOiJhZG1pbiIsImlzX3N1cGVydXNlciI6dHJ1ZSwidGVuYW50X2lkIjoxfQ.e2e";

const JOB_ID = 72;
const AUDIT_ID = 41;
const DRAFT_ID = 11;

type DraftStatus = "draft" | "accepted" | "rejected" | "promoted";

function baseJob(status: string) {
  return {
    id: JOB_ID,
    audit_run_id: AUDIT_ID,
    reference_number: "IMP-00072",
    status,
    specialist_home_path: "/uvdb",
    specialist_home_label: "Open Achilles / UVDB",
    promotion_summary_json: null,
    positive_summary_json: [],
    nonconformity_summary_json: [],
    improvement_summary_json: [],
    evidence_preview_json: [],
    processing_warnings_json: [],
    provenance_json: {
      processing_template_id: 11,
      processing_template_version: 3,
      declared_source_origin: "third_party",
      declared_assurance_scheme: "Achilles UVDB",
    },
    source_document_asset_id: 1,
    has_tabular_data: false,
    created_at: "2026-07-01T00:00:00Z",
  };
}

function baseDraft(status: DraftStatus) {
  return {
    id: DRAFT_ID,
    import_job_id: JOB_ID,
    audit_run_id: AUDIT_ID,
    status,
    title: "Needs follow-up",
    description: "Evidence snippet",
    severity: "high",
    finding_type: "nonconformity",
    confidence_score: 0.88,
    competence_verdict: null,
    evidence_snippets_json: ["Evidence snippet"],
    mapped_frameworks_json: [{ framework: "Achilles UVDB" }],
    mapped_standards_json: [{ standard: "ISO 9001", clause_number: "8.1" }],
    suggested_action_title: "Address issue",
    suggested_risk_title: "Create risk",
    promoted_finding_id: status === "promoted" ? 9001 : null,
  };
}

async function json(route: Route, body: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

async function installImportMocks(page: Page) {
  let draftStatus: DraftStatus = "accepted";
  let jobStatus = "review_required";
  let promoteCalls = 0;
  let resetCalls = 0;

  await page.route("**/api/**", async (route) => {
    const req = route.request();
    const method = req.method();
    const url = new URL(req.url());
    const path = url.pathname;

    if (path.includes(`/external-audit-imports/jobs/${JOB_ID}/promote`) && method === "POST") {
      promoteCalls += 1;
      draftStatus = "promoted";
      jobStatus = "completed";
      await json(route, {
        ...baseJob(jobStatus),
        promoted_at: "2026-07-10T00:00:00Z",
        promotion_summary_json: {
          promoted_findings: [9001],
          failed_drafts: [],
          reconciliation: {
            promoted_total: 1,
            failed_total: 0,
            status: "ok",
          },
        },
      });
      return;
    }

    if (path.includes(`/external-audit-imports/drafts/${DRAFT_ID}`) && method === "PATCH") {
      const body = req.postDataJSON() as { status?: DraftStatus };
      if (body?.status === "draft") {
        resetCalls += 1;
        draftStatus = "draft";
      } else if (body?.status) {
        draftStatus = body.status;
      }
      await json(route, baseDraft(draftStatus));
      return;
    }

    if (path.includes(`/external-audit-imports/jobs/${JOB_ID}/drafts`) && method === "GET") {
      await json(route, [baseDraft(draftStatus)]);
      return;
    }

    if (path.includes(`/external-audit-imports/jobs/${JOB_ID}/reconciliation`) && method === "GET") {
      await json(route, {
        job_id: JOB_ID,
        audit_run_id: AUDIT_ID,
        audit_reference: "AUD-00041",
        job_status: jobStatus,
        canonical_read_model: "external_audit_import_job",
        specialist_home: { path: "/uvdb", label: "Open Achilles / UVDB" },
        accepted_total: 1,
        promoted_total: draftStatus === "promoted" ? 1 : 0,
        accepted_pending_total: draftStatus === "accepted" ? 1 : 0,
        failed_total: 0,
        failed_drafts: [],
        materialized: {
          audit_findings: draftStatus === "promoted" ? 1 : 0,
          capa_actions: draftStatus === "promoted" ? 1 : 0,
          enterprise_risks: 0,
          uvdb_audit_id: null,
        },
        proof_matrix: [
          {
            step: "findings",
            status: draftStatus === "promoted" ? "ok" : "none",
            detail: "Mock proof step",
          },
        ],
        draft_results: [],
        view_links: {
          actions: "/actions?sourceType=audit_finding",
          risk_register: "/risk-register?triage=import",
          uvdb: "/uvdb",
          specialist_home: "/uvdb",
        },
      });
      return;
    }

    if (path.includes(`/external-audit-imports/jobs/${JOB_ID}`) && method === "GET") {
      await json(route, baseJob(jobStatus));
      return;
    }

    if (path.includes(`/external-audit-imports/runs/${AUDIT_ID}/latest-job`) && method === "GET") {
      await json(route, baseJob(jobStatus));
      return;
    }

    if (path.includes(`/audits/runs/${AUDIT_ID}`) && method === "GET") {
      await json(route, {
        id: AUDIT_ID,
        reference_number: "AUD-00041",
        template_id: 11,
        template_version: 3,
        template_name: "External Audit Intake",
        title: "Achilles follow-up audit",
        source_origin: "third_party",
        assurance_scheme: "Achilles UVDB",
        status: "completed",
        is_external_audit_import: true,
      });
      return;
    }

    // Soft-default ALL remaining API traffic — never hit live staging (avoids 429s).
    await json(route, method === "GET" ? {} : { ok: true });
  });

  return {
    getPromoteCalls: () => promoteCalls,
    getResetCalls: () => resetCalls,
  };
}

async function openImportReview(page: Page) {
  await page.addInitScript((token) => {
    localStorage.setItem("access_token", token);
  }, E2E_JWT);

  const counters = await installImportMocks(page);
  await page.goto(`/audits/${AUDIT_ID}/import-review?jobId=${JOB_ID}`, {
    waitUntil: "domcontentloaded",
  });
  await expect(page.getByRole("heading", { name: "External Audit Review" })).toBeVisible({
    timeout: 20_000,
  });
  // Wait until mocked drafts hydrate (not the loading-only chrome).
  await expect(page.getByText("Needs follow-up")).toBeVisible({ timeout: 20_000 });
  return counters;
}

test.describe("Import review Reset / Promote", () => {
  test("Reset accepted finding to draft via review PATCH", async ({ page }) => {
    const counters = await openImportReview(page);

    await expect(page.getByRole("button", { name: /Reset finding to draft/i })).toBeVisible();
    await page.getByRole("button", { name: /Reset finding to draft/i }).click();

    await expect.poll(() => counters.getResetCalls()).toBe(1);
    await expect(page.getByRole("button", { name: /Reset finding to draft/i })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Accept" })).toBeVisible();
  });

  test("Promote accepted drafts confirms and completes", async ({ page }) => {
    const counters = await openImportReview(page);

    await expect(page.getByRole("button", { name: "Promote Accepted Drafts" })).toBeEnabled();
    await page.getByRole("button", { name: "Promote Accepted Drafts" }).click();
    await page.getByRole("button", { name: "Confirm Promote" }).click();

    await expect.poll(() => counters.getPromoteCalls()).toBe(1);
    await expect(page.getByRole("alert")).toContainText(/Successfully promoted/i);
  });
});
