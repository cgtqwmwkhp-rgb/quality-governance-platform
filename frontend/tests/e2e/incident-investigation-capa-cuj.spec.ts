import { expect, test, type Page, type Route } from "@playwright/test";

/**
 * Incident → Investigation → CAPA critical journey (mocked APIs).
 */

const E2E_JWT =
  "eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJzdWIiOiJlMmUiLCJleHAiOjE4MTUxODgxNTUsInJvbGUiOiJhZG1pbiIsImlzX3N1cGVydXNlciI6dHJ1ZSwidGVuYW50X2lkIjoxfQ.e2e";

const INCIDENT_ID = 11;
const INVESTIGATION_ID = 21;
const ACTION_ID = 901;

async function json(route: Route, body: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

const incidentRecord = {
  id: INCIDENT_ID,
  reference_number: "INC-00011",
  title: "Loader slip near north gate",
  description: "A colleague slipped on a wet access point.",
  incident_type: "injury",
  severity: "high",
  status: "reported",
  incident_date: "2026-03-12T09:45:00Z",
  location: "North gate",
  department: "Facilities",
  reported_date: "2026-03-12T10:00:00Z",
  created_at: "2026-03-12T10:05:00Z",
  updated_at: "2026-03-12T10:05:00Z",
  reporter_name: "Alice Reporter",
  reporter_email: "alice@example.com",
  people_involved: "Bob Worker",
  first_aid_given: true,
  emergency_services_called: false,
  reporter_submission: {
    contract: "facilities",
    person_name: "Bob Worker",
    person_role: "Cleaner",
    witness_names: "Jane Witness",
    medical_assistance: "first_aid",
    has_injuries: true,
    photos: { count: 2 },
  },
};

const investigationRecord = {
  id: INVESTIGATION_ID,
  reference_number: "INV-00021",
  template_id: 1,
  assigned_entity_type: "reporting_incident",
  assigned_entity_id: INCIDENT_ID,
  title: "Loader slip investigation",
  description: "Determine contributing factors",
  status: "in_progress",
  data: {},
  created_at: "2026-03-12T11:00:00Z",
  updated_at: "2026-03-12T11:30:00Z",
};

async function installIncidentCujMocks(page: Page, options?: { withActions?: boolean }) {
  const withActions = options?.withActions ?? false;

  await page.route("**/api/v1/**", async (route) => {
    const req = route.request();
    const url = new URL(req.url());
    const path = url.pathname;
    const method = req.method();

    if (path.endsWith(`/incidents/${INCIDENT_ID}`) && method === "GET") {
      await json(route, incidentRecord);
      return;
    }

    if (path.endsWith(`/incidents/${INCIDENT_ID}/investigations`) && method === "GET") {
      await json(route, {
        items: [investigationRecord],
        total: 1,
        page: 1,
        page_size: 10,
        pages: 1,
      });
      return;
    }

    if (path.endsWith(`/incidents/${INCIDENT_ID}/running-sheet`) && method === "GET") {
      await json(route, []);
      return;
    }

    if (path.endsWith(`/investigations/${INVESTIGATION_ID}`) && method === "GET") {
      await json(route, investigationRecord);
      return;
    }

    if (path.includes(`/investigations/${INVESTIGATION_ID}/timeline`) && method === "GET") {
      await json(route, {
        items: [],
        total: 0,
        page: 1,
        page_size: 50,
        pages: 0,
        investigation_id: INVESTIGATION_ID,
      });
      return;
    }

    if (path.includes(`/investigations/${INVESTIGATION_ID}/comments`) && method === "GET") {
      await json(route, {
        items: [],
        total: 0,
        page: 1,
        page_size: 50,
        pages: 0,
        investigation_id: INVESTIGATION_ID,
      });
      return;
    }

    if (path.includes(`/investigations/${INVESTIGATION_ID}/packs`) && method === "GET") {
      await json(route, {
        items: [],
        total: 0,
        page: 1,
        page_size: 50,
        pages: 0,
        investigation_id: INVESTIGATION_ID,
      });
      return;
    }

    if (path.includes(`/investigations/${INVESTIGATION_ID}/closure-validation`) && method === "GET") {
      await json(route, { can_close: false, reasons: ["STATUS_NOT_COMPLETE"] });
      return;
    }

    if (path.includes("/evidence-assets") && method === "GET") {
      await json(route, { items: [], total: 0, page: 1, page_size: 50, pages: 0 });
      return;
    }

    if (path.endsWith("/actions/summary") && method === "GET") {
      await json(route, {
        total: withActions ? 1 : 0,
        by_display_status: withActions ? { open: 1 } : {},
      });
      return;
    }

    if (path.includes("/actions") && method === "GET") {
      const sourceType = url.searchParams.get("source_type") || url.searchParams.get("sourceType");
      const sourceId = Number(url.searchParams.get("source_id") || url.searchParams.get("sourceId"));

      const items =
        withActions && sourceType === "incident" && sourceId === INCIDENT_ID
          ? [
              {
                id: ACTION_ID,
                reference_number: "INA-00901",
                title: "Install anti-slip matting",
                description: "Reduce slip risk at north gate",
                action_type: "corrective",
                status: "open",
                display_status: "open",
                action_key: `incident_action:${ACTION_ID}`,
                source_type: "incident",
                source_id: INCIDENT_ID,
                priority: "high",
                created_at: "2026-03-12T12:00:00Z",
              },
            ]
          : withActions && sourceType === "investigation" && sourceId === INVESTIGATION_ID
            ? [
                {
                  id: ACTION_ID,
                  reference_number: "INA-00901",
                  title: "Install anti-slip matting",
                  description: "Reduce slip risk at north gate",
                  action_type: "corrective",
                  status: "open",
                  display_status: "open",
                  action_key: `investigation_action:${ACTION_ID}`,
                  source_type: "investigation",
                  source_id: INVESTIGATION_ID,
                  priority: "high",
                  created_at: "2026-03-12T12:00:00Z",
                },
              ]
            : [];

      await json(route, {
        items,
        total: items.length,
        page: 1,
        page_size: 50,
        pages: items.length > 0 ? 1 : 0,
      });
      return;
    }

    await json(route, method === "GET" ? { items: [], total: 0, page: 1, page_size: 50, pages: 0 } : { ok: true });
  });
}

test.describe("Incident → Investigation → CAPA CUJ", () => {
  test.use({ serviceWorkers: "block" });

  test("Incident handoff creates CAPA workspace when no actions exist", async ({ page }) => {
    await page.addInitScript((token) => {
      localStorage.setItem("access_token", token);
    }, E2E_JWT);

    await installIncidentCujMocks(page, { withActions: false });
    await page.goto(`/incidents/${INCIDENT_ID}`, { waitUntil: "domcontentloaded" });

    await expect(page.getByText("Loader slip near north gate")).toBeVisible({ timeout: 20_000 });
    await page.getByTestId("incident-capa-handoff-cta").click();
    await expect(page).toHaveURL(
      new RegExp(`/actions\\?.*sourceType=incident.*sourceId=${INCIDENT_ID}`),
    );
    await expect(page.getByTestId("actions-incident-playbook")).toBeVisible({ timeout: 20_000 });
  });

  test("Incident handoff opens scoped CAPA Actions when actions exist", async ({ page }) => {
    await page.addInitScript((token) => {
      localStorage.setItem("access_token", token);
    }, E2E_JWT);

    await installIncidentCujMocks(page, { withActions: true });
    await page.goto(`/incidents/${INCIDENT_ID}`, { waitUntil: "domcontentloaded" });

    await expect(page.getByText("Loader slip near north gate")).toBeVisible({ timeout: 20_000 });
    await page.getByTestId("incident-capa-handoff-cta").click();
    await expect(page).toHaveURL(
      new RegExp(`/actions\\?.*sourceType=incident.*sourceId=${INCIDENT_ID}`),
    );
    await expect(page.getByText(/Install anti-slip matting/i)).toBeVisible({ timeout: 20_000 });
  });

  test("Investigation proof strip deep-links into scoped CAPA Actions", async ({ page }) => {
    await page.addInitScript((token) => {
      localStorage.setItem("access_token", token);
    }, E2E_JWT);

    await installIncidentCujMocks(page, { withActions: true });
    await page.goto(`/investigations/${INVESTIGATION_ID}`, { waitUntil: "domcontentloaded" });

    await expect(page.getByText("Loader slip investigation")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("investigation-workflow-proof")).toBeVisible();
    await expect(page.getByTestId("investigation-capa-count")).toHaveTextContent("1");
    await page.getByTestId("investigation-capa-handoff-cta").click();
    await expect(page).toHaveURL(
      new RegExp(`/actions\\?.*sourceType=investigation.*sourceId=${INVESTIGATION_ID}`),
    );
    await expect(page.getByTestId("actions-investigation-playbook")).toBeVisible({
      timeout: 20_000,
    });
  });

  test("Incident workflow proof strip is honest and CAPA CTA stays wired", async ({ page }) => {
    await page.addInitScript((token) => {
      localStorage.setItem("access_token", token);
    }, E2E_JWT);

    await installIncidentCujMocks(page, { withActions: true });
    await page.goto(`/incidents/${INCIDENT_ID}`, { waitUntil: "domcontentloaded" });

    await expect(page.getByText("Loader slip near north gate")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("incident-workflow-proof")).toBeVisible();
    await expect(page.getByTestId("incident-capa-count")).toHaveTextContent("1");
    await page.getByTestId("incident-capa-handoff-cta").click();
    await expect(page).toHaveURL(
      new RegExp(`/actions\\?.*sourceType=incident.*sourceId=${INCIDENT_ID}`),
    );
  });

  test("Action detail reverse deep-links incident and investigation sources", async ({ page }) => {
    await page.addInitScript((token) => {
      localStorage.setItem("access_token", token);
    }, E2E_JWT);

    await page.route("**/api/v1/**", async (route) => {
      const req = route.request();
      const url = new URL(req.url());
      const path = url.pathname;
      const method = req.method();

      if (path.includes("/actions/by-key") && method === "GET") {
        const key = url.searchParams.get("key") || "";
        if (key === `incident_action:${ACTION_ID}`) {
          await json(route, {
            id: ACTION_ID,
            reference_number: "INA-00901",
            title: "Install anti-slip matting",
            description: "Reduce slip risk at north gate",
            action_type: "corrective",
            status: "open",
            display_status: "open",
            action_key: `incident_action:${ACTION_ID}`,
            source_type: "incident",
            source_id: INCIDENT_ID,
            priority: "high",
            created_at: "2026-03-12T12:00:00Z",
          });
          return;
        }
        if (key === `investigation_action:${ACTION_ID}`) {
          await json(route, {
            id: ACTION_ID,
            reference_number: "INA-00901",
            title: "Root-cause CAPA",
            description: "Investigation-backed corrective action",
            action_type: "corrective",
            status: "open",
            display_status: "open",
            action_key: `investigation_action:${ACTION_ID}`,
            source_type: "investigation",
            source_id: INVESTIGATION_ID,
            priority: "high",
            created_at: "2026-03-12T12:00:00Z",
          });
          return;
        }
      }

      if (path.includes("/actions/") && path.includes("/owner-notes") && method === "GET") {
        await json(route, { items: [], total: 0 });
        return;
      }

      if (path.includes("/evidence-assets") && method === "GET") {
        await json(route, { items: [], total: 0, page: 1, page_size: 50, pages: 0 });
        return;
      }

      if (path.includes("/notifications/delivery-status") && method === "GET") {
        await json(route, { email_configured: true });
        return;
      }

      await json(route, method === "GET" ? { items: [], total: 0 } : { ok: true });
    });

    await page.goto(`/actions/item?key=incident_action%3A${ACTION_ID}`, {
      waitUntil: "domcontentloaded",
    });
    await expect(page.getByRole("heading", { name: "Install anti-slip matting" })).toBeVisible({
      timeout: 20_000,
    });
    await expect(page.getByTestId("action-source-deeplink")).toHaveAttribute(
      "href",
      `/incidents/${INCIDENT_ID}`,
    );

    await page.goto(`/actions/item?key=investigation_action%3A${ACTION_ID}`, {
      waitUntil: "domcontentloaded",
    });
    await expect(page.getByRole("heading", { name: "Root-cause CAPA" })).toBeVisible({
      timeout: 20_000,
    });
    await expect(page.getByTestId("action-source-deeplink")).toHaveAttribute(
      "href",
      `/investigations/${INVESTIGATION_ID}`,
    );
  });
});
