'use strict';

/**
 * Production auto-rollback depends on PREVIOUS_IMAGE when Basic tier has no slots.
 *
 * Measured failures (30528881486, 30526435273, 30523733124): capture queried
 * `az webapp config container show --query linuxFxVersion`, which is always empty
 * because that command returns a {name,value} list — not linuxFxVersion. Deploy
 * then overwrote production, migrate failed, and auto-rollback had nothing to restore.
 *
 * C-48 (false-success when nothing deployed) is covered by the release gate in the
 * same workflow; keep that regression locked here too.
 *
 * Run with: node --test scripts/governance/__tests__/prod-auto-rollback-previous-image.test.cjs
 */

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const ROOT = path.join(__dirname, '..', '..', '..');
const WORKFLOW = path.join(ROOT, '.github', 'workflows', 'deploy-production.yml');

/** Strip YAML `# …` comments so historical notes cannot trip the regression. */
function activeLines(body) {
  return body
    .split('\n')
    .map((line) => line.replace(/#.*$/, ''))
    .join('\n');
}

test('auto-rollback capture reads DOCKER_CUSTOM_IMAGE_NAME from container show', () => {
  const active = activeLines(fs.readFileSync(WORKFLOW, 'utf8'));

  assert.match(
    active,
    /DOCKER_CUSTOM_IMAGE_NAME/,
    'capture must read DOCKER_CUSTOM_IMAGE_NAME (container show returns a settings list)',
  );
  assert.match(
    active,
    /\[\?name=='DOCKER_CUSTOM_IMAGE_NAME'\]\.value/,
    'JMESPath must select DOCKER_CUSTOM_IMAGE_NAME from the container settings list',
  );
});

test('capture must not query linuxFxVersion on config container show', () => {
  const body = fs.readFileSync(WORKFLOW, 'utf8');
  // Allow siteConfig.linuxFxVersion on `az webapp show` (valid fallback).
  // Forbid the broken pattern that always returned empty in production.
  const broken =
    /az webapp config container show[\s\S]{0,220}--query\s+"linuxFxVersion"/;
  assert.equal(
    broken.test(body),
    false,
    'az webapp config container show --query linuxFxVersion is always empty',
  );
});

test('empty previous_image refuses to overwrite production (fail-closed)', () => {
  const active = activeLines(fs.readFileSync(WORKFLOW, 'utf8'));
  assert.match(
    active,
    /Unable to capture previous production image before deploy/,
    'capture step must error when no rollback target is available',
  );
  assert.match(
    active,
    /refusing to overwrite production without a rollback target/,
    'must refuse deploy when previous_image cannot be captured',
  );
});

test('C-48: release gate still refuses success without a real deploy', () => {
  const active = activeLines(fs.readFileSync(WORKFLOW, 'utf8'));
  assert.match(
    active,
    /Release gate — refuse to conclude success without a real deploy/,
    'C-48 release gate step must remain in deploy-production.yml',
  );
  assert.match(
    active,
    /Production was not deployed/,
    'release gate must fail the run conclusion when build-and-deploy did not succeed',
  );
});

test('auto-rollback job still restores previous_image when no slot exists', () => {
  const active = activeLines(fs.readFileSync(WORKFLOW, 'utf8'));
  assert.match(active, /auto-rollback:/);
  assert.match(active, /needs\.build-and-deploy\.outputs\.previous_image/);
  assert.match(active, /--container-image-name "\$PREVIOUS_IMAGE"/);
});
