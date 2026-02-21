import { Page, expect } from '@playwright/test';

export async function assertPageLoadPerformance(page: Page, maxLoadMs = 3000) {
  const timing = await page.evaluate(() => {
    const perf = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming;
    return {
      loadComplete: perf?.loadEventEnd - perf?.fetchStart,
      domContentLoaded: perf?.domContentLoadedEventEnd - perf?.fetchStart,
    };
  });
  if (timing.loadComplete > 0) {
    expect(timing.loadComplete).toBeLessThan(maxLoadMs);
  }
}

export async function assertInteractionPerformance(
  page: Page,
  action: () => Promise<void>,
  maxMs = 500,
) {
  const start = Date.now();
  await action();
  const duration = Date.now() - start;
  expect(duration).toBeLessThan(maxMs);
}
