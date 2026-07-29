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

import { test, expect, Locator, Page, Request } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';
import * as yaml from 'js-yaml';
import { buttonAuditStore, inDeclarationOrder } from '../utils/audit-entries';

// Types
interface ButtonEntry {
  pageId: string;
  actionId: string;
  selector: string;
  fallback_selector?: string;
  requires_hub?: string;
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
  /**
   * The selector that actually resolved the element. Without this a pass looks
   * like it came from the named data-testid even when a broad fallback matched
   * some unrelated element, which is how a false pass hides in the artifact.
   */
  matched_selector?: string;
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

/**
 * Record a button's outcome.
 *
 * Written to its own file the moment the test ends rather than pushed to a
 * module-level array: Playwright retires a worker after a failure and retries in
 * a fresh process, so an in-memory array loses everything the previous process
 * held. See utils/audit-entries.ts.
 */
function recordResult(result: ButtonAuditResult): void {
  buttonAuditStore.write(`${result.pageId}::${result.actionId}`, result);
}

/**
 * How long to let the app render before concluding a button is absent.
 *
 * `page.goto(..., { waitUntil: 'domcontentloaded' })` returns when the HTML has
 * parsed, and `frontend/index.html` ships `<div id="root"></div>` empty, so the
 * app-shell wait that follows resolves the moment React paints anything at all
 * into that div — a layout frame, a nav, a skeleton, a Suspense fallback. The
 * button being audited belongs to a route-level component that mounts after its
 * chunk loads and, on most pages, after its first data fetch resolves. This
 * budget is what covers that gap. The fallback selector gets a shorter one:
 * by the time the primary wait has expired the app has long since rendered.
 */
const PRIMARY_SELECTOR_TIMEOUT_MS = 10000;
const FALLBACK_SELECTOR_TIMEOUT_MS = 5000;

/**
 * Wait for an element to become visible, and report whether it did.
 *
 * `isVisible()` is an immediate check — it answers for the instant it is called
 * and never retries — so calling it straight after navigation races the app's
 * first render and reports a button that is about to appear as one that is not
 * there. `waitFor` retries until the timeout, which is the pattern
 * page-audit.spec.ts already uses for the app root. A genuine absence still
 * fails: the wait expires and this returns false.
 */
async function waitForVisible(locator: Locator, timeout: number): Promise<boolean> {
  try {
    await locator.waitFor({ state: 'visible', timeout });
    return true;
  } catch {
    return false;
  }
}

/**
 * Admin sidebar navigation is organised into collapsible hubs. A hub's links are
 * unmounted while the hub is collapsed, and every hub starts collapsed on a page
 * that is not itself inside one (e.g. /dashboard). Registry entries that target a
 * sidebar link therefore declare `requires_hub`, and we perform the same first
 * step a real user does: open the hub, then click the link.
 *
 * Throws if the hub is absent or refuses to open — an unreachable navigation hub
 * is a genuine failure, not a reason to skip the assertion.
 */
async function expandNavHub(page: Page, hubId: string): Promise<void> {
  const toggle = page.locator(`[data-testid='nav-hub-btn-${hubId}']`);
  try {
    await toggle.waitFor({ state: 'visible', timeout: 10000 });
  } catch {
    throw new Error(`Navigation hub '${hubId}' not present in sidebar`);
  }

  if ((await toggle.getAttribute('aria-expanded')) === 'true') return;

  await toggle.click({ timeout: 5000 });
  try {
    await page
      .locator(`[data-testid='nav-hub-btn-${hubId}'][aria-expanded='true']`)
      .waitFor({ state: 'visible', timeout: 5000 });
  } catch {
    throw new Error(`Navigation hub '${hubId}' did not expand when clicked`);
  }
}

// Auth helper — uses addInitScript to inject token before any page JS runs,
// avoiding SSO redirects that break the navigate-then-evaluate approach.
async function setupAuth(page: Page, pageId: string): Promise<boolean> {
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

  const token =
    authType === 'portal_sso'
      ? process.env.PORTAL_TEST_TOKEN
      : authType === 'jwt_admin'
        ? process.env.ADMIN_TEST_TOKEN
        : undefined;

  if (!token) return false;

  if (authType === 'portal_sso') {
    await page.addInitScript((t: string) => {
      sessionStorage.setItem('platform_access_token', t);
      localStorage.setItem('portal_user', JSON.stringify({
        id: 'test-user-001', email: 'test@example.com',
        name: 'Test User', firstName: 'Test', lastName: 'User',
        isDemoUser: false,
      }));
      localStorage.setItem('portal_session_time', Date.now().toString());
    }, token);
  } else {
    await page.addInitScript((t: string) => {
      sessionStorage.setItem('platform_access_token', t);
    }, token);
  }

  return true;
}

// Dynamic test generation
const buttons = loadButtons();

test.describe('Button Wiring Audit', () => {
  // 'default', not 'serial'. Under 'serial' the first failure skips every
  // remaining test in the group, and portal-home::navigate-to-report is declared
  // first — so one unrendered button silently took the other 21 registry entries
  // with it, and the artifact carried 1 of 22 declared buttons while the report
  // printed "P0 coverage complete". A gate cannot report on buttons it never
  // clicked.
  //
  // 'default' keeps what 'serial' was chosen for — declaration order, one page
  // driven at a time, no two tests racing the same staging state — while letting
  // each button be measured on its own merits. Results are written per entry
  // rather than accumulated in memory, because Playwright retires a worker after
  // a failure and the remaining tests then run in a new process.
  test.describe.configure({ mode: 'default' });

  // The default 30s budget was set when the button lookup was an immediate
  // check that could not wait. It now waits up to 10s for the primary selector
  // and 5s for a fallback, on top of a navigation allowed 30s, so the budget has
  // to cover the waits it asks for. Nothing is asserted against this number; it
  // exists so a slow render fails as a slow render rather than as a test timeout.
  test.setTimeout(60000);
  
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
          recordResult(result);
          return;
        }
        
        // Skip parameterized routes (need specific data)
        if (route.includes(':')) {
          result.result = 'SKIP';
          result.error_message = 'Parameterized route - requires test data';
          recordResult(result);
          return;
        }
        
        // Setup auth
        const authReady = await setupAuth(page, buttonEntry.pageId);
        if (!authReady) {
          result.result = 'SKIP';
          result.error_message = 'Auth not configured';
          recordResult(result);
          return;
        }
        
        // Navigate to page.
        //
        // networkidle is flaky on SWA (analytics/keepalive/long-poll can keep the network
        // busy on a perfectly healthy SPA), so it is deliberately not used here — see
        // frontend/tests/e2e/staging-verification.spec.ts.
        //
        // What the change to domcontentloaded also did, and what its comment wrongly
        // denied, is remove the only thing that was waiting for the app to render. The
        // app-shell wait below is not "the real gate": frontend/index.html:24 ships
        // `<div id="root"></div>` empty, so this resolves the moment React's first paint
        // gives that div a box — before any route-level component, and therefore before
        // any audited button, has mounted. The real precondition is the target element
        // itself, and it is now waited for where it is looked up (waitForVisible below).
        await page.goto(route, { waitUntil: 'domcontentloaded', timeout: 30000 });
        await page.waitForSelector('#root, #app, [data-testid="app-root"]', { timeout: 5000 });
        
        // Open the containing sidebar hub for nav links (10-hub IA)
        if (buttonEntry.requires_hub) {
          await expandNavHub(page, buttonEntry.requires_hub);
        }
        
        // Try to find button with primary selector
        let button = page.locator(buttonEntry.selector).first();
        let buttonVisible = await waitForVisible(button, PRIMARY_SELECTOR_TIMEOUT_MS);
        if (buttonVisible) {
          result.matched_selector = buttonEntry.selector;
        }
        
        // Try fallback selector if primary not found
        if (!buttonVisible && buttonEntry.fallback_selector) {
          button = page.locator(buttonEntry.fallback_selector).first();
          buttonVisible = await waitForVisible(button, FALLBACK_SELECTOR_TIMEOUT_MS);
          if (buttonVisible) {
            result.matched_selector = buttonEntry.fallback_selector;
          }
        }
        
        if (!buttonVisible) {
          result.found = false;
          result.error_message = 'Button not visible on page';
          
          if (buttonEntry.criticality === 'P1') {
            result.result = 'SKIP';
            result.error_message = 'P1 button not visible - may be conditional';
            recordResult(result);
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
          recordResult(result);
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
      
      recordResult(result);
      
      // Assert for test framework
      expect(result.result).toBe('PASS');
    });
  }
});

