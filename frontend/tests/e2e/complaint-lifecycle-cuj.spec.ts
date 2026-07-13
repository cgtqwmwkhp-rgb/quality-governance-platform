import { expect, test, type Page, type Route } from "@playwright/test";

/**
 * Complaint admin lifecycle critical journey (mocked APIs).
 * CUJ-01: detail → acknowledge → action → investigation (stay on detail)
 * CUJ-02: running-sheet narrative + key dates honesty
 */

const E2E_JWT =
  "eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJzdWIiOiJlMmUiLCJleHAiOjE4MTUxODgxNTUsInJvbGUiOiJhZG1pbiIsImlzX3N1cGVydXNlciI6dHJ1ZSwidGVuYW50X2lkIjoxfQ.e2e";

const COMPLAINT_ID = 15;
const INVESTIGATION_ID = 25;
const ACTION_ID = 301;

async function json(route: Route, body: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

const complaintRecord = {
  id: COMPLAINT_ID,
  reference_number: "COMP-00015",
  title: "Late repairs response",
  description: "The operative did not arrive when promised.",
  complaint_type: "service",
  priority: "high",
  status: "received",
  received_date: "2026-03-10T08:30:00Z",
  complainant_name: "Carol Customer",
  complainant_email: "carol@example.com",
  complainant_phone: "07000000000",
  department: "Responsive Repairs",
  resolution_summary: null,
  created_at: "2026-03-10T08:35:00Z",
  updated_at: "2026-03-10T08:35:00Z",
  reporter_submission: {
    contract: "responsive_repairs",
    complainant_role: "Resident",
    location: "Block A",
    photos: { count: 1 },
  },
};

async function installComplaintCujMocks(
  page: Page,
  options?: { investigations?: unknown[]; runningSheet?: unknown[]; actions?: unknown[] },
) {
  let complaint = { ...complaintRecord };
  const investigations = options?.investigations ?? [];
  const runningSheet = options?.runningSheet ?? [];
  const actions = options?.actions ?? [];

  await page.route("**/api/v1/**", async (route) => {
    const req = route.request();
    const url = new URL(req.url());
    const path = url.pathname;
    const method = req.method();

    if (path.endsWith(`/complaints/${COMPLAINT_ID}`) && method === "GET") {
      await json(route, complaint);
      return;
    }

    if (path.endsWith(`/complaints/${COMPLAINT_ID}`) && method === "PATCH") {
      const body = req.postDataJSON() as Record<string, unknown>;
      complaint = { ...complaint, ...body, updated_at: new Date().toISOString() };
      await json(route, complaint);
      return;
    }

    if (path.endsWith(`/complaints/${COMPLAINT_ID}/investigations`) && method === "GET") {
      await json(route, {
        items: investigations,
        total: investigations.length,
        page: 1,
        page_size: 10,
        pages: investigations.length > 0 ? 1 : 0,
      });
      return;
    }

    if (path.endsWith(`/complaints/${COMPLAINT_ID}/running-sheet`) && method === "GET") {
      await json(route, runningSheet);
      return;
    }

    if (path.endsWith(`/complaints/${COMPLAINT_ID}/running-sheet`) && method === "POST") {
      const body = req.postDataJSON() as { content: string };
      runningSheet.unshift({
        id: runningSheet.length + 1,
        content: body.content,
        created_at: new Date().toISOString(),
        author_email: "admin@example.com",
        entry_type: "note",
      });
      await json(route, runningSheet[0], 201);
      return;
    }

    if (path.endsWith("/investigations/from-record") && method === "POST") {
      const body = req.postDataJSON() as { title: string; source_type: string; source_id: number };
      const created = {
        id: INVESTIGATION_ID,
        reference_number: "INV-00025",
        title: body.title,
        assigned_entity_type: "complaint",
        assigned_entity_id: body.source_id,
        status: "draft",
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      investigations.unshift(created);
      await json(route, created, 201);
      return;
    }

    if (path.includes("/actions") && method === "GET") {
      const sourceType = url.searchParams.get("source_type") || url.searchParams.get("sourceType");
      const sourceId = Number(url.searchParams.get("source_id") || url.searchParams.get("sourceId"));
      const items =
        sourceType === "complaint" && sourceId === COMPLAINT_ID ? actions : [];
      await json(route, {
        items,
        total: items.length,
        page: 1,
        page_size: 50,
        pages: items.length > 0 ? 1 : 0,
      });
      return;
    }

    if (path.endsWith("/actions") && method === "POST") {
      const body = req.postDataJSON() as { title: string };
      actions.push({
        id: ACTION_ID,
        title: body.title,
        status: "open",
        priority: "medium",
        source_type: "complaint",
        source_id: COMPLAINT_ID,
      });
      await json(route, actions[actions.length - 1], 201);
      return;
    }

    await json(route, method === "GET" ? { items: [], total: 0, page: 1, page_size: 50, pages: 0 } : { ok: true });
  });
}

test.describe("Complaint admin lifecycle CUJ", () => {
  test.use({ serviceWorkers: "block" });

  test("CUJ-01: investigation modal is API-honest and stays on complaint detail after create", async ({
    page,
  }) => {
    await page.addInitScript((token) => {
      localStorage.setItem("access_token", token);
    }, E2E_JWT);

    await installComplaintCujMocks(page);
    await page.goto(`/complaints/${COMPLAINT_ID}`, { waitUntil: "domcontentloaded" });

    await expect(page.getByRole("heading", { name: "Late repairs response" })).toBeVisible({
      timeout: 20_000,
    });

    await page.getByTestId("complaint-start-investigation").click();
    await expect(page.getByTestId("complaint-investigation-modal")).toBeVisible();
    await expect(page.getByTestId("complaint-investigation-title")).toBeVisible();
    await expect(page.getByText(/investigation type/i)).toHaveCount(0);
    await expect(page.getByTestId("user-email-search")).toHaveCount(0);

    await page.getByTestId("complaint-investigation-title").fill("Complaint root-cause review");
    await page.getByRole("button", { name: /create investigation/i }).click();

    await expect(page).toHaveURL(new RegExp(`/complaints/${COMPLAINT_ID}$`));
    await expect(page.getByText("INV-00025")).toBeVisible({ timeout: 10_000 });
  });

  test("CUJ-02: key dates card is honest and running sheet captures narrative", async ({ page }) => {
    await page.addInitScript((token) => {
      localStorage.setItem("access_token", token);
    }, E2E_JWT);

    await installComplaintCujMocks(page, {
      investigations: [
        {
          id: INVESTIGATION_ID,
          reference_number: "INV-00025",
          title: "Complaint investigation",
        },
      ],
    });
    await page.goto(`/complaints/${COMPLAINT_ID}`, { waitUntil: "domcontentloaded" });

    await expect(page.getByTestId("complaint-key-dates")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByText(/Running Sheet tab/i)).toBeVisible();
    await expect(page.getByText("Activity timeline", { exact: false })).toHaveCount(0);

    await page.getByRole("button", { name: "Running Sheet" }).click();
    await page.getByPlaceholder(/Add to the story/i).fill("Acknowledged complainant by phone");
    await page.getByRole("button", { name: /add entry|add note|add/i }).first().click();
    await expect(page.getByText("Acknowledged complainant by phone")).toBeVisible({
      timeout: 10_000,
    });
  });
});
