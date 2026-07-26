'use strict';

/**
 * Unit tests for the UX coverage gate's frontend target resolver.
 *
 * Run with: node --test scripts/governance/__tests__/
 *
 * The property under test: the gate mints staging credentials, so it must
 * resolve a verified pre-production frontend or refuse to run — never quietly
 * fall back to the production hostname.
 */

const test = require('node:test');
const assert = require('node:assert/strict');

const {
  deriveCandidateHosts,
  bakeVerdict,
  extractAssetUrls,
  normaliseUrl,
  resolveFrontendUrl,
} = require('../resolve-ux-frontend-url.cjs');

const PRODUCTION_HOST = 'purple-water-03205fa03.6.azurestaticapps.net';
const STAGING_API = 'https://qgp-staging-plantexpand.azurewebsites.net';
const PRODUCTION_API = 'https://app-qgp-prod.azurewebsites.net';

const BASE_OPTIONS = {
  productionHost: PRODUCTION_HOST,
  stagingApiUrl: STAGING_API,
  productionApiUrl: PRODUCTION_API,
  environment: 'staging',
  region: 'westeurope',
};

const INDEX_HTML = '<!doctype html><html><head>' +
  '<script type="module" crossorigin src="/assets/index-abc123.js"></script>' +
  '<link rel="modulepreload" href="/assets/vendor-def456.js">' +
  '</head><body><div id="root"></div></body></html>';

// A real bake carries the whole API_URLS map, so the production URL appears as
// a map value in the staging bundle too.
const API_MAP = `{staging:"${STAGING_API}",production:"${PRODUCTION_API}",development:"http://localhost:8000"}`;
const STAGING_BUNDLE = `const A=${API_MAP};const base="${STAGING_API}";`;
const PRODUCTION_BUNDLE = `const A=${API_MAP};const base="${PRODUCTION_API}";`;

// Minimal HTTP stub: a map of url -> {status, body}.
function stubGet(routes) {
  const calls = [];
  const get = async (url) => {
    calls.push(url);
    return routes[url] || { status: 404, body: '' };
  };
  get.calls = calls;
  return get;
}

function siteRoutes(host, bundle) {
  return {
    [`https://${host}/`]: { status: 200, body: INDEX_HTML },
    [`https://${host}/assets/index-abc123.js`]: { status: 200, body: bundle },
    [`https://${host}/assets/vendor-def456.js`]: { status: 200, body: '' },
  };
}

test('candidate hostnames are derived from the production host and environment name', () => {
  assert.deepEqual(
    deriveCandidateHosts({ productionHost: PRODUCTION_HOST, environment: 'staging', region: 'westeurope' }),
    [
      'purple-water-03205fa03-staging.6.azurestaticapps.net',
      'purple-water-03205fa03-staging.westeurope.6.azurestaticapps.net',
    ]
  );
});

test('no region means only the documented pattern is offered', () => {
  assert.deepEqual(
    deriveCandidateHosts({ productionHost: PRODUCTION_HOST, environment: 'staging' }),
    ['purple-water-03205fa03-staging.6.azurestaticapps.net']
  );
});

test('a bundle carrying the production API in the map is still a staging bake', () => {
  assert.equal(
    bakeVerdict(STAGING_BUNDLE, { stagingApiUrl: STAGING_API, productionApiUrl: PRODUCTION_API }).ok,
    true
  );
});

test('a production bake is rejected', () => {
  const verdict = bakeVerdict(PRODUCTION_BUNDLE, {
    stagingApiUrl: STAGING_API,
    productionApiUrl: PRODUCTION_API,
  });
  assert.equal(verdict.ok, false);
  assert.match(verdict.reason, /baked against the production API/);
});

test('a bundle mentioning neither API is rejected', () => {
  const verdict = bakeVerdict('const x=1;', {
    stagingApiUrl: STAGING_API,
    productionApiUrl: PRODUCTION_API,
  });
  assert.equal(verdict.ok, false);
  assert.match(verdict.reason, /does not reference the staging API/);
});

test('asset URLs are read from script and modulepreload tags', () => {
  assert.deepEqual(extractAssetUrls(INDEX_HTML, 'https://example.test'), [
    'https://example.test/assets/index-abc123.js',
    'https://example.test/assets/vendor-def456.js',
  ]);
});

