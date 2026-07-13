import { expect, test, type Page, type Route } from "@playwright/test";

/**
 * UVDB / Achilles import → specialist home → CAPA / Risk critical journey (mocked APIs).
 */

const E2E_JWT =
  "eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJzdWIiOiJlMmUiLCJleHAiOjE4MTUxODgxNTUsInJvbGUiOiJhZG1pbiIsImlzX3N1cGVydXNlciI6dHJ1ZSwidGVuYW50X2lkIjoxfQ.e2e";

const AUDIT_REF = "UVDB-2026-0041";
const RUN_ID = 41;
const JOB_ID = 72;
const UVDB_ROW_ID = 99;

async function json(route: Route, body: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

async function installUvdbDownstreamMocks(page: Page, options?: { missAuditRef?: boolean }) {
  const miss = options?.missAuditRef === true;

  await page.route("**/api/v1/**", async (route) => {
    const req = route.request();
    const url = new URL(req.url());
    const path = url.pathname;
    const method = req.method();

    if (path.endsWith("/uvdb/dashboard") && method === "GET") {
      await json(route, {
        summary: {
          total_audits: miss ? 0 : 1,
          active_audits: 0,
          completed_audits: miss ? 0 : 1,
          average_score: miss ? 0 : 91,
        },
        protocol: { name: "UVDB Verify B2", version: "V11.2", sections: 2 },
        certification_alignment: {},
      });
      return;
    }

    if (path.endsWith("/uvdb/sections") && method === "GET") {
      await json(route, { total_sections: 0, sections: [] });
      return;
    }

    if (path.includes("/uvdb/sections/scores") && method === "GET") {
      await json(route, { sections: {} });
      return;
    }

    if (path.endsWith("/uvdb/iso-mapping") && method === "GET") {
      await json(route, { description: "ISO", total_mappings: 0, mappings: [] });
      return;
    }

    if (path.endsWith("/uvdb/audits") && method === "GET") {
      await json(route, {
        total: miss ? 0 : 1,
        audits: miss
          ? []
          : [
              {
                id: UVDB_ROW_ID,
                audit_reference: AUDIT_REF,
                company_name: "Plantexpand Limited",
                audit_type: "B2",
                audit_date: "2026-07-01",
                status: "completed",
                percentage_score: 91,
                lead_auditor: "Jane Smith",
                audit_run_id: RUN_ID,
                import_job_id: JOB_ID,
              },
            ],
      });
      return;
    }

    if (path.endsWith(`/uvdb/audits/${UVDB_ROW_ID}`) && method === "GET") {
      await json(route, {
        id: UVDB_ROW_ID,
        audit_reference: AUDIT_REF,
        company_name: "Plantexpand Limited",
        company_id: "00019685",
        audit_type: "B2",
        audit_scope: null,
        audit_date: "2026-07-01",
        status: "completed",
        lead_auditor: "Jane Smith",
        total_score: 91,
        max_possible_score: 100,
        percentage_score: 91,
        section_scores: null,
        score_breakdown: [],
        source_document_asset_id: null,
        source_filename: null,
        findings_count: 1,
        major_findings: 0,
        minor_findings: 1,
        observations: 0,
        certifications: {},
        audit_notes: null,
        audit_run_id: RUN_ID,
        import_job_id: JOB_ID,
      });
      return;
    }

    if (path.endsWith(`/external-audit-imports/jobs/${JOB_ID}/reconciliation`) && method === "GET") {
      await json(route, {
        job_id: JOB_ID,
        audit_run_id: RUN_ID,
        audit_reference: AUDIT_REF,
        job_status: "completed",
        canonical_read_model: "specialist_sync_verification",
        specialist_home: { path: "/uvdb", label: "Achilles / UVDB" },
        accepted_total: 1,
        promoted_total: 1,
        accepted_pending_total: 0,
        failed_total: 0,
        failed_drafts: [],
        materialized: {
          audit_findings: 1,
          capa_actions: 1,
          enterprise_risks: 1,
          uvdb_audit_id: UVDB_ROW_ID,
        },
        proof_matrix: [
          { step: "promotion", status: "ok", detail: "1 finding(s) materialized" },
          { step: "uvdb_sync", status: "ok", detail: `UVDB audit id ${UVDB_ROW_ID}` },
        ],
        draft_results: [],
        view_links: {
          actions: "/actions?sourceType=audit_finding",
          risk_register: `/risk-register?auditOnly=1&auditRef=${AUDIT_REF}`,
          uvdb: `/uvdb?auditRef=${AUDIT_REF}`,
        },
      });
      return;
    }

    if (path.includes("/actions") && method === "GET") {
      await json(route, { items: [], total: 0, page: 1, page_size: 50, pages: 0 });
      return;
    }

    if (path.includes("/risk-register") && method === "GET") {
      await json(route, { items: [], total: 0, page: 1, page_size: 50, pages: 0 });
      return;
    }

    if (path.includes("/audits/runs") && method === "GET") {
      await json(route, { items: [], total: 0, page: 1, page_size: 100, pages: 0 });
      return;
    }

    await json(route, {});
  });
}

async function seedAuth(page: Page) {
  await page.addInitScript((token) => {
    window.localStorage.setItem("access_token", token);
    window.localStorage.setItem("token", token);
  }, E2E_JWT);
}

test.describe("UVDB import → home → CAPA/Risk CUJ", () => {
  test("import handoff lands on UVDB home with CAPA and Risk deep-links", async ({ page }) => {
    await seedAuth(page);
    await installUvdbDownstreamMocks(page);

    await page.goto(`/uvdb?auditRef=${AUDIT_REF}`);

    await expect(page.getByTestId("uvdb-reconciliation-panel")).toBeVisible();
    await expect(page.getByText(/Proof ready/i)).toBeVisible();

    await page.getByRole("button", { name: /audit history|uvdb\.tab\.audit_history/i }).click();
    await expect(page.getByRole("link", { name: "Import review" })).toHaveAttribute(
      "href",
      `/audits/${RUN_ID}/import-review?jobId=${JOB_ID}`,
    );

    const capa = page.getByTestId("uvdb-open-capa").first();
    await expect(capa).toHaveAttribute("href", "/actions?sourceType=audit_finding");
    await capa.click();
    await expect(page).toHaveURL(/\/actions\?.*sourceType=audit_finding/);
  });

  test("Risk Register deep-link is scoped to the UVDB audit reference", async ({ page }) => {
    await seedAuth(page);
    await installUvdbDownstreamMocks(page);

    await page.goto(`/uvdb?auditRef=${AUDIT_REF}`);
    await expect(page.getByTestId("uvdb-open-risk").first()).toBeVisible();

    await page.getByTestId("uvdb-open-risk").first().click();
    await expect(page).toHaveURL(
      new RegExp(`/risk-register\\?.*auditOnly=1.*auditRef=${AUDIT_REF}`),
    );
  });

  test("auditRef miss offers recovery CTAs instead of a dead end", async ({ page }) => {
    await seedAuth(page);
    await installUvdbDownstreamMocks(page, { missAuditRef: true });

    await page.goto("/uvdb?auditRef=MISSING-REF");

    await expect(page.getByTestId("uvdb-auditref-miss")).toBeVisible();
    await expect(page.getByTestId("uvdb-auditref-miss-recovery-audits")).toHaveAttribute(
      "href",
      "/audits?source=achilles",
    );
    await expect(page.getByTestId("uvdb-auditref-miss-recovery-clear")).toHaveAttribute(
      "href",
      "/uvdb",
    );
  });
});
