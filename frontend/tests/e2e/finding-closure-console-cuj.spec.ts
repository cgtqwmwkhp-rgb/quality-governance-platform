import { expect, test, type Page, type Route } from "@playwright/test";

/**
 * CUJ-A11 — Inspector Finding Closure & Loop-Status Console (mocked APIs).
 * Path: /audits?view=findings → ribbon → assign CAPA → complete CAPA → close finding.
 */

const E2E_JWT =
  "eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJzdWIiOiJlMmUiLCJleHAiOjE4MTUxODgxNTUsInJvbGUiOiJhZG1pbiIsImlzX3N1cGVydXNlciI6dHJ1ZSwidGVuYW50X2lkIjoxfQ.e2e";

const FINDING_ID = 501;
const FINDING_REF = "AF-00501";
const CAPA_ID = 900;

async function json(route: Route, body: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

function findingPayload(overrides: Record<string, unknown> = {}) {
  return {
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
    ...overrides,
  };
}

function capaPayload(overrides: Record<string, unknown> = {}) {
  return {
    id: CAPA_ID,
    reference_number: "CAPA-00900",
    title: "Action plan: Missing PPE at gate",
    description: "Operator without gloves during inspection",
    action_type: "corrective",
    status: "open",
    display_status: "open",
    action_key: `capa:${CAPA_ID}`,
    source_type: "audit_finding",
    source_id: FINDING_ID,
    assigned_to_email: "capa.owner@example.com",
    priority: "high",
    created_at: "2026-07-12T10:05:00Z",
    ...overrides,
  };
}

async function installFindingLoopMocks(
  page: Page,
  options?: { capaCompleted?: boolean },
) {
  let finding = findingPayload();
  let capa = capaPayload(
    options?.capaCompleted
      ? { status: "closed", display_status: "completed" }
      : {},
  );
  let closeCalls = 0;
  let assignCalls = 0;

  await page.route("**/api/v1/**", async (route) => {
    const req = route.request();
    const url = new URL(req.url());
    const path = url.pathname;
    const method = req.method();

    if (path.endsWith("/audits/findings") && method === "GET") {
      await json(route, {
        items: [finding],
        total: 1,
        page: 1,
        page_size: 100,
        pages: 1,
      });
      return;
    }

    if (path.endsWith(`/audits/findings/${FINDING_ID}`) && method === "PATCH") {
      closeCalls += 1;
      const body = req.postDataJSON() as Record<string, unknown>;
      finding = findingPayload({
        status: body.status || "closed",
        closure_note: body.closure_note,
      });
      await json(route, finding);
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

    if (path.includes("/actions") && method === "GET" && !path.includes("/by-key")) {
      await json(route, {
        items: [capa],
        total: 1,
        page: 1,
        page_size: 100,
        pages: 1,
      });
      return;
    }

    if (path.includes(`/actions/${CAPA_ID}`) && method === "PATCH") {
      assignCalls += 1;
      const body = req.postDataJSON() as Record<string, unknown>;
      capa = capaPayload({
        ...capa,
        assigned_to_email: body.assigned_to_email || capa.assigned_to_email,
        status: body.status || capa.status,
        display_status: body.status === "completed" || body.status === "closed"
          ? "completed"
          : (body.display_status as string) || capa.display_status,
      });
      await json(route, capa);
      return;
    }

    if (path.includes("/actions/") && method === "POST") {
      assignCalls += 1;
      const body = req.postDataJSON() as Record<string, unknown>;
      capa = capaPayload({
        assigned_to_email: body.assigned_to_email,
      });
      await json(route, capa, 201);
      return;
    }

    await json(
      route,
      method === "GET" ? { items: [], total: 0, page: 1, page_size: 50, pages: 0 } : { ok: true },
    );
  });

  return {
    closeCalls: () => closeCalls,
    assignCalls: () => assignCalls,
    setCapaCompleted: () => {
      capa = capaPayload({ status: "closed", display_status: "completed" });
    },
  };
}

test.describe("CUJ-A11 finding loop status console", () => {
  test("ribbon shows finding / CAPA / risk and gates close while CAPA is open", async ({
    page,
  }) => {
    await page.addInitScript((token) => {
      localStorage.setItem("access_token", token);
    }, E2E_JWT);
    const proof = await installFindingLoopMocks(page);

    await page.goto("/audits?view=findings", { waitUntil: "domcontentloaded" });
    await expect(page.getByText("Missing PPE at gate")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId(`finding-loop-ribbon-${FINDING_ID}`)).toBeVisible();
    await expect(page.getByTestId(`finding-loop-capa-status-${FINDING_ID}`)).toContainText("open");
    await expect(page.getByTestId(`finding-loop-capa-assignee-${FINDING_ID}`)).toContainText(
      "capa.owner@example.com",
    );
    await expect(page.getByTestId(`finding-loop-risk-status-${FINDING_ID}`)).toContainText("Linked");
    await expect(page.getByTestId(`finding-loop-gate-${FINDING_ID}`)).toBeVisible();

    await page.getByTestId(`finding-loop-close-${FINDING_ID}`).click();
    await expect(page.getByTestId(`finding-loop-close-submit-${FINDING_ID}`)).toBeDisabled();
    await page.getByTestId(`finding-loop-override-${FINDING_ID}`).check();
    await page
      .getByTestId(`finding-loop-override-reason-${FINDING_ID}`)
      .fill("Supervisor accepted residual risk");
    await page.getByTestId(`finding-loop-close-submit-${FINDING_ID}`).click();
    await expect.poll(() => proof.closeCalls()).toBe(1);
    await expect(page.getByTestId(`finding-loop-finding-status-${FINDING_ID}`)).toContainText(
      "closed",
    );
  });

  test("assign CAPA from card then close after CAPA completed without override", async ({
    page,
  }) => {
    await page.addInitScript((token) => {
      localStorage.setItem("access_token", token);
    }, E2E_JWT);
    const proof = await installFindingLoopMocks(page, { capaCompleted: true });

    await page.goto("/audits?view=findings", { waitUntil: "domcontentloaded" });
    await expect(page.getByTestId(`finding-loop-ribbon-${FINDING_ID}`)).toBeVisible({
      timeout: 20_000,
    });
    await expect(page.getByTestId(`finding-loop-capa-status-${FINDING_ID}`)).toContainText(
      "completed",
    );
    await expect(page.getByTestId(`finding-loop-gate-${FINDING_ID}`)).toHaveCount(0);

    await page.getByTestId(`finding-loop-assign-${FINDING_ID}`).click();
    await page
      .getByTestId(`finding-loop-assign-email-${FINDING_ID}`)
      .fill("new.owner@example.com");
    await page.getByTestId(`finding-loop-assign-submit-${FINDING_ID}`).click();
    await expect.poll(() => proof.assignCalls()).toBe(1);

    await page.getByTestId(`finding-loop-close-${FINDING_ID}`).click();
    await page.getByTestId(`finding-loop-close-submit-${FINDING_ID}`).click();
    await expect.poll(() => proof.closeCalls()).toBe(1);
    await expect(page.getByTestId(`finding-loop-ribbon-${FINDING_ID}`)).toHaveAttribute(
      "data-loop-complete",
      "true",
    );
  });
});