test('resolves the derived staging hostname that actually serves a staging bake', async () => {
  const host = 'purple-water-03205fa03-staging.westeurope.6.azurestaticapps.net';
  const get = stubGet(siteRoutes(host, STAGING_BUNDLE));

  const resolved = await resolveFrontendUrl(BASE_OPTIONS, get);

  assert.equal(resolved.url, `https://${host}`);
  assert.equal(resolved.source, 'derived');
  // The pattern documented in the SWA workflow was tried first and rejected.
  assert.match(resolved.attempts[0].url, /-staging\.6\.azurestaticapps\.net$/);
  assert.match(resolved.attempts[0].reason, /HTTP 404/);
});

test('refuses to resolve when no candidate exists, rather than using production', async () => {
  // Exactly today's state: the named environment has not been created, so both
  // derived hostnames 404.
  const get = stubGet({});

  await assert.rejects(
    () => resolveFrontendUrl(BASE_OPTIONS, get),
    (error) => {
      assert.match(error.message, /No verified pre-production frontend was found/);
      assert.match(error.message, /Pointing this gate at production is not an option/);
      // Names what it tried so the next person does not have to guess.
      assert.match(error.message, /purple-water-03205fa03-staging\.6\.azurestaticapps\.net/);
      assert.match(error.message, /purple-water-03205fa03-staging\.westeurope\.6\.azurestaticapps\.net/);
      assert.doesNotMatch(error.message, /Resolved/);
      return true;
    }
  );
  // It never even requested the production hostname.
  assert.equal(get.calls.some(url => url.includes(`https://${PRODUCTION_HOST}`)), false);
});

test('a candidate that serves the production bake is rejected, not accepted', async () => {
  const host = 'purple-water-03205fa03-staging.6.azurestaticapps.net';
  const get = stubGet(siteRoutes(host, PRODUCTION_BUNDLE));

  await assert.rejects(
    () => resolveFrontendUrl(BASE_OPTIONS, get),
    /baked against the production API/
  );
});

test('an explicit override pointing at production is refused', async () => {
  const get = stubGet(siteRoutes(PRODUCTION_HOST, STAGING_BUNDLE));

  await assert.rejects(
    () => resolveFrontendUrl({ ...BASE_OPTIONS, override: `https://${PRODUCTION_HOST}` }, get),
    (error) => {
      assert.match(error.message, /this is the production hostname/);
      return true;
    }
  );
  assert.deepEqual(get.calls, []);
});

test('a trailing root-zone dot does not slip past the production refusal', async () => {
  // https://host./ addresses exactly the same site.
  const get = stubGet(siteRoutes(`${PRODUCTION_HOST}.`, STAGING_BUNDLE));

  await assert.rejects(
    () => resolveFrontendUrl({ ...BASE_OPTIONS, override: `https://${PRODUCTION_HOST}.` }, get),
    /this is the production hostname/
  );
  assert.deepEqual(get.calls, []);
});

test('an explicit override is accepted only after the same bake verification', async () => {
  const host = 'purple-water-03205fa03-1301.westeurope.6.azurestaticapps.net';
  const get = stubGet(siteRoutes(host, STAGING_BUNDLE));

  const resolved = await resolveFrontendUrl({ ...BASE_OPTIONS, override: host }, get);
  assert.equal(resolved.url, `https://${host}`);
  assert.equal(resolved.source, 'explicit');

  const badGet = stubGet(siteRoutes(host, PRODUCTION_BUNDLE));
  await assert.rejects(
    () => resolveFrontendUrl({ ...BASE_OPTIONS, override: host }, badGet),
    /baked against the production API/
  );
});

test('missing configuration fails loudly rather than defaulting', async () => {
  await assert.rejects(
    () => resolveFrontendUrl({ productionHost: PRODUCTION_HOST }, stubGet({})),
    /STAGING_API_URL, PRODUCTION_API_URL not set/
  );
});

test('a site that serves no JavaScript is not accepted as the frontend', async () => {
  const host = 'purple-water-03205fa03-staging.6.azurestaticapps.net';
  const get = stubGet({ [`https://${host}/`]: { status: 200, body: '<html><body>hello</body></html>' } });

  await assert.rejects(
    () => resolveFrontendUrl(BASE_OPTIONS, get),
    /referenced no JavaScript bundle/
  );
});

test('url normalisation keeps the origin and nothing else', () => {
  assert.equal(normaliseUrl('example.test'), 'https://example.test');
  assert.equal(normaliseUrl('https://example.test/some/path?x=1'), 'https://example.test');
  assert.equal(normaliseUrl('  '), null);
  assert.equal(normaliseUrl('not a url'), null);
});
