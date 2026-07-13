import { expect, test, type Page, type Route } from "@playwright/test";

/**
 * RTA admin lifecycle critical journey (mocked APIs).
 * CUJ-01: list → detail → investigation (stay on detail) → CAPA handoff
 * CUJ-02: key dates honesty + running-sheet narrative
 */

const E2E_JWT =
  "eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJzdWIiOiJlMmUiLCJleHAiOjE4MTUxODgxNTUsInJvbGUiOiJhZG1pbiIsImlzX3N1cGVydXNlciI6dHJ1ZSwidGVuYW50X2lkIjoxfQ.e2e";

const RTA_ID = 42;
const INVESTIGATION_ID = 88;
const ACTION_ID = 401;

async function json(route: Route, body: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

const rtaRecord = {
  id: RTA_ID,
  reference_number: "RTA-00042",
  title: "Fleet collision on A1",
  description: "Minor bumper contact at roundabout",
  severity: "damage_only",
  status: "reported",
  collision_date: "2026-06-01T09:00:00Z",
  reported_date: "2026-06-01T10:00:00Z",
  location: "A1 northbound junction",
  driver_name: "Alex Driver",
  reporter_name: "Alex Driver",
  driver_injured: false,
  police_attended: false,
  insurance_notified: false,
  created_at: "2026-06-01T10:05:00Z",
  updated_at: "2026-06-01T10:05:00Z",
};

async function installRtaCujMocks(
  page: Page,
  options?: { investigations?: unknown[]; runningSheet?: unknown[]; actions?: unknown[] },
) {
  let rta = { ...rtaRecord };
  const investigations = options?.investigations ?? [];
  const runningSheet = options?.runningSheet ?? [];
  const actions = options?.actions ?? [];

  await page.route("**/api/v1/**", async (route) => {
    const req = route.request();
    const url = new URL(req.url());
    const path = url.pathname;
    const method = req.method();

    if (path.endsWith("/rtas") && method === "GET" && !path.match(/\/rtas\/\d+/)) {
      await json(route, {
        items: [rta],
        total: 1,
        page: 1,
        page_size: 50,
        pages: 1,
      });
      return;
    }

    if (path.endsWith(`/rtas/${RTA_ID}`) && method === "GET") {
      await json(route, rta);
      return;
    }

    if (path.endsWith(`/rtas/${RTA_ID}`) && method === "PATCH") {
      const body = req.postDataJSON() as Record<string, unknown>;
      rta = { ...rta, ...body, updated_at: new Date().toISOString() };
      await json(route, rta);
      return;
    }

    if (path.endsWith(`/rtas/${RTA_ID}/investigations`) && method === "GET") {
      await json(route, {
        items: investigations,
        total: investigations.length,
        page: 1,
        page_size: 10,
        pages: investigations.length > 0 ? 1 : 0,
      });
      return;
    }

    if (path.endsWith(`/rtas/${RTA_ID}/running-sheet`) && method === "GET") {
      await json(route, runningSheet);
      return;
    }

    if (path.endsWith(`/rtas/${RTA_ID}/running-sheet`) && method === "POST") {
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
        reference_number: "INV-00088",
        title: body.title,
        assigned_entity_type: "road_traffic_collision",
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
      const items = sourceType === "rta" && sourceId === RTA_ID ? actions : [];
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
        display_status: "open",
        priority: "medium",
        source_type: "rta",
        source_id: RTA_ID,
      });
      await json(route, actions[actions.length - 1], 201);
      return;
    }

    if (path.includes("/evidence-assets") && method === "GET") {
      await json(route, { items: [], total: 0, page: 1, page_size: 50, pages: 0 });
      return;
    }

    await json(route, method === "GET" ? { items: [], total: 0, page: 1, page_size: 50, pages: 0 } : { ok: true });
  });
}

test.describe("RTA admin lifecycle CUJ", () => {
  test.use({ serviceWorkers: "block" });

  test("CUJ-01: list→detail investigation modal is API-honest and stays on RTA detail", async ({
    page,
  }) => {
    await page.addInitScript((token) => {
      localStorage.setItem("access_token", token);
    }, E2E_JWT);

    await installRtaCujMocks(page);
    await page.goto("/rtas", { waitUntil: "domcontentloaded" });

    await expect(page.getByText("RTA-00042")).toBeVisible({ timeout: 20_000 });
    await page.getByText("RTA-00042").click();

    await expect(page.getByRole("heading", { name: "Fleet collision on A1" })).toBeVisible({
      timeout: 20_000,
    });

    await page.getByTestId("rta-start-investigation").click();
    await expect(page.getByTestId("rta-investigation-modal")).toBeVisible();
    await expect(page.getByTestId("rta-investigation-title")).toBeVisible();
    await expect(page.getByText(/investigation type/i)).toHaveCount(0);
    await expect(page.getByTestId("user-email-search")).toHaveCount(0);

    await page.getByTestId("rta-investigation-title").fill("RTA root-cause review");
    await page.getByRole("button", { name: /create investigation/i }).click();

    await expect(page).toHaveURL(new RegExp(`/rtas/${RTA_ID}$`));
    await expect(page.getByText("INV-00088")).toBeVisible({ timeout: 10_000 });
  });

  test("CUJ-02: key dates card is honest and running sheet captures narrative", async ({ page }) => {
    await page.addInitScript((token) => {
      localStorage.setItem("access_token", token);
    }, E2E_JWT);

    await installRtaCujMocks(page, {
      investigations: [
        {
          id: INVESTIGATION_ID,
          reference_number: "INV-00088",
          title: "RTA investigation",
        },
      ],
      actions: [
        {
          id: ACTION_ID,
          title: "Secure dashcam",
          status: "open",
          display_status: "open",
        },
      ],
    });
    await page.goto(`/rtas/${RTA_ID}`, { waitUntil: "domcontentloaded" });

    await expect(page.getByTestId("rta-key-dates")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByText(/Running Sheet tab/i)).toBeVisible();
    await expect(page.getByText("Activity timeline", { exact: false })).toHaveCount(0);

    await expect(page.getByTestId("rta-open-capa")).toBeVisible();
    await page.getByTestId("rta-open-capa").click();
    await expect(page).toHaveURL(/\/actions\?sourceType=rta&sourceId=42/);

    await page.goto(`/rtas/${RTA_ID}`, { waitUntil: "domcontentloaded" });
    await page.getByRole("button", { name: /Running Sheet/i }).click();
    await page.getByPlaceholder(/Add to the story/i).fill("Police reference confirmed by phone");
    await page.getByRole("button", { name: /add entry|add note|add/i }).first().click();
    await expect(page.getByText("Police reference confirmed by phone")).toBeVisible({
      timeout: 10_000,
    });
  });
});
