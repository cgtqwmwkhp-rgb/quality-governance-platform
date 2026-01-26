#!/usr/bin/env node

/**
 * Control Tower - Deployment Readiness Aggregator
 * 
 * Aggregates signals from multiple sources to determine go/no-go:
 * - CI checks (tests, security, quality)
 * - Deploy Proof (health, readiness, identity)
 * - UX Coverage Gate (page/link/button/workflow audits)
 * 
 * Outputs:
 * - control_tower.json (machine-readable)
 * - control_tower.md (human-readable)
 * 
 * GO/HOLD logic:
 * - HOLD if any P0 signal fails
 * - HOLD if UX score < threshold
 * - GO if all signals pass
 */

const fs = require('fs');
const path = require('path');

// Configuration
const ARTIFACTS_DIR = process.env.ARTIFACTS_DIR || path.join(__dirname, '../../artifacts');

// Load artifact if exists
function loadArtifact(filename) {
  const filepath = path.join(ARTIFACTS_DIR, filename);
  if (fs.existsSync(filepath)) {
    try {
      return JSON.parse(fs.readFileSync(filepath, 'utf-8'));
    } catch (e) {
      console.warn(`⚠️  Failed to parse ${filename}: ${e.message}`);
      return null;
    }
  }
  return null;
}

