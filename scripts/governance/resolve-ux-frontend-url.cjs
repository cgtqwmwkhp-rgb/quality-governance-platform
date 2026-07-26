#!/usr/bin/env node

/**
 * Resolve the frontend the UX Functional Coverage Gate is allowed to drive.
 *
 * THE DEFECT THIS FIXES (PX-179):
 * The gate hard-coded FRONTEND_URL to the production Static Web App hostname
 * while get-ux-test-tokens.cjs minted its tokens against staging. Playwright's
 * baseURL is `FRONTEND_URL || APP_URL`, so every audit drove the *production*
 * frontend — which talks to the production API — holding *staging* credentials.
 * Client-side assertions survived that; anything needing real data did not, and
 * a governance gate was pointing synthetic traffic and login attempts at a live
 * production system.
 *
 * WHY THIS IS A SCRIPT AND NOT A CONSTANT:
 * PR #1295 gave the staging bake its own named Static Web Apps environment, so
 * a separate staging hostname now exists in principle. Azure derives that
 * hostname from the app name and the environment name, but the exact form is
 * not something to guess into a workflow file: this app's non-default
 * environments carry a region segment (…-<env>.<region>.6.azurestaticapps.net)
 * that the documented pattern omits. So the gate derives candidates, proves
 * which one is real, and refuses to run at all if it cannot.
 *
 * A candidate is only accepted if it:
 *   1. is not the production hostname — absolutely, on every path;
 *   2. answers 200; and
 *   3. serves a bundle baked against the STAGING API, not the production API.
 *
 * Rule 3 is what makes this a verification rather than an assumption: it is the
 * same evidence the SWA workflow uses to police its own environment isolation.
 * If nothing verifies, this exits non-zero with the candidates it tried. It
 * never falls back to production.
 *
 * Env:
 *   SWA_PRODUCTION_HOST     (required) hostname the gate must never drive
 *   STAGING_API_URL         (required) API the tokens are minted against
 *   PRODUCTION_API_URL      (required) API that must not appear in the bundle
 *   SWA_STAGING_ENVIRONMENT (optional) named environment, default "staging"
 *   SWA_REGION              (optional) region segment used by named environments
 *   UX_FRONTEND_URL         (optional) explicit target; still fully verified
 *
 * Output: writes frontend_url / frontend_url_source to $GITHUB_OUTPUT.
 */

const fs = require('fs');
const http = require('http');
const https = require('https');

const MAX_ASSETS_INSPECTED = 6;
const REQUEST_TIMEOUT_MS = 20000;

/**
 * Candidate hostnames for a named Static Web Apps environment.
 *
 * Azure publishes named environments as <app>-<environment> alongside the
 * default hostname. Which suffix follows differs between apps, so both observed
 * forms are offered and the caller proves which one exists:
 *   - <app>-<env>.<zone>            the form documented in the SWA workflow
 *   - <app>-<env>.<region>.<zone>   the form this app's environments actually use
 */
function deriveCandidateHosts({ productionHost, environment, region }) {
  if (!productionHost || !environment) return [];

  const firstDot = productionHost.indexOf('.');
  if (firstDot <= 0) return [];

  const appName = productionHost.slice(0, firstDot);
  const zone = productionHost.slice(firstDot + 1);
  const base = `${appName}-${environment}`;

  const candidates = [`${base}.${zone}`];
  if (region) candidates.push(`${base}.${region}.${zone}`);

  return candidates.filter(host => host !== productionHost);
}

function normaliseUrl(value) {
  const trimmed = String(value || '').trim();
  if (!trimmed) return null;
  const withScheme = /^https?:\/\//i.test(trimmed) ? trimmed : `https://${trimmed}`;
  try {
    const url = new URL(withScheme);
    return `${url.protocol}//${url.host}`;
  } catch {
    return null;
  }
}

// Lower-cased and stripped of the trailing root-zone dot, which addresses the
// same host but would otherwise slip past a string comparison.
function canonicalHost(value) {
  return String(value || '').toLowerCase().replace(/\.+$/, '');
}

function hostOf(url) {
  try {
    return canonicalHost(new URL(url).hostname);
  } catch {
    return '';
  }
}

/**
 * Does this bundle belong to the staging bake?
 *
 * The frontend ships an API_URLS map that names every environment, so the
 * production URL legitimately appears as a map value even in a staging build.
 * That one shape is stripped before looking for production leakage — the same
 * allowance the SWA workflow's own isolation probe makes, inverted.
 */
function bakeVerdict(bundleText, { stagingApiUrl, productionApiUrl }) {
  if (!bundleText) {
    return { ok: false, reason: 'no JavaScript bundle content could be read' };
  }
  if (!bundleText.includes(stagingApiUrl)) {
    return { ok: false, reason: `bundle does not reference the staging API (${stagingApiUrl})` };
  }

  const mapEntry = new RegExp(`production\\s*:\\s*['"]${escapeRegExp(productionApiUrl)}['"]`, 'g');
  const withoutMap = bundleText.replace(mapEntry, '');
  if (withoutMap.includes(productionApiUrl)) {
    return { ok: false, reason: `bundle is baked against the production API (${productionApiUrl})` };
  }

  return { ok: true, reason: 'bundle is baked against the staging API' };
}

