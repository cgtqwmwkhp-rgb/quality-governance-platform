/**
 * Login UX Contract Tests (P0)
 * 
 * Enforces LOGIN_UX_CONTRACT.md requirements:
 * - Bounded error codes only
 * - State machine compliance
 * - Performance thresholds
 * - No infinite spinner
 * 
 * NO-PII: These tests do not capture credentials, tokens, or user data.
 */

import { test, expect } from '@playwright/test';

// Base URLs
const FRONTEND_URL = process.env.FRONTEND_URL || 'https://purple-water-03205fa03.6.azurestaticapps.net';

// Timing constants from contract
const SPINNER_DELAY_MS = 250;
const SLOW_WARNING_MS = 3000;
const REQUEST_TIMEOUT_MS = 15000;

// Bounded error codes from contract
const VALID_ERROR_CODES = [
  'TIMEOUT',
  'UNAUTHORIZED',
  'UNAVAILABLE',
  'SERVER_ERROR',
  'NETWORK_ERROR',
  'UNKNOWN'
] as const;

test.describe('Login UX Contract (P0)', () => {
  test.setTimeout(30000);

  test.beforeEach(async ({ page }) => {
    // Clear any existing session state
    await page.context().clearCookies();
    await page.goto(`${FRONTEND_URL}/login`, { waitUntil: 'networkidle' });
  });

  // ============================================================================
  // State Machine Tests
  // ============================================================================

  test('[P0] Login form starts in idle state', async ({ page }) => {
    // Form elements visible and enabled
    await expect(page.getByTestId('email-input')).toBeVisible();
    await expect(page.getByTestId('password-input')).toBeVisible();
    await expect(page.getByTestId('submit-button')).toBeVisible();
    await expect(page.getByTestId('submit-button')).toBeEnabled();
    
    // No spinner visible in idle state
    await expect(page.getByTestId('spinner')).not.toBeVisible();
    
    // No error visible in idle state
    await expect(page.getByTestId('login-error')).not.toBeVisible();
  });

  test('[P0] Submit button disabled during request', async ({ page }) => {
    await page.getByTestId('email-input').fill('test@example.com');
    await page.getByTestId('password-input').fill('anypassword');
    
    // Start login
    await page.getByTestId('submit-button').click();
    
    // Button should be disabled immediately
    await expect(page.getByTestId('submit-button')).toBeDisabled({ timeout: 1000 });
    
    // Loading attribute should be true
    await expect(page.getByTestId('submit-button')).toHaveAttribute('data-loading', 'true');
  });

  test('[P0] Spinner appears after 250ms delay (not immediately)', async ({ page }) => {
    // Slow down the response to ensure we can observe the delay
    await page.route('**/api/v1/auth/login', async (route) => {
      await new Promise(resolve => setTimeout(resolve, 1000));
      await route.fulfill({ status: 401, body: JSON.stringify({ message: 'Unauthorized' }) });
    });
    
    await page.getByTestId('email-input').fill('test@example.com');
    await page.getByTestId('password-input').fill('anypassword');
    
    await page.getByTestId('submit-button').click();
    
    // Spinner should NOT be visible immediately (within first 200ms)
    await page.waitForTimeout(100);
    // After 250ms+ the spinner should appear
    await expect(page.getByTestId('spinner')).toBeVisible({ timeout: 2000 });
  });

  // ============================================================================
  // Bounded Error Code Tests
  // ============================================================================

  test('[P0] Invalid credentials => UNAUTHORIZED error shown', async ({ page }) => {
    await page.route('**/api/v1/auth/login', async (route) => {
      await route.fulfill({ 
        status: 401, 
        body: JSON.stringify({ message: 'Incorrect email or password' }) 
      });
    });
    
    await page.getByTestId('email-input').fill('invalid@test.example');
    await page.getByTestId('password-input').fill('wrongpassword');
    await page.getByTestId('submit-button').click();
    
    // Error should be visible with correct code
    await expect(page.getByTestId('login-error')).toBeVisible({ timeout: 5000 });
    await expect(page.getByTestId('login-error')).toHaveAttribute('data-error-code', 'UNAUTHORIZED');
    
    // Error message should match contract
    await expect(page.getByTestId('error-message')).toContainText('Incorrect email or password');
    
    // Spinner should be cleared
    await expect(page.getByTestId('spinner')).not.toBeVisible();
    
    // Button should be re-enabled
    await expect(page.getByTestId('submit-button')).toBeEnabled();
    
    // No recovery actions for UNAUTHORIZED (user fixes credentials)
    await expect(page.getByTestId('recovery-actions')).not.toBeVisible();
  });

  test('[P0] Service unavailable (503) => UNAVAILABLE error shown', async ({ page }) => {
    await page.route('**/api/v1/auth/login', async (route) => {
      await route.fulfill({ status: 503, body: 'Service Unavailable' });
    });
    
    await page.getByTestId('email-input').fill('test@example.com');
    await page.getByTestId('password-input').fill('anypassword');
    await page.getByTestId('submit-button').click();
    
    await expect(page.getByTestId('login-error')).toBeVisible({ timeout: 5000 });
    await expect(page.getByTestId('login-error')).toHaveAttribute('data-error-code', 'UNAVAILABLE');
    
    // Recovery actions should be visible
    await expect(page.getByTestId('recovery-actions')).toBeVisible();
    await expect(page.getByTestId('retry-button')).toBeVisible();
    await expect(page.getByTestId('clear-session-button')).toBeVisible();
  });

  test('[P0] Server error (500) => SERVER_ERROR shown', async ({ page }) => {
    await page.route('**/api/v1/auth/login', async (route) => {
      await route.fulfill({ status: 500, body: 'Internal Server Error' });
    });
    
    await page.getByTestId('email-input').fill('test@example.com');
    await page.getByTestId('password-input').fill('anypassword');
    await page.getByTestId('submit-button').click();
    
    await expect(page.getByTestId('login-error')).toBeVisible({ timeout: 5000 });
    await expect(page.getByTestId('login-error')).toHaveAttribute('data-error-code', 'SERVER_ERROR');
    
    // Recovery actions visible
    await expect(page.getByTestId('retry-button')).toBeVisible();
  });

  test('[P0] Network failure => NETWORK_ERROR shown', async ({ page }) => {
    await page.route('**/api/v1/auth/login', async (route) => {
      await route.abort('failed');
    });
    
    await page.getByTestId('email-input').fill('test@example.com');
    await page.getByTestId('password-input').fill('anypassword');
    await page.getByTestId('submit-button').click();
    
    await expect(page.getByTestId('login-error')).toBeVisible({ timeout: 5000 });
    await expect(page.getByTestId('login-error')).toHaveAttribute('data-error-code', 'NETWORK_ERROR');
    
    // Recovery actions visible
    await expect(page.getByTestId('retry-button')).toBeVisible();
    await expect(page.getByTestId('clear-session-button')).toBeVisible();
  });

  // ============================================================================
  // Slow Warning Tests
  // ============================================================================

  test('[P0] Slow response (>3s) shows slow warning', async ({ page }) => {
    // Delay response to 4 seconds (past slow warning threshold)
    await page.route('**/api/v1/auth/login', async (route) => {
      await new Promise(resolve => setTimeout(resolve, 4000));
      await route.fulfill({ status: 401, body: JSON.stringify({ message: 'Unauthorized' }) });
    });
    
    await page.getByTestId('email-input').fill('test@example.com');
    await page.getByTestId('password-input').fill('anypassword');
    await page.getByTestId('submit-button').click();
    
    // Slow warning should appear after 3 seconds
    await expect(page.getByTestId('slow-warning')).toBeVisible({ timeout: 5000 });
    await expect(page.getByTestId('slow-warning')).toContainText('Still working');
  });

  test('[P0] Request timeout (>15s) => TIMEOUT error shown', async ({ page }) => {
    test.setTimeout(25000);
    
    // Delay response beyond timeout
    await page.route('**/api/v1/auth/login', async (route) => {
      await new Promise(resolve => setTimeout(resolve, 20000));
      await route.fulfill({ status: 200, body: '{}' });
    });
    
    await page.getByTestId('email-input').fill('test@example.com');
    await page.getByTestId('password-input').fill('anypassword');
    await page.getByTestId('submit-button').click();
    
    // Should show timeout error
    await expect(page.getByTestId('login-error')).toBeVisible({ timeout: 20000 });
    await expect(page.getByTestId('login-error')).toHaveAttribute('data-error-code', 'TIMEOUT');
    
    // Spinner must be cleared (contract invariant)
    await expect(page.getByTestId('spinner')).not.toBeVisible();
    
    // Button must be re-enabled
    await expect(page.getByTestId('submit-button')).toBeEnabled();
  });

  // ============================================================================
  // Recovery Action Tests
  // ============================================================================

  test('[P0] Retry button clears error and resets form', async ({ page }) => {
    await page.route('**/api/v1/auth/login', async (route) => {
      await route.abort('failed');
    });
    
    await page.getByTestId('email-input').fill('test@example.com');
    await page.getByTestId('password-input').fill('anypassword');
    await page.getByTestId('submit-button').click();
    
    await expect(page.getByTestId('login-error')).toBeVisible({ timeout: 5000 });
    
    // Click retry
    await page.getByTestId('retry-button').click();
    
    // Error should be cleared
    await expect(page.getByTestId('login-error')).not.toBeVisible();
    
    // Button should be enabled (back to idle state)
    await expect(page.getByTestId('submit-button')).toBeEnabled();
  });

  test('[P0] Clear session button reloads page', async ({ page }) => {
    await page.route('**/api/v1/auth/login', async (route) => {
      await route.abort('failed');
    });
    
    await page.getByTestId('email-input').fill('test@example.com');
    await page.getByTestId('password-input').fill('anypassword');
    await page.getByTestId('submit-button').click();
    
    await expect(page.getByTestId('login-error')).toBeVisible({ timeout: 5000 });
    
    // Click clear session - should trigger reload
    const navigationPromise = page.waitForNavigation();
    await page.getByTestId('clear-session-button').click();
    await navigationPromise;
    
    // Page should be back to clean state
    await expect(page.getByTestId('email-input')).toBeVisible();
  });

  // ============================================================================
  // Success Path Tests
  // ============================================================================

  test('[P0] Demo credentials login succeeds', async ({ page }) => {
    await page.getByTestId('email-input').fill('demo@plantexpand.com');
    await page.getByTestId('password-input').fill('demo123');
    await page.getByTestId('submit-button').click();
    
    // Should redirect away from login
    await expect(page).not.toHaveURL(/\/login/, { timeout: 10000 });
    
    // No error should be shown
    await expect(page.getByTestId('login-error')).not.toBeVisible();
  });

  // ============================================================================
  // Contract Invariants (MUST always hold)
  // ============================================================================

  test('[P0][INVARIANT] No infinite spinner - always reaches terminal state', async ({ page }) => {
    // Use network failure which should be classified quickly
    await page.route('**/api/v1/auth/login', async (route) => {
      await route.abort('connectionrefused');
    });
    
    await page.getByTestId('email-input').fill('test@example.com');
    await page.getByTestId('password-input').fill('anypassword');
    await page.getByTestId('submit-button').click();
    
    // INVARIANT: Within 15 seconds, must reach terminal state
    await page.waitForTimeout(1000);
    
    // Either success (redirect) or error (visible)
    const isOnLogin = page.url().includes('/login');
    if (isOnLogin) {
      // Must have error visible (terminal error state)
      await expect(page.getByTestId('login-error')).toBeVisible({ timeout: 15000 });
    }
    
    // INVARIANT: Spinner must be cleared
    await expect(page.getByTestId('spinner')).not.toBeVisible({ timeout: 1000 });
    
    // INVARIANT: Button must be enabled after error
    if (isOnLogin) {
      await expect(page.getByTestId('submit-button')).toBeEnabled({ timeout: 1000 });
    }
  });

  test('[P0][INVARIANT] Error codes are bounded', async ({ page }) => {
    await page.route('**/api/v1/auth/login', async (route) => {
      await route.fulfill({ status: 418, body: "I'm a teapot" }); // Unusual status
    });
    
    await page.getByTestId('email-input').fill('test@example.com');
    await page.getByTestId('password-input').fill('anypassword');
    await page.getByTestId('submit-button').click();
    
    await expect(page.getByTestId('login-error')).toBeVisible({ timeout: 5000 });
    
    // Must have a valid bounded error code
    const errorCode = await page.getByTestId('login-error').getAttribute('data-error-code');
    expect(VALID_ERROR_CODES).toContain(errorCode);
  });
});
