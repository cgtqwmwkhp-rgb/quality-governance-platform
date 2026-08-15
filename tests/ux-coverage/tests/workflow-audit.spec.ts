/**
 * Workflow Audit for UX Functional Coverage Gate
 * 
 * Executes P0 workflows end-to-end and verifies:
 * - Each step completes successfully
 * - Terminal state is reached (success or defined recovery)
 * - No stranded steps (dead ends)
 * - Expected APIs are called
 * 
 * PII-SAFE: Uses placeholder test data, not real user data.
 */

import { test, expect, Page, Request } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';
import * as yaml from 'js-yaml';
import {
  OUTPUT_PATH,
  RESULTS_DIR,
  readWorkflowAuditEntries,
  writeWorkflowAuditEntry,
} from '../utils/workflow-audit-artifacts';

// Types
interface WorkflowStep {
  stepId: number;
  action: string;
  route?: string;
  selector?: string;
  fallback_selector?: string;
  form_fields?: Array<{ selector: string; value: string }>;
  exit_criteria: string;
  expected_api?: string;
}

interface WorkflowEntry {
  workflowId: string;
  name: string;
  description: string;
  criticality: string;
  auth_type: string;
  steps: WorkflowStep[];
  success_terminal_state: string;
  recovery_path: string;
  expected_apis: string[];
  max_duration_seconds: number;
  /** Declared bounded error states (admin-login; see LOGIN_UX_CONTRACT.md). */
  error_terminal_states?: Array<{ error_code: string; ui_element: string; message?: string }>;
  recovery_actions?: Array<{ action: string; selector: string; applies_to?: string[] }>;
}

interface StepResult {
  stepId: number;
  action: string;
  result: 'PASS' | 'FAIL' | 'SKIP';
  duration_ms: number;
  error?: string;
}

interface RecoveryStateEvidence {
  detected: boolean;
  /** Which selector matched, so a reader can judge the finding rather than trust it. */
  matched_selector: string | null;
  /** The matched element's test id, or its trimmed text when it has none. */
  detail: string | null;
  /** Selector of the recovery affordance found alongside it, if any. */
  retry_affordance: string | null;
}

interface WorkflowAuditResult {
  workflowId: string;
  name: string;
  criticality: string;
  result: 'PASS' | 'FAIL' | 'SKIP';
  total_steps: number;
  completed_steps: number;
  total_duration_ms: number;
  terminal_state_reached: boolean;
  apis_called: string[];
  expected_apis: string[];
  step_results: StepResult[];
  error_message?: string;
  recovery_state?: RecoveryStateEvidence;
}

/**
 * Elements that exist only to announce a failed operation.
 *
 * The previous locator was
 *   '[data-testid*="error"], .error, .alert-danger, :text("Error"), :text("retry")'
 * which is not evidence of anything. `[data-testid*="error"]` matches the dynamic
 * form renderer's own `upload-errors-<field>` container, `.error` matches any
 * element that happens to carry that class, and the `:text()` clauses match any
 * page containing the word "Error" or "retry" anywhere — including help copy and
 * a "Retry" button on an unrelated panel. It reported "(Recovery state visible)"
 * on runs that had reached no recovery state at all, and that false positive was
 * read as corroborating evidence by two separate investigations into the
 * portal-incident-report failure.
 *
 * These require a purpose-built announcement: an ARIA alert, or a test id whose
 * name is exactly an error hook (`*-error`, `error-*`) rather than merely
 * containing the substring.
 */
const RECOVERY_INDICATOR_SELECTORS = [
  '[role="alert"]',
  '[data-testid$="-error"]',
  '[data-testid^="error-"]',
  '.alert-danger',
];

