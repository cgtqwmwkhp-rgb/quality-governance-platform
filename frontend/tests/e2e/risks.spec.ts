import { test, expect } from '@playwright/test';

test.describe('Enterprise Risk Register', () => {
  test.describe.configure({ mode: 'parallel' });

  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('access_token', 'test-token-e2e');
    });
  });

  test.describe('Risk Register Page', () => {
    test('should render the risk register heading', async ({ page }) => {
      await page.goto('/risk-register');
      await page.waitForLoadState('networkidle');

      await expect(page.getByRole('heading', { name: /Enterprise Risk Register/i })).toBeVisible();
      await expect(page.getByText(/ISO 31000 Compliant Risk Management/i)).toBeVisible();
    });

    test('should display summary stat cards', async ({ page }) => {
      await page.goto('/risk-register');
      await page.waitForLoadState('networkidle');

      await expect(page.getByText('Total Risks')).toBeVisible();
      await expect(page.getByText('Critical')).toBeVisible();
      await expect(page.getByText('High')).toBeVisible();
      await expect(page.getByText('Medium')).toBeVisible();
      await expect(page.getByText('Outside Appetite')).toBeVisible();
      await expect(page.getByText('Overdue Review')).toBeVisible();
    });

    test('should display view toggle buttons', async ({ page }) => {
      await page.goto('/risk-register');
      await page.waitForLoadState('networkidle');

      await expect(page.getByRole('button', { name: /Risk Register/i })).toBeVisible();
      await expect(page.getByRole('button', { name: /Heat Map/i })).toBeVisible();
      await expect(page.getByRole('button', { name: /Bow-Tie Analysis/i })).toBeVisible();
    });

    test('should render risk table or empty state', async ({ page }) => {
      await page.goto('/risk-register');
      await page.waitForLoadState('networkidle');

      const table = page.locator('table');
      const hasTable = await table.isVisible().catch(() => false);

      if (hasTable) {
        await expect(page.locator('th', { hasText: /Reference/i })).toBeVisible();
        await expect(page.locator('th', { hasText: /Risk Title/i })).toBeVisible();
        await expect(page.locator('th', { hasText: /Category/i })).toBeVisible();
        await expect(page.locator('th', { hasText: /Inherent/i })).toBeVisible();
        await expect(page.locator('th', { hasText: /Residual/i })).toBeVisible();
        await expect(page.locator('th', { hasText: /Level/i })).toBeVisible();
        await expect(page.locator('th', { hasText: /Treatment/i })).toBeVisible();
        await expect(page.locator('th', { hasText: /Owner/i })).toBeVisible();
      } else {
        await expect(page.getByText(/No risks registered/i)).toBeVisible();
      }
    });

    test('should show action buttons (Filters, Export, Add Risk)', async ({ page }) => {
      await page.goto('/risk-register');
      await page.waitForLoadState('networkidle');

      await expect(page.getByRole('button', { name: /Filters/i })).toBeVisible();
      await expect(page.getByRole('button', { name: /Export/i })).toBeVisible();
      await expect(page.getByRole('button', { name: /Add Risk/i })).toBeVisible();
    });
  });

  test.describe('Create Risk Flow', () => {
    test('should open create risk modal', async ({ page }) => {
      await page.goto('/risk-register');
      await page.waitForLoadState('networkidle');

      await page.getByRole('button', { name: /Add Risk/i }).click();

      await expect(page.getByRole('heading', { name: /Add New Risk/i })).toBeVisible();
    });

    test('should render all form fields in the create modal', async ({ page }) => {
      await page.goto('/risk-register');
      await page.waitForLoadState('networkidle');

      await page.getByRole('button', { name: /Add Risk/i }).click();

      await expect(page.getByText('Title *')).toBeVisible();
      await expect(page.getByText('Description *')).toBeVisible();
      await expect(page.getByText('Category')).toBeVisible();
      await expect(page.getByText('Department')).toBeVisible();
      await expect(page.getByText('Risk Owner')).toBeVisible();
      await expect(page.getByText('Inherent Risk (before controls)')).toBeVisible();
      await expect(page.getByText('Residual Risk (after controls)')).toBeVisible();
      await expect(page.getByText('Treatment Strategy')).toBeVisible();
      await expect(page.getByText('Treatment Plan')).toBeVisible();
    });

    test('should fill in the risk form fields', async ({ page }) => {
      await page.goto('/risk-register');
      await page.waitForLoadState('networkidle');

      await page.getByRole('button', { name: /Add Risk/i }).click();

      const titleInput = page.locator('input[placeholder*="Risk title"]');
      await titleInput.fill('Server room fire risk assessment');
      await expect(titleInput).toHaveValue('Server room fire risk assessment');

      const descriptionInput = page.locator('textarea[placeholder*="Detailed risk description"]');
      await descriptionInput.fill('Risk of fire in the main server room due to electrical faults');
      await expect(descriptionInput).toHaveValue('Risk of fire in the main server room due to electrical faults');

      const ownerInput = page.locator('input[placeholder*="Person responsible"]');
      await ownerInput.fill('John Smith');
      await expect(ownerInput).toHaveValue('John Smith');
    });

    test('should close create modal with Cancel button', async ({ page }) => {
      await page.goto('/risk-register');
      await page.waitForLoadState('networkidle');

      await page.getByRole('button', { name: /Add Risk/i }).click();
      await expect(page.getByRole('heading', { name: /Add New Risk/i })).toBeVisible();

      await page.getByRole('button', { name: /Cancel/i }).click();
      await expect(page.getByRole('heading', { name: /Add New Risk/i })).not.toBeVisible();
    });
  });

  test.describe('Filters', () => {
    test('should toggle filter panel', async ({ page }) => {
      await page.goto('/risk-register');
      await page.waitForLoadState('networkidle');

      await page.getByRole('button', { name: /Filters/i }).click();

      await expect(page.getByText('All Categories')).toBeVisible();
      await expect(page.getByText('All Statuses')).toBeVisible();
      await expect(page.getByRole('button', { name: /Clear Filters/i })).toBeVisible();
    });
  });

  test.describe('View Switching', () => {
    test('should switch to heat map view', async ({ page }) => {
      await page.goto('/risk-register');
      await page.waitForLoadState('networkidle');

      await page.getByRole('button', { name: /Heat Map/i }).click();

      const hasHeatMap = await page.getByText(/5x5 Risk Heat Map/i).isVisible().catch(() => false);
      const hasNoData = await page.getByText(/No heat map data available/i).isVisible().catch(() => false);

      expect(hasHeatMap || hasNoData).toBe(true);
    });

    test('should switch to bow-tie analysis view', async ({ page }) => {
      await page.goto('/risk-register');
      await page.waitForLoadState('networkidle');

      await page.getByRole('button', { name: /Bow-Tie Analysis/i }).click();

      await expect(page.getByText(/Bow-Tie Analysis/i)).toBeVisible();
    });

    test('should return to register view', async ({ page }) => {
      await page.goto('/risk-register');
      await page.waitForLoadState('networkidle');

      await page.getByRole('button', { name: /Heat Map/i }).click();
      await page.getByRole('button', { name: /Risk Register/i }).click();

      const table = page.locator('table');
      const hasTable = await table.isVisible().catch(() => false);
      const hasEmpty = await page.getByText(/No risks registered/i).isVisible().catch(() => false);

      expect(hasTable || hasEmpty).toBe(true);
    });
  });

  test.describe('Navigation', () => {
    test('should be accessible via /risk-register URL', async ({ page }) => {
      await page.goto('/risk-register');
      await page.waitForLoadState('networkidle');

      expect(page.url()).toContain('/risk-register');
      await expect(page.getByRole('heading', { name: /Enterprise Risk Register/i })).toBeVisible();
    });

    test('should redirect /risks to /risk-register', async ({ page }) => {
      await page.goto('/risks');
      await page.waitForLoadState('networkidle');

      expect(page.url()).toContain('/risk-register');
    });
  });
});
