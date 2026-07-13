import { expect, test, type Page, type Route } from "@playwright/test";

/**
 * Documents library critical journey (mocked APIs).
 * Honesty + proof — live vs empty vs unavailable; exclusive of sibling CUJ pages.
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

const SAMPLE_DOC = {
  id: 11,
  reference_number: "DOC-11",
  title: "Safety Policy",
  description: "Site safety policy",
  file_name: "policy.pdf",
  file_type: "pdf",
  file_size: 2048,
  document_type: "policy",
  category: "H&S",
  department: "Quality",
  sensitivity: "internal",
  status: "approved",
  version: "1.0",
  ai_summary: "Covers PPE and induction requirements.",
  ai_tags: ["safety", "ppe"],
  ai_keywords: ["ppe"],
  page_count: 4,
  word_count: 1200,
  view_count: 3,
  download_count: 1,
  is_public: false,
  created_at: "2026-07-12T10:00:00Z",
  indexed_at: "2026-07-12T11:00:00Z",
};

const STATS = {
  total_documents: 1,
  indexed_documents: 1,
  total_chunks: 12,
  by_status: { approved: 1 },
  by_type: { policy: 1 },
};

async function installDocumentsMocks(
  page: Page,
  opts?: { failList?: boolean; failStats?: boolean; failSearch?: boolean },
) {
  await page.route("**/api/v1/**", async (route) => {
    const req = route.request();
    const url = new URL(req.url());
    const path = url.pathname;
    const method = req.method();

    if (path.match(/\/documents\/?$/) && method === "GET") {
      if (opts?.failList) {
        await json(route, { detail: "Documents offline" }, 503);
        return;
      }
      await json(route, { items: [SAMPLE_DOC], total: 1, page: 1, page_size: 50 });
      return;
    }

    if (path.includes("/documents/stats/overview") && method === "GET") {
      if (opts?.failStats) {
        await json(route, { detail: "Stats offline" }, 503);
        return;
      }
      await json(route, STATS);
      return;
    }

    if (path.includes("/documents/search/semantic") && method === "GET") {
      if (opts?.failSearch) {
        await json(route, { detail: "Search offline" }, 503);
        return;
      }
      await json(route, {
        results: [
          {
            document_id: 11,
            reference_number: "DOC-11",
            title: "Safety Policy",
            score: 0.92,
            chunk_preview: "PPE must be worn in all operational areas.",
            page_number: 1,
            heading: "PPE",
          },
        ],
      });
      return;
    }

    if (path.includes("/documents/") && path.includes("/signed-url") && method === "GET") {
      await json(route, {
        signed_url: "/api/v1/evidence-assets/download?key=policy.pdf",
      });
      return;
    }

    if (path.includes("/documents/upload") && method === "POST") {
      await json(route, { id: 12, status: "pending" }, 201);
      return;
    }

    await json(route, method === "GET" ? [] : { ok: true });
  });
}

async function openDocuments(
  page: Page,
  opts?: { failList?: boolean; failStats?: boolean; failSearch?: boolean },
) {
  await page.addInitScript((token) => {
    localStorage.setItem("access_token", token);
  }, E2E_JWT);

  await installDocumentsMocks(page, opts);
  await page.goto("/documents", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { level: 1, name: /Library/i })).toBeVisible({
    timeout: 20_000,
  });
}

test.describe("Documents library CUJ", () => {
  test.use({ serviceWorkers: "block" });

  test("CUJ-01 live library shows Live data and document card", async ({ page }) => {
    await openDocuments(page);

    await expect(page.getByTestId("documents-live-badge")).toHaveTextContent("Live data");
    await expect(page.getByText("Safety Policy")).toBeVisible();
    await expect(page.getByTestId("documents-empty")).toHaveCount(0);
    await expect(page.getByTestId("documents-list-unavailable")).toHaveCount(0);
  });

  test("CUJ-02 list failure shows unavailable — not fake empty library", async ({ page }) => {
    await openDocuments(page, { failList: true });

    await expect(page.getByTestId("documents-partial-badge")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("documents-list-unavailable")).toBeVisible();
    await expect(page.getByText("Documents unavailable")).toBeVisible();
    await expect(page.getByText(/not an empty library/i)).toBeVisible();
    await expect(page.getByTestId("documents-empty")).toHaveCount(0);
  });

  test("CUJ-03 stats failure keeps list live with Partial badge", async ({ page }) => {
    await openDocuments(page, { failStats: true });

    await expect(page.getByText("Safety Policy")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("documents-partial-badge")).toBeVisible();
    await expect(page.getByTestId("documents-partial-warning")).toHaveTextContent(
      /stats unavailable/i,
    );
    await expect(page.getByTestId("documents-live-badge")).toHaveCount(0);
  });

  test("CUJ-04 search failure distinguishes unavailable from zero matches", async ({ page }) => {
    await openDocuments(page, { failSearch: true });

    await expect(page.getByTestId("documents-live-badge")).toBeVisible({ timeout: 20_000 });
    await page.getByPlaceholder(/AI-powered semantic search/i).fill("ppe induction");
    await expect(page.getByTestId("documents-search-unavailable")).toBeVisible({
      timeout: 10_000,
    });
    await expect(page.getByText(/do not treat this as zero matches/i)).toBeVisible();
    await expect(page.getByText(/AI Semantic Search Results/i)).toHaveCount(0);
  });
});
