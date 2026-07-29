'use strict';

/**
 * Unit tests for the UX coverage aggregator verdict.
 *
 * Run with: node --test scripts/governance/__tests__/
 *
 * The property under test is the one the gate is sold on: a run that did not
 * exercise its P0 coverage must not report GO, however clean its score looks.
 */

const test = require('node:test');
const assert = require('node:assert/strict');

const { computeCoverage } = require('../ux-coverage-aggregate.cjs');

function workflow(workflowId, result, extra = {}) {
  return {
    workflowId,
    name: workflowId,
    criticality: 'P0',
    result,
    total_steps: 1,
    completed_steps: result === 'PASS' ? 1 : 0,
    ...extra,
  };
}

function page(pageId, result, criticality = 'P0', extra = {}) {
  return { pageId, route: `/${pageId}`, criticality, result, ...extra };
}

function emptyLinkAudit() {
  return { total_links: 0, total_valid: 0, total_dead: 0, total_external: 0, dead_end_map: [] };
}

// A run in which every P0 workflow executed and passed.
function passingRun() {
  return {
    pageAudit: { results: [page('dashboard', 'PASS')] },
    linkAudit: emptyLinkAudit(),
    buttonAudit: { results: [] },
    workflowAudit: {
      results: [workflow('admin-login', 'PASS'), workflow('portal-incident-report', 'PASS')],
      dead_ends: [],
    },
  };
}

test('an all-skipped run does not report GO', () => {
  const coverage = computeCoverage({
    pageAudit: { results: [page('dashboard', 'SKIP', 'P0', { error_message: 'Auth type jwt_admin not configured' })] },
    linkAudit: emptyLinkAudit(),
    buttonAudit: { results: [] },
    workflowAudit: {
      results: [
        workflow('admin-login', 'SKIP', { error_message: 'Auth type jwt_admin not configured' }),
        workflow('portal-incident-report', 'SKIP', { error_message: 'Auth type portal_sso not configured' }),
      ],
      dead_ends: [],
    },
  });

  assert.equal(coverage.status, 'HOLD');
  assert.equal(coverage.coverage_complete, false);
  assert.equal(coverage.readiness.production, false);
  assert.equal(coverage.readiness.staging, false);

  // The pathology: nothing failed, so the old score stayed at 100.
  assert.equal(coverage.summary.p0_failures, 0);
  assert.equal(coverage.score, 100);

  // The two numbers that make it visible.
  assert.equal(coverage.p0_coverage.expected, 3);
  assert.equal(coverage.p0_coverage.executed, 0);
  assert.equal(coverage.p0_coverage.not_executed, 3);
  assert.equal(coverage.p0_coverage.execution_rate_pct, 0);
  assert.equal(coverage.p0_coverage.pass_rate_pct, null);

  // The failure message names the entries rather than leaving them to be
  // reverse-engineered from the artifact.
  assert.deepEqual(
    coverage.not_executed.map(e => e.id).sort(),
    ['admin-login', 'dashboard', 'portal-incident-report']
  );
  assert.match(coverage.hold_reasons.join(' '), /3 of 3 P0 entries did not execute/);
});

test('a run with one un-executed P0 does not report GO', () => {
  const coverage = computeCoverage({
    pageAudit: { results: [] },
    linkAudit: emptyLinkAudit(),
    buttonAudit: { results: [] },
    workflowAudit: {
      results: [
        workflow('admin-login', 'PASS'),
        workflow('admin-view-incident', 'PASS'),
        workflow('portal-rta-report', 'SKIP', { error_message: 'Auth type portal_sso not configured' }),
      ],
      dead_ends: [],
    },
  });

  assert.equal(coverage.status, 'HOLD');
  assert.equal(coverage.coverage_complete, false);
  assert.equal(coverage.summary.p0_failures, 0);
  assert.equal(coverage.score, 100);
  assert.equal(coverage.p0_coverage.executed, 2);
  assert.equal(coverage.p0_coverage.expected, 3);
  assert.equal(coverage.p0_coverage.not_executed, 1);

  // Executed and passed are reported separately: 2 of 3 ran, and both of those
  // passed. A single blended number would read as 100%.
  assert.equal(coverage.p0_coverage.execution_rate_pct, 66.7);
  assert.equal(coverage.p0_coverage.pass_rate_pct, 100);

  assert.deepEqual(coverage.not_executed.map(e => e.id), ['portal-rta-report']);
});

