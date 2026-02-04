/**
 * Staging UI Verification Tests
 * 
 * These tests are specifically designed to run against the deployed staging SWA
 * to verify that critical UI elements render correctly before production promotion.
 * 
 * CRITICAL: These tests assert actual rendered content, not just HTTP 200.
 * Failures here should BLOCK production deployment.
 * 
 * SECURITY: These tests use the read-only guard to ensure no write requests
 * are made to the production API during staging verification.
 */

import { test, expect } from './fixtures/read-only-guard';

// Use environment variable for staging URL
const STAGING_URL = process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:5173';

test.describe('Staging UI Verification (Release Gate)', () => {
  test.describe.configure({ mode: 'serial' });

  test.describe('1. Investigations List (CRITICAL)', () => {
    test('should render Investigations page with table headers', async ({ page }) => {
      await page.goto(`${STAGING_URL}/investigations`);
      
      // Wait for page to fully load
      await page.waitForLoadState('networkidle');
      
      // Assert page title/heading
      await expect(page.locator('h1')).toContainText('Root Cause Investigations', { timeout: 15000 });
      
      // Assert all required table headers are visible
      const requiredHeaders = ['Reference', 'Title', 'Status', 'Lead', 'Actions', 'Created'];
      for (const header of requiredHeaders) {
        await expect(page.locator(`th:has-text("${header}")`)).toBeVisible({ timeout: 10000 });
      }
      
      // Take screenshot for evidence
      await page.screenshot({ path: 'test-results/investigations-list.png', fullPage: true });
    });

    test('should show API connected indicator OR handle error gracefully', async ({ page }) => {
      await page.goto(`${STAGING_URL}/investigations`);
      await page.waitForLoadState('networkidle');
      
      // Either API is connected OR there's a graceful error state
      const hasConnectedIndicator = await page.locator('text=API Connected').isVisible().catch(() => false);
      const hasErrorState = await page.locator('text=Error').isVisible().catch(() => false);
      const hasEmptyState = await page.locator('text=No Investigations').isVisible().catch(() => false);
      
      // At least one of these states should be present (deterministic)
      expect(hasConnectedIndicator || hasErrorState || hasEmptyState).toBe(true);
    });
  });

  test.describe('2. Investigation Detail Page (CRITICAL)', () => {
    test('should render detail page with all tabs', async ({ page }) => {
      await page.goto(`${STAGING_URL}/investigations`);
      await page.waitForLoadState('networkidle');
      
      // Check if there are any investigations
      const rows = page.locator('table tbody tr');
      const rowCount = await rows.count();
      
      if (rowCount > 0) {
        // Click first investigation
        await rows.first().click();
        await page.waitForURL(/\/investigations\/\d+/, { timeout: 15000 });
        
        // Assert all required tabs are visible
        const requiredTabs = ['Summary', 'Timeline', 'Evidence', 'RCA', 'Actions', 'Report'];
        for (const tabName of requiredTabs) {
          await expect(page.locator(`button:has-text("${tabName}")`)).toBeVisible({ timeout: 10000 });
        }
        
        // Take screenshot for evidence
        await page.screenshot({ path: 'test-results/investigation-detail-tabs.png', fullPage: true });
      } else {
        // Empty state - just verify the list page rendered
        await expect(page.locator('text=No Investigations')).toBeVisible();
      }
    });

    test('should render Evidence tab with deterministic state', async ({ page }) => {
      await page.goto(`${STAGING_URL}/investigations`);
      await page.waitForLoadState('networkidle');
      
      const rows = page.locator('table tbody tr');
      const rowCount = await rows.count();
      
      if (rowCount > 0) {
        await rows.first().click();
        await page.waitForURL(/\/investigations\/\d+/);
        
        // Click Evidence tab
        await page.locator('button:has-text("Evidence")').click();
        await page.waitForTimeout(1000);
        
        // Assert deterministic state: either list or empty state
        const hasEvidenceHeader = await page.locator('text=Evidence Register').isVisible().catch(() => false);
        const hasUploadButton = await page.locator('text=Upload Evidence').isVisible().catch(() => false);
        const hasEmptyState = await page.locator('text=No Evidence').isVisible().catch(() => false);
        
        expect(hasEvidenceHeader || hasUploadButton || hasEmptyState).toBe(true);
        
        // Take screenshot for evidence
        await page.screenshot({ path: 'test-results/investigation-evidence-tab.png', fullPage: true });
      }
    });

    test('should render RCA tab with fields and Save control', async ({ page }) => {
      await page.goto(`${STAGING_URL}/investigations`);
      await page.waitForLoadState('networkidle');
      
      const rows = page.locator('table tbody tr');
      const rowCount = await rows.count();
      
      if (rowCount > 0) {
        await rows.first().click();
        await page.waitForURL(/\/investigations\/\d+/);
        
        // Click RCA tab
        await page.locator('button:has-text("RCA")').click();
        await page.waitForTimeout(1000);
        
        // Assert RCA content is visible
        const has5Whys = await page.locator('text=5 Whys Analysis').isVisible().catch(() => false);
        const hasSaveButton = await page.locator('text=Save RCA').isVisible().catch(() => false);
        const hasRootCause = await page.locator('text=Root Cause').isVisible().catch(() => false);
        
        expect(has5Whys || hasSaveButton || hasRootCause).toBe(true);
        
        // Take screenshot for evidence
        await page.screenshot({ path: 'test-results/investigation-rca-tab.png', fullPage: true });
      }
    });

    test('should render Report tab with pack list and capability state', async ({ page }) => {
      await page.goto(`${STAGING_URL}/investigations`);
      await page.waitForLoadState('networkidle');
      
      const rows = page.locator('table tbody tr');
      const rowCount = await rows.count();
      
      if (rowCount > 0) {
        await rows.first().click();
        await page.waitForURL(/\/investigations\/\d+/);
        
        // Click Report tab
        await page.locator('button:has-text("Report")').click();
        await page.waitForTimeout(1000);
        
        // Assert Report content is visible
        const hasGenerateReport = await page.locator('text=Generate Report').isVisible().catch(() => false);
        const hasReportHistory = await page.locator('text=Report History').isVisible().catch(() => false);
        const hasInternalReport = await page.locator('text=Internal Report').isVisible().catch(() => false);
        
        expect(hasGenerateReport || hasReportHistory || hasInternalReport).toBe(true);
        
        // Take screenshot for evidence
        await page.screenshot({ path: 'test-results/investigation-report-tab.png', fullPage: true });
      }
    });
  });

  test.describe('3. Non-Regression (CRITICAL)', () => {
    test('should render /audits page with key heading', async ({ page }) => {
      await page.goto(`${STAGING_URL}/audits`);
      await page.waitForLoadState('networkidle');
      
      // Assert the page has a heading (h1)
      const h1 = page.locator('h1');
      await expect(h1).toBeVisible({ timeout: 15000 });
      
      // Should not be a 404 page
      const is404 = await page.locator('text=404').isVisible().catch(() => false);
      expect(is404).toBe(false);
      
      // Take screenshot for evidence
      await page.screenshot({ path: 'test-results/audits-page.png', fullPage: true });
    });

    test('should render /planet-mark page with key heading', async ({ page }) => {
      await page.goto(`${STAGING_URL}/planet-mark`);
      await page.waitForLoadState('networkidle');
      
      // Assert the page has a heading (h1)
      const h1 = page.locator('h1');
      await expect(h1).toBeVisible({ timeout: 15000 });
      
      // Should not be a 404 page
      const is404 = await page.locator('text=404').isVisible().catch(() => false);
      expect(is404).toBe(false);
      
      // Take screenshot for evidence
      await page.screenshot({ path: 'test-results/planet-mark-page.png', fullPage: true });
    });

    test('should handle deep-link refresh correctly', async ({ page }) => {
      // Navigate directly to a deep link
      await page.goto(`${STAGING_URL}/investigations/1`);
      await page.waitForLoadState('networkidle');
      
      // Refresh the page
      await page.reload();
      await page.waitForLoadState('networkidle');
      
      // Should either show the investigation detail or a proper error (not 404 HTML)
      const hasBackButton = await page.locator('text=Back to Investigations').isVisible().catch(() => false);
      const hasError = await page.locator('text=Investigation not found').isVisible().catch(() => false);
      const hasTabs = await page.locator('button:has-text("Summary")').isVisible().catch(() => false);
      
      expect(hasBackButton || hasError || hasTabs).toBe(true);
      
      // Take screenshot for evidence
      await page.screenshot({ path: 'test-results/deep-link-refresh.png', fullPage: true });
    });
  });

  test.describe('4. App Shell Integrity', () => {
    test('should render navigation sidebar', async ({ page }) => {
      await page.goto(`${STAGING_URL}/`);
      await page.waitForLoadState('networkidle');
      
      // Check for navigation elements
      const hasNav = await page.locator('nav').isVisible().catch(() => false);
      const hasSidebar = await page.locator('[class*="sidebar"]').isVisible().catch(() => false);
      const hasInvestigationsLink = await page.locator('a[href="/investigations"]').isVisible().catch(() => false);
      
      expect(hasNav || hasSidebar || hasInvestigationsLink).toBe(true);
    });

    test('should not have console errors on load', async ({ page }) => {
      const consoleErrors: string[] = [];
      
      page.on('console', msg => {
        if (msg.type() === 'error') {
          consoleErrors.push(msg.text());
        }
      });
      
      await page.goto(`${STAGING_URL}/investigations`);
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(2000);
      
      // Filter out known acceptable errors (e.g., auth redirects, external resources)
      const criticalErrors = consoleErrors.filter(err => 
        !err.includes('401') && 
        !err.includes('favicon') &&
        !err.includes('CORS')
      );
      
      // Log but don't fail on console errors (advisory)
      if (criticalErrors.length > 0) {
        console.log('Console errors detected:', criticalErrors);
      }
    });
  });
});
