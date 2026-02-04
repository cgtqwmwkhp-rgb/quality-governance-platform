import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright Configuration for Quality Governance Platform
 * 
 * IMPORTANT: This config is designed for machine-verifiable CI gates.
 * 
 * Reporters (ALWAYS generated - not conditional):
 * - HTML: Human-readable report at playwright-report/index.html
 * - JSON: Machine-readable at playwright-report/results.json
 * - JUnit: CI integration at playwright-report/junit.xml
 * - List: Console output for live feedback
 * 
 * Artifacts:
 * - Screenshots: On failure only
 * - Traces: On first retry (for debugging)
 * - Video: On first retry (for debugging)
 * 
 * Output Paths (STABLE for CI artifact upload):
 * - playwright-report/       HTML report + JSON + JUnit
 * - test-results/            Screenshots, videos, traces
 */
export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  
  // Output directories for artifacts (stable paths)
  outputDir: './test-results',
  
  // ALWAYS emit all reporters for machine-verifiable results
  // Not conditional - ensures consistent behavior in all environments
  reporter: [
    ['html', { outputFolder: 'playwright-report', open: 'never' }],
    ['json', { outputFile: 'playwright-report/results.json' }],
    ['junit', { outputFile: 'playwright-report/junit.xml' }],
    ['list'],
  ],
  
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:5173',
    
    // Artifact capture configuration
    screenshot: 'only-on-failure',
    trace: 'on-first-retry',
    video: 'on-first-retry',
    
    // Viewport and timing
    viewport: { width: 1280, height: 720 },
    actionTimeout: 15000,
    navigationTimeout: 30000,
    
    // Helpful for debugging
    ignoreHTTPSErrors: true,
  },

  // Expect settings
  expect: {
    timeout: 10000,
    toHaveScreenshot: {
      maxDiffPixelRatio: 0.05,
    },
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],

  /* Run local dev server before starting tests if not in CI */
  webServer: process.env.CI ? undefined : {
    command: 'npm run dev',
    url: 'http://localhost:5173',
    reuseExistingServer: !process.env.CI,
    timeout: 60000,
  },
});
