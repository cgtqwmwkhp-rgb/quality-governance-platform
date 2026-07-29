import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright configuration for UX Functional Coverage Gate
 * 
 * This configuration is optimized for:
 * - Registry-driven testing
 * - PII-safe artifact generation
 * - Deterministic test execution
 * - CI/CD integration
 */

export default defineConfig({
  testDir: './tests',
  // Clears the previous run's per-workflow audit entries exactly once, before
  // any worker starts. See utils/workflow-audit-artifacts.ts.
  globalSetup: './global-setup.ts',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 2 : undefined,
  reporter: [
    ['html', { outputFolder: 'playwright-report' }],
    ['json', { outputFile: 'results/test-results.json' }],
    ['list'],
  ],
  
  outputDir: 'results/test-artifacts',
  
  use: {
    baseURL: process.env.FRONTEND_URL || process.env.APP_URL || 'http://localhost:5173',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    
    // Stability settings
    actionTimeout: 15000,
    navigationTimeout: 30000,
    
    // Viewport for consistent testing
    viewport: { width: 1280, height: 720 },

    // No extraHTTPHeaders. `X-Test-Context: ux-coverage-audit` used to be set
    // here "for test identification", but nothing on the API side ever read it,
    // and Playwright applies extraHTTPHeaders to *every* request the browser
    // makes — including cross-origin XHR from the audited frontend to the API.
    //
    // A custom request header makes such a request non-simple, so the browser
    // sends a CORS preflight listing `x-test-context` in
    // Access-Control-Request-Headers. That header is not in the API's
    // allow_headers (src/main.py), so the preflight is answered 400, the browser
    // blocks the request, and the service worker (frontend/public/sw.js) turns
    // the resulting network failure into a synthetic
    // `503 {"error":"Offline","message":"Network unavailable"}`.
    //
    // Net effect: the gate broke every API call made by the application it was
    // auditing, then reported the damage as an application defect — the P0
    // portal-incident-report journey dead-ended on "Unable to Load Form", and
    // the fake 503 was repeatedly misread as staging being down. Any header
    // added here must be present in the API's CORS allow_headers; see
    // tests/unit/test_ux_coverage_gate_request_headers.py, which enforces that.
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],

  // Optional: Start dev server before tests
  // webServer: {
  //   command: 'npm run dev',
  //   url: 'http://localhost:5173',
  //   reuseExistingServer: !process.env.CI,
  // },
});
