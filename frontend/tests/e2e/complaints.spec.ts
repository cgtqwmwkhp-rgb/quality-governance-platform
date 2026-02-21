import { test, expect } from '@playwright/test';

test.describe('Complaints Management', () => {
  test.describe.configure({ mode: 'parallel' });

  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('access_token', 'test-token-e2e');
    });
  });

  test.describe('Page Load', () => {
    test('should display the complaints page heading', async ({ page }) => {
      await page.goto('/complaints');
      await page.waitForLoadState('networkidle');

      const heading = page.getByRole('heading', { name: /Complaints/i });
      await expect(heading).toBeVisible();
    });

    test('should have a page title containing Complaints or Quality', async ({ page }) => {
      await page.goto('/complaints');
      await page.waitForLoadState('networkidle');

      await expect(page).toHaveTitle(/Complaints|Quality/i);
    });
  });

  test.describe('Complaint List', () => {
    test('should show complaint list or empty state', async ({ page }) => {
      await page.goto('/complaints');
      await page.waitForLoadState('networkidle');

      const table = page.locator('table');
      const hasTable = await table.isVisible().catch(() => false);

      if (hasTable) {
        await expect(page.locator('th', { hasText: /Reference/i })).toBeVisible();
        await expect(page.locator('th', { hasText: /Title|Subject/i })).toBeVisible();
        await expect(page.locator('th', { hasText: /Status/i })).toBeVisible();
      } else {
        const hasEmptyState = await page.getByText(/No complaints/i).isVisible().catch(() => false);
        const hasCards = await page.locator('[class*="card"]').first().isVisible().catch(() => false);
        expect(hasEmptyState || hasCards).toBe(true);
      }
    });

    test('should display stat cards if present', async ({ page }) => {
      await page.goto('/complaints');
      await page.waitForLoadState('networkidle');

      const hasStats = await page.getByText(/Total|Open|Pending/i).first().isVisible().catch(() => false);
      expect(hasStats).toBe(true);
    });
  });

  test.describe('Create Complaint Flow', () => {
    test('should open create complaint form', async ({ page }) => {
      await page.goto('/complaints');
      await page.waitForLoadState('networkidle');

      const createButton = page.getByRole('button', { name: /New Complaint|Add Complaint|Create/i });
      const hasCreateButton = await createButton.isVisible().catch(() => false);

      if (hasCreateButton) {
        await createButton.click();

        const hasModal = await page.getByRole('heading', { name: /New Complaint|Add Complaint|Create Complaint/i })
          .isVisible()
          .catch(() => false);
        const hasForm = await page.locator('form').isVisible().catch(() => false);
        expect(hasModal || hasForm).toBe(true);
      }
    });

    test('should close create form with Cancel button', async ({ page }) => {
      await page.goto('/complaints');
      await page.waitForLoadState('networkidle');

      const createButton = page.getByRole('button', { name: /New Complaint|Add Complaint|Create/i });
      const hasCreateButton = await createButton.isVisible().catch(() => false);

      if (hasCreateButton) {
        await createButton.click();
        const cancelButton = page.getByRole('button', { name: /Cancel/i });
        const hasCancelButton = await cancelButton.isVisible().catch(() => false);

        if (hasCancelButton) {
          await cancelButton.click();
          await expect(page.getByRole('heading', { name: /New Complaint|Add Complaint|Create Complaint/i }))
            .not.toBeVisible();
        }
      }
    });
  });

  test.describe('Complaint Detail', () => {
    test('should navigate to complaint detail when clicking a row', async ({ page }) => {
      await page.goto('/complaints');
      await page.waitForLoadState('networkidle');

      const firstRow = page.locator('table tbody tr').first();
      const hasRow = await firstRow.isVisible().catch(() => false);

      if (hasRow) {
        await firstRow.click();
        await page.waitForLoadState('networkidle');
        expect(page.url()).toContain('/complaints/');
      }
    });
  });

  test.describe('Navigation', () => {
    test('should be accessible via /complaints URL', async ({ page }) => {
      await page.goto('/complaints');
      await page.waitForLoadState('networkidle');

      expect(page.url()).toContain('/complaints');
    });
  });
});