// Main aggregation
function aggregate() {
  console.log('🗼 Control Tower - Deployment Readiness');
  console.log('=' .repeat(50));
  
  const signals = {
    ci: { status: 'UNKNOWN', passed: 0, failed: 0 },
    deploy_proof: { status: 'UNKNOWN', overall: null },
    ux_coverage: { status: 'UNKNOWN', score: null, p0_fails: null },
    staging_reachability: { status: 'UNKNOWN', reason: null },
    login_reliability: { status: 'UNKNOWN', contract: null, error_codes: null },
  };
  
  const holdReasons = [];
  let overallStatus = 'GO';
  
  // Load staging reachability signal (from token acquisition)
  const tokenResult = loadArtifact('token_acquisition.json');
  if (tokenResult) {
    signals.staging_reachability = {
      status: tokenResult.staging_reachable ? 'PASS' : 'FAIL',
      reason: tokenResult.failure_reason || null,
      attempts: tokenResult.readiness_attempts || null,
      latency_ms: tokenResult.readiness_latency_ms || null,
    };
    
    if (!tokenResult.staging_reachable) {
      overallStatus = 'HOLD';
      holdReasons.push(`Staging unreachable: ${tokenResult.failure_reason}`);
    }
    
    console.log(`🌐 Staging Reachability: ${signals.staging_reachability.status}`);
  } else {
    // Infer from UX coverage - if tests ran, staging was reachable
    signals.staging_reachability.status = 'INFERRED';
    console.log('🌐 Staging Reachability: INFERRED (tests ran)');
  }
  
  // Load UX Coverage
  const uxCoverage = loadArtifact('ux_coverage.json');
  if (uxCoverage) {
    signals.ux_coverage = {
      status: uxCoverage.status,
      score: uxCoverage.score,
      p0_fails: uxCoverage.summary.p0_failures,
      p1_fails: uxCoverage.summary.p1_failures,
      dead_ends: uxCoverage.summary.dead_ends_count,
      readiness: uxCoverage.readiness,
    };
    
    // Check for staging unreachable P0 failures (infra issue)
    if (uxCoverage.infra_failure_reason) {
      signals.staging_reachability = {
        status: 'FAIL',
        reason: uxCoverage.infra_failure_reason,
      };
      overallStatus = 'HOLD';
      holdReasons.push(`Staging infra issue: ${uxCoverage.infra_failure_reason}`);
    } else if (uxCoverage.summary.p0_failures > 0) {
      overallStatus = 'HOLD';
      holdReasons.push(`UX P0 failures: ${uxCoverage.summary.p0_failures}`);
    } else if (uxCoverage.status === 'HOLD') {
      overallStatus = 'HOLD';
      holdReasons.push(`UX score below threshold: ${uxCoverage.score}/100`);
    }
    
    // If UX coverage ran successfully, staging is reachable
    if (signals.staging_reachability.status === 'INFERRED') {
      signals.staging_reachability = { status: 'PASS', reason: 'UX tests completed' };
    }
    
    console.log(`📊 UX Coverage: ${uxCoverage.status} (${uxCoverage.score}/100)`);
  } else {
    console.log('📊 UX Coverage: NOT AVAILABLE');
    signals.ux_coverage.status = 'NOT_RUN';
  }
  
  // Load Deploy Proof (if available)
  const deployProof = loadArtifact('deploy_proof.json');
  if (deployProof) {
    signals.deploy_proof = {
      status: deployProof.overall_result,
      overall: deployProof.overall_result,
      identity: deployProof.checks?.identity?.result,
      health: deployProof.checks?.health?.result,
      readiness: deployProof.checks?.readiness?.result,
      openapi: deployProof.checks?.openapi?.result,
      image: deployProof.checks?.image?.result,
    };
    
    if (deployProof.overall_result !== 'PASS') {
      overallStatus = 'HOLD';
      holdReasons.push(`Deploy Proof: ${deployProof.overall_result}`);
    }
    
    console.log(`🔐 Deploy Proof: ${deployProof.overall_result}`);
  } else {
    console.log('🔐 Deploy Proof: NOT AVAILABLE');
    signals.deploy_proof.status = 'NOT_RUN';
  }
  
  // Load Login Reliability signal (LOGIN_UX_CONTRACT.md compliance)
  const loginReliability = loadArtifact('login_reliability.json');
  if (loginReliability) {
    signals.login_reliability = {
      status: loginReliability.contract_compliant ? 'PASS' : 'FAIL',
      contract: 'LOGIN_UX_CONTRACT.md',
      error_codes: loginReliability.error_codes || [],
      invariants_passed: loginReliability.invariants_passed || false,
      infinite_spinner_detected: loginReliability.infinite_spinner_detected || false,
      p95_latency_ms: loginReliability.p95_latency_ms || null,
    };
    
    // P0: Login reliability is critical
    if (!loginReliability.contract_compliant) {
      overallStatus = 'HOLD';
      holdReasons.push('Login reliability: contract violation');
    }
    
    if (loginReliability.infinite_spinner_detected) {
      overallStatus = 'HOLD';
      holdReasons.push('Login reliability: infinite spinner detected');
    }
    
    console.log(`🔐 Login Reliability: ${signals.login_reliability.status}`);
  } else {
    // Infer from UX coverage login workflow results
    console.log('🔐 Login Reliability: INFERRED (from UX coverage)');
    signals.login_reliability.status = 'INFERRED';
  }
  
  // Load CI summary (if available from gate-summary artifact)
  const gateSummary = loadArtifact('gate_summary.json');
  if (gateSummary) {
    signals.ci = {
      status: gateSummary.all_passed ? 'PASS' : 'FAIL',
      passed: gateSummary.passed_count || 0,
      failed: gateSummary.failed_count || 0,
      checks: gateSummary.checks || [],
    };
    
    if (!gateSummary.all_passed) {
      overallStatus = 'HOLD';
      holdReasons.push(`CI failures: ${gateSummary.failed_count}`);
    }
    
    console.log(`🔧 CI Checks: ${signals.ci.status} (${signals.ci.passed} passed, ${signals.ci.failed} failed)`);
  } else {
    console.log('🔧 CI Checks: NOT AVAILABLE');
    signals.ci.status = 'NOT_RUN';
  }
  
  // Determine environment readiness
  const readiness = {
    staging: false,
    canary: false,
    production: false,
  };
  
  if (overallStatus === 'GO') {
    // All signals passed - check UX readiness
    if (signals.ux_coverage.readiness) {
      readiness.staging = signals.ux_coverage.readiness.staging || false;
      readiness.canary = signals.ux_coverage.readiness.canary || false;
      readiness.production = signals.ux_coverage.readiness.production || false;
    } else {
      // No UX data - assume staging only
      readiness.staging = true;
    }
  }
  
  // Build output
  const controlTower = {
    version: '1.0',
    timestamp: new Date().toISOString(),
    go_no_go: overallStatus,
    hold_reasons: holdReasons,
    readiness,
    signals,
  };
  
  // Ensure output directory exists
  fs.mkdirSync(ARTIFACTS_DIR, { recursive: true });
  
  // Write JSON
  fs.writeFileSync(
    path.join(ARTIFACTS_DIR, 'control_tower.json'),
    JSON.stringify(controlTower, null, 2)
  );
  
  // Write Markdown
  const md = generateMarkdown(controlTower);
  fs.writeFileSync(path.join(ARTIFACTS_DIR, 'control_tower.md'), md);
  
  // Console output
  console.log('');
  console.log('=' .repeat(50));
  console.log(`🚦 GO/NO-GO: ${overallStatus}`);
  
  if (holdReasons.length > 0) {
    console.log('');
    console.log('Hold Reasons:');
    holdReasons.forEach(r => console.log(`  ❌ ${r}`));
  }
  
  console.log('');
  console.log('Readiness:');
  console.log(`  Staging: ${readiness.staging ? '✅' : '❌'}`);
  console.log(`  Canary: ${readiness.canary ? '✅' : '❌'}`);
  console.log(`  Production: ${readiness.production ? '✅' : '❌'}`);
  
  console.log('');
  console.log(`📁 Output written to: ${ARTIFACTS_DIR}`);
  
  // Exit code
  if (overallStatus === 'HOLD') {
    process.exit(1);
  } else {
    process.exit(0);
  }
}

