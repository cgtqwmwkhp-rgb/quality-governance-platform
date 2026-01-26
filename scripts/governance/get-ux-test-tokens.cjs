#!/usr/bin/env node

/**
 * UX Test Token Acquisition Script
 * 
 * Acquires auth tokens for UX coverage testing in CI.
 * Tokens are obtained via the standard login endpoint.
 * 
 * Security:
 * - Credentials read from environment (GitHub secrets)
 * - Tokens written to $GITHUB_OUTPUT (masked by Actions)
 * - No tokens printed to stdout/stderr
 * - Tokens are short-lived (per API config)
 * 
 * Usage:
 *   node scripts/governance/get-ux-test-tokens.cjs
 * 
 * Required env vars:
 *   - UX_TEST_USER_EMAIL
 *   - UX_TEST_USER_PASSWORD
 *   - APP_URL (staging URL)
 * 
 * Outputs (to $GITHUB_OUTPUT):
 *   - admin_token
 *   - portal_token
 */

const https = require('https');
const http = require('http');
const fs = require('fs');

// Configuration
const APP_URL = process.env.APP_URL || 'https://app-qgp-staging.azurewebsites.net';
const TEST_EMAIL = process.env.UX_TEST_USER_EMAIL;
const TEST_PASSWORD = process.env.UX_TEST_USER_PASSWORD;
const GITHUB_OUTPUT = process.env.GITHUB_OUTPUT;

// Validate required env vars
function validateEnv() {
  const missing = [];
  if (!TEST_EMAIL) missing.push('UX_TEST_USER_EMAIL');
  if (!TEST_PASSWORD) missing.push('UX_TEST_USER_PASSWORD');
  
  if (missing.length > 0) {
    console.log(`⚠️  Missing credentials: ${missing.join(', ')}`);
    console.log('ℹ️  Tokens will not be acquired. Auth-protected tests will skip.');
    return false;
  }
  return true;
}

// Make HTTP(S) request
function makeRequest(url, options, body) {
  return new Promise((resolve, reject) => {
    const isHttps = url.startsWith('https');
    const lib = isHttps ? https : http;
    
    const req = lib.request(url, options, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        resolve({
          status: res.statusCode,
          headers: res.headers,
          body: data,
        });
      });
    });
    
    req.on('error', reject);
    req.setTimeout(30000, () => {
      req.destroy();
      reject(new Error('Request timeout'));
    });
    
    if (body) {
      req.write(body);
    }
    req.end();
  });
}

// Acquire token via login endpoint
async function acquireToken() {
  const loginUrl = `${APP_URL}/api/v1/auth/login`;
  
  console.log(`🔐 Acquiring token from: ${loginUrl.replace(/\/\/[^@]+@/, '//<redacted>@')}`);
  
  const body = JSON.stringify({
    email: TEST_EMAIL,
    password: TEST_PASSWORD,
  });
  
  const options = {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Content-Length': Buffer.byteLength(body),
      'User-Agent': 'ux-coverage-ci/1.0',
    },
  };
  
  try {
    const response = await makeRequest(loginUrl, options, body);
    
    if (response.status === 200 || response.status === 201) {
      const data = JSON.parse(response.body);
      
      if (data.access_token) {
        console.log('✅ Token acquired successfully');
        // Validate token format (starts with expected pattern)
        if (data.access_token.length > 20) {
          return data.access_token;
        }
      }
    }
    
    if (response.status === 401) {
      console.log('❌ Authentication failed: Invalid credentials');
      return null;
    }
    
    if (response.status === 403) {
      console.log('❌ Authentication failed: User account disabled');
      return null;
    }
    
    console.log(`❌ Unexpected response: HTTP ${response.status}`);
    return null;
    
  } catch (error) {
    console.log(`❌ Request failed: ${error.message}`);
    return null;
  }
}

// Write output to GitHub Actions
function writeOutput(name, value) {
  if (!GITHUB_OUTPUT) {
    console.log(`ℹ️  Would set output: ${name}=<masked>`);
    return;
  }
  
  // Mask the value in logs
  console.log(`::add-mask::${value}`);
  
  // Write to GITHUB_OUTPUT file
  fs.appendFileSync(GITHUB_OUTPUT, `${name}=${value}\n`);
  console.log(`✅ Output set: ${name}=<masked>`);
}

// Main
async function main() {
  console.log('🔑 UX Test Token Acquisition');
  console.log('=' .repeat(50));
  
  // Check if credentials are available
  if (!validateEnv()) {
    // Write empty tokens - tests will handle gracefully
    if (GITHUB_OUTPUT) {
      fs.appendFileSync(GITHUB_OUTPUT, 'admin_token=\n');
      fs.appendFileSync(GITHUB_OUTPUT, 'portal_token=\n');
      fs.appendFileSync(GITHUB_OUTPUT, 'tokens_acquired=false\n');
    }
    process.exit(0); // Don't fail the job
  }
  
  // Acquire admin token
  console.log('\n📋 Acquiring admin token...');
  const adminToken = await acquireToken();
  
  if (adminToken) {
    writeOutput('admin_token', adminToken);
    // Portal uses same token since we're using password auth
    writeOutput('portal_token', adminToken);
    writeOutput('tokens_acquired', 'true');
    console.log('\n✅ Token acquisition complete');
    process.exit(0);
  } else {
    console.log('\n⚠️  Token acquisition failed');
    if (GITHUB_OUTPUT) {
      fs.appendFileSync(GITHUB_OUTPUT, 'admin_token=\n');
      fs.appendFileSync(GITHUB_OUTPUT, 'portal_token=\n');
      fs.appendFileSync(GITHUB_OUTPUT, 'tokens_acquired=false\n');
    }
    process.exit(0); // Don't fail - tests will skip gracefully
  }
}

main().catch(error => {
  console.log(`❌ Fatal error: ${error.message}`);
  process.exit(1);
});
