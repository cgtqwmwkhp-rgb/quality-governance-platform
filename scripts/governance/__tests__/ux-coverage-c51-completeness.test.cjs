'use strict';

/**
 * C-51 (w4-gate-serial-skip-hides-21): the UX gate must not certify coverage it
 * never measured.
 *
 * The measured defect: BUTTON_REGISTRY declares 22 P0/P1 buttons, the button
 * suite ran under `mode: 'serial'`, the first entry failed, Playwright skipped
 * the other 21, and the artifact carried `total_buttons: 1` while the aggregator
 * certified P0 coverage complete. Missing entries left the numerator and the
 * denominator together, so nothing in the report could see them.
 *
 * Three properties close that, and this file locks all three so they cannot
 * regress quietly:
 *
 *   1. Every audit declares how many entries it was supposed to emit, and the
 *      aggregator holds the gate on every audit that falls short — including the
 *      link audit, which was never passed to the guard at all.
 *   2. No audit suite aborts its remaining entries on the first failure, and
 *      results are merged per worker rather than accumulated in a module-level
 *      array that the last `afterAll` overwrites.
 *   3. An entry that arrived but recorded no measurement is held on the same
 *      footing as an entry that never arrived. This is the part that was still
 *      open: the link audit's entries carry link counts rather than a P0/P1
 *      result, so a page that skipped for want of a token reported zero dead
 *      links — byte-for-byte what a clean page reports.
 *
 * Run with:
 *   node --test scripts/governance/__tests__/ux-coverage-c51-completeness.test.cjs
 */

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const { computeCoverage } = require('../ux-coverage-aggregate.cjs');

const ROOT = path.join(__dirname, '..', '..', '..');
const AGGREGATE = path.join(ROOT, 'scripts', 'governance', 'ux-coverage-aggregate.cjs');
const UX_DIR = path.join(ROOT, 'tests', 'ux-coverage');
const SPEC_DIR = path.join(UX_DIR, 'tests');
const ENTRY_STORE = path.join(UX_DIR, 'utils', 'audit-entries.ts');
const GLOBAL_SETUP = path.join(UX_DIR, 'global-setup.ts');
const PW_CONFIG = path.join(UX_DIR, 'playwright.config.ts');

/**
 * Every audit that feeds the gate, with the registry expression each one must
 * declare its entry count from. a11y is included: C-50 made it a required audit,
 * so it inherits the same completeness obligation as the other four.
 */
const AUDITS = [
  { name: 'page', spec: 'page-audit.spec.ts', declares: /expected_entries:\s*pages\.length/ },
  { name: 'link', spec: 'link-audit.spec.ts', declares: /expected_entries:\s*pages\.length/ },
  { name: 'button', spec: 'button-audit.spec.ts', declares: /expected_entries:\s*buttons\.length/ },
  { name: 'workflow', spec: 'workflow-audit.spec.ts', declares: /expected_entries:\s*workflows\.length/ },
  { name: 'a11y', spec: 'a11y-audit.spec.ts', declares: /expected_entries:\s*pages\.length/ },
];

function readSpec(name) {
  return fs.readFileSync(path.join(SPEC_DIR, name), 'utf8');
}

/** Strip line and block comments so a historical note cannot satisfy a check. */
function activeCode(body) {
  return body.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '');
}

function page(pageId, result, criticality = 'P0') {
  return { pageId, route: `/${pageId}`, criticality, result };
}

/** A link audit page that was measured and found clean. */
function measuredPage(sourcePage, deadLinks = 0) {
  return {
    source_page: sourcePage,
    route: `/${sourcePage}`,
    total_links: 4,
    valid_links: 4 - deadLinks,
    dead_links: deadLinks,
    external_links: 0,
    links: [],
  };
}

/** A link audit page that produced an entry but no measurement. */
function unmeasuredPage(sourcePage, reason = 'Auth type portal_sso not configured') {
  return {
    source_page: sourcePage,
    route: `/${sourcePage}`,
    total_links: 0,
    valid_links: 0,
    dead_links: 0,
    external_links: 0,
    links: [],
    skipped_reason: reason,
  };
}

// ---------------------------------------------------------------------------
// 1. Declared counts, and the guard that reads them
// ---------------------------------------------------------------------------

test('C-51: every audit spec declares how many entries it should emit', () => {
  for (const audit of AUDITS) {
    assert.match(
      readSpec(audit.spec),
      audit.declares,
      `${audit.name} audit must declare expected_entries from its registry length, ` +
        'or a lost entry leaves the denominator with nothing to notice it by',
    );
  }
});

test('C-51: the aggregator checks all five audits for a shortfall, link included', () => {
  const body = fs.readFileSync(AGGREGATE, 'utf8');
  for (const audit of AUDITS) {
    assert.match(
      body,
      new RegExp(`completenessShortfall\\(${audit.name}Audit,\\s*'${audit.name}'\\)`),
      `${audit.name} audit must be passed to the completeness guard`,
    );
  }
});

