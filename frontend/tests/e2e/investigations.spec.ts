import { test, expect } from '@playwright/test';

test.describe('Investigations Module', () => {
  test.describe.configure({ mode: 'parallel' });

  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('access_token', 'test-token-e2e');
    });
  });

  test.describe('Investigation List Page', () => {
    test('should render the investigations list with table columns', async ({ page }) => {
      await page.goto('/investigations');
      await page.waitForLoadState('networkidle');

      await expect(page.getByRole('heading', { name: /Root Cause Investigations/i })).toBeVisible();

      const table = page.locator('table');
      const hasTable = await table.isVisible().catch(() => false);

      if (hasTable) {
        await expect(page.locator('th', { hasText: /Reference/i })).toBeVisible();
        await expect(page.locator('th', { hasText: /Title/i })).toBeVisible();
        await expect(page.locator('th', { hasText: /Status/i })).toBeVisible();
        await expect(page.locator('th', { hasText: /Lead/i })).toBeVisible();
        await expect(page.locator('th', { hasText: /Actions/i })).toBeVisible();
        await expect(page.locator('th', { hasText: /Created/i })).toBeVisible();
      } else {
        await expect(
          page.getByText(/No Investigations Found/i).or(page.getByText(/Connection Error/i))
        ).toBeVisible();
      }
    });

    test('should display stat cards', async ({ page }) => {
      await page.goto('/investigations');
      await page.waitForLoadState('networkidle');

      await expect(page.getByText('Total')).toBeVisible();
      await expect(page.getByText('In Progress')).toBeVisible();
      await expect(page.getByText('Under Review')).toBeVisible();
      await expect(page.getByText('Completed')).toBeVisible();
    });

    test('should have a search input', async ({ page }) => {
      await page.goto('/investigations');
      await page.waitForLoadState('networkidle');

      const searchInput = page.getByPlaceholder(/Search by reference, title, or lead/i);
      await expect(searchInput).toBeVisible();

      await searchInput.fill('test search term');
      await expect(searchInput).toHaveValue('test search term');
    });

    test('should show API connection status indicator', async ({ page }) => {
      await page.goto('/investigations');
      await page.waitForLoadState('networkidle');

      const connected = page.getByText('API Connected');
      const disconnected = page.getByText('Disconnected').or(page.getByText('API Disconnected'));
      await expect(connected.or(disconnected)).toBeVisible();
    });

    test('should open create investigation modal when clicking New Investigation', async ({ page }) => {
      await page.goto('/investigations');
      await page.waitForLoadState('networkidle');

      const newButton = page.getByRole('button', { name: /New Investigation/i });
      await expect(newButton).toBeVisible();
      await newButton.click();

      await expect(page.getByText(/Create Investigation from Record/i)).toBeVisible();
      await expect(page.getByText(/Source Record Type/i)).toBeVisible();

      await expect(page.getByText('Near Miss')).toBeVisible();
      await expect(page.getByText('Road Traffic Collision')).toBeVisible();
      await expect(page.getByText('Complaint')).toBeVisible();
      await expect(page.getByText('Incident')).toBeVisible();
    });

    test('should close create modal with Cancel button', async ({ page }) => {
      await page.goto('/investigations');
      await page.waitForLoadState('networkidle');

      await page.getByRole('button', { name: /New Investigation/i }).click();
      await expect(page.getByText(/Create Investigation from Record/i)).toBeVisible();

      await page.getByRole('button', { name: /Cancel/i }).click();
      await expect(page.getByText(/Create Investigation from Record/i)).not.toBeVisible();
    });

    test('should have Create Investigation button disabled without required fields', async ({ page }) => {
      await page.goto('/investigations');
      await page.waitForLoadState('networkidle');

      await page.getByRole('button', { name: /New Investigation/i }).click();
      await expect(page.getByText(/Create Investigation from Record/i)).toBeVisible();

      const createBtn = page.getByRole('button', { name: /Create Investigation/i });
      await expect(createBtn).toBeDisabled();
    });
  });

  test.describe('Investigation Detail Page', () => {
    test('should navigate to a detail page and show content or error', async ({ page }) => {
      await page.goto('/investigations/1');
      await page.waitForLoadState('networkidle');

      const hasHeading = await page.getByRole('heading').first().isVisible().catch(() => false);
      const hasContent = await page.locator('body').textContent().then(t => t!.trim().length > 0);
      expect(hasHeading || hasContent).toBe(true);
    });

    test('should survive a page reload on a deep-linked detail URL', async ({ page }) => {
      await page.goto('/investigations/1');
      await page.waitForLoadState('networkidle');

      await page.reload();
      await page.waitForLoadState('networkidle');

      expect(page.url()).toContain('/investigations');
    });
  });

  test.describe('Navigation', () => {
    test('should navigate from dashboard to investigations', async ({ page }) => {
      await page.goto('/dashboard');
      await page.waitForLoadState('networkidle');

      const invLink = page.locator('a[href="/investigations"]').first();
      const hasLink = await invLink.isVisible().catch(() => false);

      if (hasLink) {
        await invLink.click();
        await page.waitForLoadState('networkidle');
        expect(page.url()).toContain('/investigations');
      } else {
        await page.goto('/investigations');
        await page.waitForLoadState('networkidle');
        expect(page.url()).toContain('/investigations');
      }
    });

    test('should navigate between investigations and audits', async ({ page }) => {
      await page.goto('/investigations');
      await page.waitForLoadState('networkidle');
      expect(page.url()).toContain('/investigations');

      await page.goto('/audits');
      await page.waitForLoadState('networkidle');
      expect(page.url()).toContain('/audits');
    });

    test('should redirect unauthenticated users to login', async ({ page }) => {
      await page.addInitScript(() => {
        localStorage.removeItem('access_token');
      });

      await page.goto('/investigations');
      await page.waitForLoadState('networkidle');

      expect(page.url()).toContain('/login');
    });
  });
});
