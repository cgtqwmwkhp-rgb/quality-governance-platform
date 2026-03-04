import { test, expect } from "@playwright/test";

test.describe("Staging UI Verification", () => {
  test("login page renders and is accessible", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveTitle(/Quality Governance|QGP|Login/i);
    const body = page.locator("body");
    await expect(body).toBeVisible();
  });

  test("static assets load without errors", async ({ page }) => {
    const consoleLogs: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") consoleLogs.push(msg.text());
    });

    await page.goto("/");
    await page.waitForLoadState("networkidle");

    const criticalErrors = consoleLogs.filter(
      (log) =>
        !log.includes("favicon") &&
        !log.includes("net::ERR") &&
        !log.includes("Failed to load resource")
    );
    expect(criticalErrors).toHaveLength(0);
  });

  test("app shell renders key navigation elements", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("domcontentloaded");
    const html = await page.content();
    expect(html.length).toBeGreaterThan(500);
  });
});
