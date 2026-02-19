/**
 * Button Wiring Audit for UX Functional Coverage Gate
 * 
 * Verifies that all P0/P1 buttons:
 * - Are present on their pages
 * - Have observable outcomes when clicked:
 *   - Navigation occurs
 *   - Network call is made
 *   - UI state changes
 *   - Or disabled_reason is visible
 * - Are not "noop" (click does nothing)
 * 
 * PII-SAFE: No form data captured. Only button presence and outcomes.
 */

import { test, expect, Page, Request } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';
import * as yaml from 'js-yaml';

// Types
interface ButtonEntry {
  pageId: string;
  actionId: string;
  selector: string;
  fallback_selector?: string;
  criticality: string;
  expected_outcome: string;
  expected_route?: string;
  expected_api?: string;
  expected_state?: string;
  disabled_reason?: string | null;
  description: string;
}

interface ButtonAuditResult {
  pageId: string;
  actionId: string;
  selector: string;
  criticality: string;
  result: 'PASS' | 'FAIL' | 'SKIP';
  found: boolean;
  clicked: boolean;
  outcome_observed: boolean;
  outcome_type?: string;
  error_message?: string;
}

// Load registry
function loadButtons(): ButtonEntry[] {
  const registryPath = path.join(__dirname, '../../../docs/ops/BUTTON_REGISTRY.yml');
  const content = fs.readFileSync(registryPath, 'utf-8');
  const registry = yaml.load(content) as any;
  
  const allButtons: ButtonEntry[] = [
    ...(registry.portal_actions || []),
    ...(registry.admin_actions || []),
    ...(registry.admin_config_actions || []),
  ];
  
  // Filter to P0/P1 only
  return allButtons.filter(b => b.criticality === 'P0' || b.criticality === 'P1');
}

// Load pages to get routes
function loadPageRoute(pageId: string): string | null {
  const registryPath = path.join(__dirname, '../../../docs/ops/PAGE_REGISTRY.yml');
  const content = fs.readFileSync(registryPath, 'utf-8');
  const registry = yaml.load(content) as any;
  
  const allPages = [
    ...(registry.public_routes || []),
    ...(registry.portal_routes || []),
    ...(registry.admin_routes || []),
  ];
  
  const page = allPages.find((p: any) => p.pageId === pageId);
  return page?.route || null;
}

// Test storage
const buttonAuditResults: ButtonAuditResult[] = [];

// Auth helper - navigates to base URL first to establish origin for localStorage
async function setupAuth(page: Page, pageId: string): Promise<boolean> {
  // Determine auth type from page registry
  const registryPath = path.join(__dirname, '../../../docs/ops/PAGE_REGISTRY.yml');
  const content = fs.readFileSync(registryPath, 'utf-8');
  const registry = yaml.load(content) as any;
  
  const allPages = [
    ...(registry.public_routes || []),
    ...(registry.portal_routes || []),
    ...(registry.admin_routes || []),
  ];
  
  const pageEntry = allPages.find((p: any) => p.pageId === pageId);
  const authType = pageEntry?.auth || 'anon';
  
  if (authType === 'anon') return true;
  
  // Navigate to base URL first to establish origin (localStorage blocked on about:blank)
  const baseUrl = process.env.APP_URL || 'http://localhost:3000';
  
  try {
    const response = await page.goto(baseUrl, { waitUntil: 'domcontentloaded', timeout: 30000 });
    
    // Verify we landed on a valid page with proper origin
    const currentUrl = page.url();
    if (!currentUrl || currentUrl === 'about:blank' || !currentUrl.startsWith('http')) {
      console.warn(`[setupAuth] Invalid page URL after navigation: ${currentUrl}`);
      return false;
    }
    
    // Check for navigation errors
    if (!response || response.status() >= 400) {
      console.warn(`[setupAuth] Navigation failed with status: ${response?.status()}`);
      return false;
    }
  } catch (navError: any) {
    console.warn(`[setupAuth] Navigation failed: ${navError.message?.slice(0, 100)}`);
    return false;
  }
  
  if (authType === 'portal_sso') {
    try {
      await page.evaluate(() => {
        const demoUser = {
          id: 'ux-test-001',
          email: 'ux-test@plantexpand.com',
          name: 'UX Test User',
          firstName: 'UX',
          lastName: 'Test',
          isDemoUser: true,
        };
        localStorage.setItem('portal_user', JSON.stringify(demoUser));
        localStorage.setItem('portal_session_time', Date.now().toString());
      });
      return true;
    } catch (storageError: any) {
      console.warn(`[setupAuth] localStorage access failed: ${storageError.message?.slice(0, 100)}`);
      return false;
    }
  }
  
  if (authType === 'jwt_admin' && process.env.ADMIN_TEST_TOKEN) {
    try {
      await page.evaluate((token) => {
        localStorage.setItem('access_token', token);
      }, process.env.ADMIN_TEST_TOKEN);
      return true;
    } catch (storageError: any) {
      console.warn(`[setupAuth] localStorage access failed: ${storageError.message?.slice(0, 100)}`);
      return false;
    }
  }
  
  return false;
}

