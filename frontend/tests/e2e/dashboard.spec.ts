import { test, expect } from '@playwright/test';

test.describe('Dashboard', () => {
  test.describe.configure({ mode: 'parallel' });

  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('access_token', 'test-token-e2e');
    });
  });

  test.describe('Page Load', () => {
    test('should load the dashboard and display heading', async ({ page }) => {
      await page.goto('/dashboard');
      await page.waitForLoadState('networkidle');

      await expect(page.getByRole('heading', { name: /Dashboard/i })).toBeVisible();
      await expect(page.getByText(/Quality Governance Platform Overview/i)).toBeVisible();
    });

    test('should display Refresh button', async ({ page }) => {
      await page.goto('/dashboard');
      await page.waitForLoadState('networkidle');

      await expect(page.getByRole('button', { name: /Refresh/i })).toBeVisible();
    });

    test('should display Notifications link', async ({ page }) => {
      await page.goto('/dashboard');
      await page.waitForLoadState('networkidle');

      const notifButton = page.getByRole('link', { name: /Notifications/i });
      await expect(notifButton).toBeVisible();
    });
  });

  test.describe('Stat Cards', () => {
    test('should render primary stat cards', async ({ page }) => {
      await page.goto('/dashboard');
      await page.waitForLoadState('networkidle');

      await expect(page.getByText('Open Incidents')).toBeVisible();
      await expect(page.getByText('Open RTAs')).toBeVisible();
      await expect(page.getByText('Open Complaints')).toBeVisible();
      await expect(page.getByText('Overdue Actions')).toBeVisible();
    });

    test('should render secondary stat cards', async ({ page }) => {
      await page.goto('/dashboard');
      await page.waitForLoadState('networkidle');

      await expect(page.getByText('Audit Score (Avg)')).toBeVisible();
      await expect(page.getByText('High Risks')).toBeVisible();
    });

    test('should link stat cards to their module pages', async ({ page }) => {
      await page.goto('/dashboard');
      await page.waitForLoadState('networkidle');

      const incidentCard = page.locator('a[href="/incidents"]').first();
      await expect(incidentCard).toBeVisible();

      const auditCard = page.locator('a[href="/audits"]').first();
      await expect(auditCard).toBeVisible();

      const riskCard = page.locator('a[href="/risk-register"]').first();
      await expect(riskCard).toBeVisible();
    });
  });

  test.describe('Widgets', () => {
    test('should render IMS Compliance section', async ({ page }) => {
      await page.goto('/dashboard');
      await page.waitForLoadState('networkidle');

      await expect(page.getByText('IMS Compliance')).toBeVisible();
      await expect(page.getByText('ISO 9001:2015')).toBeVisible();
      await expect(page.getByText('ISO 14001:2015')).toBeVisible();
      await expect(page.getByText('ISO 45001:2018')).toBeVisible();
      await expect(page.getByText('ISO 27001:2022')).toBeVisible();
    });

    test('should render Recent Activity section', async ({ page }) => {
      await page.goto('/dashboard');
      await page.waitForLoadState('networkidle');

      await expect(page.getByText('Recent Activity')).toBeVisible();
    });

    test('should render Upcoming Events section', async ({ page }) => {
      await page.goto('/dashboard');
      await page.waitForLoadState('networkidle');

      await expect(page.getByText('Upcoming Events')).toBeVisible();
    });

    test('should render Recent Incidents table', async ({ page }) => {
      await page.goto('/dashboard');
      await page.waitForLoadState('networkidle');

      await expect(page.getByText('Recent Incidents')).toBeVisible();

      const table = page.locator('table');
      const hasTable = await table.isVisible().catch(() => false);

      if (hasTable) {
        await expect(page.locator('th', { hasText: /Reference/i })).toBeVisible();
        await expect(page.locator('th', { hasText: /Title/i })).toBeVisible();
        await expect(page.locator('th', { hasText: /Severity/i })).toBeVisible();
        await expect(page.locator('th', { hasText: /Status/i })).toBeVisible();
      }
    });
  });

  test.describe('Quick Actions', () => {
    test('should render quick action cards', async ({ page }) => {
      await page.goto('/dashboard');
      await page.waitForLoadState('networkidle');

      await expect(page.getByText('New Incident')).toBeVisible();
      await expect(page.getByText('Start Audit')).toBeVisible();
      await expect(page.getByText('View Analytics')).toBeVisible();
      await expect(page.getByText('Compliance')).toBeVisible();
    });

    test('should navigate to incidents from quick action', async ({ page }) => {
      await page.goto('/dashboard');
      await page.waitForLoadState('networkidle');

      const incidentLink = page.locator('a[href="/incidents"]', { hasText: /New Incident/i });
      await expect(incidentLink).toBeVisible();
      await incidentLink.click();
      await page.waitForLoadState('networkidle');

      expect(page.url()).toContain('/incidents');
    });

    test('should navigate to audits from quick action', async ({ page }) => {
      await page.goto('/dashboard');
      await page.waitForLoadState('networkidle');

      const auditLink = page.locator('a[href="/audits"]', { hasText: /Start Audit/i });
      await expect(auditLink).toBeVisible();
      await auditLink.click();
      await page.waitForLoadState('networkidle');

      expect(page.url()).toContain('/audits');
    });
  });

  test.describe('Navigation', () => {
    test('should navigate to notifications page', async ({ page }) => {
      await page.goto('/dashboard');
      await page.waitForLoadState('networkidle');

      const notifLink = page.getByRole('link', { name: /Notifications/i });
      await notifLink.click();
      await page.waitForLoadState('networkidle');

      expect(page.url()).toContain('/notifications');
    });

    test('should navigate to analytics via View Analytics quick action', async ({ page }) => {
      await page.goto('/dashboard');
      await page.waitForLoadState('networkidle');

      const analyticsLink = page.locator('a[href="/analytics"]', { hasText: /View Analytics/i });
      await expect(analyticsLink).toBeVisible();
      await analyticsLink.click();
      await page.waitForLoadState('networkidle');

      expect(page.url()).toContain('/analytics');
    });
  });
});
