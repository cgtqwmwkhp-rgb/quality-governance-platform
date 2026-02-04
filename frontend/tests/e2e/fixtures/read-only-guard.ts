/**
 * Read-Only Guard for E2E Tests
 * 
 * This fixture enforces that Playwright tests cannot make write requests
 * (POST, PUT, PATCH, DELETE) to the production API during staging verification.
 * 
 * SECURITY: This is a critical safety control to ensure E2E tests are truly
 * read-only when running against the production backend.
 * 
 * Usage:
 *   import { test } from './fixtures/read-only-guard';
 *   // All tests using this fixture will fail if write requests are attempted
 */

import { test as base, expect } from '@playwright/test';

// HTTP methods that are considered "write" operations
const WRITE_METHODS = ['POST', 'PUT', 'PATCH', 'DELETE'];

// Allowed POST endpoints (authentication, etc.) - must be explicitly whitelisted
const ALLOWED_WRITE_ENDPOINTS: RegExp[] = [
  // Authentication endpoints are allowed (they don't modify business data)
  /\/oauth2\/token/,
  /\/\.auth\//,
  // Add other safe endpoints here as needed
];

interface WriteAttempt {
  method: string;
  url: string;
  timestamp: string;
}

/**
 * Extended test fixture that blocks write requests to the API
 */
export const test = base.extend<{
  readOnlyMode: void;
  writeAttempts: WriteAttempt[];
}>({
  writeAttempts: [[], { option: true }],
  
  readOnlyMode: [async ({ page }, use, testInfo) => {
    const writeAttempts: WriteAttempt[] = [];
    
    // Intercept all requests and block write operations
    await page.route('**/*', async (route, request) => {
      const method = request.method();
      const url = request.url();
      
      // Check if this is a write method
      if (WRITE_METHODS.includes(method)) {
        // Check if it's an allowed endpoint
        const isAllowed = ALLOWED_WRITE_ENDPOINTS.some(pattern => pattern.test(url));
        
        if (!isAllowed) {
          // Log the blocked request
          const attempt: WriteAttempt = {
            method,
            url,
            timestamp: new Date().toISOString(),
          };
          writeAttempts.push(attempt);
          
          console.error(`🚫 READ-ONLY GUARD: Blocked ${method} request to ${url}`);
          
          // Abort the request with a clear error
          await route.abort('blockedbyclient');
          return;
        }
      }
      
      // Allow the request to continue
      await route.continue();
    });
    
    // Run the test
    await use();
    
    // After the test, fail if any write attempts were made
    if (writeAttempts.length > 0) {
      const details = writeAttempts
        .map(a => `  - ${a.method} ${a.url} at ${a.timestamp}`)
        .join('\n');
      
      throw new Error(
        `READ-ONLY VIOLATION: Test attempted ${writeAttempts.length} write request(s):\n${details}\n\n` +
        `E2E tests running against production API must be READ-ONLY.\n` +
        `If this endpoint is safe, add it to ALLOWED_WRITE_ENDPOINTS in read-only-guard.ts`
      );
    }
  }, { auto: true }],
});

export { expect };

/**
 * Re-export describe for convenience
 */
export const describe = test.describe;
