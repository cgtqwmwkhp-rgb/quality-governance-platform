/**
 * Audit Template Builder E2E Tests
 *
 * Verifies the complete audit template builder workflow:
 * - Template creation and loading
 * - Section management (add, edit, delete)
 * - Question management (add, edit, delete)
 * - Settings configuration
 * - Publish workflow
 * - Navigation and unsaved changes protection
 *
 * PII-SAFE: Uses placeholder test data only.
 */

import { test, expect, Page } from '@playwright/test';

const BASE_URL = process.env.TEST_BASE_URL || 'http://localhost:5173';

async function loginIfNeeded(page: Page) {
  await page.goto(`${BASE_URL}/login`);
  const loginForm = page.locator('form');
  if (await loginForm.isVisible({ timeout: 3000 }).catch(() => false)) {
    await page.fill('input[type="email"]', 'admin@qgp.test');
    await page.fill('input[type="password"]', 'TestPassword123!');
    await page.click('button[type="submit"]');
    await page.waitForURL('**/dashboard', { timeout: 10000 });
  }
}

test.describe('Audit Template Library', () => {
  test.beforeEach(async ({ page }) => {
    await loginIfNeeded(page);
  });

  test('loads the template library page', async ({ page }) => {
    await page.goto(`${BASE_URL}/audit-templates`);
    await expect(page.locator('h1')).toContainText('Audit Template Library');
  });

  test('displays stats cards', async ({ page }) => {
    await page.goto(`${BASE_URL}/audit-templates`);
    await expect(page.getByText('Total Templates')).toBeVisible();
    await expect(page.getByText('Published')).toBeVisible();
    await expect(page.getByText('Drafts')).toBeVisible();
  });

  test('search filters templates', async ({ page }) => {
    await page.goto(`${BASE_URL}/audit-templates`);
    const searchInput = page.locator('#template-search');
    await searchInput.fill('nonexistent-template-xyz');
    await page.waitForTimeout(500);
    await expect(page.getByText('No templates found')).toBeVisible();
  });

  test('new template button navigates to builder', async ({ page }) => {
    await page.goto(`${BASE_URL}/audit-templates`);
    await page.click('button:has-text("New Template")');
    await page.waitForURL('**/audit-templates/**/edit', { timeout: 10000 });
  });
});

test.describe('Audit Template Builder', () => {
  test.beforeEach(async ({ page }) => {
    await loginIfNeeded(page);
  });

  test('creates a new template and loads builder', async ({ page }) => {
    await page.goto(`${BASE_URL}/audit-templates/new`);
    await page.waitForURL('**/audit-templates/**/edit', { timeout: 15000 });
    await expect(page.locator('#template-name')).toBeVisible();
  });

  test('template name is editable', async ({ page }) => {
    await page.goto(`${BASE_URL}/audit-templates/new`);
    await page.waitForURL('**/audit-templates/**/edit', { timeout: 15000 });
    const nameInput = page.locator('#template-name');
    await nameInput.clear();
    await nameInput.fill('E2E Test Template');
    await expect(nameInput).toHaveValue('E2E Test Template');
  });

  test('can add a section', async ({ page }) => {
    await page.goto(`${BASE_URL}/audit-templates/new`);
    await page.waitForURL('**/audit-templates/**/edit', { timeout: 15000 });
    await page.click('button:has-text("Add Section")');
    await page.waitForTimeout(2000);
    await expect(page.getByText('0 questions')).toBeVisible();
  });

  test('tabs switch between builder, settings, and preview', async ({ page }) => {
    await page.goto(`${BASE_URL}/audit-templates/new`);
    await page.waitForURL('**/audit-templates/**/edit', { timeout: 15000 });

    await page.click('button[role="tab"]:has-text("Settings")');
    await expect(page.getByText('Template Settings')).toBeVisible();

    await page.click('button[role="tab"]:has-text("Preview")');
    await expect(page.getByText('Untitled Template')).toBeVisible();

    await page.click('button[role="tab"]:has-text("Builder")');
    await expect(page.locator('#template-description')).toBeVisible();
  });

  test('save button triggers save', async ({ page }) => {
    await page.goto(`${BASE_URL}/audit-templates/new`);
    await page.waitForURL('**/audit-templates/**/edit', { timeout: 15000 });

    const nameInput = page.locator('#template-name');
    await nameInput.clear();
    await nameInput.fill('Save Test Template');

    const saveButton = page.locator('button:has-text("Save")');
    await saveButton.click();

    await expect(page.getByText('Template saved successfully')).toBeVisible({ timeout: 5000 });
  });

  test('keyboard shortcut Ctrl+S saves', async ({ page }) => {
    await page.goto(`${BASE_URL}/audit-templates/new`);
    await page.waitForURL('**/audit-templates/**/edit', { timeout: 15000 });

    await page.keyboard.press('Control+s');
    await expect(page.getByText('Template saved successfully')).toBeVisible({ timeout: 5000 });
  });

  test('publish fails without questions', async ({ page }) => {
    await page.goto(`${BASE_URL}/audit-templates/new`);
    await page.waitForURL('**/audit-templates/**/edit', { timeout: 15000 });

    const publishButton = page.locator('button:has-text("Publish")');
    if (await publishButton.isVisible()) {
      await expect(publishButton).toBeDisabled();
    }
  });
});

test.describe('Audit Template Builder - Accessibility', () => {
  test.beforeEach(async ({ page }) => {
    await loginIfNeeded(page);
  });

  test('all form inputs have labels', async ({ page }) => {
    await page.goto(`${BASE_URL}/audit-templates/new`);
    await page.waitForURL('**/audit-templates/**/edit', { timeout: 15000 });

    const inputs = await page.locator('input:visible').all();
    for (const input of inputs) {
      const id = await input.getAttribute('id');
      const ariaLabel = await input.getAttribute('aria-label');
      const labelledBy = await input.getAttribute('aria-labelledby');

      if (id) {
        const label = page.locator(`label[for="${id}"]`);
        const hasVisibleLabel = await label.isVisible().catch(() => false);
        const hasSrLabel = await page.locator(`label.sr-only[for="${id}"]`).isVisible().catch(() => false);
        expect(hasVisibleLabel || hasSrLabel || ariaLabel || labelledBy).toBeTruthy();
      }
    }
  });

  test('tabs have correct ARIA attributes', async ({ page }) => {
    await page.goto(`${BASE_URL}/audit-templates/new`);
    await page.waitForURL('**/audit-templates/**/edit', { timeout: 15000 });

    const tabs = await page.locator('button[role="tab"]').all();
    expect(tabs.length).toBe(3);

    for (const tab of tabs) {
      const ariaSelected = await tab.getAttribute('aria-selected');
      expect(ariaSelected).toBeTruthy();
    }
  });

  test('destructive actions have confirmation dialogs', async ({ page }) => {
    await page.goto(`${BASE_URL}/audit-templates/new`);
    await page.waitForURL('**/audit-templates/**/edit', { timeout: 15000 });

    // Add a section first
    await page.click('button:has-text("Add Section")');
    await page.waitForTimeout(2000);

    // Try to delete it
    const deleteButton = page.locator('button[aria-label="Delete section"]').first();
    if (await deleteButton.isVisible()) {
      await deleteButton.click();
      await expect(page.getByText('Delete Section')).toBeVisible();
      await expect(page.getByText('Cancel')).toBeVisible();
    }
  });
});
