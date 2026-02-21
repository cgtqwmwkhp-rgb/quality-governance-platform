import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { mockApiEndpoints, mockDashboardData } from './helpers/api-mocks';

test.describe('Accessibility', () => {
  test('login page passes axe', async ({ page }) => {
    await page.goto('/login');
    await page.waitForLoadState('networkidle');
    const results = await new AxeBuilder({ page }).analyze();
    expect(results.violations).toEqual([]);
  });

  test('dashboard page passes axe (authenticated)', async ({ page }) => {
    await mockApiEndpoints(page);
    await mockDashboardData(page);
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    const results = await new AxeBuilder({ page })
      .exclude('.recharts-wrapper') // third-party chart library
      .analyze();
    expect(results.violations).toEqual([]);
  });
});
