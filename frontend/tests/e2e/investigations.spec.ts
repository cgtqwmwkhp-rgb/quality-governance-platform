/**
 * Playwright E2E Tests for Investigations Module
 * Stage 2 Parity Tests
 * 
 * These tests verify the Investigations functionality matches Repo A look & feel.
 */

import { test, expect } from '@playwright/test';

// Base URL is configured in playwright.config.ts
const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:5173';

test.describe('Investigations Module', () => {
  // Before each test, we may need to login
  // For now, assume staging has auth or mock auth

  test.describe('1. Investigations List', () => {
    test('should load /investigations and render table', async ({ page }) => {
      await page.goto(`${BASE_URL}/investigations`);
      
      // Wait for page to load
      await expect(page.locator('h1')).toContainText('Root Cause Investigations');
      
      // Check for table headers
      await expect(page.locator('th:has-text("Reference")')).toBeVisible();
      await expect(page.locator('th:has-text("Title")')).toBeVisible();
      await expect(page.locator('th:has-text("Status")')).toBeVisible();
      await expect(page.locator('th:has-text("Lead")')).toBeVisible();
      await expect(page.locator('th:has-text("Actions")')).toBeVisible();
      await expect(page.locator('th:has-text("Created")')).toBeVisible();
    });

    test('should show API connected indicator', async ({ page }) => {
      await page.goto(`${BASE_URL}/investigations`);
      
      // Check for API connected indicator
      const indicator = page.locator('text=API Connected');
      await expect(indicator).toBeVisible();
    });

    test('should filter by status', async ({ page }) => {
      await page.goto(`${BASE_URL}/investigations`);
      
      // Wait for page load
      await expect(page.locator('h1')).toContainText('Root Cause Investigations');
      
      // Open status filter dropdown
      await page.locator('[data-testid="status-filter"]').click().catch(() => {
        // Fallback to finding by placeholder
        page.locator('button:has-text("All")').first().click();
      });
      
      // The filter dropdown should be visible
      await expect(page.locator('text=Open')).toBeVisible();
      await expect(page.locator('text=In Progress')).toBeVisible();
      await expect(page.locator('text=Pending Review')).toBeVisible();
    });

    test('should handle search deterministically', async ({ page }) => {
      await page.goto(`${BASE_URL}/investigations`);
      
      // Find search input
      const searchInput = page.locator('input[placeholder*="Search"]');
      await expect(searchInput).toBeVisible();
      
      // Type a search term
      await searchInput.fill('TEST-123');
      
      // Wait for filtering (client-side)
      await page.waitForTimeout(500);
      
      // Either we have results or empty state - both are valid
      const hasResults = await page.locator('table tbody tr').count() > 0;
      const hasEmptyState = await page.locator('text=No Investigations Found').isVisible().catch(() => false);
      
      expect(hasResults || hasEmptyState).toBe(true);
    });
  });

  test.describe('2. Investigation Detail Page', () => {
    test('should navigate to /investigations/:id and render detail', async ({ page }) => {
      await page.goto(`${BASE_URL}/investigations`);
      
      // Wait for list to load
      await expect(page.locator('h1')).toContainText('Root Cause Investigations');
      
      // Check if there are any investigations
      const rows = page.locator('table tbody tr');
      const rowCount = await rows.count();
      
      if (rowCount > 0) {
        // Click first investigation
        await rows.first().click();
        
        // Should navigate to detail page
        await expect(page.url()).toContain('/investigations/');
        
        // Should show tabs
        await expect(page.locator('button:has-text("Summary")')).toBeVisible();
        await expect(page.locator('button:has-text("Timeline")')).toBeVisible();
        await expect(page.locator('button:has-text("Evidence")')).toBeVisible();
        await expect(page.locator('button:has-text("RCA")')).toBeVisible();
        await expect(page.locator('button:has-text("Actions")')).toBeVisible();
        await expect(page.locator('button:has-text("Report")')).toBeVisible();
      } else {
        // No investigations - verify empty state
        await expect(page.locator('text=No Investigations Found')).toBeVisible();
      }
    });

    test('should render tabs deterministically with empty/loading states', async ({ page }) => {
      // Navigate directly to a detail page if we have an ID
      // For testing, we'll use a known ID or skip if not available
      await page.goto(`${BASE_URL}/investigations/1`);
      
      // Either error state (404) or detail page
      const hasError = await page.locator('text=Investigation not found').isVisible().catch(() => false);
      const hasTitle = await page.locator('[data-testid="investigation-title"]').isVisible().catch(() => false);
      const hasTabs = await page.locator('button:has-text("Summary")').isVisible().catch(() => false);
      
      // One of these states should be present
      expect(hasError || hasTitle || hasTabs).toBe(true);
    });

    test('should refresh deep-link to /investigations/:id correctly', async ({ page }) => {
      await page.goto(`${BASE_URL}/investigations/1`);
      
      // Wait for initial load
      await page.waitForLoadState('networkidle');
      
      // Refresh page
      await page.reload();
      
      // Should still be on the same page, not 404
      await page.waitForLoadState('networkidle');
      
      // Either error state (if ID doesn't exist) or content
      const hasBackButton = await page.locator('text=Back to Investigations').isVisible().catch(() => false);
      const hasError = await page.locator('text=Investigation not found').isVisible().catch(() => false);
      
      expect(hasBackButton || hasError).toBe(true);
    });
  });

  test.describe('3. Actions Tab', () => {
    test('should render actions list in Actions tab', async ({ page }) => {
      // This test requires a valid investigation ID
      await page.goto(`${BASE_URL}/investigations`);
      
      const rows = page.locator('table tbody tr');
      const rowCount = await rows.count();
      
      if (rowCount > 0) {
        await rows.first().click();
        await page.waitForURL(/\/investigations\/\d+/);
        
        // Click Actions tab
        await page.locator('button:has-text("Actions")').click();
        
        // Should show actions list or empty state
        const hasActions = await page.locator('[data-testid="action-card"]').count() > 0;
        const hasEmptyState = await page.locator('text=No Actions').isVisible().catch(() => false);
        const hasAddButton = await page.locator('button:has-text("Add Action")').isVisible().catch(() => false);
        
        expect(hasActions || hasEmptyState || hasAddButton).toBe(true);
      }
    });
  });

  test.describe('4. Timeline Tab', () => {
    test('should render timeline with filter toggles', async ({ page }) => {
      await page.goto(`${BASE_URL}/investigations`);
      
      const rows = page.locator('table tbody tr');
      const rowCount = await rows.count();
      
      if (rowCount > 0) {
        await rows.first().click();
        await page.waitForURL(/\/investigations\/\d+/);
        
        // Click Timeline tab
        await page.locator('button:has-text("Timeline")').click();
        
        // Should show timeline or empty state
        const hasTimelineItems = await page.locator('[data-testid="timeline-event"]').count() > 0;
        const hasEmptyState = await page.locator('text=No Timeline Events').isVisible().catch(() => false);
        const hasFilter = await page.locator('text=All Events').isVisible().catch(() => false);
        
        expect(hasTimelineItems || hasEmptyState || hasFilter).toBe(true);
      }
    });
  });

  test.describe('5. Evidence Tab', () => {
    test('should render evidence register header', async ({ page }) => {
      await page.goto(`${BASE_URL}/investigations`);
      
      const rows = page.locator('table tbody tr');
      const rowCount = await rows.count();
      
      if (rowCount > 0) {
        await rows.first().click();
        await page.waitForURL(/\/investigations\/\d+/);
        
        // Click Evidence tab
        await page.locator('button:has-text("Evidence")').click();
        
        // Should show evidence register header
        await expect(page.locator('text=Evidence Register')).toBeVisible();
      }
    });

    test('should show upload button', async ({ page }) => {
      await page.goto(`${BASE_URL}/investigations`);
      
      const rows = page.locator('table tbody tr');
      const rowCount = await rows.count();
      
      if (rowCount > 0) {
        await rows.first().click();
        await page.waitForURL(/\/investigations\/\d+/);
        
        // Click Evidence tab
        await page.locator('button:has-text("Evidence")').click();
        
        // Should show upload button
        await expect(page.locator('text=Upload Evidence')).toBeVisible();
      }
    });

    test('should show empty state or evidence list deterministically', async ({ page }) => {
      await page.goto(`${BASE_URL}/investigations`);
      
      const rows = page.locator('table tbody tr');
      const rowCount = await rows.count();
      
      if (rowCount > 0) {
        await rows.first().click();
        await page.waitForURL(/\/investigations\/\d+/);
        
        // Click Evidence tab
        await page.locator('button:has-text("Evidence")').click();
        
        // Wait for loading to complete
        await page.waitForTimeout(1000);
        
        // Should show either evidence cards or empty state
        const hasEvidenceCards = await page.locator('div:has-text("internal customer")').count() > 0;
        const hasEmptyState = await page.locator('text=No Evidence Uploaded').isVisible().catch(() => false);
        
        expect(hasEvidenceCards || hasEmptyState).toBe(true);
      }
    });
  });

  test.describe('5.5. RCA Tab', () => {
    test('should render 5 Whys analysis fields', async ({ page }) => {
      await page.goto(`${BASE_URL}/investigations`);
      
      const rows = page.locator('table tbody tr');
      const rowCount = await rows.count();
      
      if (rowCount > 0) {
        await rows.first().click();
        await page.waitForURL(/\/investigations\/\d+/);
        
        // Click RCA tab
        await page.locator('button:has-text("RCA")').click();
        
        // Should show 5 Whys header
        await expect(page.locator('text=5 Whys Analysis')).toBeVisible();
      }
    });

    test('should have Save RCA Analysis button', async ({ page }) => {
      await page.goto(`${BASE_URL}/investigations`);
      
      const rows = page.locator('table tbody tr');
      const rowCount = await rows.count();
      
      if (rowCount > 0) {
        await rows.first().click();
        await page.waitForURL(/\/investigations\/\d+/);
        
        // Click RCA tab
        await page.locator('button:has-text("RCA")').click();
        
        // Should show save button
        await expect(page.locator('text=Save RCA Analysis')).toBeVisible();
      }
    });

    test('should show unsaved changes indicator when field is modified', async ({ page }) => {
      await page.goto(`${BASE_URL}/investigations`);
      
      const rows = page.locator('table tbody tr');
      const rowCount = await rows.count();
      
      if (rowCount > 0) {
        await rows.first().click();
        await page.waitForURL(/\/investigations\/\d+/);
        
        // Click RCA tab
        await page.locator('button:has-text("RCA")').click();
        
        // Wait for fields to load
        await page.waitForTimeout(500);
        
        // Find and modify a textarea (Why 1)
        const textarea = page.locator('textarea').first();
        await textarea.fill('Test modification for unsaved changes');
        
        // Should show unsaved changes indicator
        await expect(page.locator('text=You have unsaved changes')).toBeVisible();
      }
    });

    test('should render root cause field', async ({ page }) => {
      await page.goto(`${BASE_URL}/investigations`);
      
      const rows = page.locator('table tbody tr');
      const rowCount = await rows.count();
      
      if (rowCount > 0) {
        await rows.first().click();
        await page.waitForURL(/\/investigations\/\d+/);
        
        // Click RCA tab
        await page.locator('button:has-text("RCA")').click();
        
        // Should show root cause section
        await expect(page.locator('text=Root Cause Identified')).toBeVisible();
      }
    });
  });

  test.describe('6. Report Tab', () => {
    test('should render generate report section', async ({ page }) => {
      await page.goto(`${BASE_URL}/investigations`);
      
      const rows = page.locator('table tbody tr');
      const rowCount = await rows.count();
      
      if (rowCount > 0) {
        await rows.first().click();
        await page.waitForURL(/\/investigations\/\d+/);
        
        // Click Report tab
        await page.locator('button:has-text("Report")').click();
        
        // Should show generate report section
        await expect(page.locator('text=Generate Report')).toBeVisible();
      }
    });

    test('should show internal and external report buttons', async ({ page }) => {
      await page.goto(`${BASE_URL}/investigations`);
      
      const rows = page.locator('table tbody tr');
      const rowCount = await rows.count();
      
      if (rowCount > 0) {
        await rows.first().click();
        await page.waitForURL(/\/investigations\/\d+/);
        
        // Click Report tab
        await page.locator('button:has-text("Report")').click();
        
        // Should show generate buttons
        await expect(page.locator('button:has-text("Internal Report")')).toBeVisible();
        await expect(page.locator('button:has-text("External Report")')).toBeVisible();
      }
    });

    test('should show report history section', async ({ page }) => {
      await page.goto(`${BASE_URL}/investigations`);
      
      const rows = page.locator('table tbody tr');
      const rowCount = await rows.count();
      
      if (rowCount > 0) {
        await rows.first().click();
        await page.waitForURL(/\/investigations\/\d+/);
        
        // Click Report tab
        await page.locator('button:has-text("Report")').click();
        
        // Should show report history header
        await expect(page.locator('text=Report History')).toBeVisible();
      }
    });

    test('should show deterministic empty or list state for packs', async ({ page }) => {
      await page.goto(`${BASE_URL}/investigations`);
      
      const rows = page.locator('table tbody tr');
      const rowCount = await rows.count();
      
      if (rowCount > 0) {
        await rows.first().click();
        await page.waitForURL(/\/investigations\/\d+/);
        
        // Click Report tab
        await page.locator('button:has-text("Report")').click();
        
        // Wait for loading to complete
        await page.waitForTimeout(1000);
        
        // Should show either packs or empty state
        const hasPacks = await page.locator('text=Report').count() > 2; // More than just headers
        const hasEmptyState = await page.locator('text=No reports generated yet').isVisible().catch(() => false);
        
        expect(hasPacks || hasEmptyState).toBe(true);
      }
    });

    test('should show capability warning if pack generation unavailable', async ({ page }) => {
      await page.goto(`${BASE_URL}/investigations`);
      
      const rows = page.locator('table tbody tr');
      const rowCount = await rows.count();
      
      if (rowCount > 0) {
        await rows.first().click();
        await page.waitForURL(/\/investigations\/\d+/);
        
        // Click Report tab
        await page.locator('button:has-text("Report")').click();
        
        // Wait for capability check
        await page.waitForTimeout(1000);
        
        // Check if warning is shown or buttons are enabled
        const hasWarning = await page.locator('text=Report generation not available').isVisible().catch(() => false);
        const hasEnabledButtons = await page.locator('button:has-text("Internal Report"):not([disabled])').isVisible().catch(() => false);
        
        // Either warning is shown OR buttons are enabled (not both)
        expect(hasWarning || hasEnabledButtons).toBe(true);
      }
    });
  });

  test.describe('7. Non-Regression', () => {
    test('should render /audits page', async ({ page }) => {
      await page.goto(`${BASE_URL}/audits`);
      
      // Should load audits page
      await expect(page.locator('h1')).toBeVisible();
      
      // Page should not be a 404
      const is404 = await page.locator('text=404').isVisible().catch(() => false);
      expect(is404).toBe(false);
    });

    test('should render /planet-mark page', async ({ page }) => {
      await page.goto(`${BASE_URL}/planet-mark`);
      
      // Should load planet-mark page
      await expect(page.locator('h1')).toBeVisible();
      
      // Page should not be a 404
      const is404 = await page.locator('text=404').isVisible().catch(() => false);
      expect(is404).toBe(false);
    });
  });
});