test('a genuinely fully-passing run still reports GO', () => {
  const coverage = computeCoverage(passingRun());

  assert.equal(coverage.status, 'GO');
  assert.equal(coverage.coverage_complete, true);
  assert.deepEqual(coverage.hold_reasons, []);
  assert.deepEqual(coverage.readiness, { staging: true, canary: true, production: true });
  assert.equal(coverage.score, 100);
  assert.equal(coverage.p0_coverage.executed, 3);
  assert.equal(coverage.p0_coverage.expected, 3);
  assert.equal(coverage.p0_coverage.execution_rate_pct, 100);
  assert.equal(coverage.p0_coverage.pass_rate_pct, 100);
  assert.deepEqual(coverage.not_executed, []);
});

test('an explicitly waived P0 leaves the denominator and is named in the report', () => {
  const coverage = computeCoverage({
    pageAudit: { results: [] },
    linkAudit: emptyLinkAudit(),
    buttonAudit: { results: [] },
    workflowAudit: {
      results: [
        workflow('admin-login', 'PASS'),
        workflow('portal-rta-report', 'SKIP', {
          waived: true,
          waiver_reason: 'RTA intake retired for Q3; removal tracked in PX-260',
        }),
      ],
      dead_ends: [],
    },
  });

  assert.equal(coverage.status, 'GO');
  assert.equal(coverage.p0_coverage.total, 2);
  assert.equal(coverage.p0_coverage.waived, 1);
  assert.equal(coverage.p0_coverage.expected, 1);
  assert.equal(coverage.p0_coverage.executed, 1);
  assert.equal(coverage.p0_coverage.execution_rate_pct, 100);
  assert.deepEqual(coverage.not_executed, []);
  assert.deepEqual(coverage.waivers, [{
    type: 'workflow',
    id: 'portal-rta-report',
    criticality: 'P0',
    reason: 'RTA intake retired for Q3; removal tracked in PX-260',
  }]);
});

test('a waiver without a stated reason is not a waiver', () => {
  const coverage = computeCoverage({
    workflowAudit: {
      results: [
        workflow('admin-login', 'PASS'),
        workflow('portal-rta-report', 'SKIP', { waived: true }),
        workflow('portal-near-miss-report', 'SKIP', { waived: true, waiver_reason: '   ' }),
      ],
      dead_ends: [],
    },
  });

  assert.equal(coverage.status, 'HOLD');
  assert.equal(coverage.p0_coverage.waived, 0);
  assert.equal(coverage.p0_coverage.not_executed, 2);
  assert.deepEqual(coverage.waivers, []);
  assert.deepEqual(
    coverage.not_executed.map(e => e.id).sort(),
    ['portal-near-miss-report', 'portal-rta-report']
  );
});

test('waiving every P0 does not clear the gate', () => {
  const coverage = computeCoverage({
    workflowAudit: {
      results: [
        workflow('admin-login', 'SKIP', { waived: true, waiver_reason: 'documented waiver A' }),
        workflow('portal-rta-report', 'SKIP', { waived: true, waiver_reason: 'documented waiver B' }),
      ],
      dead_ends: [],
    },
  });

  assert.equal(coverage.status, 'HOLD');
  assert.equal(coverage.coverage_complete, false);
  assert.equal(coverage.p0_coverage.expected, 0);
  assert.equal(coverage.p0_coverage.execution_rate_pct, null);
  assert.match(coverage.hold_reasons.join(' '), /All 2 P0 entries are waived/);
});

test('a waived entry that actually ran keeps its real result', () => {
  const coverage = computeCoverage({
    workflowAudit: {
      results: [
        workflow('admin-login', 'PASS'),
        workflow('portal-rta-report', 'FAIL', {
          waived: true,
          waiver_reason: 'known broken, waiver requested',
          error_message: 'Step 1 failed',
        }),
      ],
      dead_ends: [],
    },
  });

  assert.equal(coverage.status, 'HOLD');
  assert.equal(coverage.summary.p0_failures, 1);
  assert.equal(coverage.p0_coverage.waived, 0);
  assert.equal(coverage.p0_coverage.failed, 1);
  assert.match(coverage.hold_reasons.join(' '), /1 P0 failure/);
});

