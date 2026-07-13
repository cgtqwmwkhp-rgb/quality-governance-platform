import { expect, test, type Page, type Route } from "@playwright/test";

/**
 * Documents / Library search CUJ — discoverability, deep links, honesty.
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
  view_count: 3,
  download_count: 1,
  is_public: false,
  created_at: "2026-07-12T10:00:00Z",
  indexed_at: "2026-07-12T11:00:00Z",
};

async function installMocks(
  page: Page,
  opts?: { failSearch?: boolean; zeroSemantic?: boolean },
) {
  await page.route("**/api/v1/**", async (route) => {
    const req = route.request();
    const url = new URL(req.url());
    const path = url.pathname;
    const method = req.method();

    if (path.match(/\/documents\/?$/) && method === "GET") {
      const q = url.searchParams.get("search");
      const items = q && !SAMPLE_DOC.title.toLowerCase().includes(q.toLowerCase()) ? [] : [SAMPLE_DOC];
      await json(route, { items, total: items.length, page: 1, page_size: 50 });
      return;
    }

    if (path.includes("/documents/stats/overview") && method === "GET") {
      await json(route, {
        total_documents: 1,
        indexed_documents: 1,
        total_chunks: 12,
        by_status: { approved: 1 },
        by_type: { policy: 1 },
      });
      return;
    }

    if (path.includes("/documents/search/semantic") && method === "GET") {
      if (opts?.failSearch) {
        await json(route, { detail: "Search offline" }, 503);
        return;
      }
      if (opts?.zeroSemantic) {
        await json(route, { results: [] });
        return;
      }
      await json(route, {
        results: [
          {
            document_id: 11,
            reference_number: "DOC-11",
            title: "Safety Policy",
            score: 0.92,
            chunk_preview: "PPE must be worn.",
            page_number: 1,
            heading: "PPE",
          },
        ],
      });
      return;
    }

    await json(route, method === "GET" ? [] : { ok: true });
  });
}

async function openLibrary(page: Page, path = "/documents", opts?: { failSearch?: boolean; zeroSemantic?: boolean }) {
  await page.addInitScript((token) => {
    localStorage.setItem("access_token", token);
  }, E2E_JWT);
  await installMocks(page, opts);
  await page.goto(path, { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { level: 1, name: /Library/i })).toBeVisible({
    timeout: 20_000,
  });
}

test.describe("Documents library search CUJ", () => {
  test.use({ serviceWorkers: "block" });

  test("CUJ-SEARCH-01 search control is visible and labeled", async ({ page }) => {
    await openLibrary(page);
    await expect(page.getByLabel("Search document library")).toBeVisible();
    await expect(page.getByTestId("documents-library-search")).toBeVisible();
    await expect(page.getByText("Search library")).toBeVisible();
  });

  test("CUJ-SEARCH-02 ?q= deep link hydrates search and shows keyword status", async ({ page }) => {
    await openLibrary(page, "/documents?q=Safety");
    await expect(page.getByTestId("documents-library-search")).toHaveValue("Safety");
    await expect(page.getByTestId("documents-search-status")).toContainText(/Keyword matches/i);
    await expect(page.getByText("Safety Policy")).toBeVisible({ timeout: 20_000 });
  });

  test("CUJ-SEARCH-03 semantic failure is unavailable — not zero matches", async ({ page }) => {
    await openLibrary(page, "/documents", { failSearch: true });
    await page.getByTestId("documents-library-search").fill("ppe induction");
    await expect(page.getByTestId("documents-search-unavailable")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByTestId("documents-search-zero")).toHaveCount(0);
  });

  test("CUJ-SEARCH-04 honest zero semantic matches panel", async ({ page }) => {
    await openLibrary(page, "/documents", { zeroSemantic: true });
    await page.getByTestId("documents-library-search").fill("zzzz-no-hit");
    await expect(page.getByTestId("documents-search-zero")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByTestId("documents-search-unavailable")).toHaveCount(0);
  });
});
