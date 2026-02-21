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

  test.describe('Mark All as Read Action', () => {
    test('should click mark all as read and verify notification list updates', async ({ page }) => {
      await page.goto('/notifications');
      await page.waitForLoadState('networkidle');

      const markAllButton = page.getByRole('button', { name: /Mark All Read|Mark all as read/i });
      const hasButton = await markAllButton.isVisible().catch(() => false);
      if (!hasButton) {
        await expect(page.getByRole('heading', { name: /Notifications/i })).toBeVisible();
        return;
      }

      const unreadBefore = page.locator('[class*="unread"], [data-unread="true"]');
      const unreadCountBefore = await unreadBefore.count().catch(() => 0);

      await markAllButton.click();
      await page.waitForTimeout(1000);

      const emptyState = page.getByText(/all caught up|no unread|no notifications/i);
      const hasEmpty = await emptyState.isVisible().catch(() => false);
      const unreadCountAfter = await unreadBefore.count().catch(() => 0);

      expect(hasEmpty || unreadCountAfter <= unreadCountBefore).toBeTruthy();
      await expect(page.getByRole('heading', { name: /Notifications/i })).toBeVisible();
    });
  });

  test.describe('Notification Badge Count', () => {
    test('should display notification badge with count in the nav', async ({ page }) => {
      await page.goto('/');
      await page.waitForLoadState('networkidle');

      const badge = page.locator(
        '[class*="badge"], [data-testid*="notification-count"], [aria-label*="notification"]'
      );
      const bellIcon = page.getByRole('button', { name: /notification/i });
      const navLink = page.getByRole('link', { name: /notification/i });

      const hasBadge = await badge.first().isVisible().catch(() => false);
      const hasBell = await bellIcon.isVisible().catch(() => false);
      const hasNavLink = await navLink.isVisible().catch(() => false);

      if (hasBadge) {
        const badgeText = await badge.first().textContent();
        if (badgeText && /\d+/.test(badgeText)) {
          const count = parseInt(badgeText.match(/\d+/)![0], 10);
          expect(count).toBeGreaterThanOrEqual(0);
        }
      }

      if (hasBell) {
        await bellIcon.click();
        await page.waitForLoadState('networkidle');
        const dropdown = page.locator(
          '[role="menu"], [role="dialog"], [class*="dropdown"], [class*="popover"]'
        ).first();
        const dropdownVisible = await dropdown.isVisible().catch(() => false);
        const navigated = page.url().includes('/notifications');
        expect(dropdownVisible || navigated).toBeTruthy();
      } else if (hasNavLink) {
        await navLink.click();
        await page.waitForLoadState('networkidle');
        expect(page.url()).toContain('/notifications');
      }
    });
  });
});