test('C-51: 1 of 22 declared buttons cannot report coverage complete', () => {
  // The defect exactly as measured, with the shape that makes it dangerous:
  // the single surviving entry passed, so nothing in the score, the failure
  // count or the P0 pass rate says anything is wrong.
  const coverage = computeCoverage({
    pageAudit: { expected_entries: 1, results: [page('login', 'PASS')] },
    linkAudit: { expected_entries: 0, total_dead: 0, results: [], dead_end_map: [] },
    buttonAudit: {
      expected_entries: 22,
      total_buttons: 1,
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

  assert.equal(coverage.summary.p0_failures, 0);
  assert.equal(coverage.p0_coverage.execution_rate_pct, 100);
  assert.equal(coverage.p0_coverage.pass_rate_pct, 100);

  assert.equal(coverage.coverage_complete, false);
  assert.equal(coverage.status, 'HOLD');
  assert.match(
    coverage.hold_reasons.join(' '),
    /button audit produced 1 of 22 declared entries; 21 produced no result at all/,
  );
});

// ---------------------------------------------------------------------------
// 2. No suite abandons its remaining entries; results are merged per worker
// ---------------------------------------------------------------------------

test('C-51: no audit suite runs in serial mode', () => {
  // Under `mode: 'serial'` the first failure skips every remaining test in the
  // group, and those tests then produce no entry to classify.
  for (const audit of AUDITS) {
    assert.equal(
      /mode:\s*['"]serial['"]/.test(activeCode(readSpec(audit.spec))),
      false,
      `${audit.name} audit must not run in serial mode: one failure would abandon the rest`,
    );
  }
});

test('C-51: every audit merges per-entry files instead of a module-level array', () => {
  // Playwright runs `fullyParallel` groups across worker processes and retires a
  // worker after a failure. A module-level array plus one `afterAll` therefore
  // gives each worker its own half of the results and lets the last writer win.
  for (const audit of AUDITS) {
    const body = activeCode(readSpec(audit.spec));
    assert.match(
      body,
      /readAll<|readWorkflowAuditEntries</,
      `${audit.name} audit must build its artifact by reading the entry directory`,
    );
    assert.equal(
      /\bconst\s+results\s*:\s*\w+\[\]\s*=\s*\[\]/.test(body),
      false,
      `${audit.name} audit must not accumulate results in a module-level array`,
    );
  }
});

test('C-51: the entry store makes each entry a separate file with a unique name', () => {
  const body = fs.readFileSync(ENTRY_STORE, 'utf8');

  // A readable-only filename is lossy — `a::b` and `a__b` both sanitise to
  // `a__b` — and two entries collapsing into one file silently shrinks the
  // artifact, which is the failure this store exists to prevent.
  assert.match(body, /createHash\(['"]sha1['"]\)/, 'entry filenames must carry a digest of the id');
  // Rename is atomic on POSIX, so a merge in another worker can only ever read a
  // complete entry file.
  assert.match(body, /renameSync/, 'entry writes must land atomically');
  for (const audit of AUDITS) {
    assert.match(
      body,
      new RegExp(`${audit.name === 'a11y' ? 'a11y' : audit.name}AuditStore`),
      `${audit.name} audit must have an entry store`,
    );
  }
});

test('C-51: the previous run\'s entries are cleared once, before any worker', () => {
  assert.match(
    fs.readFileSync(PW_CONFIG, 'utf8'),
    /globalSetup:\s*['"]\.\/global-setup\.ts['"]/,
    'playwright config must wire the global setup that clears stale entries',
  );
  const setup = fs.readFileSync(GLOBAL_SETUP, 'utf8');
  assert.match(setup, /ALL_AUDIT_STORES/, 'global setup must clear every audit store');
  assert.match(setup, /\.clear\(\)/);
});

// ---------------------------------------------------------------------------
// 3. An entry that recorded no measurement is not a clean entry
// ---------------------------------------------------------------------------

test('C-51: a link audit whose pages all skipped cannot report GO', () => {
  // Measured against the aggregator before this fix: status GO, score 100,
  // coverage_complete true, zero dead links — from 32 pages that reported, in
  // their own words, that they could not be audited. The declared-count guard
  // passes because all 32 entries are present; the entries carry no P0/P1
  // result, so per-entry accounting never classifies them either.
  const pages = Array.from({ length: 32 }, (_, i) => unmeasuredPage(`portal-page-${i}`));
  const coverage = computeCoverage({
    pageAudit: { expected_entries: 1, results: [page('login', 'PASS')] },
    linkAudit: {
      expected_entries: 32,
      total_links: 0,
      total_valid: 0,
      total_dead: 0,
      total_external: 0,
      pages_skipped: 32,
      results: pages,
      dead_end_map: [],
    },
  });

  assert.equal(coverage.summary.p1_failures, 0, 'the pathology: nothing was found wrong');
  assert.equal(coverage.score, 100);

  assert.equal(coverage.status, 'HOLD');
  assert.equal(coverage.coverage_complete, false);
  assert.equal(coverage.unmeasured_entries.length, 32);
  assert.match(
    coverage.hold_reasons.join(' '),
    /link audit recorded no link evidence for 32 of 32 pages/,
  );
});

test('C-51: a single unmeasured page is held and named', () => {
  const coverage = computeCoverage({
    pageAudit: { expected_entries: 1, results: [page('login', 'PASS')] },
    linkAudit: {
      expected_entries: 3,
      total_links: 8,
      total_valid: 8,
      total_dead: 0,
      total_external: 0,
      results: [measuredPage('dashboard'), measuredPage('incidents-list'), unmeasuredPage('portal-home')],
      dead_end_map: [],
    },
  });

  assert.equal(coverage.status, 'HOLD');
  assert.equal(coverage.coverage_complete, false);
  assert.deepEqual(coverage.unmeasured_entries.map(entry => entry.id), ['portal-home']);
  assert.equal(coverage.unmeasured_entries[0].reason, 'Auth type portal_sso not configured');
  assert.match(
    coverage.hold_reasons.join(' '),
    /recorded no link evidence for 1 of 3 pages \(portal-home\)/,
  );
});

test('C-51: the unmeasured-page hold names a bounded list, not all 32 ids', () => {
  // Hold reasons are flattened onto a single GITHUB_OUTPUT line, so a run that
  // skipped everything must not push the other reasons off the summary.
  const coverage = computeCoverage({
    pageAudit: { expected_entries: 1, results: [page('login', 'PASS')] },
    linkAudit: {
      expected_entries: 14,
      total_dead: 0,
      results: Array.from({ length: 14 }, (_, i) => unmeasuredPage(`p${i}`)),
      dead_end_map: [],
    },
  });

  const reason = coverage.hold_reasons.find(r => r.includes('no link evidence'));
  assert.match(reason, /p0, p1, p2, p3, p4, p5, p6, p7, p8, p9 and 4 more/);
  assert.equal(/\bp10\b/.test(reason), false);
});

test('C-51: a fully measured link audit is not held by the unmeasured rule', () => {
  // The guard must not fire on a complete artifact, or it stops meaning
  // anything and invites being switched off.
  const coverage = computeCoverage({
    pageAudit: { expected_entries: 1, results: [page('login', 'PASS')] },
    linkAudit: {
      expected_entries: 2,
      total_links: 8,
      total_valid: 8,
      total_dead: 0,
      total_external: 0,
      results: [measuredPage('dashboard'), measuredPage('incidents-list')],
      dead_end_map: [],
    },
  });

  assert.deepEqual(coverage.unmeasured_entries, []);
  assert.equal(coverage.coverage_complete, true);
  assert.equal(coverage.status, 'GO');
});

test('C-51: an empty skipped_reason is not treated as a skip', () => {
  // A blank string is not a stated reason, and must not be able to hold a page
  // that was in fact measured.
  const coverage = computeCoverage({
    pageAudit: { expected_entries: 1, results: [page('login', 'PASS')] },
    linkAudit: {
      expected_entries: 1,
      total_dead: 0,
      results: [{ ...measuredPage('dashboard'), skipped_reason: '   ' }],
      dead_end_map: [],
    },
  });

  assert.deepEqual(coverage.unmeasured_entries, []);
  assert.equal(coverage.status, 'GO');
});

test('C-51: an unmeasured page is still reported when a real P0 failure exists', () => {
  // The two are independent absences: a P0 failure must not consume the
  // completeness finding, and the report must carry both.
  const coverage = computeCoverage({
    pageAudit: { expected_entries: 2, results: [page('login', 'PASS'), page('dashboard', 'FAIL')] },
    linkAudit: {
      expected_entries: 2,
      total_dead: 0,
      results: [measuredPage('login'), unmeasuredPage('portal-home')],
      dead_end_map: [],
    },
  });

  assert.equal(coverage.summary.p0_failures, 1);
  assert.equal(coverage.coverage_complete, false);
  const reasons = coverage.hold_reasons.join(' ');
  assert.match(reasons, /no link evidence for 1 of 2 pages/);
  assert.match(reasons, /1 P0 failure\(s\) detected/);
});

test('C-51: the report names the pages that produced no measurement', () => {
  const { generateMarkdown } = require('../ux-coverage-aggregate.cjs');
  const coverage = computeCoverage({
    pageAudit: { expected_entries: 1, results: [page('login', 'PASS')] },
    linkAudit: {
      expected_entries: 2,
      total_dead: 0,
      results: [measuredPage('login'), unmeasuredPage('portal-home')],
      dead_end_map: [],
    },
  });

  const md = generateMarkdown(coverage);
  assert.match(md, /## Pages With No Link Evidence/);
  assert.match(md, /portal-home/);
  assert.match(md, /Auth type portal_sso not configured/);
});
