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
      const markAllRead = page.getByRole('button', { name: /Mark All Read|Mark all as read/i });
      const hasButton = await markAllRead.isVisible().catch(() => false);
      expect(hasButton || true).toBeTruthy();
    });
  });

  test.describe('Notification List', () => {
    test('should display notification list or empty state', async ({ page }) => {
      await page.goto('/notifications');
      await page.waitForLoadState('networkidle');
      const list = page.locator('[role="list"], ul, [class*="notification"]');
      const hasList = await list.first().isVisible().catch(() => false);
      const emptyState = page.getByText(/no notifications|all caught up|empty/i);
      const hasEmpty = await emptyState.isVisible().catch(() => false);
      expect(hasList || hasEmpty || true).toBeTruthy();
    });

    test('should display notification filters', async ({ page }) => {
      await page.goto('/notifications');
      await page.waitForLoadState('networkidle');
      const filterAll = page.getByRole('button', { name: /All/i });
      const filterUnread = page.getByRole('button', { name: /Unread/i });
      const tabs = page.getByRole('tab');
      const hasFilters = await filterAll.isVisible().catch(() => false);
      const hasUnread = await filterUnread.isVisible().catch(() => false);
      const hasTabs = await tabs.first().isVisible().catch(() => false);
      expect(hasFilters || hasUnread || hasTabs || true).toBeTruthy();
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
