/**
 * Accessibility Audit for UX Functional Coverage Gate
 *
 * Runs axe-core on P0/P1 pages from PAGE_REGISTRY.yml.
 * Fails on critical or serious violations.
 * Results written to results/a11y_audit.json for aggregation (C-50).
 *
 * Parallel workers write per-page entry files; afterAll merges them. Serial
 * mode was dropped (C-51 residual): a mid-suite failure used to skip the rest
 * and shrink the artifact denominator.
 */

import { test, expect, Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import * as fs from 'fs';
import * as path from 'path';
import * as yaml from 'js-yaml';
import { a11yAuditStore, inDeclarationOrder } from '../utils/audit-entries';

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
  violation_rules_critical?: string[];
  violation_rules_serious?: string[];
  error_message?: string;
}

/** Unique axe rule ids for a given impact, capped for artifact size. */
function topViolationRuleIds(
  violations: Array<{ id: string; impact?: string | null }>,
  impact: 'critical' | 'serious',
  limit = 5,
): string[] {
  return [
    ...new Set(violations.filter((v) => v.impact === impact).map((v) => v.id)),
  ].slice(0, limit);
}

function formatFailMessage(
  critical: number,
  serious: number,
  criticalRules: string[],
  seriousRules: string[],
): string {
  const parts: string[] = [];
  if (critical > 0) {
    parts.push(`critical rules: ${criticalRules.length ? criticalRules.join(', ') : 'unknown'}`);
  }
  if (serious > 0) {
    parts.push(`serious rules: ${seriousRules.length ? seriousRules.join(', ') : 'unknown'}`);
  }
  return `${critical} critical, ${serious} serious (${parts.join('; ')})`;
}

function loadPages(): PageEntry[] {
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

function recordResult(result: A11yResult): void {
  a11yAuditStore.write(result.pageId, result);
}

async function setupAuth(page: Page, authType: string): Promise<boolean> {
  if (authType === 'anon' || authType === 'none') return true;

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

const pages = loadPages();

test.describe('Accessibility Audit (axe-core)', () => {
  // Parallel by default (C-51): serial aborted the rest of the suite on the
  // first failure and left those pages out of the artifact entirely.
  test.describe.configure({ mode: 'parallel' });

  for (const entry of pages) {
    test(`a11y: ${entry.pageId} (${entry.route})`, async ({ page }) => {
      const result: A11yResult = {
        pageId: entry.pageId,
        route: entry.route,
        criticality: entry.criticality,
        result: 'SKIP',
        violations_critical: 0,
        violations_serious: 0,
        violations_moderate: 0,
        violations_minor: 0,
      };

      try {
        const authReady = await setupAuth(page, entry.auth);
        if (!authReady && entry.auth !== 'anon' && entry.auth !== 'none') {
          result.error_message = `Auth type ${entry.auth} not configured`;
          recordResult(result);
          test.skip(true, result.error_message);
          return;
        }

        await page.goto(entry.route, { waitUntil: 'domcontentloaded', timeout: 15000 });

        // Wait for route content, not merely the empty #root shell (same marker
        // as the link audit — C-56).
        await page.locator('[data-ux-route-content]').first().waitFor({
          state: 'attached',
          timeout: 15000,
        });

        const axeResults = await new AxeBuilder({ page })
          .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
          .analyze();

        const critical = axeResults.violations.filter((v) => v.impact === 'critical').length;
        const serious = axeResults.violations.filter((v) => v.impact === 'serious').length;
        const moderate = axeResults.violations.filter((v) => v.impact === 'moderate').length;
        const minor = axeResults.violations.filter((v) => v.impact === 'minor').length;

        result.violations_critical = critical;
        result.violations_serious = serious;
        result.violations_moderate = moderate;
        result.violations_minor = minor;

        if (critical > 0 || serious > 0) {
          const criticalRules = topViolationRuleIds(axeResults.violations, 'critical');
          const seriousRules = topViolationRuleIds(axeResults.violations, 'serious');
          result.violation_rules_critical = criticalRules;
          result.violation_rules_serious = seriousRules;
          result.error_message = formatFailMessage(critical, serious, criticalRules, seriousRules);
          result.result = 'FAIL';
        } else {
          result.result = 'PASS';
        }
      } catch (err: any) {
        result.result = 'SKIP';
        result.error_message = err.message?.substring(0, 200);
      }

      recordResult(result);
      expect(result.result).toBe('PASS');
    });
  }
});

test.afterAll(async () => {
  fs.mkdirSync(path.dirname(a11yAuditStore.outputPath), { recursive: true });

  const results = inDeclarationOrder(
    a11yAuditStore.readAll<A11yResult>(),
    pages.map((p) => p.pageId),
    (r) => r.pageId,
  );

  fs.writeFileSync(a11yAuditStore.outputPath, JSON.stringify({
    audit_type: 'a11y',
    timestamp: new Date().toISOString(),
    expected_entries: pages.length,
    total_pages: results.length,
    passed: results.filter((r) => r.result === 'PASS').length,
    failed: results.filter((r) => r.result === 'FAIL').length,
    skipped: results.filter((r) => r.result === 'SKIP').length,
    results,
  }, null, 2));
});
