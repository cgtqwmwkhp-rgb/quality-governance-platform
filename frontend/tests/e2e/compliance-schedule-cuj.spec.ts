import { expect, test, type Page, type Route } from "@playwright/test";

/**
 * Compliance Schedule critical journey (mocked APIs).
 *
 * Register → requirement detail → record completion → next due date rolls
 * forward by the recurrence frequency and the register reflects it.
 *
 * READ THIS BEFORE "FIXING" A FAILURE
 * -----------------------------------
 * CUJ-01 currently FAILS on its last assertion, and that failure is the point.
 * `createComplianceScheduleApi` builds its paths from `const base =
 * '/compliance-schedule'`, while the axios instance is configured with
 * `baseURL = API_BASE_URL` and no version segment. Every sibling client
 * (`complaintsClient`, `nearMissesClient`, …) spells the version itself, e.g.
 * `/api/v1/complaints/`. The backend mounts this router at
 * `/api/v1/compliance-schedule`, so the twelve endpoints the UI calls are
 * unreachable in every environment. The fix belongs in
 * `frontend/src/api/complianceScheduleClient.ts`, not here — do not delete the
 * assertion to get green.
 *
 * The mock below therefore serves the requirement data under either path shape,
 * so the rest of the journey (submission payload, refetch, roll-forward, list
 * refresh) is still genuinely exercised, and records every unversioned request
 * so exactly one assertion reports the defect.
 *
 * The roll-forward arithmetic itself is backend behaviour
 * (`compliance_schedule_policy.compute_next_due`). What this spec proves about
 * the frontend is that it sends a `completed_at` the server can anchor to, and
 * that it re-reads and displays the rolled-forward date rather than the stale
 * one it already had in state.
 */

const E2E_JWT =
  "eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJzdWIiOiJlMmUiLCJleHAiOjE4MTUxODgxNTUsInJvbGUiOiJhZG1pbiIsImlzX3N1cGVydXNlciI6dHJ1ZSwidGVuYW50X2lkIjoxfQ.e2e";

/**
 * Fixed clock for the mocked server, so `status` never depends on the day the
 * suite runs. The real route derives status the same way, via
 * `derive_status(clock, next_due_date)`.
 */
const SERVER_TODAY = "2026-08-04";

/** Typed into the completion sheet, so the rolled-forward date is a literal. */
const COMPLETED_AT_LOCAL = "2026-08-04T09:30";
const EXPECTED_NEXT_DUE = "2027-08-04";

const FRA_ID = 4201;
const FRA_REF = "CSR-04201";
const PAT_REF = "CSR-04202";

/** The occurrence closed by the completion — the due date the requirement held. */
const CLOSED_OCCURRENCE_DUE = "2026-08-20";

interface MockRequirement {
  id: number;
  external_id: string;
  tenant_id: number;
  reference_number: string;
  title: string;
  taxonomy_id: string;
  description: string | null;
  regulatory_basis: string | null;
  frequency_months: number | null;
  frequency_days: number | null;
  anchor: "completion" | "schedule";
  statutory: boolean;
  next_due_date: string;
  last_completed_at: string | null;
  owner_id: number | null;
  is_active: boolean;
  created_at: string;
  updated_at: string | null;
}

interface MockRecord {
  id: number;
  external_id: string;
  tenant_id: number;
  reference_number: string;
  requirement_id: number;
  due_date: string;
  outcome: "completed" | "missed";
  completed_at: string | null;
  check_passed: boolean | null;
  notes: string | null;
  library_document_id: number | null;
  filing_status: string;
  filing_error: string | null;
  created_at: string;
  updated_at: string | null;
}

interface CompletionPayload {
  completed_at?: string;
  check_passed?: boolean;
  notes?: string;
  due_date?: string;
}

