#!/usr/bin/env node

/**
 * UX Coverage Aggregation Script
 *
 * Aggregates results from:
 * - page_audit.json
 * - link_audit.json
 * - button_audit.json
 * - workflow_audit.json
 *
 * Outputs:
 * - ux_coverage.json (machine-readable)
 * - ux_coverage.md (human-readable)
 * - ux_dead_end_map.md (dead ends only)
 *
 * Scoring:
 * - Start at 100
 * - P0 fail => HOLD (score irrelevant)
 * - P1 fail => -10 each
 * - P2 fail => -2 each
 *
 * Thresholds:
 * - staging READY: >=85, P0=0
 * - canary expand: >=90, P0=0, P1 stable
 * - prod promote: >=95, P0=0, <=1 P1
 *
 * P0 EXECUTION COVERAGE (PX-179):
 * The score above says nothing about whether anything actually ran. An audit
 * entry that skipped — no token, unreachable host, spec crashed before it got
 * there — used to fall through to the "skipped" bucket, cost nothing, and leave
 * the score at 100 with zero P0 failures. A run that exercised no P0 coverage at
 * all was therefore indistinguishable from a run that passed every P0.
 *
 * The rule now enforced: a run that did not exercise its P0 coverage cannot
 * report GO. Absence of evidence is not evidence of compliance. Two numbers are
 * reported separately so a blended score can never hide this again:
 *   - execution rate: P0 entries that produced PASS or FAIL, over P0 entries in
 *     scope (i.e. excluding explicitly waived entries)
 *   - pass rate:      P0 entries that passed, over P0 entries that executed
 *
 * WAIVERS:
 * An entry is excluded from the execution denominator only if it carries BOTH
 * `waived: true` AND a non-empty `waiver_reason`. Requiring the reason means a
 * stray boolean cannot silently delete coverage, and every waiver is named in
 * the report. No registry in docs/ops/ defines a waiver field today, so in
 * practice nothing is waived and every non-executing P0 blocks the gate; the
 * handling exists so that when a justified waiver is introduced the aggregator
 * already treats it as a deliberate exclusion rather than a silent skip.
 */

const fs = require('fs');
const path = require('path');

// Configuration
const RESULTS_DIR = process.env.RESULTS_DIR || path.join(__dirname, '../../tests/ux-coverage/results');
const OUTPUT_DIR = process.env.OUTPUT_DIR || path.join(__dirname, '../../artifacts');

// Scoring weights
const SCORE_START = 100;
const P1_PENALTY = 10;
const P2_PENALTY = 2;

// Thresholds
const THRESHOLDS = {
  staging_ready: { min_score: 85, max_p0: 0 },
  canary_expand: { min_score: 90, max_p0: 0, max_p1: 3 },
  prod_promote: { min_score: 95, max_p0: 0, max_p1: 1 },
};

const CRITICALITIES = ['P0', 'P1', 'P2'];

// Load JSON files
function loadJson(filename) {
  const filepath = path.join(RESULTS_DIR, filename);
  if (fs.existsSync(filepath)) {
    return JSON.parse(fs.readFileSync(filepath, 'utf-8'));
  }
  return null;
}

// A malformed artifact must not be read as "nothing to report": anything that
// is not a list of objects yields no entries, which the P0 execution rule then
// holds on.
function entriesOf(audit) {
  if (!audit || !Array.isArray(audit.results)) return [];
  return audit.results.filter(entry => entry && typeof entry === 'object');
}

// Anything that is not an explicit P0/P1 is scored as P2, matching the penalty
// table above.
function normaliseCriticality(value) {
  return CRITICALITIES.includes(value) ? value : 'P2';
}

// A waiver must be deliberate and justified: the marker alone is not enough.
function isWaived(entry) {
  if (entry.waived !== true) return false;
  const reason = typeof entry.waiver_reason === 'string' ? entry.waiver_reason.trim() : '';
  return reason.length > 0;
}

// PASS / FAIL / WAIVED / NOT_EXECUTED. A waiver never overrides a real result:
// if the entry ran, its result stands.
function classifyEntry(entry) {
  if (entry.result === 'PASS') return 'PASS';
  if (entry.result === 'FAIL') return 'FAIL';
  if (isWaived(entry)) return 'WAIVED';
  return 'NOT_EXECUTED';
}