function escapeRegExp(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/**
 * Entry chunks referenced by index.html. Enough to tell which API was baked in
 * without downloading the whole site.
 */
function extractAssetUrls(html, baseUrl) {
  const urls = [];
  const pattern = /<(?:script|link)\b[^>]*?(?:src|href)\s*=\s*["']([^"']+\.js)["'][^>]*>/gi;
  let match;
  while ((match = pattern.exec(html)) !== null) {
    try {
      urls.push(new URL(match[1], `${baseUrl}/`).toString());
    } catch {
      // Unparseable asset reference: nothing useful to fetch.
    }
    if (urls.length >= MAX_ASSETS_INSPECTED) break;
  }
  return urls;
}

function fetchText(url) {
  return new Promise((resolve) => {
    const lib = url.startsWith('https') ? https : http;
    const req = lib.get(url, { headers: { 'User-Agent': 'ux-coverage-ci/1.0' } }, (res) => {
      let data = '';
      res.on('data', chunk => { data += chunk; });
      res.on('end', () => resolve({ status: res.statusCode, body: data }));
    });
    req.on('error', error => resolve({ status: 0, body: '', error: error.message }));
    req.setTimeout(REQUEST_TIMEOUT_MS, () => {
      req.destroy();
      resolve({ status: 0, body: '', error: 'request timeout' });
    });
  });
}

/**
 * Verify one candidate. Returns { ok, reason }.
 */
async function verifyCandidate(url, options, get) {
  const root = await get(`${url}/`);
  if (root.status !== 200) {
    return { ok: false, reason: root.error ? `unreachable (${root.error})` : `HTTP ${root.status}` };
  }

  const assets = extractAssetUrls(root.body, url);
  if (assets.length === 0) {
    return { ok: false, reason: 'index.html referenced no JavaScript bundle' };
  }

  let bundleText = '';
  for (const asset of assets) {
    const response = await get(asset);
    if (response.status === 200) bundleText += response.body;
  }

  return bakeVerdict(bundleText, options);
}

/**
 * Resolve and verify. Throws with an operator-readable message on failure.
 */
async function resolveFrontendUrl(options, get = fetchText) {
  const { productionHost, stagingApiUrl, productionApiUrl, environment, region, override } = options;

  const missing = [];
  if (!productionHost) missing.push('SWA_PRODUCTION_HOST');
  if (!stagingApiUrl) missing.push('STAGING_API_URL');
  if (!productionApiUrl) missing.push('PRODUCTION_API_URL');
  if (missing.length > 0) {
    throw new Error(`Cannot resolve a frontend target: ${missing.join(', ')} not set.`);
  }

  const normalisedProductionHost = canonicalHost(productionHost);
  const attempts = [];

  let candidates;
  let source;
  if (override) {
    const normalised = normaliseUrl(override);
    if (!normalised) {
      throw new Error(`The supplied frontend URL is not a valid URL: ${override}`);
    }
    candidates = [normalised];
    source = 'explicit';
  } else {
    candidates = deriveCandidateHosts({
      productionHost,
      environment: environment || 'staging',
      region,
    }).map(host => `https://${host}`);
    source = 'derived';
  }

  if (candidates.length === 0) {
    throw new Error(
      `Cannot derive a pre-production hostname from ${productionHost}. ` +
      'Set UX_FRONTEND_URL to the environment the test tokens belong to.'
    );
  }

  for (const candidate of candidates) {
    // Absolute, on every path: this gate mints staging credentials and must not
    // drive the live production frontend.
    if (hostOf(candidate) === normalisedProductionHost) {
      attempts.push({
        url: candidate,
        reason: 'refused: this is the production hostname, and the gate holds staging credentials',
      });
      continue;
    }

    const verdict = await verifyCandidate(candidate, { stagingApiUrl, productionApiUrl }, get);
    attempts.push({ url: candidate, reason: verdict.reason });
    if (verdict.ok) {
      return { url: candidate, source, attempts };
    }
  }

  const detail = attempts.map(a => `  - ${a.url}: ${a.reason}`).join('\n');
  throw new Error(
    'No verified pre-production frontend was found, so the UX coverage gate has ' +
    'nothing it may legitimately test.\n' +
    `Tokens are minted against ${stagingApiUrl}, so the target must be the ` +
    'matching pre-production Static Web Apps environment.\n' +
    `Tried:\n${detail}\n` +
    'Fix the pre-production deployment, or set UX_FRONTEND_URL to the correct ' +
    'hostname. Pointing this gate at production is not an option.'
  );
}

async function main() {
  console.log('🌐 Resolving UX coverage frontend target');
  console.log('='.repeat(50));

  const options = {
    productionHost: process.env.SWA_PRODUCTION_HOST,
    stagingApiUrl: process.env.STAGING_API_URL,
    productionApiUrl: process.env.PRODUCTION_API_URL,
    environment: process.env.SWA_STAGING_ENVIRONMENT,
    region: process.env.SWA_REGION,
    override: process.env.UX_FRONTEND_URL,
  };

  const resolved = await resolveFrontendUrl(options);

  resolved.attempts.forEach(attempt => {
    console.log(`  ${attempt.url}: ${attempt.reason}`);
  });
  console.log(`\n✅ Frontend target (${resolved.source}): ${resolved.url}`);

  if (process.env.GITHUB_OUTPUT) {
    fs.appendFileSync(
      process.env.GITHUB_OUTPUT,
      `frontend_url=${resolved.url}\nfrontend_url_source=${resolved.source}\n`
    );
  }
}

module.exports = {
  deriveCandidateHosts,
  bakeVerdict,
  extractAssetUrls,
  normaliseUrl,
  resolveFrontendUrl,
};

if (require.main === module) {
  main().catch(error => {
    console.error(`\n❌ ${error.message}`);
    process.exit(1);
  });
}