async function json(route: Route, body: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

/** Mirrors `compliance_schedule_policy.add_months`, month-end clamp included. */
function addMonths(isoDate: string, months: number): string {
  const [year, month, day] = isoDate.split("-").map(Number);
  const monthIndex = month - 1 + months;
  const targetYear = year + Math.floor(monthIndex / 12);
  const targetMonth = ((monthIndex % 12) + 12) % 12;
  const lastDay = new Date(Date.UTC(targetYear, targetMonth + 1, 0)).getUTCDate();
  const targetDay = Math.min(day, lastDay);
  return `${targetYear}-${String(targetMonth + 1).padStart(2, "0")}-${String(targetDay).padStart(2, "0")}`;
}

/** Mirrors `compliance_schedule_policy.derive_status` (30-day due-soon window). */
function deriveStatus(nextDue: string): "current" | "due_soon" | "overdue" {
  const delta = Math.round(
    (Date.parse(`${nextDue}T00:00:00Z`) - Date.parse(`${SERVER_TODAY}T00:00:00Z`)) / 86_400_000,
  );
  if (delta < 0) return "overdue";
  if (delta <= 30) return "due_soon";
  return "current";
}

function requirement(overrides: Partial<MockRequirement> & Pick<MockRequirement, "id">): MockRequirement {
  return {
    external_id: `csr-${overrides.id}`,
    tenant_id: 1,
    reference_number: `CSR-0${overrides.id}`,
    title: "Requirement",
    taxonomy_id: "fire_safety",
    description: null,
    regulatory_basis: null,
    frequency_months: 12,
    frequency_days: null,
    anchor: "completion",
    statutory: true,
    next_due_date: "2026-08-20",
    last_completed_at: null,
    owner_id: null,
    is_active: true,
    created_at: "2026-01-05T09:00:00Z",
    updated_at: null,
    ...overrides,
  };
}

/**
 * Stands in for `/api/v1/compliance-schedule/*` with server-side state, so the
 * roll-forward the UI displays is one the server computed from the payload the
 * UI actually sent — not a value the test handed back unchanged.
 */
async function installComplianceScheduleMocks(
  page: Page,
  opts: { complianceScheduleFlag: boolean },
) {
  const requirements = new Map<number, MockRequirement>([
    [
      FRA_ID,
      requirement({
        id: FRA_ID,
        title: "Fire risk assessment — Head office",
        taxonomy_id: "fire_safety",
        regulatory_basis: "Regulatory Reform (Fire Safety) Order 2005",
        frequency_months: 12,
        anchor: "completion",
        next_due_date: CLOSED_OCCURRENCE_DUE,
      }),
    ],
    [
      4202,
      requirement({
        id: 4202,
        title: "Portable appliance testing — Depot",
        taxonomy_id: "electrical_safety",
        regulatory_basis: "Electricity at Work Regulations 1989",
        frequency_months: 12,
        anchor: "schedule",
        next_due_date: "2026-07-01",
      }),
    ],
  ]);

  const records: MockRecord[] = [];
  const unversionedRequests: string[] = [];
  const completionPayloads: CompletionPayload[] = [];
  let nextRecordId = 9001;

  const withStatus = (req: MockRequirement) => ({
    ...req,
    status: deriveStatus(req.next_due_date),
  });

  const handler = async (route: Route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const method = request.method();

    if (path.endsWith("/meta/features")) {
      await json(route, {
        flags: { compliance_schedule: opts.complianceScheduleFlag },
        scope: "user",
      });
      return;
    }

    const marker = "/compliance-schedule";
    const markerAt = path.indexOf(marker);
    if (markerAt === -1) {
      await json(route, method === "GET" ? { items: [], total: 0, page: 1, page_size: 50, pages: 0 } : { ok: true });
      return;
    }

    // The real API only answers under the version segment; anything else 404s.
    if (!path.startsWith("/api/v1/compliance-schedule")) {
      unversionedRequests.push(`${method} ${path}`);
    }

    const rel = path.slice(markerAt + marker.length) || "/";

    if (rel === "/stats" && method === "GET") {
      const active = [...requirements.values()].filter((r) => r.is_active);
      const byStatus = active.map((r) => deriveStatus(r.next_due_date));
      await json(route, {
        total_active: active.length,
        current: byStatus.filter((s) => s === "current").length,
        due_soon: byStatus.filter((s) => s === "due_soon").length,
        overdue: byStatus.filter((s) => s === "overdue").length,
      });
      return;
    }

    if (rel === "/catalogue" && method === "GET") {
      await json(route, {
        items: [
          {
            id: 11,
            template_key: "legionella_risk_assessment",
            title: "Legionella risk assessment",
            taxonomy_id: "water_safety",
            description: "ACoP L8 written scheme review",
            regulatory_basis: "ACoP L8",
            frequency_months: 24,
            frequency_days: null,
            anchor: "schedule",
            statutory: true,
            is_active: true,
          },
        ],
        total: 1,
      });
      return;
    }

    if (rel === "/requirements" && method === "GET") {
      const statusFilter = url.searchParams.get("status");
      const items = [...requirements.values()]
        .filter((r) => r.is_active)
        .map(withStatus)
        .filter((r) => !statusFilter || r.status === statusFilter);
      await json(route, { items, total: items.length, page: 1, page_size: 100, pages: 1 });
      return;
    }

    const recordsMatch = rel.match(/^\/requirements\/(\d+)\/records$/);
    if (recordsMatch) {
      const id = Number(recordsMatch[1]);
      const target = requirements.get(id);
      if (!target) {
        await json(route, { detail: "Requirement not found" }, 404);
        return;
      }

      if (method === "GET") {
        const items = records.filter((r) => r.requirement_id === id);
        await json(route, { items, total: items.length, page: 1, page_size: 50, pages: 1 });
        return;
      }

      if (method === "POST") {
        const payload = (request.postDataJSON() ?? {}) as CompletionPayload;
        completionPayloads.push(payload);

        const completedAt = payload.completed_at ?? `${SERVER_TODAY}T00:00:00.000Z`;
        const occurrenceDue = payload.due_date ?? target.next_due_date;

        if (records.some((r) => r.requirement_id === id && r.due_date === occurrenceDue)) {
          await json(
            route,
            { detail: `Occurrence for due date ${occurrenceDue} already recorded` },
            409,
          );
          return;
        }

        // compute_next_due: 'completion' anchors on the completion date,
        // 'schedule' on the due date that was just closed.
        const base =
          target.anchor === "completion" ? completedAt.slice(0, 10) : occurrenceDue;
        const nextDue = target.frequency_months
          ? addMonths(base, target.frequency_months)
          : base;

        const record: MockRecord = {
          id: nextRecordId,
          external_id: `ccr-${nextRecordId}`,
          tenant_id: 1,
          reference_number: `CCR-0${nextRecordId}`,
          requirement_id: id,
          due_date: occurrenceDue,
          outcome: "completed",
          completed_at: completedAt,
          check_passed: payload.check_passed ?? null,
          notes: payload.notes ?? null,
          library_document_id: null,
          filing_status: "not_filed",
          filing_error: null,
          created_at: completedAt,
          updated_at: null,
        };
        nextRecordId += 1;
        records.push(record);

        requirements.set(id, {
          ...target,
          next_due_date: nextDue,
          last_completed_at: completedAt,
          updated_at: completedAt,
        });

        await json(route, record, 201);
        return;
      }
    }

    const requirementMatch = rel.match(/^\/requirements\/(\d+)$/);
    if (requirementMatch && method === "GET") {
      const target = requirements.get(Number(requirementMatch[1]));
      if (!target) {
        await json(route, { detail: "Requirement not found" }, 404);
        return;
      }
      await json(route, withStatus(target));
      return;
    }

    await json(route, method === "GET" ? { items: [], total: 0, page: 1, page_size: 50, pages: 0 } : { ok: true });
  };

  // One handler, two shapes: the versioned API surface everything else uses,
  // and the unversioned path this feature's client actually requests.
  await page.route(/\/(?:api\/v1|compliance-schedule)\//, handler);

  return {
    unversionedRequests: () => [...new Set(unversionedRequests)],
    completionPayloads: () => [...completionPayloads],
  };
}

async function signIn(page: Page, opts: { flagOverride: boolean }) {
  await page.addInitScript(
    ({ token, flagOverride }) => {
      localStorage.setItem("access_token", token);
      // Documented override in `useFeatureFlag`: localStorage wins over the
      // runtime flags the provider fetches from /api/v1/meta/features.
      if (flagOverride) {
        localStorage.setItem("ff_override_compliance_schedule", "true");
      }
    },
    { token: E2E_JWT, flagOverride: opts.flagOverride },
  );
}

test.describe("Compliance Schedule CUJ", () => {
  // UTC keeps `new Date(completedAt).toISOString()` in the completion sheet on
  // the date typed into it, whatever the runner's zone.
  test.use({ serviceWorkers: "block", timezoneId: "UTC" });

  test("CUJ-01 register → detail → completion rolls the next due date forward", async ({
    page,
  }) => {
    await signIn(page, { flagOverride: true });
    const proof = await installComplianceScheduleMocks(page, { complianceScheduleFlag: true });

    await page.goto("/compliance-schedule", { waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("compliance-schedule-page")).toBeVisible({ timeout: 20_000 });

    // The flag is on, so the register is reachable by navigation and not just
    // by URL — an under-privileged user never sees this entry.
    await expect(
      page.locator("#app-sidebar").getByRole("link", { name: "Compliance Schedule" }),
    ).toBeVisible();

    // Requirements listed with due date and status.
    const list = page.getByTestId("compliance-schedule-list");
    const fraRow = list.locator("li").filter({ hasText: FRA_REF });
    await expect(fraRow).toContainText("Fire risk assessment — Head office");
    await expect(fraRow).toContainText(`Due ${CLOSED_OCCURRENCE_DUE}`);
    await expect(fraRow).toContainText("Due soon");

    const patRow = list.locator("li").filter({ hasText: PAT_REF });
    await expect(patRow).toContainText("Due 2026-07-01");
    await expect(patRow).toContainText("Overdue");

    await expect(page.getByTestId("compliance-schedule-stats")).toContainText("2");

    // Open the requirement.
    await page.getByTestId(`compliance-schedule-row-${FRA_ID}`).click();
    await expect(page).toHaveURL(new RegExp(`/compliance-schedule/${FRA_ID}$`));
    await expect(page.getByTestId("compliance-schedule-detail")).toBeVisible({ timeout: 20_000 });

    const summary = page.getByTestId("compliance-schedule-detail").locator("dl");
    await expect(summary).toContainText(CLOSED_OCCURRENCE_DUE);
    await expect(page.getByTestId("compliance-schedule-records-empty")).toBeVisible();

    // Record a completion.
    await page.getByTestId("compliance-schedule-open-complete").click();
    const sheet = page.getByTestId("compliance-schedule-complete-sheet");
    await expect(sheet).toBeVisible();
    await page.locator("#cs-completed-at").fill(COMPLETED_AT_LOCAL);
    await expect(page.locator("#cs-check-passed")).toBeChecked();
    await page.locator("#cs-notes").fill("Assessment carried out by Ledger Fire Safety Ltd.");
    await page.getByTestId("compliance-schedule-complete-submit").click();

    await expect(page.getByText("Occurrence recorded")).toBeVisible({ timeout: 20_000 });

    // The completion the server anchors the roll-forward to must actually reach it.
    await expect.poll(() => proof.completionPayloads().length).toBe(1);
    const [payload] = proof.completionPayloads();
    expect(payload.completed_at).toBeTruthy();
    expect(payload.completed_at?.slice(0, 10)).toBe(COMPLETED_AT_LOCAL.slice(0, 10));
    expect(payload.check_passed).toBe(true);
    expect(payload.notes).toBe("Assessment carried out by Ledger Fire Safety Ltd.");

    // Roll-forward: 12-month completion anchor, so 2026-08-04 → 2027-08-04.
    // The stale due date must be gone from the summary, not merely joined by
    // the new one.
    await expect(summary).toContainText(EXPECTED_NEXT_DUE, { timeout: 20_000 });
    await expect(summary).not.toContainText(CLOSED_OCCURRENCE_DUE);
    await expect(summary).toContainText("2026");
    await expect(page.getByTestId("compliance-schedule-detail").getByText("Current")).toBeVisible();

    // The closed occurrence is on the record, dated to the due date it closed.
    const recordRow = page.getByTestId("compliance-schedule-records").locator("li").first();
    await expect(recordRow).toContainText("completed");
    await expect(recordRow).toContainText(`Due ${CLOSED_OCCURRENCE_DUE}`);

    // The register reflects the new state.
    await page.getByRole("link", { name: "Back to schedule" }).click();
    await expect(page.getByTestId("compliance-schedule-page")).toBeVisible({ timeout: 20_000 });
    const refreshedRow = page
      .getByTestId("compliance-schedule-list")
      .locator("li")
      .filter({ hasText: FRA_REF });
    await expect(refreshedRow).toContainText(`Due ${EXPECTED_NEXT_DUE}`);
    await expect(refreshedRow).toContainText("Current");
    await expect(refreshedRow).not.toContainText("Due soon");

    // Read the header comment before touching this. The journey above is proved
    // against a path the deployed API does not serve.
    expect(
      proof.unversionedRequests(),
      "Compliance Schedule reads/writes must go to /api/v1/compliance-schedule; " +
        "complianceScheduleClient.ts omits the version segment every sibling client spells out, " +
        "so the deployed API answers 404",
    ).toEqual([]);
  });

  test("CUJ-02 register stays out of navigation while the flag is off", async ({ page }) => {
    await signIn(page, { flagOverride: false });
    await installComplianceScheduleMocks(page, { complianceScheduleFlag: false });

    // Note: only the navigation entry is gated — App.tsx registers the route
    // unconditionally, so a typed URL still renders the page.
    await page.goto("/compliance-schedule", { waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("compliance-schedule-page")).toBeVisible({ timeout: 20_000 });

    const sidebar = page.locator("#app-sidebar");
    await sidebar.getByTestId("nav-hub-btn-compliance-sustainability").click();

    // Control: the hub is open and populated, so the absence below is gating
    // rather than an unrendered sidebar.
    await expect(sidebar.getByRole("link", { name: "ISO Compliance" })).toBeVisible();
    await expect(sidebar.getByRole("link", { name: "Compliance Schedule" })).toHaveCount(0);
  });
});
