import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright Configuration for Quality Governance Platform
 * 
 * Artifact Configuration:
 * - Screenshots: Always on failure, optionally on success for key tests
 * - Traces: On first retry (for debugging failures)
 * - Video: On first retry (helps reproduce issues)
 * 
 * CI Integration:
 * - Uploads playwright-report/, screenshots/, traces/ as artifacts
 * - Used by staging UI verification job for release evidence
 */
export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  
  // Output directories for artifacts
  outputDir: './test-results',
  
  reporter: [
    ['html', { outputFolder: 'playwright-report', open: 'never' }],
    ['list'],
    ['json', { outputFile: 'playwright-report/results.json' }],
    // JUnit for CI integration
    ...(process.env.CI ? [['junit', { outputFile: 'playwright-report/junit.xml' }] as const] : []),
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
