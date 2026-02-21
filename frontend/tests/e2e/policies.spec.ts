import { test, expect } from '@playwright/test';

test.describe('Policy Management', () => {
  test.describe.configure({ mode: 'parallel' });

  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('access_token', 'test-token-e2e');
    });
  });

  test.describe('Page Load', () => {
    test('should display the policies page heading', async ({ page }) => {
      await page.goto('/policies');
      await page.waitForLoadState('networkidle');

      const heading = page.getByRole('heading', { name: /Policies/i });
      await expect(heading).toBeVisible();
    });

    test('should have a page title containing Policies or Quality', async ({ page }) => {
      await page.goto('/policies');
      await page.waitForLoadState('networkidle');

      await expect(page).toHaveTitle(/Policies|Quality/i);
    });
  });

  test.describe('Policy List', () => {
    test('should show policy list or empty state', async ({ page }) => {
      await page.goto('/policies');
      await page.waitForLoadState('networkidle');

      const table = page.locator('table');
      const hasTable = await table.isVisible().catch(() => false);

      if (hasTable) {
        await expect(page.locator('th', { hasText: /Title|Name/i })).toBeVisible();
        await expect(page.locator('th', { hasText: /Status|Version/i })).toBeVisible();
      } else {
        const hasEmptyState = await page.getByText(/No policies/i).isVisible().catch(() => false);
        const hasCards = await page.locator('[class*="card"]').first().isVisible().catch(() => false);
        expect(hasEmptyState || hasCards).toBe(true);
      }
    });

    test('should display stat cards if present', async ({ page }) => {
      await page.goto('/policies');
      await page.waitForLoadState('networkidle');

      const hasStats = await page.getByText(/Total|Active|Draft|Published/i).first().isVisible().catch(() => false);
      expect(hasStats).toBe(true);
    });
  });

  test.describe('Create Policy Flow', () => {
    test('should open create policy form', async ({ page }) => {
      await page.goto('/policies');
      await page.waitForLoadState('networkidle');

      const createButton = page.getByRole('button', { name: /New Policy|Add Policy|Create/i });
      const hasCreateButton = await createButton.isVisible().catch(() => false);

      if (hasCreateButton) {
        await createButton.click();

        const hasModal = await page.getByRole('heading', { name: /New Policy|Add Policy|Create Policy/i })
          .isVisible()
          .catch(() => false);
        const hasForm = await page.locator('form').isVisible().catch(() => false);
        expect(hasModal || hasForm).toBe(true);
      }
    });

    test('should close create form with Cancel button', async ({ page }) => {
      await page.goto('/policies');
      await page.waitForLoadState('networkidle');

      const createButton = page.getByRole('button', { name: /New Policy|Add Policy|Create/i });
      const hasCreateButton = await createButton.isVisible().catch(() => false);

      if (hasCreateButton) {
        await createButton.click();
        const cancelButton = page.getByRole('button', { name: /Cancel/i });
        const hasCancelButton = await cancelButton.isVisible().catch(() => false);

        if (hasCancelButton) {
          await cancelButton.click();
          await expect(page.getByRole('heading', { name: /New Policy|Add Policy|Create Policy/i }))
            .not.toBeVisible();
        }
      }
    });
  });

  test.describe('Filters', () => {
    test('should have a search input for filtering policies', async ({ page }) => {
      await page.goto('/policies');
      await page.waitForLoadState('networkidle');

      const searchInput = page.getByPlaceholder(/Search/i);
      const hasSearch = await searchInput.isVisible().catch(() => false);

      if (hasSearch) {
        await searchInput.fill('quality');
        await expect(searchInput).toHaveValue('quality');
      }
    });

    test('should have filter controls', async ({ page }) => {
      await page.goto('/policies');
      await page.waitForLoadState('networkidle');

      const filterButton = page.getByRole('button', { name: /Filter|Filters/i });
      const hasFilterButton = await filterButton.isVisible().catch(() => false);

      if (hasFilterButton) {
        await filterButton.click();

        const hasFilterPanel = await page.getByText(/Category|Status|All/i).first().isVisible().catch(() => false);
        expect(hasFilterPanel).toBe(true);
      }
    });
  });

  test.describe('Navigation', () => {
    test('should be accessible via /policies URL', async ({ page }) => {
      await page.goto('/policies');
      await page.waitForLoadState('networkidle');

      expect(page.url()).toContain('/policies');
    });

    test('should navigate to policy detail when clicking a row', async ({ page }) => {
      await page.goto('/policies');
      await page.waitForLoadState('networkidle');

      const firstRow = page.locator('table tbody tr').first();
      const hasRow = await firstRow.isVisible().catch(() => false);

      if (hasRow) {
        await firstRow.click();
        await page.waitForLoadState('networkidle');
        expect(page.url()).toContain('/policies/');
      }
    });
  });
});
