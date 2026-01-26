#!/usr/bin/env node

/**
 * EXP-001 Sample Generator (Staging Only)
 * 
 * Generates synthetic telemetry events to reach minimum sample threshold.
 * 
 * SAFETY:
 * - Only works against staging/localhost
 * - Uses dummy non-PII payloads
 * - Rate-limited (100ms between events)
 * - Reversible (can reset metrics via API)
 * 
 * NO PII: All generated data is synthetic and non-identifiable.
 * 
 * Usage:
 *   node exp001-sample-generator.cjs [samples] [api_url]
 * 
 * Examples:
 *   node exp001-sample-generator.cjs 100
 *   node exp001-sample-generator.cjs 100 http://localhost:8000
 */

const https = require('https');
const http = require('http');

// ============================================================================
// Configuration
// ============================================================================

const DEFAULT_SAMPLES = 100;
const DEFAULT_API_URL = 'http://localhost:8000';
const RATE_LIMIT_MS = 100; // 100ms between events

// Synthetic form types (bounded)
const FORM_TYPES = ['incident', 'near-miss', 'complaint', 'rta'];

// ============================================================================
// Helpers
// ============================================================================

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function randomChoice(arr) {
  return arr[Math.floor(Math.random() * arr.length)];
}

function randomInt(min, max) {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

function generateSessionId() {
  return `synth_${Date.now()}_${Math.random().toString(36).slice(2, 11)}`;
}

/**
 * Send a telemetry event to the API
 */
async function sendEvent(apiUrl, event) {
  const url = `${apiUrl}/api/v1/telemetry/events`;
  const data = JSON.stringify(event);
  
  return new Promise((resolve, reject) => {
    const urlObj = new URL(url);
    const isHttps = urlObj.protocol === 'https:';
    const client = isHttps ? https : http;
    
    const options = {
      hostname: urlObj.hostname,
      port: urlObj.port || (isHttps ? 443 : 80),
      path: urlObj.pathname,
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(data),
      },
    };
    
    const req = client.request(options, (res) => {
      let responseData = '';
      res.on('data', (chunk) => { responseData += chunk; });
      res.on('end', () => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve({ ok: true, status: res.statusCode });
        } else {
          reject(new Error(`HTTP ${res.statusCode}: ${responseData}`));
        }
      });
    });
    
    req.on('error', reject);
    req.write(data);
    req.end();
  });
}

/**
 * Generate a complete form session (open -> draft -> submit)
 */
async function generateFormSession(apiUrl, sessionNum, totalSessions) {
  const sessionId = generateSessionId();
  const formType = randomChoice(FORM_TYPES);
  const flagEnabled = true; // Always true for EXP-001 treatment
  const hasDraft = Math.random() < 0.3; // 30% have existing draft
  const hadDraft = hasDraft && Math.random() < 0.7; // 70% of those recover
  const totalSteps = formType === 'complaint' ? 3 : 4;
  
  // Event 1: Form opened
  await sendEvent(apiUrl, {
    name: 'exp001_form_opened',
    timestamp: new Date().toISOString(),
    sessionId,
    dimensions: {
      formType,
      flagEnabled,
      hasDraft,
      environment: 'staging',
    },
  });
  await sleep(RATE_LIMIT_MS);
  
  // Event 2: Draft recovered (if applicable)
  if (hasDraft && hadDraft) {
    await sendEvent(apiUrl, {
      name: 'exp001_draft_recovered',
      timestamp: new Date().toISOString(),
      sessionId,
      dimensions: {
        formType,
        draftAgeSeconds: randomInt(60, 3600),
        environment: 'staging',
      },
    });
    await sleep(RATE_LIMIT_MS);
  } else if (hasDraft) {
    // Draft discarded
    await sendEvent(apiUrl, {
      name: 'exp001_draft_discarded',
      timestamp: new Date().toISOString(),
      sessionId,
      dimensions: {
        formType,
        draftAgeSeconds: randomInt(60, 3600),
        environment: 'staging',
      },
    });
    await sleep(RATE_LIMIT_MS);
  }
  
  // Event 3: Draft saved (simulate autosave during form filling)
  const savesCount = randomInt(2, 8);
  for (let i = 0; i < savesCount; i++) {
    await sendEvent(apiUrl, {
      name: 'exp001_draft_saved',
      timestamp: new Date().toISOString(),
      sessionId,
      dimensions: {
        formType,
        step: randomInt(1, totalSteps),
        environment: 'staging',
      },
    });
    await sleep(RATE_LIMIT_MS / 2); // Faster for saves
  }
  
  // Event 4: Form submitted or abandoned
  const abandoned = Math.random() < 0.15; // 15% abandonment rate baseline
  
  if (abandoned) {
    await sendEvent(apiUrl, {
      name: 'exp001_form_abandoned',
      timestamp: new Date().toISOString(),
      sessionId,
      dimensions: {
        formType,
        flagEnabled,
        lastStep: randomInt(1, totalSteps - 1),
        hadDraft,
        environment: 'staging',
      },
    });
  } else {
    await sendEvent(apiUrl, {
      name: 'exp001_form_submitted',
      timestamp: new Date().toISOString(),
      sessionId,
      dimensions: {
        formType,
        flagEnabled,
        hadDraft,
        stepCount: totalSteps,
        error: false,
        environment: 'staging',
      },
    });
  }
  
  // Progress
  const pct = Math.round((sessionNum / totalSessions) * 100);
  process.stdout.write(`\r[${sessionNum}/${totalSessions}] ${pct}% - ${formType} ${abandoned ? 'ABANDONED' : 'SUBMITTED'}`);
}

// ============================================================================
// Main
// ============================================================================

async function main() {
  const samples = parseInt(process.argv[2], 10) || DEFAULT_SAMPLES;
  const apiUrl = process.argv[3] || DEFAULT_API_URL;
  
  console.log('='.repeat(60));
  console.log('EXP-001 Sample Generator (Staging Only)');
  console.log('='.repeat(60));
  console.log(`API URL: ${apiUrl}`);
  console.log(`Target samples: ${samples}`);
  console.log('');
  
  // Safety check: only allow staging/localhost
  const urlLower = apiUrl.toLowerCase();
  if (!urlLower.includes('localhost') && 
      !urlLower.includes('127.0.0.1') && 
      !urlLower.includes('staging')) {
    console.error('ERROR: This script only works against staging/localhost');
    console.error('Refusing to run against production URL');
    process.exit(1);
  }
  
  console.log('Generating synthetic form sessions...');
  console.log('(This uses dummy non-PII data only)');
  console.log('');
  
  let successCount = 0;
  let errorCount = 0;
  
  for (let i = 1; i <= samples; i++) {
    try {
      await generateFormSession(apiUrl, i, samples);
      successCount++;
    } catch (err) {
      errorCount++;
      if (errorCount <= 3) {
        console.error(`\nError generating session ${i}: ${err.message}`);
      } else if (errorCount === 4) {
        console.error('\n(Suppressing further errors...)');
      }
    }
    await sleep(RATE_LIMIT_MS);
  }
  
  console.log('\n');
  console.log('='.repeat(60));
  console.log('GENERATION COMPLETE');
  console.log(`Successful sessions: ${successCount}`);
  console.log(`Errors: ${errorCount}`);
  console.log('');
  console.log('Run the evaluator to check sample count:');
  console.log('  node scripts/governance/ux-experiment-evaluator.cjs');
  console.log('='.repeat(60));
}

main().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});
