import { expect, test, type Page, type Route } from "@playwright/test";

/**
 * Compliance Evidence hub critical journey (mocked APIs).
 * Honesty + deep-link proof — no SMTP/secrets; exclusive of IMS/UVDB/Actions page edits.
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

const STANDARD = {
  id: "iso9001",
  code: "ISO 9001:2015",
  name: "Quality Management System",
  description: "QMS",
  clause_count: 1,
  db_standard_id: 1,
  db_standard_code: "ISO9001",
  db_standard_name: "ISO 9001:2015",
  db_clause_count: 1,
  ims_requirement_count: 2,
  covered_clauses: 1,
  coverage_percentage: 100,
  has_canonical_standard: true,
  canonical_data_degraded: false,
  canonical_data_message: null,
};

const CLAUSE = {
  id: "9001-7.5",
  standard: "iso9001",
  clause_number: "7.5",
  title: "Documented information",
  description: "Control of documented information",
  keywords: ["documents", "records"],
  parent_clause: null,
  level: 2,
};

const COVERAGE = {
  total_clauses: 1,
  full_coverage: 1,
  partial_coverage: 0,
  gaps: 0,
  coverage_percentage: 100,
  gap_clauses: [],
  by_standard: {
    iso9001: {
      total: 1,
      covered: 1,
      partial_coverage: 0,
      gaps: 0,
      percentage: 100,
    },
  },
};

const EVIDENCE_LINK = {
  id: 1,
  entity_type: "audit_finding",
  entity_id: "501",
  clause_id: "9001-7.5",
  linked_by: "manual",
  confidence: 95,
  title: "Missing PPE evidence pack",
  notes: "Linked from inspection finding",
  created_at: "2026-07-12T10:00:00Z",
  created_by_email: "qa@example.com",
};

async function installEvidenceHubMocks(page: Page, opts?: { failCoverage?: boolean; failMappings?: boolean }) {
  await page.route("**/api/v1/**", async (route) => {
    const req = route.request();
    const url = new URL(req.url());
    const path = url.pathname;
    const method = req.method();

    if (path.endsWith("/compliance/standards") && method === "GET") {
      await json(route, [STANDARD]);
      return;
    }

    if (path.includes("/compliance/clauses") && method === "GET") {
      await json(route, [CLAUSE]);
      return;
    }

    if (path.includes("/compliance/coverage") && method === "GET") {
      if (opts?.failCoverage) {
        await json(route, { detail: "Coverage unavailable" }, 503);
        return;
      }
      await json(route, COVERAGE);
      return;
    }

    if (path.includes("/compliance/report") && method === "GET") {
      await json(route, {
        generated_at: "2026-07-12T12:00:00Z",
        persisted_evidence_links: 1,
        summary: COVERAGE,
        clauses: [
          {
            clause_id: "9001-7.5",
            clause_number: "7.5",
            title: "Documented information",
            description: "Control of documented information",
            standard: "iso9001",
            status: "full",
            evidence_count: 1,
            evidence: [
              {
                entity_type: "audit_finding",
                entity_id: "501",
                linked_by: "manual",
                confidence: 95,
              },
            ],
          },
        ],
      });
      return;
    }

    if (path.includes("/compliance/evidence/links") && method === "GET") {
      await json(route, [EVIDENCE_LINK]);
      return;
    }

    if (path.includes("/compliance/evidence/link/") && method === "DELETE") {
      await json(route, { status: "deleted" });
      return;
    }

    if (path.includes("/cross-standard") || path.includes("/mappings")) {
      if (opts?.failMappings) {
        await json(route, { detail: "Mappings offline" }, 503);
        return;
      }
      await json(route, [
        {
          id: 1,
          primary_standard: "ISO 9001:2015",
          primary_clause: "7.5",
          mapped_standard: "ISO 14001:2015",
          mapped_clause: "7.5",
          mapping_type: "equivalent",
          mapping_strength: 9,
          mapping_notes: "Shared documented information controls",
          annex_sl_element: "Support",
        },
      ]);
      return;
    }

    if (path.includes("/external-audit") && method === "GET") {
      await json(route, { records: [], total: 0 });
      return;
    }

    await json(route, method === "GET" ? [] : { ok: true });
  });
}

async function openEvidenceHub(page: Page, opts?: { failCoverage?: boolean; failMappings?: boolean }) {
  await page.addInitScript((token) => {
    localStorage.setItem("access_token", token);
  }, E2E_JWT);

  await installEvidenceHubMocks(page, opts);
  await page.goto("/compliance", { waitUntil: "domcontentloaded" });
  await expect(page.getByText("ISO Compliance Evidence Center")).toBeVisible({ timeout: 20_000 });
}

test.describe("Compliance Evidence hub CUJ", () => {
  test.use({ serviceWorkers: "block" });

  test("CUJ-01 live hub shows Live data and deep-links to IMS/Audits", async ({ page }) => {
    await openEvidenceHub(page);

    await expect(page.getByTestId("compliance-live-badge")).toHaveTextContent("Live data");
    await expect(page.getByTestId("compliance-link-ims")).toHaveAttribute("href", "/ims");
    await expect(page.getByTestId("compliance-link-audits")).toHaveAttribute(
      "href",
      "/audits?view=findings",
    );

    await expect(page.getByText("Missing PPE evidence pack")).toBeVisible();
    await expect(page.getByTestId("clause-link-ims")).toHaveAttribute(
      "href",
      "/ims?standard=iso9001&clause=7.5",
    );
    await expect(page.getByTestId("clause-link-audits")).toHaveAttribute(
      "href",
      "/audits?view=findings&clause=7.5",
    );

    // Evidence arrow deep-links audit findings without editing Audits.tsx
    const evidenceLink = page.getByRole("link", { name: /View Audit Finding/i }).first();
    await expect(evidenceLink).toHaveAttribute("href", /\/audits\?view=findings&findingId=501/);
  });

  test("CUJ-02 coverage failure shows unavailable — not fake zero gaps", async ({ page }) => {
    await openEvidenceHub(page, { failCoverage: true });

    await expect(page.getByTestId("compliance-partial-badge")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("compliance-score-iso9001")).toHaveAttribute(
      "aria-label",
      "Coverage unavailable",
    );

    await page.getByRole("tab", { name: /Gap Analysis/i }).click();
    await expect(page.getByText("Coverage unavailable")).toBeVisible();
    await expect(page.getByText(/do not treat this as zero gaps/i)).toBeVisible();
    await expect(page.getByText("No gaps found")).toHaveCount(0);
  });

  test("mappings failure distinguishes unavailable from empty", async ({ page }) => {
    await openEvidenceHub(page, { failMappings: true });

    await expect(page.getByTestId("mappings-unavailable")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByText("Mappings unavailable")).toBeVisible();
    await expect(page.getByText(/No cross-standard mappings found/i)).toHaveCount(0);
  });
});
