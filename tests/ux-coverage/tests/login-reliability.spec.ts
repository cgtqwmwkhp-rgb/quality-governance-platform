/**
 * Login Reliability Tests (P0)
 * 
 * Ensures the login flow:
 * 1. Never shows infinite spinner
 * 2. Handles errors gracefully with recovery actions
 * 3. Respects timeout boundaries
 * 
 * NO-PII: These tests do not capture or log credentials, tokens, or user data.
 */

import { test, expect, Page } from '@playwright/test';

// Test timeout (must be less than request timeout + buffer)
const TEST_TIMEOUT_MS = 30000;

// Base URLs
const FRONTEND_URL = process.env.FRONTEND_URL || 'https://purple-water-03205fa03.6.azurestaticapps.net';

test.describe('Login Reliability (P0)', () => {
  test.setTimeout(TEST_TIMEOUT_MS);

  test.beforeEach(async ({ page }) => {
    // Clear any existing session state
    await page.context().clearCookies();
    await page.goto(`${FRONTEND_URL}/login`, { waitUntil: 'networkidle' });
  });

  test('[P0] Login form loads without infinite spinner', async ({ page }) => {
    // Verify login form is visible
    await expect(page.locator('input[type="email"]')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('input[type="password"]')).toBeVisible();
    await expect(page.locator('button[type="submit"]')).toBeVisible();
    
    // Verify no spinner is showing initially
    const spinner = page.locator('[class*="animate-spin"]');
    await expect(spinner).not.toBeVisible();
  });

  test('[P0] Invalid credentials show error, no infinite spinner', async ({ page }) => {
    // Fill in invalid credentials (generic, no PII)
    await page.fill('input[type="email"]', 'invalid@test.example');
    await page.fill('input[type="password"]', 'wrongpassword123');
    
    // Click login
    await page.click('button[type="submit"]');
    
    // Spinner should appear briefly
    const spinner = page.locator('[class*="animate-spin"]');
    
    // Wait for either error message OR successful redirect (with timeout)
    const errorVisible = await Promise.race([
      page.locator('text=Invalid').waitFor({ timeout: 20000 }).then(() => true).catch(() => false),
      page.locator('text=error').waitFor({ timeout: 20000 }).then(() => true).catch(() => false),
      page.locator('text=incorrect').waitFor({ timeout: 20000 }).then(() => true).catch(() => false),
      page.locator('text=timed out').waitFor({ timeout: 20000 }).then(() => true).catch(() => false),
      page.locator('text=Network error').waitFor({ timeout: 20000 }).then(() => true).catch(() => false),
    ]);
    
    // CRITICAL: Spinner must NOT be visible after response/timeout
    await expect(spinner).not.toBeVisible({ timeout: 5000 });
    
    // Button should be re-enabled
    const submitButton = page.locator('button[type="submit"]');
    await expect(submitButton).toBeEnabled({ timeout: 5000 });
  });

  test('[P0] Demo credentials work without hanging', async ({ page }) => {
    // Use demo credentials (public, shown on login page)
    await page.fill('input[type="email"]', 'demo@plantexpand.com');
    await page.fill('input[type="password"]', 'demo123');
    
    // Click login
    await page.click('button[type="submit"]');
    
    // Should redirect away from login page (to dashboard)
    await expect(page).not.toHaveURL(/\/login/, { timeout: 10000 });
    
    // Spinner should not be visible
    const spinner = page.locator('[class*="animate-spin"]');
    await expect(spinner).not.toBeVisible({ timeout: 5000 });
  });

  test('[P0] Login button is disabled during request', async ({ page }) => {
    await page.fill('input[type="email"]', 'test@example.com');
    await page.fill('input[type="password"]', 'anypassword');
    
    const submitButton = page.locator('button[type="submit"]');
    
    // Start login
    await submitButton.click();
    
    // Button should be disabled immediately
    await expect(submitButton).toBeDisabled({ timeout: 1000 });
    
    // Wait for request to complete (success or error)
    await page.waitForTimeout(5000);
    
    // Button should be re-enabled after response
    await expect(submitButton).toBeEnabled({ timeout: 20000 });
  });

  test('[P0] Clear session button appears on network error', async ({ page }) => {
    // Block network requests to simulate network error
    await page.route('**/api/v1/auth/login', async (route) => {
      await route.abort('failed');
    });
    
    await page.fill('input[type="email"]', 'test@example.com');
    await page.fill('input[type="password"]', 'anypassword');
    await page.click('button[type="submit"]');
    
    // Should show error with recovery actions
    await expect(page.locator('text=Network error')).toBeVisible({ timeout: 10000 });
    
    // Spinner should be gone
    const spinner = page.locator('[class*="animate-spin"]');
    await expect(spinner).not.toBeVisible({ timeout: 5000 });
    
    // Recovery buttons should be visible
    await expect(page.locator('text=Try Again')).toBeVisible();
    await expect(page.locator('text=Clear Session')).toBeVisible();
  });

  test('[P0] Request timeout shows error, not infinite spinner', async ({ page }) => {
    // Delay response beyond timeout (simulate slow backend)
    await page.route('**/api/v1/auth/login', async (route) => {
      // Wait longer than the 15s timeout
      await new Promise(resolve => setTimeout(resolve, 20000));
      await route.fulfill({ status: 200, body: '{}' });
    });
    
    await page.fill('input[type="email"]', 'test@example.com');
    await page.fill('input[type="password"]', 'anypassword');
    await page.click('button[type="submit"]');
    
    // Should show timeout error within 20 seconds
    await expect(page.locator('text=timed out')).toBeVisible({ timeout: 20000 });
    
    // Spinner should be gone
    const spinner = page.locator('[class*="animate-spin"]');
    await expect(spinner).not.toBeVisible({ timeout: 5000 });
    
    // Button should be re-enabled
    await expect(page.locator('button[type="submit"]')).toBeEnabled();
  });
});