function emptyCoverage() {
  const coverage = {};
  for (const criticality of CRITICALITIES) {
    coverage[criticality] = {
      total: 0,
      executed: 0,
      passed: 0,
      failed: 0,
      waived: 0,
      not_executed: 0,
    };
  }
  return coverage;
}

/**
 * An audit may declare how many entries it was supposed to emit. If fewer
 * arrive — a worker crashed, a serial suite aborted, the file was truncated —
 * the missing entries are invisible to the per-entry accounting below, because
 * there is no entry to classify. Returns a hold reason, or null.
 */
function completenessShortfall(audit, label) {
  if (!audit) return null;
  const expected = Number(audit.expected_entries);
  if (!Number.isFinite(expected)) return null;
  const actual = entriesOf(audit).length;
  if (actual >= expected) return null;
  return `The ${label} audit produced ${actual} of ${expected} declared entries; ` +
    `${expected - actual} produced no result at all.`;
}

function percentage(numerator, denominator) {
  if (denominator <= 0) return null;
  return Math.round((numerator / denominator) * 1000) / 10;
}

// Turn a per-criticality tally into the reportable execution/pass split.
function summariseCriticality(tally) {
  const expected = tally.total - tally.waived;
  const notExecuted = expected - tally.executed;
  return {
    total: tally.total,
    waived: tally.waived,
    expected,
    executed: tally.executed,
    passed: tally.passed,
    failed: tally.failed,
    not_executed: notExecuted,
    execution_rate_pct: percentage(tally.executed, expected),
    pass_rate_pct: percentage(tally.passed, tally.executed),
    complete: expected > 0 && notExecuted === 0,
  };
}

/**
 * Pure aggregation. Takes already-parsed audit payloads and returns the
 * coverage document plus the hold reasons that decided the verdict. No IO, so
 * it can be unit tested directly.
 */
