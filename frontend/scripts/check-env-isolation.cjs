/**
 * CI Guardrail: Environment Isolation Check
 * 
 * Fails the build if a staging/non-production build contains production API URLs.
 * This prevents accidental cross-environment data access.
 */

const fs = require('fs');
const path = require('path');

// Production URLs that should NEVER appear in non-production builds
const PRODUCTION_PATTERNS = [
  'app-qgp-prod.azurewebsites.net',
];

// Check environment
const VITE_ENVIRONMENT = process.env.VITE_ENVIRONMENT || '';
const VITE_API_URL = process.env.VITE_API_URL || '';
const isProductionBuild = VITE_ENVIRONMENT === 'production' || VITE_API_URL.includes('prod');

console.log('🔍 Environment Isolation Check');
console.log(`   VITE_ENVIRONMENT: ${VITE_ENVIRONMENT || '(not set)'}`);
console.log(`   VITE_API_URL: ${VITE_API_URL || '(not set)'}`);
console.log(`   Is Production Build: ${isProductionBuild}`);
console.log('');

// Skip check for production builds - they're allowed to have prod URLs
if (isProductionBuild) {
  console.log('✅ Production build - skipping environment isolation check');
  process.exit(0);
}

const distDir = path.join(__dirname, '..', 'dist');

if (!fs.existsSync(distDir)) {
  console.log('⚠️  No dist directory found - skipping check');
  process.exit(0);
}

// Recursively find all JS files in dist
function findJsFiles(dir) {
  const files = [];
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...findJsFiles(fullPath));
    } else if (entry.name.endsWith('.js')) {
      files.push(fullPath);
    }
  }
  
  return files;
}

const jsFiles = findJsFiles(distDir);
console.log(`   Checking ${jsFiles.length} JavaScript files...`);
console.log('');

let violations = [];

for (const file of jsFiles) {
  const content = fs.readFileSync(file, 'utf-8');
  
  for (const pattern of PRODUCTION_PATTERNS) {
    if (content.includes(pattern)) {
      const relativePath = path.relative(distDir, file);
      violations.push({
        file: relativePath,
        pattern: pattern,
      });
    }
  }
}

if (violations.length > 0) {
  console.log('❌ ENVIRONMENT ISOLATION VIOLATION DETECTED');
  console.log('');
  console.log('   Non-production build contains production API URLs:');
  console.log('');
  
  for (const v of violations) {
    console.log(`   📁 ${v.file}`);
    console.log(`      Contains: ${v.pattern}`);
    console.log('');
  }
  
  console.log('   This is a security issue. Non-production builds should not');
  console.log('   contain hardcoded production API URLs.');
  console.log('');
  console.log('   Fix: Ensure VITE_API_URL is set to the staging/dev API URL');
  console.log('   during the build process.');
  console.log('');
  
  process.exit(1);
}

console.log('✅ Environment isolation check passed');
console.log('   No production URLs found in non-production build');
process.exit(0);