test('an empty results set is held, not scored as full compliance', () => {
  // What the gate job writes when every audit artifact is missing.
  const coverage = computeCoverage({
    pageAudit: { results: [] },
    linkAudit: { results: [], dead_end_map: [] },
    buttonAudit: { results: [] },
    workflowAudit: { results: [], dead_ends: [] },
  });

  assert.equal(coverage.status, 'HOLD');
  assert.equal(coverage.coverage_complete, false);
  assert.equal(coverage.p0_coverage.total, 0);
  assert.match(coverage.hold_reasons.join(' '), /No P0 entries were audited/);
  // A link audit with no total_dead must not poison the score with NaN.
  assert.equal(coverage.score, 100);
  assert.equal(Number.isFinite(coverage.summary.p1_failures), true);
});

test('no audit files at all is held', () => {
  const coverage = computeCoverage({});

  assert.equal(coverage.status, 'HOLD');
  assert.equal(coverage.coverage_complete, false);
  assert.equal(coverage.audits.page, null);
  assert.match(coverage.hold_reasons.join(' '), /No P0 entries were audited/);
});

test('an entry with no result at all counts as not executed', () => {
  const coverage = computeCoverage({
    workflowAudit: {
      results: [workflow('admin-login', 'PASS'), { workflowId: 'ghost', criticality: 'P0' }],
      dead_ends: [],
    },
  });

  assert.equal(coverage.status, 'HOLD');
  assert.equal(coverage.p0_coverage.not_executed, 1);
  assert.equal(coverage.not_executed[0].recorded_result, 'none');
});

test('P0 execution is enforced independently of the P1/P2 score', () => {
  // Score stays above the production threshold and no P0 fails, but a P0 never
  // ran. Score alone would have said GO.
  const coverage = computeCoverage({
    pageAudit: {
      results: [
        page('dashboard', 'SKIP', 'P0', { error_message: 'token missing' }),
        page('settings', 'PASS', 'P1'),
      ],
    },
    linkAudit: emptyLinkAudit(),
    buttonAudit: { results: [] },
    workflowAudit: { results: [workflow('admin-login', 'PASS')], dead_ends: [] },
  });

  assert.equal(coverage.score, 100);
  assert.equal(coverage.summary.p0_failures, 0);
  assert.equal(coverage.status, 'HOLD');
  assert.equal(coverage.p0_coverage.executed, 1);
  assert.equal(coverage.p0_coverage.expected, 2);
});

test('P1 execution is reported even though the gate turns on P0', () => {
  const coverage = computeCoverage({
    pageAudit: {
      results: [
        page('dashboard', 'PASS', 'P0'),
        page('settings', 'SKIP', 'P1', { error_message: 'token missing' }),
        page('reports', 'PASS', 'P1'),
      ],
    },
    linkAudit: emptyLinkAudit(),
    buttonAudit: { results: [] },
    workflowAudit: { results: [], dead_ends: [] },
  });

  assert.equal(coverage.status, 'GO');
  assert.equal(coverage.p1_coverage.executed, 1);
  assert.equal(coverage.p1_coverage.expected, 2);
  assert.equal(coverage.p1_coverage.not_executed, 1);
});

test('entries that never reached the artifact hold the gate', () => {
  // A serial suite that aborts, or a crashed worker, drops entries entirely:
  // there is no SKIP record to count, so per-entry accounting cannot see them.
  const coverage = computeCoverage({
    linkAudit: emptyLinkAudit(),
    workflowAudit: {
      expected_entries: 5,
      results: [workflow('admin-login', 'PASS'), workflow('admin-view-incident', 'PASS')],
      dead_ends: [],
    },
  });

  assert.equal(coverage.status, 'HOLD');
  assert.equal(coverage.coverage_complete, false);
  assert.equal(coverage.p0_coverage.not_executed, 0);
  assert.equal(coverage.p0_coverage.execution_rate_pct, 100);
  assert.match(
    coverage.hold_reasons.join(' '),
    /workflow audit produced 2 of 5 declared entries; 3 produced no result at all/
  );
});

