#!/usr/bin/env node
/**
 * CI Regression Guard: Ensure no HTTP API URLs in production build.
 * 
 * This script scans the built dist/ directory for any hardcoded HTTP
 * API URLs that would cause mixed content errors in production.
 * 
 * Exit codes:
 *   0 = Pass (no HTTP URLs found)
 *   1 = Fail (HTTP URLs found in build output)
 */

const fs = require('fs');
const path = require('path');

const DIST_DIR = path.join(__dirname, '..', 'dist');

// Patterns that indicate a mixed content vulnerability
const FORBIDDEN_PATTERNS = [
  /http:\/\/app-qgp-prod\.azurewebsites\.net/g,
  /http:\/\/[^"'\s]*azurewebsites\.net\/api/g,
  /http:\/\/qgp-[^"'\s]*\.azurewebsites\.net/g,
];

// File extensions to scan
const SCAN_EXTENSIONS = ['.js', '.html', '.css', '.json'];

let violations = [];

function scanFile(filePath) {
  const content = fs.readFileSync(filePath, 'utf8');
  const relativePath = path.relative(DIST_DIR, filePath);
  
  for (const pattern of FORBIDDEN_PATTERNS) {
    const matches = content.match(pattern);
    if (matches) {
      violations.push({
        file: relativePath,
        pattern: pattern.source,
        matches: matches,
      });
    }
  }
}

function scanDirectory(dir) {
  if (!fs.existsSync(dir)) {
    console.error(`Error: Directory not found: ${dir}`);
    console.error('Run "npm run build" first.');
    process.exit(1);
  }
  
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    
    if (entry.isDirectory()) {
      scanDirectory(fullPath);
    } else if (entry.isFile()) {
      const ext = path.extname(entry.name).toLowerCase();
      if (SCAN_EXTENSIONS.includes(ext)) {
        scanFile(fullPath);
      }
    }
  }
}

console.log('🔍 Scanning build output for HTTP API URLs...\n');
console.log(`   Directory: ${DIST_DIR}`);
console.log(`   Patterns:  ${FORBIDDEN_PATTERNS.length} forbidden patterns\n`);

scanDirectory(DIST_DIR);

if (violations.length > 0) {
  console.error('❌ FAIL: Found HTTP API URLs in build output!\n');
  console.error('   This will cause Mixed Content errors in production.\n');
  
  for (const v of violations) {
    console.error(`   File: ${v.file}`);
    console.error(`   Pattern: ${v.pattern}`);
    console.error(`   Matches: ${v.matches.join(', ')}`);
    console.error('');
  }
  
  console.error('   Fix: Ensure VITE_API_URL uses HTTPS and all API');
  console.error('   base URL references use the centralized config.\n');
  
  process.exit(1);
} else {
  console.log('✅ PASS: No HTTP API URLs found in build output.\n');
  process.exit(0);
}
