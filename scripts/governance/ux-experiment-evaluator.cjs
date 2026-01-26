#!/usr/bin/env node

/**
 * UX Experiment Evaluator
 * 
 * Evaluates UX experiments against their KPI targets and proposes decisions:
 * - KEEP: Metrics meet targets, ready for wider rollout
 * - HOLD: Insufficient data, continue collecting
 * - ROLLBACK: Guardrails breached, disable experiment
 * - EXPAND: Exceptional results, accelerate rollout
 * 
 * Usage: node ux-experiment-evaluator.cjs [experiment_id]
 */

const fs = require('fs');
const path = require('path');

// Experiment definitions
// KPI comparison types:
// - "lower_is_better" (default): target means "at most this value" (e.g., error rate)
// - "higher_is_better": target means "at least this value" (e.g., usage rate)
// - "delta_negative": target is a negative change (e.g., -15% abandonment)
const EXPERIMENTS = {
  'EXP_001': {
    id: 'EXP_001',
    name: 'Autosave + Draft Recovery',
    featureFlag: 'portal_form_autosave',
    minSamples: 100,
    kpis: {
      abandonmentRate: { target: -0.15, guardrail: 0.05, comparison: 'delta_negative' }, // -15% target, +5% max
      completionTime: { target: 0, guardrail: 0.20, comparison: 'lower_is_better' }, // No change, +20% max
      errorRate: { target: 0, guardrail: 0.02, comparison: 'lower_is_better' }, // No change, +2% max
      draftRecoveryUsage: { target: 0.05, guardrail: null, comparison: 'higher_is_better' }, // 5% min usage
    },
  },
};

/**
 * Fetch metrics from analytics API (placeholder)
 */
async function fetchMetrics(experimentId) {
  // In production, this would call the analytics API
  // For now, return placeholder indicating no data yet
  
  // Try to read from local metrics file if available
  const metricsPath = path.join(__dirname, `../../artifacts/experiment_metrics_${experimentId}.json`);
  
  if (fs.existsSync(metricsPath)) {
    return JSON.parse(fs.readFileSync(metricsPath, 'utf-8'));
  }
  
  // No metrics available yet
  return {
    experimentId,
    samples: 0,
    metrics: null,
    collectionPeriod: null,
  };
}

/**
 * Evaluate experiment against KPI targets
 */
function evaluateExperiment(experiment, metrics) {
  const result = {
    experimentId: experiment.id,
    experimentName: experiment.name,
    featureFlag: experiment.featureFlag,
    evaluatedAt: new Date().toISOString(),
    samples: metrics.samples,
    minSamplesRequired: experiment.minSamples,
    hasSufficientData: metrics.samples >= experiment.minSamples,
    decision: 'HOLD',
    decisionReason: '',
    kpiResults: {},
    guardrailsBreeched: [],
    targetsHit: [],
  };
  
  // Check if we have sufficient data
  if (!result.hasSufficientData) {
    result.decision = 'HOLD';
    result.decisionReason = `Insufficient data: ${metrics.samples}/${experiment.minSamples} samples collected`;
    return result;
  }
  
  // Evaluate each KPI
  for (const [kpiName, kpiConfig] of Object.entries(experiment.kpis)) {
    const metricValue = metrics.metrics?.[kpiName];
    
    if (metricValue === undefined || metricValue === null) {
      result.kpiResults[kpiName] = {
        status: 'MISSING',
        value: null,
        target: kpiConfig.target,
        guardrail: kpiConfig.guardrail,
      };
      continue;
    }
    
    const kpiResult = {
      value: metricValue,
      target: kpiConfig.target,
      guardrail: kpiConfig.guardrail,
      comparison: kpiConfig.comparison || 'lower_is_better',
      status: 'NEUTRAL',
    };
    
    // Check guardrail (always: value must not exceed guardrail)
    if (kpiConfig.guardrail !== null && metricValue > kpiConfig.guardrail) {
      kpiResult.status = 'GUARDRAIL_BREACHED';
      result.guardrailsBreeched.push(kpiName);
    }
    // Check target based on comparison type
    else {
      let targetMet = false;
      const comparison = kpiConfig.comparison || 'lower_is_better';
      
      if (comparison === 'higher_is_better') {
        // For usage metrics: value >= target is good
        targetMet = metricValue >= kpiConfig.target;
      } else if (comparison === 'delta_negative') {
        // For reduction metrics: value <= target (more negative is better)
        targetMet = metricValue <= kpiConfig.target;
      } else {
        // Default (lower_is_better): value <= target is good
        targetMet = metricValue <= kpiConfig.target;
      }
      
      if (targetMet) {
        kpiResult.status = 'TARGET_HIT';
        result.targetsHit.push(kpiName);
      }
    }
    
    result.kpiResults[kpiName] = kpiResult;
  }
  
  // Determine decision
  if (result.guardrailsBreeched.length > 0) {
    result.decision = 'ROLLBACK';
    result.decisionReason = `Guardrails breached: ${result.guardrailsBreeched.join(', ')}`;
  } else if (result.targetsHit.length === Object.keys(experiment.kpis).length) {
    result.decision = 'EXPAND';
    result.decisionReason = 'All KPI targets exceeded - recommend accelerated rollout';
  } else if (result.targetsHit.length >= Object.keys(experiment.kpis).length / 2) {
    result.decision = 'KEEP';
    result.decisionReason = `Majority of KPI targets met (${result.targetsHit.length}/${Object.keys(experiment.kpis).length})`;
  } else {
    result.decision = 'HOLD';
    result.decisionReason = 'Insufficient KPI targets met - continue monitoring';
  }
  
  return result;
}

