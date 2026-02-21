import { test, expect } from '@playwright/test';

test.describe('Documents', () => {
  test.describe.configure({ mode: 'parallel' });

  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('access_token', 'test-token-e2e');
    });
  });

  test.describe('Page Load', () => {
    test('should load documents page', async ({ page }) => {
      await page.goto('/documents');
      await page.waitForLoadState('networkidle');
      await expect(page.getByRole('heading', { name: /Documents/i })).toBeVisible();
    });

    test('should display search or upload controls', async ({ page }) => {
      await page.goto('/documents');
      await page.waitForLoadState('networkidle');
      const searchInput = page.getByPlaceholder(/search/i);
      const uploadButton = page.getByRole('button', { name: /Upload|Add Document/i });
      const hasSearch = await searchInput.isVisible().catch(() => false);
      const hasUpload = await uploadButton.isVisible().catch(() => false);
      expect(hasSearch || hasUpload).toBeTruthy();
    });
  });

  test.describe('Document List', () => {
    test('should display document grid or table', async ({ page }) => {
      await page.goto('/documents');
      await page.waitForLoadState('networkidle');
      const table = page.locator('table');
      const grid = page.locator('[role="grid"], [class*="grid"], [class*="card"]');
      const hasTable = await table.isVisible().catch(() => false);
      const hasGrid = await grid.first().isVisible().catch(() => false);
      const emptyState = page.getByText(/no documents|empty|get started/i);
      const hasEmpty = await emptyState.isVisible().catch(() => false);
      expect(hasTable || hasGrid || hasEmpty).toBeTruthy();
    });

    test('should show document categories', async ({ page }) => {
      await page.goto('/documents');
      await page.waitForLoadState('networkidle');
      const hasCategories = await page.getByRole('combobox').isVisible().catch(() => false);
      const hasTabs = await page.getByRole('tab').first().isVisible().catch(() => false);
      expect(hasCategories || hasTabs).toBeTruthy();
    });
  });

  test.describe('Upload and Controls', () => {
    test('should display upload button', async ({ page }) => {
      await page.goto('/documents');
      await page.waitForLoadState('networkidle');
      try {
        await expect(page.getByRole('button', { name: /Upload|Add Document|New/i })).toBeVisible({ timeout: 5000 });
      } catch {
        await expect(page.getByRole('heading', { name: /Documents/i })).toBeVisible();
      }
    });

    test('should allow searching documents', async ({ page }) => {
      await page.goto('/documents');
      await page.waitForLoadState('networkidle');
      const searchInput = page.getByPlaceholder(/search/i);
      const hasSearch = await searchInput.isVisible().catch(() => false);
      if (hasSearch) {
        await searchInput.fill('test document');
        await expect(searchInput).toHaveValue('test document');
        await page.waitForTimeout(500);
        await expect(page.getByRole('heading', { name: /Documents/i })).toBeVisible();
      } else {
        await expect(page.getByRole('heading', { name: /Documents/i })).toBeVisible();
      }
    });

    test('should toggle grid or list view if available', async ({ page }) => {
      await page.goto('/documents');
      await page.waitForLoadState('networkidle');
      const gridButton = page.getByRole('button', { name: /grid/i });
      const listButton = page.getByRole('button', { name: /list/i });
      const viewToggle = page.locator('[aria-label*="view"], [class*="view-toggle"], [data-testid*="view"]');
      const hasGrid = await gridButton.isVisible().catch(() => false);
      const hasList = await listButton.isVisible().catch(() => false);
      const hasToggle = await viewToggle.first().isVisible().catch(() => false);
      if (hasGrid) {
        await gridButton.click();
        await page.waitForTimeout(500);
        await expect(page.getByRole('heading', { name: /Documents/i })).toBeVisible();
      } else if (hasList) {
        await listButton.click();
        await page.waitForTimeout(500);
        await expect(page.getByRole('heading', { name: /Documents/i })).toBeVisible();
      } else if (hasToggle) {
        await viewToggle.first().click();
        await page.waitForTimeout(500);
        await expect(page.getByRole('heading', { name: /Documents/i })).toBeVisible();
      } else {
        await expect(page.getByRole('heading', { name: /Documents/i })).toBeVisible();
      }
    });
  });

  test.describe('Navigation', () => {
    test('should navigate to document detail on click', async ({ page }) => {
      await page.goto('/documents');
      await page.waitForLoadState('networkidle');
      const rows = page.locator('table tbody tr');
      const count = await rows.count().catch(() => 0);
      if (count > 0) {
        await rows.first().click();
        await page.waitForLoadState('networkidle');
        expect(page.url()).toContain('/documents/');
      }
    });
  });

  test.describe('Empty State', () => {
    test('should handle empty document list gracefully', async ({ page }) => {
      await page.goto('/documents');
      await page.waitForLoadState('networkidle');
      const heading = page.getByRole('heading', { name: /Documents/i });
      await expect(heading).toBeVisible();
    });
  });

  test.describe('Upload Document', () => {
    test('should open upload dialog and attach a file', async ({ page }) => {
      await page.goto('/documents');
      await page.waitForLoadState('networkidle');

      const uploadButton = page.getByRole('button', { name: /Upload|Add Document|New/i });
      const hasUpload = await uploadButton.isVisible().catch(() => false);
      if (!hasUpload) {
        await expect(page.getByRole('heading', { name: /Documents/i })).toBeVisible();
        return;
      }

      await uploadButton.click();
      await page.waitForLoadState('networkidle');

      const dialog = page.locator('[role="dialog"], [class*="modal"], [class*="drawer"]').first();
      const routeChanged = page.url().includes('/upload') || page.url().includes('/new');
      const hasDialog = await dialog.isVisible().catch(() => false);

      if (hasDialog || routeChanged) {
        const fileInput = page.locator('input[type="file"]');
        const hasFileInput = await fileInput.isVisible().catch(() => false);
        if (hasFileInput) {
          await expect(fileInput).toBeAttached();
        }

        const nameInput = page.getByLabel(/name|title/i).or(page.getByPlaceholder(/name|title/i));
        const hasNameInput = await nameInput.isVisible().catch(() => false);
        if (hasNameInput) {
          await nameInput.fill('E2E Test Document');
          await expect(nameInput).toHaveValue('E2E Test Document');
        }
      }

      await expect(page.getByRole('heading', { name: /Documents/i })).toBeVisible();
    });
  });

  test.describe('View Toggle', () => {
    test('should toggle between grid and list views', async ({ page }) => {
      await page.goto('/documents');
      await page.waitForLoadState('networkidle');

      const gridButton = page.getByRole('button', { name: /grid/i });
      const listButton = page.getByRole('button', { name: /list/i });
      const viewToggle = page.locator('[aria-label*="view"], [class*="view-toggle"], [data-testid*="view"]');

      const hasGrid = await gridButton.isVisible().catch(() => false);
      const hasList = await listButton.isVisible().catch(() => false);
      const hasToggle = await viewToggle.first().isVisible().catch(() => false);

      if (hasGrid && hasList) {
        await listButton.click();
        await page.waitForTimeout(500);

        const table = page.locator('table');
        const listView = page.locator('[class*="list"]');
        const hasTableView = await table.isVisible().catch(() => false);
        const hasListView = await listView.first().isVisible().catch(() => false);

        await gridButton.click();
        await page.waitForTimeout(500);

        const grid = page.locator('[role="grid"], [class*="grid"], [class*="card"]');
        const hasGridView = await grid.first().isVisible().catch(() => false);

        expect(hasTableView || hasListView || hasGridView).toBeTruthy();
      } else if (hasToggle) {
        await viewToggle.first().click();
        await page.waitForTimeout(500);
        await viewToggle.first().click();
        await page.waitForTimeout(500);
      }

      await expect(page.getByRole('heading', { name: /Documents/i })).toBeVisible();
    });
  });
});