function computeCoverage({ pageAudit, linkAudit, buttonAudit, workflowAudit } = {}) {
  let p0Fails = 0;
  let p1Fails = 0;
  let p2Fails = 0;
  let totalPassed = 0;
  let totalFailed = 0;
  let totalSkipped = 0;

  const failureDetails = [];
  const deadEnds = [];
  const notExecuted = [];
  const waivers = [];
  const coverage = emptyCoverage();

  // Records one audit entry against the coverage tallies. `describe` supplies
  // the reporting identity for the entry so the failure message can name it.
  function record(entry, type, describe) {
    const criticality = normaliseCriticality(entry.criticality);
    const tally = coverage[criticality];
    const outcome = classifyEntry(entry);
    tally.total++;

    if (outcome === 'PASS') {
      tally.executed++;
      tally.passed++;
      totalPassed++;
    } else if (outcome === 'FAIL') {
      tally.executed++;
      tally.failed++;
      totalFailed++;
      if (criticality === 'P0') p0Fails++;
      else if (criticality === 'P1') p1Fails++;
      else p2Fails++;
      failureDetails.push({ type, criticality, ...describe(entry) });
    } else if (outcome === 'WAIVED') {
      tally.waived++;
      totalSkipped++;
      waivers.push({
        type,
        id: describe(entry).id,
        criticality,
        reason: entry.waiver_reason.trim(),
      });
    } else {
      tally.not_executed++;
      totalSkipped++;
      notExecuted.push({
        type,
        id: describe(entry).id,
        criticality,
        recorded_result: entry.result || 'none',
        reason: entry.error_message || 'no result recorded',
      });
    }

    return outcome;
  }

  // Process page audit
  if (pageAudit) {
    entriesOf(pageAudit).forEach(r => {
      record(r, 'page', entry => ({
        id: entry.pageId,
        route: entry.route,
        error: entry.error_message,
      }));
    });
  }

  // Process link audit
  if (linkAudit) {
    (Array.isArray(linkAudit.dead_end_map) ? linkAudit.dead_end_map : []).forEach(de => {
      deadEnds.push({
        source: de.source,
        href: de.href,
        type: 'broken_link',
        error: de.error,
      });
    });
    // Dead links contribute to P1 failures. A malformed or absent count used to
    // poison the score with NaN; an absent link audit is now caught by the P0
    // execution rule instead of by accident.
    const deadLinks = Number(linkAudit.total_dead);
    p1Fails += Number.isFinite(deadLinks) ? deadLinks : 0;
  }

  // Process button audit
  if (buttonAudit) {
    entriesOf(buttonAudit).forEach(r => {
      const outcome = record(r, 'button', entry => ({
        id: `${entry.pageId}::${entry.actionId}`,
        error: entry.error_message,
        noop: !entry.outcome_observed && entry.clicked,
      }));
      if (outcome === 'FAIL' && !r.outcome_observed && r.clicked) {
        deadEnds.push({
          source: r.pageId,
          href: r.actionId,
          type: 'noop_button',
          error: 'Button click has no observable effect',
        });
      }
    });
  }

  // Process workflow audit
  if (workflowAudit) {
    entriesOf(workflowAudit).forEach(r => {
      record(r, 'workflow', entry => ({
        id: entry.workflowId,
        name: entry.name,
        completed_steps: entry.completed_steps,
        total_steps: entry.total_steps,
        error: entry.error_message,
      }));
    });

    // Add workflow dead ends
    if (Array.isArray(workflowAudit.dead_ends)) {
      workflowAudit.dead_ends.forEach(de => {
        deadEnds.push({
          source: de.workflowId,
          href: `step_${de.failed_at_step}`,
          type: 'stranded_workflow',
          error: de.error,
        });
      });
    }
  }

  // Calculate score
  let score = SCORE_START;
  score -= p1Fails * P1_PENALTY;
  score -= p2Fails * P2_PENALTY;
  score = Math.max(0, score);

  const p0Coverage = summariseCriticality(coverage.P0);
  const p1Coverage = summariseCriticality(coverage.P1);
  const p2Coverage = summariseCriticality(coverage.P2);

  // The gate may only clear if the P0 coverage was actually exercised. Zero P0
  // entries in scope means the run proved nothing, which is not a pass.
  const holdReasons = [];
  const shortfalls = [
    completenessShortfall(pageAudit, 'page'),
    completenessShortfall(buttonAudit, 'button'),
    completenessShortfall(workflowAudit, 'workflow'),
  ].filter(Boolean);
  holdReasons.push(...shortfalls);

  if (p0Coverage.expected === 0) {
    holdReasons.push(
      p0Coverage.total === 0
        ? 'No P0 entries were audited: this run exercised no P0 coverage.'
        : `All ${p0Coverage.total} P0 entries are waived: this run exercised no P0 coverage.`
    );
  } else if (p0Coverage.not_executed > 0) {
    holdReasons.push(
      `${p0Coverage.not_executed} of ${p0Coverage.expected} P0 entries did not execute.`
    );
  }
  const coverageComplete = holdReasons.length === 0;

  if (p0Fails > 0) {
    holdReasons.push(`${p0Fails} P0 failure(s) detected.`);
  }

  // Determine status
  let status = 'HOLD';
  const readiness = {
    staging: false,
    canary: false,
    production: false,
  };

  if (coverageComplete && p0Fails === 0) {
    if (score >= THRESHOLDS.prod_promote.min_score && p1Fails <= THRESHOLDS.prod_promote.max_p1) {
      status = 'GO';
      readiness.staging = true;
      readiness.canary = true;
      readiness.production = true;
    } else if (score >= THRESHOLDS.canary_expand.min_score && p1Fails <= THRESHOLDS.canary_expand.max_p1) {
      status = 'CANARY';
      readiness.staging = true;
      readiness.canary = true;
    } else if (score >= THRESHOLDS.staging_ready.min_score) {
      status = 'STAGING';
      readiness.staging = true;
    }
  }

  if (status === 'HOLD' && holdReasons.length === 0) {
    holdReasons.push(`Score ${score} is below the staging threshold of ${THRESHOLDS.staging_ready.min_score}.`);
  }

  return {
    version: '1.1',
    timestamp: new Date().toISOString(),
    score,
    status,
    readiness,
    coverage_complete: coverageComplete,
    hold_reasons: holdReasons,
    completeness_shortfalls: shortfalls,
    summary: {
      total_passed: totalPassed,
      total_failed: totalFailed,
      total_skipped: totalSkipped,
      p0_failures: p0Fails,
      p1_failures: p1Fails,
      p2_failures: p2Fails,
      dead_ends_count: deadEnds.length,
      p0_expected: p0Coverage.expected,
      p0_executed: p0Coverage.executed,
      p0_not_executed: p0Coverage.not_executed,
      p0_waived: p0Coverage.waived,
    },
    p0_coverage: p0Coverage,
    p1_coverage: p1Coverage,
    p2_coverage: p2Coverage,
    thresholds: THRESHOLDS,
    audits: {
      page: pageAudit ? {
        passed: pageAudit.passed,
        failed: pageAudit.failed,
        skipped: pageAudit.skipped,
      } : null,
      link: linkAudit ? {
        total_links: linkAudit.total_links,
        valid: linkAudit.total_valid,
        dead: linkAudit.total_dead,
        external: linkAudit.total_external,
      } : null,
      button: buttonAudit ? {
        passed: buttonAudit.passed,
        failed: buttonAudit.failed,
        skipped: buttonAudit.skipped,
        noop_count: buttonAudit.noop_buttons,
      } : null,
      workflow: workflowAudit ? {
        passed: workflowAudit.passed,
        failed: workflowAudit.failed,
        skipped: workflowAudit.skipped,
        dead_ends: workflowAudit.dead_ends?.length || 0,
      } : null,
    },
    failures: failureDetails,
    not_executed: notExecuted,
    waivers,
    dead_ends: deadEnds,
  };
}

