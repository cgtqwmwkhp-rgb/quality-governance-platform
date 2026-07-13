import { expect, test, type Page, type Route } from "@playwright/test";

/**
 * Inspection → Findings → CAPA → Risk Register critical journey (mocked APIs).
 */

const E2E_JWT =
  "eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJzdWIiOiJlMmUiLCJleHAiOjE4MTUxODgxNTUsInJvbGUiOiJhZG1pbiIsImlzX3N1cGVydXNlciI6dHJ1ZSwidGVuYW50X2lkIjoxfQ.e2e";

const FINDING_ID = 501;
const FINDING_REF = "AF-00501";
const RUN_ID = 41;
const TEMPLATE_ID = 11;

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

    if (path.endsWith("/actions/summary") && method === "GET") {
      await json(route, { total: 1, by_display_status: { open: 1 } });
      return;
    }

    if (path.includes("/actions") && method === "GET") {
      await json(route, {
        items: [
          {
            id: 900,
            reference_number: "CAPA-00900",
            title: "Action plan: Missing PPE at gate",
            description: "Operator without gloves during inspection",
            action_type: "corrective",
            status: "open",
            display_status: "open",
            action_key: "capa:900",
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

    if (path.endsWith(`/audits/findings/${FINDING_ID}/flag-risk`) && method === "POST") {
      await json(route, {
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
        updated_at: "2026-07-12T10:10:00Z",
      });
      return;
    }

    await json(route, method === "GET" ? { items: [], total: 0, page: 1, page_size: 50, pages: 0 } : { ok: true });
  });
}

async function installLiveCompletionMocks(page: Page) {
  let completed = false;
  let responseCreated = false;
  let completeRequests = 0;

  await page.route("**/api/v1/**", async (route) => {
    const req = route.request();
    const path = new URL(req.url()).pathname;
    const method = req.method();

    if (path.endsWith(`/audits/runs/${RUN_ID}`) && method === "GET") {
      await json(route, {
        id: RUN_ID,
        reference_number: "AUD-00041",
        template_id: TEMPLATE_ID,
        template_version: 1,
        template_name: "Warehouse PPE inspection",
        title: "Warehouse PPE inspection",
        location: "Warehouse A",
        status: completed ? "completed" : "in_progress",
        scheduled_date: "2026-07-12T09:00:00Z",
        responses: responseCreated
          ? [
              {
                id: 701,
                question_id: 81,
                response_value: "no",
                created_at: "2026-07-12T09:05:00Z",
              },
            ]
          : [],
        findings: completed
          ? [
              {
                id: FINDING_ID,
                reference_number: FINDING_REF,
                run_id: RUN_ID,
                title: "Are operators wearing the required PPE?",
                description: "Observed response: no",
                severity: "high",
                finding_type: "nonconformity",
                status: "open",
                corrective_action_required: true,
                risk_ids: [88],
              },
            ]
          : [],
        completion_percentage: completed ? 100 : 0,
        created_at: "2026-07-12T09:00:00Z",
      });
      return;
    }

    if (path.endsWith(`/audits/templates/${TEMPLATE_ID}`) && method === "GET") {
      await json(route, {
        id: TEMPLATE_ID,
        name: "Warehouse PPE inspection",
        audit_type: "inspection",
        version: 1,
        scoring_method: "percentage",
        allow_offline: false,
        require_gps: false,
        require_signature: false,
        require_approval: false,
        auto_create_findings: true,
        is_active: true,
        is_published: true,
        sections: [
          {
            id: 5,
            title: "PPE controls",
            is_active: true,
            sort_order: 1,
            questions: [
              {
                id: 81,
                question_text: "Are operators wearing the required PPE?",
                question_type: "yes_no",
                positive_answer: "yes",
                risk_category: "high",
                is_required: true,
                is_active: true,
                sort_order: 1,
                weight: 1,
                failure_triggers_action: true,
              },
            ],
          },
        ],
      });
      return;
    }

    if (path.endsWith(`/audits/runs/${RUN_ID}/responses`) && method === "POST") {
      responseCreated = true;
      await json(
        route,
        {
          id: 701,
          run_id: RUN_ID,
          question_id: 81,
          response_value: "no",
          created_at: "2026-07-12T09:05:00Z",
        },
        201,
      );
      return;
    }

    if (path.endsWith(`/audits/runs/${RUN_ID}/complete`) && method === "POST") {
      completeRequests += 1;
      completed = true;
      await json(route, {
        id: RUN_ID,
        status: "completed",
        findings_count: 1,
        actions_count: 1,
        risks_count: 1,
      });
      return;
    }

    if (path.endsWith("/actions/summary") && method === "GET") {
      await json(route, { total: 1, by_display_status: { open: 1 } });
      return;
    }

    if (path.includes("/actions") && method === "GET") {
      await json(route, {
        items: [
          {
            id: 900,
            reference_number: "CAPA-00900",
            title: "Action plan: Are operators wearing the required PPE?",
            description: "Observed response: no",
            action_type: "corrective",
            status: "open",
            display_status: "open",
            action_key: "capa:900",
            source_type: "audit_finding",
            source_id: FINDING_ID,
            priority: "high",
            created_at: "2026-07-12T09:06:00Z",
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

  return {
    completeRequests: () => completeRequests,
    responseCreated: () => responseCreated,
  };
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
  test.use({ serviceWorkers: "block" });

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
    await expect(page.getByRole("link", { name: `Open finding ${FINDING_REF}` })).toBeVisible({
      timeout: 20_000,
    });
  });

  test("Flag-to-risk posts and opens scoped Risk Register", async ({ page }) => {
    await page.addInitScript((token) => {
      localStorage.setItem("access_token", token);
    }, E2E_JWT);

    let flagCalls = 0;
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
              risk_ids: [],
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

      if (path.endsWith(`/audits/findings/${FINDING_ID}/flag-risk`) && method === "POST") {
        flagCalls += 1;
        await json(route, {
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
          updated_at: "2026-07-12T10:10:00Z",
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
              linked_actions: [],
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

      await json(
        route,
        method === "GET" ? { items: [], total: 0, page: 1, page_size: 50, pages: 0 } : { ok: true },
      );
    });

    await page.goto("/audits?view=findings", { waitUntil: "domcontentloaded" });
    await expect(page.getByText("Missing PPE at gate")).toBeVisible({ timeout: 20_000 });
    await page.getByTestId(`finding-flag-risk-${FINDING_ID}`).click();
    await expect.poll(() => flagCalls).toBe(1);
    await expect(page).toHaveURL(new RegExp(`/risk-register\\?.*auditOnly=1.*auditRef=${FINDING_REF}`));
    await expect(page.getByRole("link", { name: `Open finding ${FINDING_REF}` })).toBeVisible({
      timeout: 20_000,
    });
  });

  test("live inspection completion hands generated work to CAPA Actions", async ({ page }) => {
    await page.addInitScript((token) => {
      localStorage.setItem("access_token", token);
    }, E2E_JWT);
    const proof = await installLiveCompletionMocks(page);

    await page.goto(`/audits/${RUN_ID}/execute`, { waitUntil: "domcontentloaded" });
    await expect(page.getByText("Are operators wearing the required PPE?")).toBeVisible({
      timeout: 20_000,
    });

    await page.getByRole("button", { name: "NO" }).click();
    await expect(page.getByRole("button", { name: "Submit Audit & Generate Action Plan" })).toBeVisible();
    await page.getByRole("button", { name: "Submit Audit & Generate Action Plan" }).click();

    await expect(page.getByText("Inspection completed")).toBeVisible();
    await expect(page.getByText("1 finding / 1 action created")).toBeVisible();
    await expect(page.getByText("This completed inspection is live in the findings, actions, and risk workflows.")).toBeVisible();
    await expect(page.getByRole("button", { name: "View Audit Risks" })).toBeVisible();
    await expect.poll(proof.responseCreated).toBe(true);
    await expect.poll(proof.completeRequests).toBe(1);

    await expect(page).toHaveURL(/\/actions\?.*sourceType=audit_finding/, {
      timeout: 5_000,
    });
  });
});
