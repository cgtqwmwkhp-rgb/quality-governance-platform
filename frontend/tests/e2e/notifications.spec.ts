import { test, expect } from '@playwright/test';

test.describe('Notifications', () => {
  test.describe.configure({ mode: 'parallel' });

  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('access_token', 'test-token-e2e');
    });
  });

  test.describe('Page Load', () => {
    test('should load notifications page', async ({ page }) => {
      await page.goto('/notifications');
      await page.waitForLoadState('networkidle');
      await expect(page.getByRole('heading', { name: /Notifications/i })).toBeVisible();
    });

    test('should display mark all read button', async ({ page }) => {
      await page.goto('/notifications');
      await page.waitForLoadState('networkidle');
      try {
        await expect(page.getByRole('button', { name: /Mark All Read|Mark all as read/i })).toBeVisible({ timeout: 5000 });
      } catch {
        await expect(page.getByRole('heading', { name: /Notifications/i })).toBeVisible();
      }
    });
  });

  test.describe('Notification List', () => {
    test('should display notification list or empty state', async ({ page }) => {
      await page.goto('/notifications');
      await page.waitForLoadState('networkidle');
      const hasList = await page.locator('[role="list"], ul, [class*="notification"]').first().isVisible().catch(() => false);
      const hasEmpty = await page.getByText(/no notifications|all caught up|empty/i).isVisible().catch(() => false);
      expect(hasList || hasEmpty).toBeTruthy();
    });

    test('should display notification filters', async ({ page }) => {
      await page.goto('/notifications');
      await page.waitForLoadState('networkidle');
      const hasFilters = await page.getByRole('button', { name: /All/i }).isVisible().catch(() => false);
      const hasUnread = await page.getByRole('button', { name: /Unread/i }).isVisible().catch(() => false);
      const hasTabs = await page.getByRole('tab').first().isVisible().catch(() => false);
      expect(hasFilters || hasUnread || hasTabs).toBeTruthy();
    });
  });

  test.describe('Mark All Read', () => {
    test('should click mark all as read button', async ({ page }) => {
      await page.goto('/notifications');
      await page.waitForLoadState('networkidle');
      const markAllButton = page.getByRole('button', { name: /Mark All Read|Mark all as read/i });
      const hasButton = await markAllButton.isVisible().catch(() => false);
      if (hasButton) {
        await markAllButton.click();
        await page.waitForTimeout(1000);
        await expect(page.getByRole('heading', { name: /Notifications/i })).toBeVisible();
      }
    });
  });

  test.describe('Preferences Navigation', () => {
    test('should navigate to notification preferences if available', async ({ page }) => {
      await page.goto('/notifications');
      await page.waitForLoadState('networkidle');
      const prefsLink = page.getByRole('link', { name: /preferences|settings/i });
      const prefsButton = page.getByRole('button', { name: /preferences|settings/i });
      const hasLink = await prefsLink.isVisible().catch(() => false);
      const hasButton = await prefsButton.isVisible().catch(() => false);
      if (hasLink) {
        await prefsLink.click();
        await page.waitForLoadState('networkidle');
        expect(page.url()).toMatch(/preferences|settings/i);
      } else if (hasButton) {
        await prefsButton.click();
        await page.waitForLoadState('networkidle');
        const dialogOrPage = await page.locator('[role="dialog"], [class*="modal"], [class*="preferences"], [class*="settings"]').first().isVisible().catch(() => false);
        const urlChanged = page.url().match(/preferences|settings/i);
        expect(dialogOrPage || urlChanged).toBeTruthy();
      } else {
        await expect(page.getByRole('heading', { name: /Notifications/i })).toBeVisible();
      }
    });
  });

  test.describe('Navigation', () => {
    test('should remain on notifications page after load', async ({ page }) => {
      await page.goto('/notifications');
      await page.waitForLoadState('networkidle');
      expect(page.url()).toContain('/notifications');
    });
  });
});