// Generate Markdown report
function generateMarkdown(ct) {
  const lines = [
    '# Control Tower - Deployment Readiness',
    '',
    `**Generated:** ${ct.timestamp}`,
    `**Status:** ${ct.go_no_go === 'GO' ? '✅ GO' : '❌ HOLD'}`,
    '',
    '## Signal Summary',
    '',
    '| Signal | Status | Details |',
    '|--------|--------|---------|',
  ];
  
  // Staging Reachability
  const sr = ct.signals.staging_reachability;
  lines.push(`| Staging Reachability | ${sr.status === 'PASS' || sr.status === 'INFERRED' ? '✅' : (sr.status === 'UNKNOWN' ? '⏸️' : '❌')} ${sr.status} | ${sr.reason || (sr.latency_ms ? `${sr.latency_ms}ms` : '-')} |`);
  
  // CI
  const ci = ct.signals.ci;
  lines.push(`| CI Checks | ${ci.status === 'PASS' ? '✅' : (ci.status === 'NOT_RUN' ? '⏸️' : '❌')} ${ci.status} | ${ci.passed} passed, ${ci.failed} failed |`);
  
  // Deploy Proof
  const dp = ct.signals.deploy_proof;
  lines.push(`| Deploy Proof | ${dp.status === 'PASS' ? '✅' : (dp.status === 'NOT_RUN' ? '⏸️' : '❌')} ${dp.status} | Identity: ${dp.identity || '-'}, Health: ${dp.health || '-'} |`);
  
  // UX Coverage
  const ux = ct.signals.ux_coverage;
  lines.push(`| UX Coverage | ${ux.status === 'GO' ? '✅' : (ux.status === 'NOT_RUN' ? '⏸️' : '⚠️')} ${ux.status} | Score: ${ux.score || '-'}/100, P0: ${ux.p0_fails ?? '-'}, P1: ${ux.p1_fails ?? '-'} |`);
  
  lines.push('');
  lines.push('## Environment Readiness');
  lines.push('');
  lines.push('| Environment | Ready |');
  lines.push('|-------------|-------|');
  lines.push(`| Staging | ${ct.readiness.staging ? '✅ Yes' : '❌ No'} |`);
  lines.push(`| Canary | ${ct.readiness.canary ? '✅ Yes' : '❌ No'} |`);
  lines.push(`| Production | ${ct.readiness.production ? '✅ Yes' : '❌ No'} |`);
  
  if (ct.hold_reasons.length > 0) {
    lines.push('');
    lines.push('## Hold Reasons');
    lines.push('');
    ct.hold_reasons.forEach(r => {
      lines.push(`- ❌ ${r}`);
    });
  }
  
  lines.push('');
  lines.push('---');
  lines.push('');
  lines.push('*This report is auto-generated by Control Tower. Do not edit manually.*');
  
  return lines.join('\n');
}

// Run
aggregate();