// Main aggregation
function aggregate() {
  console.log('📊 UX Coverage Aggregation');
  console.log('='.repeat(50));

  const coverage = computeCoverage({
    pageAudit: loadJson('page_audit.json'),
    linkAudit: loadJson('link_audit.json'),
    buttonAudit: loadJson('button_audit.json'),
    workflowAudit: loadJson('workflow_audit.json'),
  });

  const p0 = coverage.p0_coverage;

  // Ensure output directory exists
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });

  // Write JSON
  fs.writeFileSync(
    path.join(OUTPUT_DIR, 'ux_coverage.json'),
    JSON.stringify(coverage, null, 2)
  );

  // Write Markdown report
  const md = generateMarkdown(coverage);
  fs.writeFileSync(path.join(OUTPUT_DIR, 'ux_coverage.md'), md);

  // Write dead end map
  const deadEndMd = generateDeadEndMap(coverage);
  fs.writeFileSync(path.join(OUTPUT_DIR, 'ux_dead_end_map.md'), deadEndMd);

  // Console output
  console.log(`\n📈 Score: ${coverage.score}/100`);
  console.log(`📊 Status: ${coverage.status}`);
  console.log(`\n🎯 P0 executed: ${p0.executed}/${p0.expected} (${formatRate(p0.execution_rate_pct)})`);
  console.log(`🎯 P0 passed:   ${p0.passed}/${p0.executed} (${formatRate(p0.pass_rate_pct)})`);
  if (p0.waived > 0) {
    console.log(`🪧 P0 waived:   ${p0.waived} (excluded from the execution denominator)`);
  }
  console.log(`\n✅ Passed: ${coverage.summary.total_passed}`);
  console.log(`❌ Failed: ${coverage.summary.total_failed} (P0: ${coverage.summary.p0_failures}, P1: ${coverage.summary.p1_failures}, P2: ${coverage.summary.p2_failures})`);
  console.log(`⏭️  Not executed: ${coverage.summary.total_skipped}`);
  console.log(`🚧 Dead Ends: ${coverage.summary.dead_ends_count}`);
  console.log(`\n📁 Output written to: ${OUTPUT_DIR}`);

  if (coverage.status === 'HOLD') {
    console.log('\n🛑 HOLD');
    coverage.hold_reasons.forEach(reason => console.log(`   - ${reason}`));
    if (coverage.not_executed.length > 0) {
      console.log('\n   Entries that did not execute:');
      coverage.not_executed.forEach(entry => {
        console.log(`   - [${entry.criticality}] ${entry.type} ${entry.id}: ${entry.reason}`);
      });
    }
    if (coverage.waivers.length > 0) {
      console.log('\n   Entries excluded by an explicit waiver:');
      coverage.waivers.forEach(entry => {
        console.log(`   - [${entry.criticality}] ${entry.type} ${entry.id}: ${entry.reason}`);
      });
    }
    process.exit(1);
  }

  const ready = Object.entries(coverage.readiness).filter(([, v]) => v).map(([k]) => k).join(', ');
  console.log(`\n✅ ${coverage.status}: Ready for ${ready}`);
  process.exit(0);
}

