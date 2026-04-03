#!/usr/bin/env node

/**
 * Scans .tsx files for t('...') calls and validates every key exists in en.json.
 * Exit code 1 if missing keys are found.
 */

import { readFileSync, readdirSync, statSync } from 'fs';
import { join, relative } from 'path';

const LOCALE_FILE = join(import.meta.dirname, '..', 'frontend', 'src', 'i18n', 'locales', 'en.json');
const CY_LOCALE_FILE = join(import.meta.dirname, '..', 'frontend', 'src', 'i18n', 'locales', 'cy.json');
const SRC_DIR = join(import.meta.dirname, '..', 'frontend', 'src');

const T_CALL_RE = /\bt\(\s*['"`]([^'"`\n]+?)['"`]/g;

function walk(dir) {
  const files = [];
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    const st = statSync(full);
    if (st.isDirectory()) {
      if (entry === 'node_modules' || entry === '__tests__' || entry === 'test') continue;
      files.push(...walk(full));
    } else if (entry.endsWith('.tsx') || entry.endsWith('.ts')) {
      files.push(full);
    }
  }
  return files;
}

const locale = JSON.parse(readFileSync(LOCALE_FILE, 'utf-8'));
const knownKeys = new Set(Object.keys(locale));

const missing = [];
const files = walk(SRC_DIR);

for (const file of files) {
  const content = readFileSync(file, 'utf-8');
  let match;
  T_CALL_RE.lastIndex = 0;
  const localContent = content;
  const re = new RegExp(T_CALL_RE.source, 'g');
  while ((match = re.exec(localContent)) !== null) {
    const key = match[1];
    if (key.includes('{{') || key.includes('$')) continue;
    if (!knownKeys.has(key)) {
      const line = localContent.substring(0, match.index).split('\n').length;
      missing.push({ file: relative(SRC_DIR, file), key, line });
    }
  }
}

// --- Locale parity check (cy.json vs en.json) – advisory, non-blocking ---
let cyParityMessage = '';
try {
  const cyLocale = JSON.parse(readFileSync(CY_LOCALE_FILE, 'utf-8'));
  const cyKeys = new Set(Object.keys(cyLocale));
  const missingInCy = [...knownKeys].filter(k => !cyKeys.has(k));
  const coverage = ((cyKeys.size / knownKeys.size) * 100).toFixed(1);
  cyParityMessage = `ℹ️  cy.json locale coverage: ${cyKeys.size}/${knownKeys.size} keys (${coverage}%)`;
  if (missingInCy.length > 0) {
    cyParityMessage += ` — ${missingInCy.length} key(s) missing (advisory)`;
  }
  if (parseFloat(coverage) < 65) {
    console.error(cyParityMessage);
    console.error(`\n❌ Welsh (cy) locale coverage ${coverage}% is below the required 65% threshold.`);
    process.exit(1);
  }
} catch {
  cyParityMessage = '⚠️  Could not read cy.json for parity check (file missing or invalid)';
}

if (missing.length > 0) {
  console.error(`\n❌ Found ${missing.length} missing i18n key(s):\n`);
  for (const { file, key, line } of missing) {
    console.error(`  ${file}:${line}  →  "${key}"`);
  }
  console.error(`\nAdd them to frontend/src/i18n/locales/en.json\n`);
  console.log(cyParityMessage);
  process.exit(1);
} else {
  console.log(`✅ All i18n keys validated (${knownKeys.size} keys, ${files.length} files scanned)`);
  console.log(cyParityMessage);
  process.exit(0);
}