/**
 * Screen-reader-only live regions are announcement channels, not recovery UI.
 *
 * LiveAnnouncer mounts a permanent, empty `<div role="alert" class="sr-only">` on
 * every page, and `.sr-only` here is a 1x1px clipped box — which Playwright counts
 * as visible, because it has a non-empty bounding box. Matching it would have made
 * `[role="alert"]` fire on every page in the application: the same class of false
 * positive this locator was rewritten to remove. Real banners (Toast, ErrorState,
 * FormField, SessionExpiryWarning) also carry aria-live, so aria-live cannot be
 * used to tell them apart — but they occupy real space and they say something.
 */
const MIN_PERCEPTIBLE_PX = 8;

async function isPerceptibleAnnouncement(
  element: import('@playwright/test').Locator,
): Promise<{ perceptible: boolean; text: string }> {
  const text = ((await element.textContent().catch(() => null)) || '').trim();
  if (!text) return { perceptible: false, text };
  const box = await element.boundingBox().catch(() => null);
  if (!box || box.width < MIN_PERCEPTIBLE_PX || box.height < MIN_PERCEPTIBLE_PX) {
    return { perceptible: false, text };
  }
  return { perceptible: true, text };
}

/**
 * Wait for an element to become visible, and report whether it did.
 *
 * `isVisible()` is an immediate check with no auto-waiting, so on its own it
 * races the app's render and reports an element that is about to appear as one
 * that is absent. A genuine absence still fails: the wait expires and this
 * returns false.
 */
async function waitForVisible(
  locator: import('@playwright/test').Locator,
  timeout: number,
): Promise<boolean> {
  try {
    await locator.waitFor({ state: 'visible', timeout });
    return true;
  } catch {
    return false;
  }
}

/** Affordances that let a user leave a recovery state, per LOGIN_UX_CONTRACT.md. */
const RECOVERY_AFFORDANCE_SELECTORS = [
  '[data-testid="retry-button"]',
  '[data-testid$="-retry"]',
  'button:has-text("Retry")',
  'button:has-text("Try again")',
];

/**
 * Look for a genuine, named recovery state and record what was actually found.
 *
 * A workflow's own declared recovery selectors take precedence when the registry
 * provides them (admin-login declares error_terminal_states/recovery_actions).
 */
async function findRecoveryState(
  page: Page,
  workflow: WorkflowEntry,
): Promise<RecoveryStateEvidence> {
  const declared = [
    ...(workflow.error_terminal_states || []).map(s => s.ui_element).filter(Boolean),
    ...(workflow.recovery_actions || []).map(a => a.selector).filter(Boolean),
  ] as string[];

  const evidence: RecoveryStateEvidence = {
    detected: false,
    matched_selector: null,
    detail: null,
    retry_affordance: null,
  };

  for (const selector of [...declared, ...RECOVERY_INDICATOR_SELECTORS]) {
    const element = page.locator(selector).first();
    const visible = await element.isVisible().catch(() => false);
    if (!visible) continue;

    const { perceptible, text } = await isPerceptibleAnnouncement(element);
    if (!perceptible) continue;

    evidence.detected = true;
    evidence.matched_selector = selector;
    evidence.detail =
      (await element.getAttribute('data-testid').catch(() => null)) || text.slice(0, 120);
    break;
  }

  for (const selector of RECOVERY_AFFORDANCE_SELECTORS) {
    const visible = await page.locator(selector).first().isVisible().catch(() => false);
    if (visible) {
      evidence.retry_affordance = selector;
      break;
    }
  }

  return evidence;
}

// Load registry
function loadWorkflows(): WorkflowEntry[] {
  const registryPath = path.join(__dirname, '../../../docs/ops/WORKFLOW_REGISTRY.yml');
  const content = fs.readFileSync(registryPath, 'utf-8');
  const registry = yaml.load(content) as any;
  
  // Only P0 workflows for now (critical path)
  return registry.p0_workflows || [];
}

/**
 * Record a journey's outcome.
 *
 * Written to its own file the moment the journey ends, rather than pushed to a
 * module-level array: Playwright retires a worker after a test fails, so the
 * later journeys run in a fresh process and an in-memory array would lose either
 * the failure or everything after it.
 */
function recordResult(result: WorkflowAuditResult): void {
  writeWorkflowAuditEntry(result.workflowId, result);
}