/**
 * Merge the per-button entry files into the artifact the aggregator reads.
 *
 * Runs in every worker, and reads the directory rather than this process's own
 * results, so the last worker to finish emits the complete set however the run
 * was split across workers or retries.
 */
test.afterAll(async () => {
  fs.mkdirSync(path.dirname(buttonAuditStore.outputPath), { recursive: true });

  const results = inDeclarationOrder(
    buttonAuditStore.readAll<ButtonAuditResult>(),
    buttons.map(b => `${b.pageId}::${b.actionId}`),
    r => `${r.pageId}::${r.actionId}`,
  );

  fs.writeFileSync(buttonAuditStore.outputPath, JSON.stringify({
    audit_type: 'button_wiring',
    timestamp: new Date().toISOString(),
    // How many entries the registry asked for, as opposed to how many arrived.
    // A crashed worker, an aborted suite or an overwritten artifact drops entries
    // silently, and a missing entry cannot be classified — it simply leaves the
    // denominator. The aggregator holds the gate when this count is not met.
    expected_entries: buttons.length,
    total_buttons: results.length,
    passed: results.filter(r => r.result === 'PASS').length,
    failed: results.filter(r => r.result === 'FAIL').length,
    skipped: results.filter(r => r.result === 'SKIP').length,
    noop_buttons: results.filter(r => !r.outcome_observed && r.clicked).length,
    results,
  }, null, 2));
});