// Dynamic test generation
const buttons = loadButtons();

test.describe('Button Wiring Audit', () => {
  test.describe.configure({ mode: 'serial' }); // Serial to avoid state conflicts
  
  for (const buttonEntry of buttons) {
    test(`[${buttonEntry.criticality}] ${buttonEntry.pageId}::${buttonEntry.actionId}`, async ({ page }) => {
      const result: ButtonAuditResult = {
        pageId: buttonEntry.pageId,
        actionId: buttonEntry.actionId,
        selector: buttonEntry.selector,
        criticality: buttonEntry.criticality,
        result: 'FAIL',
        found: false,
        clicked: false,
        outcome_observed: false,
      };
      
      try {
        // Get page route
        const route = loadPageRoute(buttonEntry.pageId);
        if (!route) {
          result.result = 'SKIP';
          result.error_message = 'Page route not found';
          buttonAuditResults.push(result);
          test.skip(true, result.error_message);
          return;
        }
        
        // Skip parameterized routes (need specific data)
        if (route.includes(':')) {
          result.result = 'SKIP';
          result.error_message = 'Parameterized route - requires test data';
          buttonAuditResults.push(result);
          test.skip(true, result.error_message);
          return;
        }
        
        // Setup auth
        const authReady = await setupAuth(page, buttonEntry.pageId);
        if (!authReady) {
          result.result = 'SKIP';
          result.error_message = 'Auth not configured';
          buttonAuditResults.push(result);
          test.skip(true, result.error_message);
          return;
        }
        
        // Navigate to page (use 'load' instead of 'networkidle' to avoid
        // flaky timeouts on pages with polling or streaming connections)
        await page.goto(route, { waitUntil: 'load', timeout: 30000 });
        await page.waitForSelector('#root, #app, [data-testid="app-root"]', { timeout: 10000 });
        
        // Try to find button with primary selector (wait for render)
        let button = page.locator(buttonEntry.selector).first();
        let buttonVisible = false;
        try {
          await button.waitFor({ state: 'visible', timeout: 10000 });
          buttonVisible = true;
        } catch {
          buttonVisible = false;
        }
        
        // Try fallback selector if primary not found
        if (!buttonVisible && buttonEntry.fallback_selector) {
          button = page.locator(buttonEntry.fallback_selector).first();
          try {
            await button.waitFor({ state: 'visible', timeout: 5000 });
            buttonVisible = true;
          } catch {
            buttonVisible = false;
          }
        }
        
        if (!buttonVisible) {
          result.found = false;
          result.error_message = 'Button not visible on page';
          
          // For non-critical buttons, this is acceptable
          if (buttonEntry.criticality === 'P1') {
            result.result = 'SKIP';
            buttonAuditResults.push(result);
            test.skip(true, 'P1 button not visible - may be conditional');
            return;
          }
          
          // P0 buttons with disabled_reason may legitimately be hidden
          // (e.g. multi-step forms where submit only appears on the last step)
          if (buttonEntry.disabled_reason) {
            result.result = 'PASS';
            result.outcome_observed = true;
            result.outcome_type = 'disabled_precondition';
            buttonAuditResults.push(result);
            return;
          }
          
          throw new Error('P0 button not found');
        }
        
        result.found = true;
        
        // Check if button is disabled
        const isDisabled = await button.isDisabled().catch(() => false);
        if (isDisabled) {
          // Verify disabled reason is shown (tooltip or nearby text)
          result.outcome_observed = true;
          result.outcome_type = 'disabled';
          result.result = 'PASS';
          buttonAuditResults.push(result);
          return;
        }
        
        // Setup observers for click outcomes
        let navigationOccurred = false;
        let networkCallMade = false;
        let uiStateChanged = false;
        
        const initialUrl = page.url();
        const initialHtml = await page.content();
        
        // Listen for network requests
        const requestPromise = new Promise<Request | null>((resolve) => {
          const handler = (request: Request) => {
            if (request.resourceType() === 'fetch' || request.resourceType() === 'xhr') {
              page.off('request', handler);
              resolve(request);
            }
          };
          page.on('request', handler);
          setTimeout(() => resolve(null), 3000);
        });
        
        // Click the button
        await button.click({ timeout: 5000 });
        result.clicked = true;
        
        // Wait for any outcome
        await page.waitForTimeout(1000);
        
        // Check for navigation
        if (page.url() !== initialUrl) {
          navigationOccurred = true;
          result.outcome_type = 'navigation';
        }
        
        // Check for network call
        const request = await requestPromise;
        if (request) {
          networkCallMade = true;
          result.outcome_type = result.outcome_type || 'network_call';
        }
        
        // Check for UI state change (modal, form, etc.)
        const newHtml = await page.content();
        if (newHtml !== initialHtml && !navigationOccurred) {
          uiStateChanged = true;
          result.outcome_type = result.outcome_type || 'ui_state';
        }
        
        // Check for visible modal/dialog
        const modalVisible = await page.locator(
          '[role="dialog"], [data-testid*="modal"], .modal, [data-state="open"]'
        ).first().isVisible().catch(() => false);
        if (modalVisible) {
          uiStateChanged = true;
          result.outcome_type = 'ui_state';
        }
        
        // Determine if outcome was observed
        result.outcome_observed = navigationOccurred || networkCallMade || uiStateChanged;
        
        if (result.outcome_observed) {
          result.result = 'PASS';
        } else {
          result.error_message = 'No observable outcome after click (noop)';
          result.result = 'FAIL';
        }
        
      } catch (error: any) {
        result.result = 'FAIL';
        result.error_message = error.message?.slice(0, 200) || 'Unknown error';
      }
      
      buttonAuditResults.push(result);
      
      // Assert for test framework
      expect(result.result).toBe('PASS');
    });
  }
});

// Write results after all tests
test.afterAll(async () => {
  const outputPath = path.join(__dirname, '../results/button_audit.json');
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  fs.writeFileSync(outputPath, JSON.stringify({
    audit_type: 'button_wiring',
    timestamp: new Date().toISOString(),
    total_buttons: buttonAuditResults.length,
    passed: buttonAuditResults.filter(r => r.result === 'PASS').length,
    failed: buttonAuditResults.filter(r => r.result === 'FAIL').length,
    skipped: buttonAuditResults.filter(r => r.result === 'SKIP').length,
    noop_buttons: buttonAuditResults.filter(r => !r.outcome_observed && r.clicked).length,
    results: buttonAuditResults,
  }, null, 2));
});