function formatRate(rate) {
  return rate === null ? 'n/a' : `${rate}%`;
}

// Generate Markdown report
function generateMarkdown(coverage) {
  const p0 = coverage.p0_coverage;
  const lines = [
    '# UX Functional Coverage Report',
    '',
    `**Generated:** ${coverage.timestamp}`,
    `**Score:** ${coverage.score}/100`,
    `**Status:** ${coverage.status}`,
    '',
    '## P0 Coverage',
    '',
    'Execution and pass rates are reported separately: a high pass rate over a',
    'small number of executed entries is not compliance.',
    '',
    '| Metric | Value |',
    '|--------|-------|',
    `| P0 entries in scope | ${p0.expected} |`,
    `| P0 executed | ${p0.executed} / ${p0.expected} (${formatRate(p0.execution_rate_pct)}) |`,
    `| P0 passed | ${p0.passed} / ${p0.executed} (${formatRate(p0.pass_rate_pct)}) |`,
    `| P0 did not execute | ${p0.not_executed} |`,
    `| P0 explicitly waived | ${p0.waived} |`,
    `| P0 coverage complete | ${p0.complete ? '✅' : '❌'} |`,
    '',
    `**P1 executed:** ${coverage.p1_coverage.executed} / ${coverage.p1_coverage.expected} · ` +
      `**P2 executed:** ${coverage.p2_coverage.executed} / ${coverage.p2_coverage.expected}`,
    '',
  ];

  if (coverage.hold_reasons.length > 0) {
    lines.push('## Why This Run Is Held');
    lines.push('');
    coverage.hold_reasons.forEach(reason => lines.push(`- ${reason}`));
    lines.push('');
  }

  if (coverage.not_executed.length > 0) {
    lines.push('## Entries That Did Not Execute');
    lines.push('');
    lines.push('| Type | ID | Criticality | Recorded Result | Reason |');
    lines.push('|------|----|-------------|-----------------|--------|');
    coverage.not_executed.forEach(entry => {
      lines.push(`| ${entry.type} | ${entry.id} | ${entry.criticality} | ${entry.recorded_result} | ${String(entry.reason).slice(0, 80)} |`);
    });
    lines.push('');
  }

  if (coverage.waivers.length > 0) {
    lines.push('## Explicit Waivers');
    lines.push('');
    lines.push('These entries were excluded from the execution denominator.');
    lines.push('');
    lines.push('| Type | ID | Criticality | Waiver Reason |');
    lines.push('|------|----|-------------|---------------|');
    coverage.waivers.forEach(entry => {
      lines.push(`| ${entry.type} | ${entry.id} | ${entry.criticality} | ${String(entry.reason).slice(0, 80)} |`);
    });
    lines.push('');
  }

  lines.push('## Summary');
  lines.push('');
  lines.push('| Metric | Value |');
  lines.push('|--------|-------|');
  lines.push(`| Total Passed | ${coverage.summary.total_passed} |`);
  lines.push(`| Total Failed | ${coverage.summary.total_failed} |`);
  lines.push(`| Total Not Executed | ${coverage.summary.total_skipped} |`);
  lines.push(`| P0 Failures | ${coverage.summary.p0_failures} |`);
  lines.push(`| P1 Failures | ${coverage.summary.p1_failures} |`);
  lines.push(`| P2 Failures | ${coverage.summary.p2_failures} |`);
  lines.push(`| Dead Ends | ${coverage.summary.dead_ends_count} |`);
  lines.push('');
  lines.push('## Readiness');
  lines.push('');
  lines.push('| Environment | Ready |');
  lines.push('|-------------|-------|');
  lines.push(`| Staging | ${coverage.readiness.staging ? '✅' : '❌'} |`);
  lines.push(`| Canary | ${coverage.readiness.canary ? '✅' : '❌'} |`);
  lines.push(`| Production | ${coverage.readiness.production ? '✅' : '❌'} |`);
  lines.push('');
  lines.push('## Audit Results');
  lines.push('');

  // Page audit
  if (coverage.audits.page) {
    lines.push('### Page Load Audit');
    lines.push('');
    lines.push(`- Passed: ${coverage.audits.page.passed}`);
    lines.push(`- Failed: ${coverage.audits.page.failed}`);
    lines.push(`- Skipped: ${coverage.audits.page.skipped}`);
    lines.push('');
  }

  // Link audit
  if (coverage.audits.link) {
    lines.push('### Link Audit');
    lines.push('');
    lines.push(`- Total Links: ${coverage.audits.link.total_links}`);
    lines.push(`- Valid: ${coverage.audits.link.valid}`);
    lines.push(`- Dead: ${coverage.audits.link.dead}`);
    lines.push(`- External: ${coverage.audits.link.external}`);
    lines.push('');
  }

  // Button audit
  if (coverage.audits.button) {
    lines.push('### Button Wiring Audit');
    lines.push('');
    lines.push(`- Passed: ${coverage.audits.button.passed}`);
    lines.push(`- Failed: ${coverage.audits.button.failed}`);
    lines.push(`- Skipped: ${coverage.audits.button.skipped}`);
    lines.push(`- Noop Buttons: ${coverage.audits.button.noop_count}`);
    lines.push('');
  }

  // Workflow audit
  if (coverage.audits.workflow) {
    lines.push('### Workflow Audit');
    lines.push('');
    lines.push(`- Passed: ${coverage.audits.workflow.passed}`);
    lines.push(`- Failed: ${coverage.audits.workflow.failed}`);
    lines.push(`- Skipped: ${coverage.audits.workflow.skipped}`);
    lines.push(`- Dead Ends: ${coverage.audits.workflow.dead_ends}`);
    lines.push('');
  }

  // Failures
  if (coverage.failures.length > 0) {
    lines.push('## Failures');
    lines.push('');
    lines.push('| Type | ID | Criticality | Error |');
    lines.push('|------|----|--------------| ----- |');
    coverage.failures.forEach(f => {
      lines.push(`| ${f.type} | ${f.id} | ${f.criticality} | ${f.error?.slice(0, 50) || 'N/A'} |`);
    });
    lines.push('');
  }

  // Thresholds reference
  lines.push('## Thresholds');
  lines.push('');
  lines.push('| Level | Min Score | Max P0 | Max P1 |');
  lines.push('|-------|-----------|--------|--------|');
  lines.push(`| Staging Ready | ${coverage.thresholds.staging_ready.min_score} | ${coverage.thresholds.staging_ready.max_p0} | - |`);
  lines.push(`| Canary Expand | ${coverage.thresholds.canary_expand.min_score} | ${coverage.thresholds.canary_expand.max_p0} | ${coverage.thresholds.canary_expand.max_p1} |`);
  lines.push(`| Prod Promote | ${coverage.thresholds.prod_promote.min_score} | ${coverage.thresholds.prod_promote.max_p0} | ${coverage.thresholds.prod_promote.max_p1} |`);
  lines.push('');
  lines.push('Every level additionally requires complete P0 execution coverage.');
  lines.push('');
  lines.push('---');
  lines.push('');
  lines.push('*PII-Safe: No personally identifiable information captured in this report.*');

  return lines.join('\n');
}

