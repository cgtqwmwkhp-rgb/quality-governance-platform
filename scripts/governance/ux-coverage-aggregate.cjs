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

// Load JSON files
function loadJson(filename) {
  const filepath = path.join(RESULTS_DIR, filename);
  if (fs.existsSync(filepath)) {
    return JSON.parse(fs.readFileSync(filepath, 'utf-8'));
  }
  return null;
}

// Main aggregation
function aggregate() {
  console.log('📊 UX Coverage Aggregation');
  console.log('=' .repeat(50));
  
  // Load audit results
  const pageAudit = loadJson('page_audit.json');
  const linkAudit = loadJson('link_audit.json');
  const buttonAudit = loadJson('button_audit.json');
  const workflowAudit = loadJson('workflow_audit.json');
  
  // Count failures by criticality
  let p0Fails = 0;
  let p1Fails = 0;
  let p2Fails = 0;
  let totalPassed = 0;
  let totalFailed = 0;
  let totalSkipped = 0;
  
  const failureDetails = [];
  const deadEnds = [];
  
  // Process page audit
  if (pageAudit) {
    pageAudit.results.forEach(r => {
      if (r.result === 'PASS') totalPassed++;
      else if (r.result === 'FAIL') {
        totalFailed++;
        if (r.criticality === 'P0') p0Fails++;
        else if (r.criticality === 'P1') p1Fails++;
        else p2Fails++;
        failureDetails.push({
          type: 'page',
          id: r.pageId,
          route: r.route,
          criticality: r.criticality,
          error: r.error_message,
        });
      } else {
        totalSkipped++;
      }
    });
  }
  
  // Process link audit
  if (linkAudit) {
    linkAudit.dead_end_map.forEach(de => {
      deadEnds.push({
        source: de.source,
        href: de.href,
        type: 'broken_link',
        error: de.error,
      });
    });
    // Dead links contribute to P1 failures
    p1Fails += linkAudit.total_dead;
  }
  
  // Process button audit
  if (buttonAudit) {
    buttonAudit.results.forEach(r => {
      if (r.result === 'PASS') totalPassed++;
      else if (r.result === 'FAIL') {
        totalFailed++;
        if (r.criticality === 'P0') p0Fails++;
        else if (r.criticality === 'P1') p1Fails++;
        else p2Fails++;
        failureDetails.push({
          type: 'button',
          id: `${r.pageId}::${r.actionId}`,
          criticality: r.criticality,
          error: r.error_message,
          noop: !r.outcome_observed && r.clicked,
        });
        if (!r.outcome_observed && r.clicked) {
          deadEnds.push({
            source: r.pageId,
            href: r.actionId,
            type: 'noop_button',
            error: 'Button click has no observable effect',
          });
        }
      } else {
        totalSkipped++;
      }
    });
  }
  
  // Process workflow audit
  if (workflowAudit) {
    workflowAudit.results.forEach(r => {
      if (r.result === 'PASS') totalPassed++;
      else if (r.result === 'FAIL') {
        totalFailed++;
        if (r.criticality === 'P0') p0Fails++;
        else if (r.criticality === 'P1') p1Fails++;
        else p2Fails++;
        failureDetails.push({
          type: 'workflow',
          id: r.workflowId,
          name: r.name,
          criticality: r.criticality,
          completed_steps: r.completed_steps,
          total_steps: r.total_steps,
          error: r.error_message,
        });
      } else {
        totalSkipped++;
      }
    });
    
    // Add workflow dead ends
    if (workflowAudit.dead_ends) {
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
  
  // Determine status
  let status = 'HOLD';
  let readiness = {
    staging: false,
    canary: false,
    production: false,
  };
  
  if (p0Fails === 0) {
    if (score >= THRESHOLDS.prod_promote.min_score && p1Fails <= THRESHOLDS.prod_promote.max_p1) {
      status = 'GO';
      readiness = { staging: true, canary: true, production: true };
    } else if (score >= THRESHOLDS.canary_expand.min_score && p1Fails <= THRESHOLDS.canary_expand.max_p1) {
      status = 'CANARY';
      readiness = { staging: true, canary: true, production: false };
    } else if (score >= THRESHOLDS.staging_ready.min_score) {
      status = 'STAGING';
      readiness = { staging: true, canary: false, production: false };
    }
  }
  
  // Build output
  const coverage = {
    version: '1.0',
    timestamp: new Date().toISOString(),
    score,
    status,
    readiness,
    summary: {
      total_passed: totalPassed,
      total_failed: totalFailed,
      total_skipped: totalSkipped,
      p0_failures: p0Fails,
      p1_failures: p1Fails,
      p2_failures: p2Fails,
      dead_ends_count: deadEnds.length,
    },
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
    dead_ends: deadEnds,
  };
  
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
  console.log(`\n📈 Score: ${score}/100`);
  console.log(`📊 Status: ${status}`);
  console.log(`\n✅ Passed: ${totalPassed}`);
  console.log(`❌ Failed: ${totalFailed} (P0: ${p0Fails}, P1: ${p1Fails}, P2: ${p2Fails})`);
  console.log(`⏭️  Skipped: ${totalSkipped}`);
  console.log(`🚧 Dead Ends: ${deadEnds.length}`);
  console.log(`\n📁 Output written to: ${OUTPUT_DIR}`);
  
  // Exit with appropriate code
  if (p0Fails > 0) {
    console.log('\n🛑 HOLD: P0 failures detected');
    process.exit(1);
  } else if (status === 'HOLD') {
    console.log('\n⚠️  HOLD: Score below threshold');
    process.exit(1);
  } else {
    console.log(`\n✅ ${status}: Ready for ${Object.entries(readiness).filter(([k, v]) => v).map(([k]) => k).join(', ')}`);
    process.exit(0);
  }
}

// Generate Markdown report
function generateMarkdown(coverage) {
  const lines = [
    '# UX Functional Coverage Report',
    '',
    `**Generated:** ${coverage.timestamp}`,
    `**Score:** ${coverage.score}/100`,
    `**Status:** ${coverage.status}`,
    '',
    '## Summary',
    '',
    '| Metric | Value |',
    '|--------|-------|',
    `| Total Passed | ${coverage.summary.total_passed} |`,
    `| Total Failed | ${coverage.summary.total_failed} |`,
    `| Total Skipped | ${coverage.summary.total_skipped} |`,
    `| P0 Failures | ${coverage.summary.p0_failures} |`,
    `| P1 Failures | ${coverage.summary.p1_failures} |`,
    `| P2 Failures | ${coverage.summary.p2_failures} |`,
    `| Dead Ends | ${coverage.summary.dead_ends_count} |`,
    '',
    '## Readiness',
    '',
    '| Environment | Ready |',
    '|-------------|-------|',
    `| Staging | ${coverage.readiness.staging ? '✅' : '❌'} |`,
    `| Canary | ${coverage.readiness.canary ? '✅' : '❌'} |`,
    `| Production | ${coverage.readiness.production ? '✅' : '❌'} |`,
    '',
    '## Audit Results',
    '',
  ];
  
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

// Run
aggregate();