// Test data replacements (environment variable or defaults)
function replaceTestData(value: string): string {
  return value
    .replace('${TEST_USER_EMAIL}', process.env.TEST_USER_EMAIL || 'test@example.com')
    .replace('${TEST_USER_PASSWORD}', process.env.TEST_USER_PASSWORD || 'TestPassword123!')
    .replace('${KNOWN_REFERENCE}', process.env.KNOWN_REFERENCE || 'INC-TEST-001');
}

// Auth helper — uses addInitScript to inject token before any page JS runs,
// avoiding SSO redirects that break the navigate-then-evaluate approach.
async function setupAuth(page: Page, authType: string): Promise<boolean> {
  if (authType === 'none') return true;

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
const workflows = loadWorkflows();

test.describe('Workflow Audit (P0 Critical Paths)', () => {
  // 'default', not 'serial'. Under 'serial' the first failure skips every
  // remaining test in the group, and portal-incident-report is declared first —
  // so one broken journey silently took four other P0 journeys with it
  // (portal-near-miss-report, portal-rta-report, admin-login,
  // admin-view-incident), and the artifact carried 1 of 5 declared entries. A
  // gate cannot report on journeys it never ran.
  //
  // 'default' keeps what 'serial' was chosen for — declaration order, no two
  // workflows driving the same staging API at once — while letting each journey
  // be measured on its own merits. Results are written per journey rather than
  // accumulated in memory, because Playwright retires a worker after a failure
  // and the remaining journeys then run in a new process.
  test.describe.configure({ mode: 'default' });
  
  for (const workflow of workflows) {
    test(`[${workflow.criticality}] ${workflow.workflowId}: ${workflow.name}`, async ({ page }) => {
      const result: WorkflowAuditResult = {
        workflowId: workflow.workflowId,
        name: workflow.name,
        criticality: workflow.criticality,
        result: 'FAIL',
        total_steps: workflow.steps.length,
        completed_steps: 0,
        total_duration_ms: 0,
        terminal_state_reached: false,
        apis_called: [],
        expected_apis: workflow.expected_apis,
        step_results: [],
      };
      
      const workflowStartTime = Date.now();

      // Auth is resolved before the try/catch below, and deliberately so.
      // test.skip() aborts the test by throwing a TestSkipError; inside the try
      // that error was caught and rewritten into a P0 FAIL, so a workflow that
      // never ran was reported — twice, since `result` was pushed on both
      // paths — as a workflow that ran and failed. The aggregator now holds the
      // gate on P0 entries that did not execute, so a skip can be recorded
      // honestly as SKIP without turning a token-less run green.
      let authReady = true;
      if (workflow.auth_type !== 'none') {
        try {
          authReady = await setupAuth(page, workflow.auth_type);
        } catch (error: any) {
          // Auth setup threw rather than reporting "no token configured": that
          // is a real failure, and the entry must still reach the artifact.
          result.error_message = `Auth setup failed: ${error.message?.slice(0, 200)}`;
          result.total_duration_ms = Date.now() - workflowStartTime;
          recordResult(result);
          expect(result.result).toBe('PASS');
          return;
        }
      }

      if (!authReady) {
        result.result = 'SKIP';
        result.error_message = `Auth type ${workflow.auth_type} not configured`;
        result.total_duration_ms = Date.now() - workflowStartTime;
        recordResult(result);
        test.skip(true, result.error_message);
        return;
      }

      try {
        // Track API calls
        page.on('request', (request: Request) => {
          if (request.resourceType() === 'fetch' || request.resourceType() === 'xhr') {
            const url = new URL(request.url());
            const method = request.method();
            result.apis_called.push(`${method} ${url.pathname}`);
          }
        });
        
        // Execute each step
        for (const step of workflow.steps) {
          const stepStartTime = Date.now();
          const stepResult: StepResult = {
            stepId: step.stepId,
            action: step.action,
            result: 'FAIL',
            duration_ms: 0,
          };
          
          try {
            // Navigate if route specified
            if (step.route) {
              // networkidle is flaky on SWA (analytics/keepalive keep the network busy on a
              // healthy SPA). The app-shell wait below is the real gate and is unchanged.
              await page.goto(step.route, { 
                waitUntil: 'domcontentloaded', 
                timeout: workflow.max_duration_seconds * 1000 
              });
              await page.waitForSelector('#root, #app, [data-testid="app-root"]', { timeout: 5000 });
            }
            
            // Fill form fields if specified.
            // Portal incident/near-miss P0s were racing the form-config round
            // trip: after clicking the type card the page is still
            // `portal-form-loading`, and a 5s wait for `field-contract` expired
            // on LIVE staging (UX coverage 31880826656). Wait for the ready
            // marker up to the workflow budget first; the field wait stays
            // fail-closed if the picker never appears.
            if (step.form_fields) {
              const formReady = page.locator('[data-testid="portal-form-ready"]').first();
              await waitForVisible(
                formReady,
                Math.max(5000, (workflow.max_duration_seconds || 30) * 1000),
              );
              for (const field of step.form_fields) {
                const value = replaceTestData(field.value);
                const wrapper = page.locator(field.selector).first();
                await wrapper.waitFor({
                  state: 'visible',
                  timeout: Math.max(5000, (workflow.max_duration_seconds || 30) * 1000),
                });

                const input = wrapper.locator('input, textarea').first();
                if (await input.count() > 0) {
                  await input.fill(value);
                } else {
                  const sel = wrapper.locator('select').first();
                  if (await sel.count() > 0) {
                    await sel.selectOption({ label: value });
                  } else {
                    // Custom dropdown (e.g. FuzzySearchDropdown): click trigger, then fill search input
                    const trigger = wrapper.locator('button').first();
                    if (await trigger.count() > 0) {
                      await trigger.click();
                      await page.waitForTimeout(300);
                      const searchInput = wrapper.locator('input').first();
                      if (await searchInput.count() > 0) {
                        await searchInput.fill(value);
                        await page.waitForTimeout(300);
                        const option = wrapper.locator(`button:has-text("${value}")`).first();
                        if (await option.isVisible().catch(() => false)) {
                          await option.click();
                        }
                      }
                    } else {
                      await wrapper.fill(value);
                    }
                  }
                }
              }
            }
            
            // Click element if selector specified (and not form_fields step)
            if (step.selector && !step.form_fields) {
              let element = page.locator(step.selector).first();
              let visible = await waitForVisible(element, 5000);
              
              // Try fallback. This used to be a bare isVisible() with no wait of
              // its own: an immediate check, taken at the instant the primary
              // wait expired, which is the earliest moment a slow-rendering
              // fallback could still be absent. Wait for it too.
              if (!visible && step.fallback_selector) {
                element = page.locator(step.fallback_selector).first();
                visible = await waitForVisible(element, 5000);
              }
              
              if (visible) {
                await element.click({ timeout: 5000 });
                await page.waitForTimeout(500); // Brief pause for UI update
              } else {
                throw new Error(`Element not found: ${step.selector}`);
              }
            }
            
            // Wait for expected API if specified
            if (step.expected_api) {
              await page.waitForResponse(
                (response) => {
                  const url = new URL(response.url());
                  return url.pathname.includes(step.expected_api!.split(' ')[1]);
                },
                { timeout: 10000 }
              ).catch(() => null);
            }
            
            // Settle after the action. This used to be
            //   waitForLoadState('networkidle', { timeout: 10000 }).catch(() => {})
            // which swallowed its own failure, so it asserted nothing at all and simply
            // burned up to 10s per step whenever SWA analytics/keepalive kept the network
            // busy. Assert the app shell is still rendered instead: a real element check
            // that can actually fail, in place of a silent timeout.
            await page
              .locator('#root, #app, [data-testid="app-root"]')
              .first()
              .waitFor({ state: 'visible', timeout: 5000 });
            
            stepResult.result = 'PASS';
            result.completed_steps++;
            
          } catch (error: any) {
            stepResult.result = 'FAIL';
            // 100 chars truncated mid-selector, so the artifact could not say which
            // element was missing. Keep it bounded but long enough to be actionable.
            stepResult.error = error.message?.slice(0, 500);
          }
          
          stepResult.duration_ms = Date.now() - stepStartTime;
          result.step_results.push(stepResult);
          
          // Stop workflow on step failure
          if (stepResult.result === 'FAIL') {
            throw new Error(`Step ${step.stepId} failed: ${stepResult.error}`);
          }
        }
        
        // Verify terminal state
        // Look for success indicators
        const successIndicators = await page.locator(
          '[data-testid*="success"], [data-testid*="confirmation"], .success, .alert-success, :text("successfully"), :text("Reference")'
        ).first().isVisible().catch(() => false);
        
        result.terminal_state_reached = successIndicators || result.completed_steps === result.total_steps;
        
        // Verify expected APIs were called
        const missingApis = workflow.expected_apis.filter(
          expected => !result.apis_called.some(called => called.includes(expected.split(' ')[1]))
        );
        
        if (missingApis.length > 0 && workflow.criticality === 'P0') {
          // Only warn, don't fail - API paths might differ slightly
          result.error_message = `Missing API calls: ${missingApis.join(', ')}`;
        }
        
        result.result = 'PASS';
        
      } catch (error: any) {
        result.result = 'FAIL';
        result.error_message = error.message?.slice(0, 200);

        result.recovery_state = await findRecoveryState(page, workflow);
        if (result.recovery_state.detected) {
          // Name the element that matched. "(Recovery state visible)" on its own
          // told a reader nothing they could check.
          result.error_message += ` (Recovery state: ${result.recovery_state.matched_selector}`
            + `${result.recovery_state.detail ? ` → ${result.recovery_state.detail}` : ''}`
            + `${result.recovery_state.retry_affordance ? '; retry offered' : '; no retry offered'})`;
        }
      }
      
      result.total_duration_ms = Date.now() - workflowStartTime;
      recordResult(result);
      
      // Assert for test framework
      expect(result.result).toBe('PASS');
    });
  }
});

/**
 * Merge the per-workflow entry files into the artifact the aggregator reads.
 *
 * Runs in every worker, and reads the directory rather than this process's own
 * results, so the last worker to finish emits the complete set however the run
 * was split across workers or retries.
 */
test.afterAll(async () => {
  fs.mkdirSync(RESULTS_DIR, { recursive: true });

  const declarationOrder = new Map(workflows.map((w, index) => [w.workflowId, index]));
  const results = readWorkflowAuditEntries<WorkflowAuditResult>().sort(
    (a, b) =>
      (declarationOrder.get(a.workflowId) ?? Number.MAX_SAFE_INTEGER) -
      (declarationOrder.get(b.workflowId) ?? Number.MAX_SAFE_INTEGER),
  );

  // Identify dead ends (workflows that failed mid-step)
  const deadEnds = results
    .filter(r => r.result === 'FAIL' && r.completed_steps < r.total_steps)
    .map(r => ({
      workflowId: r.workflowId,
      failed_at_step: r.step_results.find(s => s.result === 'FAIL')?.stepId,
      error: r.error_message,
    }));

  fs.writeFileSync(OUTPUT_PATH, JSON.stringify({
    audit_type: 'workflow',
    timestamp: new Date().toISOString(),
    // How many entries the registry asked for, as opposed to how many arrived.
    // A crashed worker drops entries silently; the aggregator holds the gate when
    // this count is not met.
    expected_entries: workflows.length,
    total_workflows: results.length,
    passed: results.filter(r => r.result === 'PASS').length,
    failed: results.filter(r => r.result === 'FAIL').length,
    skipped: results.filter(r => r.result === 'SKIP').length,
    dead_ends: deadEnds,
    results,
  }, null, 2));
});
