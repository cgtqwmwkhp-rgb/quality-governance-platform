'use strict';

/**
 * C-60 regression: the UX coverage aggregator must not invent empty result sets
 * for missing audit artifacts.
 *
 * Run with: node --test scripts/governance/__tests__/ux-coverage-c60-no-empty-fallback.test.cjs
 */

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const WORKFLOW = path.join(
  __dirname,
  '..',
  '..',
  '..',
  '.github',
  'workflows',
  'ux-functional-coverage.yml',
);

/** Strip YAML `# …` comments so historical notes cannot trip the regression. */
function activeLines(body) {
  return body
    .split('\n')
    .map((line) => line.replace(/#.*$/, ''))
    .join('\n');
}

test('ux-functional-coverage.yml does not fabricate empty results for missing audits', () => {
  const body = fs.readFileSync(WORKFLOW, 'utf8');
  const active = activeLines(body);

  // The defect was `cp … || echo '{"results":[]}' > …` — a cancelled/missing
  // audit became an empty green contribution to the denominator.
  assert.equal(
    /echo\s+['"]\{\s*"results"\s*:\s*\[\s*\]\s*\}['"]/.test(active),
    false,
    'workflow must not invent {"results":[]} when an audit artifact is absent',
  );
  assert.equal(
    /cp\s+[^\n]*\|\|\s*echo/.test(active),
    false,
    'workflow must not fall back with cp … || echo for missing audit artifacts',
  );

  // Fail-closed copy path must remain: missing files exit 1 with an error.
  assert.match(body, /Audit artifact\(s\) absent/);
  assert.match(active, /exit 1/);

  // C-50: a11y is part of the required set; still no empty invent for it.
  assert.match(active, /a11y-audit-results\/a11y_audit\.json/);
});
