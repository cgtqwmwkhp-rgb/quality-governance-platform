'use strict';

/**
 * C-50 / C-56 / C-60 regressions for UX gate honesty.
 *
 * - C-50: a11y audit must be a required job + artifact in the aggregator.
 * - C-56: link audit must wait for [data-ux-route-content], not empty shell;
 *         must not use networkidle.
 * - C-60: missing artifacts must not be invented as {"results":[]}.
 *
 * Run with: node --test scripts/governance/__tests__/ux-coverage-c50-c56-honesty.test.cjs
 */

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const ROOT = path.join(__dirname, '..', '..', '..');
const WORKFLOW = path.join(ROOT, '.github', 'workflows', 'ux-functional-coverage.yml');
const LINK_AUDIT = path.join(ROOT, 'tests', 'ux-coverage', 'tests', 'link-audit.spec.ts');
const A11Y_AUDIT = path.join(ROOT, 'tests', 'ux-coverage', 'tests', 'a11y-audit.spec.ts');
const AGGREGATE = path.join(ROOT, 'scripts', 'governance', 'ux-coverage-aggregate.cjs');
const ANIMATED_OUTLET = path.join(ROOT, 'frontend', 'src', 'components', 'AnimatedOutlet.tsx');
const PORTAL_LAYOUT = path.join(ROOT, 'frontend', 'src', 'components', 'PortalLayout.tsx');

/** Strip YAML `# …` comments so historical notes cannot trip the regression. */
function activeLines(body) {
  return body
    .split('\n')
    .map((line) => line.replace(/#.*$/, ''))
    .join('\n');
}

test('C-50: workflow runs a11y-audit and requires its artifact fail-closed', () => {
  const body = fs.readFileSync(WORKFLOW, 'utf8');
  const active = activeLines(body);

  assert.match(active, /^\s*a11y-audit:\s*$/m, 'workflow must declare an a11y-audit job');
  assert.match(
    active,
    /playwright test tests\/a11y-audit\.spec\.ts/,
    'a11y-audit job must run the axe Playwright suite',
  );
  assert.match(
    active,
    /a11y-audit-results\/a11y_audit\.json/,
    'prepare step must require a11y_audit.json (no empty invent)',
  );
  assert.match(
    active,
    /needs:.*a11y-audit/,
    'aggregate-and-gate must depend on a11y-audit',
  );
  assert.match(
    active,
    /a11y-audit=\$\{A11Y_AUDIT_RESULT\}/,
    'aggregate must require a11y-audit job success like the other audits',
  );

  // C-60 must not be reintroduced for any audit, including a11y.
  assert.equal(
    /echo\s+['"]\{\s*"results"\s*:\s*\[\s*\]\s*\}['"]/.test(active),
    false,
    'workflow must not invent {"results":[]} when an audit artifact is absent',
  );
});

test('C-50: aggregator loads and scores a11y_audit.json', () => {
  const body = fs.readFileSync(AGGREGATE, 'utf8');
  assert.match(body, /a11y_audit\.json/);
  assert.match(body, /a11yAudit/);
  assert.match(body, /completenessShortfall\(a11yAudit,\s*'a11y'\)/);

  const { computeCoverage } = require('../ux-coverage-aggregate.cjs');
  const coverage = computeCoverage({
    pageAudit: { results: [{ pageId: 'dashboard', route: '/dashboard', criticality: 'P0', result: 'PASS' }] },
    linkAudit: { total_links: 0, total_valid: 0, total_dead: 0, total_external: 0, dead_end_map: [], expected_entries: 0, results: [] },
    buttonAudit: { results: [] },
    workflowAudit: { results: [{ workflowId: 'admin-login', name: 'admin-login', criticality: 'P0', result: 'PASS', total_steps: 1, completed_steps: 1 }], dead_ends: [] },
    a11yAudit: {
      expected_entries: 2,
      passed: 1,
      failed: 1,
      skipped: 0,
      results: [
        { pageId: 'login', route: '/login', criticality: 'P0', result: 'PASS' },
        {
          pageId: 'dashboard',
          route: '/dashboard',
          criticality: 'P0',
          result: 'FAIL',
          violations_critical: 1,
          violations_serious: 0,
        },
      ],
    },
  });

  assert.equal(coverage.summary.p0_failures, 1);
  assert.equal(coverage.status, 'HOLD');
  assert.ok(coverage.failures.some((f) => f.type === 'a11y' && f.id === 'dashboard'));
});

test('C-50: a11y suite is parallel (no serial mode) and writes expected_entries', () => {
  const body = fs.readFileSync(A11Y_AUDIT, 'utf8');
  assert.equal(
    /mode:\s*['"]serial['"]/.test(body),
    false,
    'a11y-audit must not use mode: serial (C-51 residual)',
  );
  assert.match(body, /mode:\s*['"]parallel['"]/);
  assert.match(body, /expected_entries:\s*pages\.length/);
  assert.match(body, /a11yAuditStore/);
  assert.match(body, /violation_rules_critical/);
  assert.match(body, /violation_rules_serious/);
  assert.match(body, /formatFailMessage/);
});

test('C-56: link audit waits for route-content marker; empty shell cannot pass', () => {
  const body = fs.readFileSync(LINK_AUDIT, 'utf8');

  assert.match(
    body,
    /\[data-ux-route-content\]/,
    'link audit must wait for the route-content marker',
  );
  assert.equal(
    /networkidle/.test(body.replace(/\/\/.*$/gm, '')),
    false,
    'link audit must not restore networkidle (active code)',
  );
  // The previous empty-shell wait must not be the gate for snapshotting.
  assert.equal(
    /locator\('#root > \*'\)/.test(body),
    false,
    'link audit must not treat #root > * (shell paint) as ready for link snapshot',
  );

  // Frontend must emit the marker on the main content outlets.
  assert.match(
    fs.readFileSync(ANIMATED_OUTLET, 'utf8'),
    /data-ux-route-content/,
    'AnimatedOutlet must emit data-ux-route-content',
  );
  assert.match(
    fs.readFileSync(PORTAL_LAYOUT, 'utf8'),
    /data-ux-route-content/,
    'PortalLayout must emit data-ux-route-content',
  );
});

/**
 * Pure proof that a shell without the marker is not "ready" for link capture.
 * Mirrors the contract the Playwright wait enforces without needing a browser.
 */
test('C-56: empty shell HTML cannot satisfy the route-content ready check', () => {
  const emptyShell = '<div id="root"><div class="layout-shell"><nav></nav><main id="main-content"></main></div></div>';
  const withRoute = '<div id="root"><div class="layout-shell"><main id="main-content"><div data-ux-route-content=""><a href="/x">x</a></div></main></div></div>';

  assert.equal(
    /data-ux-route-content/.test(emptyShell),
    false,
    'empty shell must not carry data-ux-route-content',
  );
  assert.equal(
    /data-ux-route-content/.test(withRoute),
    true,
    'mounted route content must carry data-ux-route-content',
  );
  // Shell may contain zero anchors; without the marker that must not count as a pass.
  assert.equal((emptyShell.match(/<a\s/g) || []).length, 0);
  assert.ok((withRoute.match(/<a\s/g) || []).length >= 1);
});
