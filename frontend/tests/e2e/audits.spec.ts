import { test, expect } from '@playwright/test';

test.describe('Audit Management', () => {
  test.describe.configure({ mode: 'parallel' });

  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('access_token', 'test-token-e2e');
    });
  });

  test.describe('Audit List Page', () => {
    test('should render the audit management page heading', async ({ page }) => {
      await page.goto('/audits');
      await page.waitForLoadState('networkidle');

      await expect(page.getByRole('heading', { name: /Audit Management/i })).toBeVisible();
      await expect(page.getByText(/Internal audits, inspections & compliance checks/i)).toBeVisible();
    });

    test('should display stat cards', async ({ page }) => {
      await page.goto('/audits');
      await page.waitForLoadState('networkidle');

      await expect(page.getByText('Total Audits')).toBeVisible();
      await expect(page.getByText('In Progress')).toBeVisible();
      await expect(page.getByText('Completed')).toBeVisible();
      await expect(page.getByText('Avg Score')).toBeVisible();
      await expect(page.getByText('Open Findings')).toBeVisible();
    });

    test('should have a search input', async ({ page }) => {
      await page.goto('/audits');
      await page.waitForLoadState('networkidle');

      const searchInput = page.getByPlaceholder(/Search audits/i);
      await expect(searchInput).toBeVisible();

      await searchInput.fill('safety inspection');
      await expect(searchInput).toHaveValue('safety inspection');
    });

    test('should display view mode toggle with Board, List, and Findings', async ({ page }) => {
      await page.goto('/audits');
      await page.waitForLoadState('networkidle');

      await expect(page.getByRole('button', { name: /Board/i })).toBeVisible();
      await expect(page.getByRole('button', { name: /List/i })).toBeVisible();
      await expect(page.getByRole('button', { name: /Findings/i })).toBeVisible();
    });

    test('should switch to list view and show table columns', async ({ page }) => {
      await page.goto('/audits');
      await page.waitForLoadState('networkidle');

      await page.getByRole('button', { name: /List/i }).click();

      const table = page.locator('table');
      const hasTable = await table.isVisible().catch(() => false);

      if (hasTable) {
        await expect(page.locator('th', { hasText: /Reference/i })).toBeVisible();
        await expect(page.locator('th', { hasText: /Title/i })).toBeVisible();
        await expect(page.locator('th', { hasText: /Location/i })).toBeVisible();
        await expect(page.locator('th', { hasText: /Status/i })).toBeVisible();
        await expect(page.locator('th', { hasText: /Score/i })).toBeVisible();
      } else {
        await expect(page.getByText(/No audits found/i)).toBeVisible();
      }
    });

    test('should display kanban columns in board view', async ({ page }) => {
      await page.goto('/audits');
      await page.waitForLoadState('networkidle');

      await expect(page.getByText('Scheduled')).toBeVisible();
      await expect(page.getByText('In Progress')).toBeVisible();
      await expect(page.getByText('Pending Review')).toBeVisible();
      await expect(page.getByText('Completed')).toBeVisible();
    });

    test('should switch to findings view', async ({ page }) => {
      await page.goto('/audits');
      await page.waitForLoadState('networkidle');

      await page.getByRole('button', { name: /Findings/i }).click();

      const hasFindingCards = await page.locator('[class*="card"]').first().isVisible().catch(() => false);
      const hasEmptyState = await page.getByText(/No findings recorded/i).isVisible().catch(() => false);

      expect(hasFindingCards || hasEmptyState).toBe(true);
    });
  });

  test.describe('Create Audit Flow', () => {
    test('should open schedule audit modal', async ({ page }) => {
      await page.goto('/audits');
      await page.waitForLoadState('networkidle');

      const newButton = page.getByRole('button', { name: /New Audit/i });
      await expect(newButton).toBeVisible();
      await newButton.click();

      await expect(page.getByText(/Schedule New Audit/i)).toBeVisible();
      await expect(page.getByText(/Select a published template/i)).toBeVisible();
    });

    test('should display form fields in the modal', async ({ page }) => {
      await page.goto('/audits');
      await page.waitForLoadState('networkidle');

      await page.getByRole('button', { name: /New Audit/i }).click();
      await expect(page.getByText(/Schedule New Audit/i)).toBeVisible();

      await expect(page.getByText(/Audit Template/i)).toBeVisible();
      await expect(page.getByText(/Audit Title/i)).toBeVisible();
      await expect(page.getByText(/Location/i)).toBeVisible();
      await expect(page.getByText(/Scheduled Date/i)).toBeVisible();
    });

    test('should have Schedule Audit button disabled without template selection', async ({ page }) => {
      await page.goto('/audits');
      await page.waitForLoadState('networkidle');

      await page.getByRole('button', { name: /New Audit/i }).click();

      const scheduleBtn = page.getByRole('button', { name: /Schedule Audit/i });
      await expect(scheduleBtn).toBeDisabled();
    });

    test('should close modal with Cancel button', async ({ page }) => {
      await page.goto('/audits');
      await page.waitForLoadState('networkidle');

      await page.getByRole('button', { name: /New Audit/i }).click();
      await expect(page.getByText(/Schedule New Audit/i)).toBeVisible();

      await page.getByRole('button', { name: /Cancel/i }).click();
      await expect(page.getByText(/Schedule New Audit/i)).not.toBeVisible();
    });

    test('should fill in optional form fields', async ({ page }) => {
      await page.goto('/audits');
      await page.waitForLoadState('networkidle');

      await page.getByRole('button', { name: /New Audit/i }).click();

      const titleInput = page.locator('#audit-title');
      await titleInput.fill('Q1 2026 Safety Inspection');
      await expect(titleInput).toHaveValue('Q1 2026 Safety Inspection');

      const locationInput = page.locator('#audit-location');
      await locationInput.fill('Warehouse B');
      await expect(locationInput).toHaveValue('Warehouse B');
    });
  });

  test.describe('Navigation', () => {
    test('should navigate to audit templates page', async ({ page }) => {
      await page.goto('/audit-templates');
      await page.waitForLoadState('networkidle');

      expect(page.url()).toContain('/audit-templates');
    });

    test('should maintain URL when switching view modes', async ({ page }) => {
      await page.goto('/audits');
      await page.waitForLoadState('networkidle');

      await page.getByRole('button', { name: /List/i }).click();
      expect(page.url()).toContain('/audits');

      await page.getByRole('button', { name: /Findings/i }).click();
      expect(page.url()).toContain('/audits');

      await page.getByRole('button', { name: /Board/i }).click();
      expect(page.url()).toContain('/audits');
    });
  });
});
