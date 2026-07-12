import { expect, test, type Page, type Route } from "@playwright/test";

/**
 * Inspection → Findings → CAPA → Risk Register critical journey (mocked APIs).
 */

const E2E_JWT =
  "eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJzdWIiOiJlMmUiLCJleHAiOjE4MTUxODgxNTUsInJvbGUiOiJhZG1pbiIsImlzX3N1cGVydXNlciI6dHJ1ZSwidGVuYW50X2lkIjoxfQ.e2e";

const FINDING_ID = 501;
const FINDING_REF = "AF-00501";

async function json(route: Route, body: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

async function installInspectionCujMocks(page: Page) {
  await page.route("**/api/v1/**", async (route) => {
    const req = route.request();
    const url = new URL(req.url());
    const path = url.pathname;
    const method = req.method();

    if (path.endsWith("/audits/findings") && method === "GET") {
      await json(route, {
        items: [
          {
            id: FINDING_ID,
            reference_number: FINDING_REF,
            run_id: 41,
            title: "Missing PPE at gate",
            description: "Operator without gloves during inspection",
            severity: "high",
            finding_type: "nonconformity",
            status: "open",
            corrective_action_required: true,
            risk_ids: [88],
            created_at: "2026-07-12T10:00:00Z",
            updated_at: "2026-07-12T10:00:00Z",
          },
        ],
        total: 1,
        page: 1,
        page_size: 100,
        pages: 1,
      });
      return;
    }

    if (path.endsWith("/audits/runs") && method === "GET") {
      await json(route, {
        items: [
          {
            id: 41,
            reference_number: "AUD-00041",
            template_id: 11,
            title: "Site inspection",
            status: "completed",
            created_at: "2026-07-12T09:00:00Z",
          },
        ],
        total: 1,
        page: 1,
        page_size: 100,
        pages: 1,
      });
      return;
    }

    if (path.includes("/audits/templates") && method === "GET") {
      await json(route, { items: [], total: 0, page: 1, page_size: 100, pages: 0 });
      return;
    }

    if (path.includes("/actions") && method === "GET") {
      await json(route, {
        items: [
          {
            id: 900,
            reference_number: "CAPA-00900",
            title: "Action plan: Missing PPE at gate",
            status: "open",
            source_type: "audit_finding",
            source_id: FINDING_ID,
            priority: "high",
            created_at: "2026-07-12T10:05:00Z",
          },
        ],
        total: 1,
        page: 1,
        page_size: 50,
        pages: 1,
      });
      return;
    }

    if (path.includes("/risk-register") && method === "GET") {
      await json(route, {
        items: [
          {
            id: 88,
            reference: "RSK-00088",
            title: `Audit escalation: AUD-00041 / ${FINDING_REF}`,
            status: "open",
            linked_audits: ["AUD-00041", FINDING_REF],
            linked_actions: ["CAPA-00900"],
            inherent_score: 12,
            category: "compliance",
          },
        ],
        total: 1,
        page: 1,
        page_size: 50,
        pages: 1,
      });
      return;
    }

    await json(route, method === "GET" ? { items: [], total: 0, page: 1, page_size: 50, pages: 0 } : { ok: true });
  });
}

async function openAuditsFindings(page: Page) {
  await page.addInitScript((token) => {
    localStorage.setItem("access_token", token);
  }, E2E_JWT);

  await installInspectionCujMocks(page);
  await page.goto("/audits?view=findings", { waitUntil: "domcontentloaded" });
  await expect(page.getByText("Missing PPE at gate")).toBeVisible({ timeout: 20_000 });
}

test.describe("Inspection → CAPA → Risk CUJ", () => {
  test("Findings deep-links open CAPA Actions filtered to the finding", async ({ page }) => {
    await openAuditsFindings(page);

    await page.getByTestId(`finding-open-capa-${FINDING_ID}`).click();
    await expect(page).toHaveURL(new RegExp(`/actions\\?.*sourceType=audit_finding.*sourceId=${FINDING_ID}`));
    await expect(page.getByText(/Action plan: Missing PPE at gate/i)).toBeVisible({
      timeout: 20_000,
    });
  });

  test("Findings deep-links open Risk Register filtered to the finding ref", async ({ page }) => {
    await openAuditsFindings(page);

    await page.getByTestId(`finding-open-risk-${FINDING_ID}`).click();
    await expect(page).toHaveURL(new RegExp(`/risk-register\\?.*auditOnly=1.*auditRef=${FINDING_REF}`));
    await expect(page.getByText(new RegExp(FINDING_REF))).toBeVisible({ timeout: 20_000 });
  });
});
