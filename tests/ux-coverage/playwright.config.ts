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
    baseURL: process.env.APP_URL || 'http://localhost:5173',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    
    // Stability settings
    actionTimeout: 15000,
    navigationTimeout: 30000,
    
    // Viewport for consistent testing
    viewport: { width: 1280, height: 720 },
    
    // Extra HTTP headers for test identification
    extraHTTPHeaders: {
      'X-Test-Context': 'ux-coverage-audit',
    },
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