/**
 * Main evaluation function
 */
async function main() {
  const experimentId = process.argv[2] || 'EXP_001';
  const experiment = EXPERIMENTS[experimentId];
  
  if (!experiment) {
    console.error(`Unknown experiment: ${experimentId}`);
    console.error(`Available experiments: ${Object.keys(EXPERIMENTS).join(', ')}`);
    process.exit(1);
  }
  
  console.log('='.repeat(60));
  console.log(`UX Experiment Evaluator: ${experiment.name}`);
  console.log('='.repeat(60));
  console.log();
  
  // Fetch metrics
  console.log('Fetching metrics...');
  const metrics = await fetchMetrics(experimentId);
  
  // Evaluate
  console.log('Evaluating experiment...');
  const result = evaluateExperiment(experiment, metrics);
  
  // Output results
  console.log();
  console.log('EVALUATION RESULTS');
  console.log('-'.repeat(40));
  console.log(`Experiment: ${result.experimentName}`);
  console.log(`Feature Flag: ${result.featureFlag}`);
  console.log(`Samples: ${result.samples}/${result.minSamplesRequired}`);
  console.log(`Has Sufficient Data: ${result.hasSufficientData}`);
  console.log();
  
  console.log('KPI Results:');
  for (const [kpi, kpiResult] of Object.entries(result.kpiResults)) {
    const statusIcon = kpiResult.status === 'TARGET_HIT' ? '✅' :
                       kpiResult.status === 'GUARDRAIL_BREACHED' ? '❌' :
                       kpiResult.status === 'MISSING' ? '⏳' : '➖';
    console.log(`  ${statusIcon} ${kpi}: ${kpiResult.value ?? 'N/A'} (target: ${kpiResult.target}, guardrail: ${kpiResult.guardrail})`);
  }
  console.log();
  
  // Decision
  const decisionIcon = {
    KEEP: '✅',
    HOLD: '⏳',
    ROLLBACK: '🛑',
    EXPAND: '🚀',
  }[result.decision];
  
  console.log('='.repeat(40));
  console.log(`DECISION: ${decisionIcon} ${result.decision}`);
  console.log(`Reason: ${result.decisionReason}`);
  console.log('='.repeat(40));
  
  // Write result to file
  const outputPath = path.join(__dirname, `../../artifacts/experiment_evaluation_${experimentId}.json`);
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  fs.writeFileSync(outputPath, JSON.stringify(result, null, 2));
  console.log();
  console.log(`Evaluation saved to: ${outputPath}`);
  
  // Exit with appropriate code
  if (result.decision === 'ROLLBACK') {
    process.exit(1);
  }
  process.exit(0);
}

main().catch(err => {
  console.error('Evaluation failed:', err);
  process.exit(1);
});