test('a button audit that lost entries to a skipped serial suite holds the gate', () => {
  // The observed failure: BUTTON_REGISTRY declares 22 P0/P1 buttons, the first
  // one fails, serial mode skips the other 21, and `total_buttons` was computed
  // from the results array — so the 21 left the denominator instead of being
  // counted as unrun. Every surviving number looked healthy.
  const coverage = computeCoverage({
    linkAudit: emptyLinkAudit(),
    buttonAudit: {
      expected_entries: 22,
      results: [{
        pageId: 'portal-home',
        actionId: 'navigate-to-report',
        criticality: 'P0',
        result: 'FAIL',
        found: false,
        clicked: false,
        outcome_observed: false,
        error_message: 'P0 button not found',
      }],
    },
    workflowAudit: {
      expected_entries: 1,
      results: [workflow('admin-login', 'PASS')],
      dead_ends: [],
    },
  });

  assert.equal(coverage.status, 'HOLD');
  assert.equal(coverage.coverage_complete, false);
  assert.match(
    coverage.hold_reasons.join(' '),
    /button audit produced 1 of 22 declared entries; 21 produced no result at all/
  );
});

test('a button audit that lost entries while every entry it kept passed still holds the gate', () => {
  // The dangerous shape: nothing failed, nothing is recorded as skipped, the
  // score is 100 and the P0 pass rate is 100% — because the entries that would
  // have said otherwise never reached the artifact at all. Without the declared
  // count there is nothing left in the document to notice them by.
  const coverage = computeCoverage({
    linkAudit: emptyLinkAudit(),
    buttonAudit: {
      expected_entries: 22,
      results: [{
        pageId: 'portal-home',
        actionId: 'navigate-to-report',
        criticality: 'P0',
        result: 'PASS',
        found: true,
        clicked: true,
        outcome_observed: true,
      }],
    },
  });

  assert.equal(coverage.score, 100);
  assert.equal(coverage.summary.p0_failures, 0);
  assert.equal(coverage.p0_coverage.not_executed, 0);
  assert.equal(coverage.p0_coverage.execution_rate_pct, 100);
  assert.equal(coverage.p0_coverage.pass_rate_pct, 100);

  // ...and it is still not a pass.
  assert.equal(coverage.status, 'HOLD');
  assert.equal(coverage.coverage_complete, false);
  assert.deepEqual(coverage.readiness, { staging: false, canary: false, production: false });
  assert.match(
    coverage.hold_reasons.join(' '),
    /button audit produced 1 of 22 declared entries/
  );
});

test('a page audit whose parallel workers overwrote each other holds the gate', () => {
  // Two workers, one module-level array each, one artifact path: the last
  // afterAll to run wrote only its own half. 18 of 36 declared pages, all
  // passing, is what that looks like from the outside.
  const coverage = computeCoverage({
    pageAudit: {
      expected_entries: 36,
      results: Array.from({ length: 18 }, (_, i) => page(`page-${i}`, 'PASS', i === 0 ? 'P0' : 'P1')),
    },
    linkAudit: emptyLinkAudit(),
  });

  assert.equal(coverage.score, 100);
  assert.equal(coverage.summary.p0_failures, 0);
  assert.equal(coverage.status, 'HOLD');
  assert.equal(coverage.coverage_complete, false);
  assert.match(
    coverage.hold_reasons.join(' '),
    /page audit produced 18 of 36 declared entries; 18 produced no result at all/
  );
});

test('a link audit that lost pages holds the gate', () => {
  // The link audit contributes only total_dead to the score, and a page that
  // never reached the artifact contributes nothing to it — so a lost page is
  // indistinguishable from a clean one. It was also the one audit never passed
  // to the completeness guard at all.
  const coverage = computeCoverage({
    pageAudit: { expected_entries: 1, results: [page('dashboard', 'PASS')] },
    linkAudit: {
      expected_entries: 32,
      total_links: 40,
      total_valid: 40,
      total_dead: 0,
      total_external: 0,
      results: [{ source_page: 'portal-home', route: '/portal', total_links: 40, valid_links: 40, dead_links: 0, external_links: 0, links: [] }],
      dead_end_map: [],
    },
  });

  assert.equal(coverage.summary.p1_failures, 0);
  assert.equal(coverage.score, 100);
  assert.equal(coverage.status, 'HOLD');
  assert.equal(coverage.coverage_complete, false);
  assert.match(
    coverage.hold_reasons.join(' '),
    /link audit produced 1 of 32 declared entries; 31 produced no result at all/
  );
});

test('every audit that falls short is named, not just the first', () => {
  const coverage = computeCoverage({
    pageAudit: { expected_entries: 36, results: [page('dashboard', 'PASS')] },
    linkAudit: { expected_entries: 32, total_dead: 0, results: [], dead_end_map: [] },
    buttonAudit: { expected_entries: 22, results: [] },
    workflowAudit: { expected_entries: 5, results: [], dead_ends: [] },
  });

  assert.equal(coverage.status, 'HOLD');
  assert.equal(coverage.completeness_shortfalls.length, 4);
  assert.deepEqual(
    coverage.completeness_shortfalls.map(reason => reason.match(/The (\w+) audit/)[1]),
    ['page', 'link', 'button', 'workflow']
  );
});

