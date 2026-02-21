import { test, expect } from '@playwright/test';
import { mockApiEndpoints, mockDashboardData } from './helpers/api-mocks';

test.describe('Visual Regression', () => {
  test.beforeEach(async ({ page }) => {
    await mockApiEndpoints(page);
    await mockDashboardData(page);
    await page.addInitScript(() => {
      localStorage.setItem('auth_token', 'mock-token');
    });
  });

  test('login page renders correctly', async ({ page }) => {
    await page.goto('/login');
    await page.waitForLoadState('networkidle');
    await expect(page).toHaveScreenshot('login-page.png', { fullPage: true });
  });
});
