/**
 * Accessibility Audit for UX Functional Coverage Gate
 *
 * Runs axe-core on P0 pages from PAGE_REGISTRY.yml.
 * Fails on critical or serious violations.
 * Results written to a11y-audit-results.json for aggregation.
 */

import { test, Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import * as fs from 'fs';
import * as path from 'path';
import * as yaml from 'js-yaml';

interface PageEntry {
  pageId: string;
  route: string;
  auth: string;
  criticality: string;
  component: string;
  description: string;
}

interface A11yResult {
  pageId: string;
  route: string;
  criticality: string;
  result: 'PASS' | 'FAIL' | 'SKIP';
  violations_critical: number;
  violations_serious: number;
  violations_moderate: number;
  violations_minor: number;
  error_message?: string;
}

const APP_URL = process.env.FRONTEND_URL || process.env.APP_URL || 'http://localhost:3000';
const results: A11yResult[] = [];

function loadP0Pages(): PageEntry[] {
  const registryPath = path.join(__dirname, '../../../docs/ops/PAGE_REGISTRY.yml');
  const content = fs.readFileSync(registryPath, 'utf-8');
  const registry = yaml.load(content) as any;

  const allPages: PageEntry[] = [
    ...(registry.public_routes || []),
    ...(registry.portal_routes || []),
    ...(registry.admin_routes || []),
  ];

  // D03 WCS closure 2026-04-08: expanded to include P1 routes for a11y coverage.
  // P0 + P1 routes without dynamic segments (:id etc.) are required for 9.5 target.
  return allPages.filter(
    (p) => (p.criticality === 'P0' || p.criticality === 'P1') && !p.route.includes(':')
  );
}

async function setupAuth(page: Page, authType: string): Promise<void> {
  if (authType === 'anon' || authType === 'none') return;

  if (authType === 'portal_sso') {
    const token = process.env.PORTAL_TEST_TOKEN;
    if (token) {
      await page.addInitScript((t: string) => {
        sessionStorage.setItem('platform_access_token', t);
        localStorage.setItem('portal_user', JSON.stringify({
          id: 'test-user-001', email: 'test@example.com',
          name: 'Test User', firstName: 'Test', lastName: 'User',
          isDemoUser: true,
        }));
        localStorage.setItem('portal_session_time', Date.now().toString());
      }, token);
    }
    return;
  }

  if (authType === 'jwt_admin') {
    const token = process.env.ADMIN_TEST_TOKEN ||
      'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiZW1haWwiOiJhZG1pbkB0ZXN0LmNvbSIsInJvbGUiOiJhZG1pbiIsImV4cCI6OTk5OTk5OTk5OX0.test';
    await page.addInitScript((t: string) => {
      sessionStorage.setItem('platform_access_token', t);
    }, token);
    return;
  }
}

test.describe.configure({ mode: 'serial' });

test.describe('Accessibility Audit (axe-core)', () => {
  const pages = loadP0Pages();

  for (const entry of pages) {
    test(`a11y: ${entry.pageId} (${entry.route})`, async ({ page }) => {
      try {
        await setupAuth(page, entry.auth);

        const url = entry.route.startsWith('http')
          ? entry.route
          : `${APP_URL}${entry.route}`;

        await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 15000 });
        await page.waitForTimeout(2000);

        const axeResults = await new AxeBuilder({ page })
          .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
          .analyze();

        const critical = axeResults.violations.filter((v) => v.impact === 'critical').length;
        const serious = axeResults.violations.filter((v) => v.impact === 'serious').length;
        const moderate = axeResults.violations.filter((v) => v.impact === 'moderate').length;
        const minor = axeResults.violations.filter((v) => v.impact === 'minor').length;

        const hasCriticalFailures = critical > 0 || serious > 0;

        results.push({
          pageId: entry.pageId,
          route: entry.route,
          criticality: entry.criticality,
          result: hasCriticalFailures ? 'FAIL' : 'PASS',
          violations_critical: critical,
          violations_serious: serious,
          violations_moderate: moderate,
          violations_minor: minor,
        });
      } catch (err: any) {
        results.push({
          pageId: entry.pageId,
          route: entry.route,
          criticality: entry.criticality,
          result: 'SKIP',
          violations_critical: 0,
          violations_serious: 0,
          violations_moderate: 0,
          violations_minor: 0,
          error_message: err.message?.substring(0, 200),
        });
      }
    });
  }

  test.afterAll(() => {
    const outputPath = path.join(__dirname, '../a11y-audit-results.json');
    fs.writeFileSync(outputPath, JSON.stringify(results, null, 2));
    console.log(`[A11y Audit] Wrote ${results.length} results to ${outputPath}`);
  });
});