test('an audit that declares its count and meets it is not held for completeness', () => {
  // The guard must not fire on a full artifact, or it stops meaning anything.
  const coverage = computeCoverage({
    pageAudit: { expected_entries: 2, results: [page('dashboard', 'PASS'), page('settings', 'PASS', 'P1')] },
    linkAudit: {
      expected_entries: 1,
      total_links: 1,
      total_valid: 1,
      total_dead: 0,
      total_external: 0,
      results: [{ source_page: 'dashboard', route: '/dashboard', total_links: 1, valid_links: 1, dead_links: 0, external_links: 0, links: [] }],
      dead_end_map: [],
    },
    buttonAudit: {
      expected_entries: 1,
      results: [{ pageId: 'dashboard', actionId: 'export', criticality: 'P1', result: 'PASS', clicked: true, outcome_observed: true }],
    },
    workflowAudit: { expected_entries: 1, results: [workflow('admin-login', 'PASS')], dead_ends: [] },
  });

  assert.deepEqual(coverage.completeness_shortfalls, []);
  assert.equal(coverage.status, 'GO');
});

test('more entries than declared is not a shortfall', () => {
  // A retry that recorded twice, or a registry read after the count was taken,
  // must not be reported as missing coverage.
  const coverage = computeCoverage({
    linkAudit: emptyLinkAudit(),
    workflowAudit: {
      expected_entries: 1,
      results: [workflow('admin-login', 'PASS'), workflow('admin-login', 'PASS')],
      dead_ends: [],
    },
  });

  assert.deepEqual(coverage.completeness_shortfalls, []);
  assert.equal(coverage.status, 'GO');
});

test('a complete artifact that meets its declared count still reports GO', () => {
  const coverage = computeCoverage({
    linkAudit: emptyLinkAudit(),
    workflowAudit: {
      expected_entries: 2,
      results: [workflow('admin-login', 'PASS'), workflow('admin-view-incident', 'PASS')],
      dead_ends: [],
    },
  });

  assert.equal(coverage.status, 'GO');
  assert.deepEqual(coverage.completeness_shortfalls, []);
});

test('a malformed artifact is held, not read as nothing to report', () => {
  const coverage = computeCoverage({
    pageAudit: { results: 'not-an-array' },
    workflowAudit: { results: [null, undefined, workflow('admin-login', 'PASS')], dead_ends: null },
    linkAudit: { dead_end_map: 'nope' },
  });

  assert.equal(coverage.status, 'GO', 'the one well-formed entry is still counted');
  assert.equal(coverage.p0_coverage.total, 1);
  assert.equal(coverage.summary.dead_ends_count, 0);

  // And with nothing well-formed at all, the gate holds.
  const nothing = computeCoverage({ workflowAudit: { results: [null, 7, 'x'] } });
  assert.equal(nothing.status, 'HOLD');
  assert.equal(nothing.p0_coverage.total, 0);
});

test('dead links still cost P1 points', () => {
  const coverage = computeCoverage({
    ...passingRun(),
    linkAudit: {
      total_links: 10,
      total_valid: 8,
      total_dead: 2,
      total_external: 0,
      dead_end_map: [{ source: '/a', href: '/b', error: '404' }],
    },
  });

  assert.equal(coverage.summary.p1_failures, 2);
  assert.equal(coverage.score, 80);
  assert.equal(coverage.status, 'HOLD');
  assert.equal(coverage.coverage_complete, true);
  assert.match(coverage.hold_reasons.join(' '), /below the staging threshold/);
});

test('button noop failures are still recorded as dead ends', () => {
  const coverage = computeCoverage({
    buttonAudit: {
      results: [{
        pageId: 'dashboard',
        actionId: 'export',
        criticality: 'P1',
        result: 'FAIL',
        clicked: true,
        outcome_observed: false,
      }],
    },
    workflowAudit: { results: [workflow('admin-login', 'PASS')], dead_ends: [] },
  });

  assert.equal(coverage.summary.dead_ends_count, 1);
  assert.equal(coverage.dead_ends[0].type, 'noop_button');
  assert.equal(coverage.summary.p1_failures, 1);
});
