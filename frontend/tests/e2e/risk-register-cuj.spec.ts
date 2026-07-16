import { expect, test, type Page, type Route } from "@playwright/test";

/**
 * Risk Register critical journey (mocked APIs).
 * Honesty + CAPA/audit deep-link proof — exclusive of locked CUJ pages (#909–#916).
 * #853 SMTP/PD parked — never invent secrets.
 */

const E2E_JWT =
  "eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJzdWIiOiJlMmUiLCJleHAiOjE4MTUxODgxNTUsInJvbGUiOiJhZG1pbiIsImlzX3N1cGVydXNlciI6dHJ1ZSwidGVuYW50X2lkIjoxfQ.e2e";

async function json(route: Route, body: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

const RISK = {
  id: 88,
  reference: "RSK-00088",
  title: "Inspection escalation",
  category: "compliance",
  department: "Operations",
  inherent_score: 16,
  residual_score: 12,
  treatment_strategy: "treat",
  status: "monitoring",
  is_within_appetite: false,
  risk_owner_name: "QA Lead",
  next_review_date: "2026-06-01",
  is_escalated: true,
  linked_audits: ["AUD-00041", "AF-00501"],
  linked_actions: ["CAPA-00900"],
};

const SUMMARY = {
  total_risks: 1,
  by_level: { critical: 0, high: 1, medium: 0, low: 0 },
  outside_appetite: 1,
  overdue_review: 3,
  escalated: 1,
  by_category: { compliance: 1 },
};

async function installRiskRegisterMocks(
  page: Page,
  opts?: { failList?: boolean; failSummary?: boolean; failHeatmap?: boolean },
) {
  await page.route("**/api/v1/**", async (route) => {
    const req = route.request();
    const url = new URL(req.url());
    const path = url.pathname;
    const method = req.method();

    if (path.includes("/risk-register/summary") && method === "GET") {
      if (opts?.failSummary) {
        await json(route, { detail: "Summary unavailable" }, 503);
        return;
      }
      await json(route, SUMMARY);
      return;
    }

    if (path.includes("/risk-register/heatmap") && method === "GET") {
      if (opts?.failHeatmap) {
        await json(route, { detail: "Heatmap unavailable" }, 503);
        return;
      }
      await json(route, {
        matrix: Array.from({ length: 5 }, (_, row) =>
          Array.from({ length: 5 }, (__, col) => ({
            likelihood: 5 - row,
            impact: col + 1,
            score: (5 - row) * (col + 1),
            level: 'low',
            color: '#22c55e',
            risk_count: 0,
            risk_ids: [],
            risk_titles: [],
          })),
        ),
        summary: {
          total_risks: 0,
          critical_risks: 0,
          high_risks: 0,
          outside_appetite: 0,
          average_inherent_score: 0,
          average_residual_score: 0,
        },
        likelihood_labels: { 1: 'Rare', 2: 'Unlikely', 3: 'Possible', 4: 'Likely', 5: 'Almost Certain' },
        impact_labels: { 1: 'Insignificant', 2: 'Minor', 3: 'Moderate', 4: 'Major', 5: 'Catastrophic' },
      });
      return;
    }

    if (path.match(/\/risk-register\/?$/) || path.includes("/risk-register/?")) {
      if (method === "GET") {
        if (opts?.failList) {
          await json(route, { detail: "Risk register unavailable" }, 503);
          return;
        }
        const triage = url.searchParams.get("suggestion_triage");
        if (triage === "pending") {
          await json(route, { items: [], total: 0, skip: 0, limit: 1 });
          return;
        }
        await json(route, { items: [RISK], total: 1, skip: 0, limit: 100 });
        return;
      }
    }

    if (path.includes("/risk-register") && method === "GET") {
      if (opts?.failList) {
        await json(route, { detail: "Risk register unavailable" }, 503);
        return;
      }
      await json(route, { items: [RISK], total: 1, skip: 0, limit: 100 });
      return;
    }

    if (path.endsWith("/audits/runs") && method === "GET") {
      await json(route, {
        items: [{ id: 41, reference_number: "AUD-00041" }],
        total: 1,
        page: 1,
        page_size: 100,
        pages: 1,
      });
      return;
    }

    if (path.endsWith("/audits/findings") && method === "GET") {
      await json(route, {
        items: [{ id: 501, reference_number: "AF-00501" }],
        total: 1,
        page: 1,
        page_size: 100,
        pages: 1,
      });
      return;
    }

    if (path.includes("/auth/") || path.includes("/users/me") || path.includes("/feature-flags")) {
      await json(route, {
        id: 1,
        email: "e2e@example.com",
        role: "admin",
        is_superuser: true,
        tenant_id: 1,
        flags: {},
      });
      return;
    }

    await json(route, {});
  });
}

async function openRiskRegister(
  page: Page,
  opts?: { failList?: boolean; failSummary?: boolean; failHeatmap?: boolean },
) {
  await page.addInitScript((token) => {
    window.localStorage.setItem("access_token", token);
    window.localStorage.setItem("token", token);
  }, E2E_JWT);
  await installRiskRegisterMocks(page, opts);
  await page.goto("/risk-register");
  await expect(page.getByRole("heading", { name: "Enterprise Risk Register" })).toBeVisible({
    timeout: 20_000,
  });
}

test.describe("Risk Register CUJ honesty", () => {
  test.use({ serviceWorkers: "block" });

  test("CUJ-01 live register shows nested summary, audit + CAPA deep-links", async ({ page }) => {
    await openRiskRegister(page);

    await expect(page.getByTestId("risk-register-live-badge")).toHaveText("Live data");
    await expect(page.getByTestId("risk-metric-high")).toHaveText("1");
    await expect(page.getByTestId("risk-metric-overdue-review")).toHaveText("3");
    await expect(page.getByTestId("risk-metric-outside-appetite")).toHaveText("1");

    await expect(page.getByText("Inspection escalation")).toBeVisible();
    await expect(page.getByRole("link", { name: "Open audit AUD-00041" })).toHaveAttribute(
      "href",
      "/audits/41/execute",
    );
    await expect(page.getByRole("link", { name: "Open finding AF-00501" })).toHaveAttribute(
      "href",
      "/audits?view=findings&findingId=501",
    );
    await expect(page.getByRole("link", { name: "Open CAPA for RSK-00088" })).toHaveAttribute(
      "href",
      "/actions?sourceType=risk&sourceId=88",
    );
  });

  test("CUJ-02 list failure shows unavailable — not faux empty zeros", async ({ page }) => {
    await openRiskRegister(page, { failList: true });

    await expect(page.getByTestId("risk-register-load-error")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("risk-register-unavailable")).toContainText(
      /not an empty register/i,
    );
    await expect(page.getByText("No risks found in the register")).toHaveCount(0);
    await expect(page.getByTestId("risk-metric-total")).toHaveText("—");
    await expect(page.getByTestId("risk-metric-overdue-review")).toHaveAttribute(
      "aria-label",
      "Overdue review unavailable",
    );
  });

  test("summary failure distinguishes unavailable metrics from empty register", async ({
    page,
  }) => {
    await openRiskRegister(page, { failSummary: true });

    await expect(page.getByTestId("risk-register-partial-badge")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByText("Inspection escalation")).toBeVisible();
    await expect(page.getByTestId("risk-metric-overdue-review")).toHaveText("—");
    await expect(page.getByText(/Overdue Review \(unavailable\)/i)).toBeVisible();
    await expect(page.getByTestId("risk-register-empty")).toHaveCount(0);
  });
});
