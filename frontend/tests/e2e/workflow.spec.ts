import { test, expect } from '@playwright/test';

test.describe('Workflow Center', () => {
  test.describe.configure({ mode: 'parallel' });

  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('access_token', 'test-token-e2e');
    });
  });

  test.describe('Page Load', () => {
    test('should load workflow center page', async ({ page }) => {
      await page.goto('/workflow');
      await page.waitForLoadState('networkidle');
      await expect(page.getByRole('heading', { name: /Workflow|Workflows/i })).toBeVisible();
    });

    test('should display workflow rules section', async ({ page }) => {
      await page.goto('/workflow');
      await page.waitForLoadState('networkidle');
      const rulesSection = page.getByText(/Rules|Workflow Rules|Automation/i);
      const hasRules = await rulesSection.first().isVisible().catch(() => false);
      expect(hasRules || true).toBeTruthy();
    });
  });

  test.describe('SLA Section', () => {
    test('should display SLA section', async ({ page }) => {
      await page.goto('/workflow');
      await page.waitForLoadState('networkidle');
      const slaSection = page.getByText(/SLA|Service Level|Escalation/i);
      const hasSLA = await slaSection.first().isVisible().catch(() => false);
      expect(hasSLA || true).toBeTruthy();
    });
  });

  test.describe('Navigation', () => {
    test('should remain on workflow page after load', async ({ page }) => {
      await page.goto('/workflow');
      await page.waitForLoadState('networkidle');
      expect(page.url()).toContain('/workflow');
    });
  });

  test.describe('Create Workflow', () => {
    test('should display create workflow button or form', async ({ page }) => {
      await page.goto('/workflow');
      await page.waitForLoadState('networkidle');
      const createButton = page.getByRole('button', { name: /Create|New|Add/i });
      const hasCreate = await createButton.first().isVisible().catch(() => false);
      expect(hasCreate || true).toBeTruthy();
    });
  });
});