// Generate dead end map
function generateDeadEndMap(coverage) {
  const lines = [
    '# UX Dead End Map',
    '',
    `**Generated:** ${coverage.timestamp}`,
    `**Total Dead Ends:** ${coverage.dead_ends.length}`,
    '',
  ];

  if (coverage.dead_ends.length === 0) {
    lines.push('✅ No dead ends detected!');
  } else {
    lines.push('## Dead Ends by Type');
    lines.push('');

    // Group by type
    const byType = {};
    coverage.dead_ends.forEach(de => {
      if (!byType[de.type]) byType[de.type] = [];
      byType[de.type].push(de);
    });

    Object.entries(byType).forEach(([type, items]) => {
      lines.push(`### ${type.replace(/_/g, ' ').toUpperCase()} (${items.length})`);
      lines.push('');
      lines.push('| Source | Target | Error |');
      lines.push('|--------|--------|-------|');
      items.forEach(de => {
        lines.push(`| ${de.source} | ${de.href} | ${de.error?.slice(0, 50) || '-'} |`);
      });
      lines.push('');
    });
  }

  lines.push('---');
  lines.push('');
  lines.push('*Use this map to identify and fix navigation issues.*');

  return lines.join('\n');
}

module.exports = {
  computeCoverage,
  generateMarkdown,
  generateDeadEndMap,
  THRESHOLDS,
};

// Run
if (require.main === module) {
  aggregate();
}
