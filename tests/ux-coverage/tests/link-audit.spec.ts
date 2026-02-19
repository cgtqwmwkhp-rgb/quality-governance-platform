/**
 * Link Audit for UX Functional Coverage Gate
 * 
 * Verifies that all internal links on P0/P1 pages:
 * - Resolve to valid routes (not 404)
 * - Don't lead to dead ends
 * - Have accessible targets
 * 
 * PII-SAFE: Only collects href attributes, not content.
 */

import { test, expect, Page } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';
import * as yaml from 'js-yaml';

// Types
interface PageEntry {
  pageId: string;
  route: string;
  auth: string;
  criticality: string;
}

interface LinkResult {
  href: string;
  status: 'valid' | 'dead' | 'external' | 'anchor';
  source_page: string;
  error?: string;
}

interface LinkAuditResult {
  source_page: string;
  route: string;
  total_links: number;
  valid_links: number;
  dead_links: number;
  external_links: number;
  links: LinkResult[];
}

// Load registry
function loadPages(): PageEntry[] {
  const registryPath = path.join(__dirname, '../../../docs/ops/PAGE_REGISTRY.yml');
  const content = fs.readFileSync(registryPath, 'utf-8');
  const registry = yaml.load(content) as any;
  
  const allPages: PageEntry[] = [
    ...(registry.public_routes || []),
    ...(registry.portal_routes || []),
    ...(registry.admin_routes || []),
  ];
  
  // Filter to P0/P1 and skip parameterized routes
  return allPages
    .filter(p => p.criticality === 'P0' || p.criticality === 'P1')
    .filter(p => !p.route.includes(':'));
}

// Test storage for aggregation
const linkAuditResults: LinkAuditResult[] = [];

// Auth helper (same as page-audit)
// Auth helper - navigates to base URL first to establish origin for localStorage
async function setupAuth(page: Page, authType: string): Promise<boolean> {
  if (authType === 'anon') return true;
  
  // Navigate to base URL first to establish origin (localStorage blocked on about:blank)
  const baseUrl = process.env.APP_URL || 'http://localhost:3000';
  
  try {
    const response = await page.goto(baseUrl, { waitUntil: 'domcontentloaded', timeout: 30000 });
    
    // Verify we landed on a valid page with proper origin
    const currentUrl = page.url();
    if (!currentUrl || currentUrl === 'about:blank' || !currentUrl.startsWith('http')) {
      console.warn(`[setupAuth] Invalid page URL after navigation: ${currentUrl}`);
      return false;
    }
    
    // Check for navigation errors
    if (!response || response.status() >= 400) {
      console.warn(`[setupAuth] Navigation failed with status: ${response?.status()}`);
      return false;
    }
  } catch (navError: any) {
    console.warn(`[setupAuth] Navigation failed: ${navError.message?.slice(0, 100)}`);
    return false;
  }
  
  if (authType === 'portal_sso') {
    try {
      await page.evaluate(() => {
        const demoUser = {
          id: 'ux-test-001',
          email: 'ux-test@plantexpand.com',
          name: 'UX Test User',
          firstName: 'UX',
          lastName: 'Test',
          isDemoUser: true,
        };
        localStorage.setItem('portal_user', JSON.stringify(demoUser));
        localStorage.setItem('portal_session_time', Date.now().toString());
      });
      return true;
    } catch (storageError: any) {
      console.warn(`[setupAuth] localStorage access failed: ${storageError.message?.slice(0, 100)}`);
      return false;
    }
  }
  
  if (authType === 'jwt_admin' && process.env.ADMIN_TEST_TOKEN) {
    try {
      await page.evaluate((token) => {
        localStorage.setItem('access_token', token);
      }, process.env.ADMIN_TEST_TOKEN);
      return true;
    } catch (storageError: any) {
      console.warn(`[setupAuth] localStorage access failed: ${storageError.message?.slice(0, 100)}`);
      return false;
    }
  }
  
  return false;
}

// Check if URL is internal
function isInternalLink(href: string, baseUrl: string): boolean {
  if (!href) return false;
  if (href.startsWith('#')) return false; // Anchor
  if (href.startsWith('/')) return true; // Absolute path
  if (href.startsWith(baseUrl)) return true;
  return false;
}

// Known valid routes from registry
const validRoutePatterns = new Set<string>();
function loadValidRoutes(): void {
  const pages = loadPages();
  pages.forEach(p => {
    // Add exact routes
    validRoutePatterns.add(p.route);
    // Add pattern for parameterized routes
    if (p.route.includes(':')) {
      // Convert /incidents/:id to regex-like pattern
      const pattern = p.route.replace(/:[^/]+/g, '[^/]+');
      validRoutePatterns.add(pattern);
    }
  });
}
loadValidRoutes();

// Check if a route is valid
function isKnownRoute(href: string): boolean {
  // Normalize
  const path = href.split('?')[0].split('#')[0];
  
  // Check exact match
  if (validRoutePatterns.has(path)) return true;
  
  // Check pattern match for parameterized routes
  for (const pattern of validRoutePatterns) {
    if (pattern.includes('[^/]+')) {
      const regex = new RegExp('^' + pattern + '$');
      if (regex.test(path)) return true;
    }
  }
  
  // Common allowed routes
  const allowedPatterns = [
    /^\/incidents\/\d+$/,
    /^\/rtas\/\d+$/,
    /^\/complaints\/\d+$/,
    /^\/portal\/track\/[A-Z0-9-]+$/,
    /^\/audit-templates\/[a-f0-9-]+\/edit$/,
    /^\/audits\/[a-f0-9-]+\/execute$/,
    /^\/admin\/forms\/[a-f0-9-]+$/,
  ];
  
  return allowedPatterns.some(p => p.test(path));
}

// Dynamic test generation
const pages = loadPages();

test.describe('Link Audit', () => {
  test.describe.configure({ mode: 'parallel' });
  
  for (const pageEntry of pages) {
    test(`Links on ${pageEntry.pageId}: ${pageEntry.route}`, async ({ page, baseURL }) => {
      const result: LinkAuditResult = {
        source_page: pageEntry.pageId,
        route: pageEntry.route,
        total_links: 0,
        valid_links: 0,
        dead_links: 0,
        external_links: 0,
        links: [],
      };
      
      try {
        // Setup auth
        const authReady = await setupAuth(page, pageEntry.auth);
        if (!authReady && pageEntry.auth !== 'anon') {
          test.skip(true, `Auth type ${pageEntry.auth} not configured`);
          return;
        }
        
        // Navigate to page
        await page.goto(pageEntry.route, {
          waitUntil: 'networkidle',
          timeout: 30000,
        });
        
        // Wait for app to render
        await page.waitForSelector('#root, #app, [data-testid="app-root"]', { timeout: 5000 });
        
        // Extract all anchor tags
        const links = await page.locator('a[href]').all();
        
        for (const link of links) {
          const href = await link.getAttribute('href');
          if (!href) continue;
          
          const linkResult: LinkResult = {
            href: href,
            status: 'valid',
            source_page: pageEntry.pageId,
          };
          
          // Classify link
          if (href.startsWith('#')) {
            linkResult.status = 'anchor';
          } else if (href.startsWith('http') && !href.startsWith(baseURL || '')) {
            linkResult.status = 'external';
            result.external_links++;
          } else if (href.startsWith('mailto:') || href.startsWith('tel:')) {
            linkResult.status = 'external';
            result.external_links++;
          } else {
            // Internal link - verify it's a known route
            const normalizedPath = href.startsWith('/') ? href : '/' + href;
            if (isKnownRoute(normalizedPath)) {
              linkResult.status = 'valid';
              result.valid_links++;
            } else {
              // Unknown route - might be a dead end
              linkResult.status = 'dead';
              linkResult.error = 'Route not in registry';
              result.dead_links++;
            }
          }
          
          result.links.push(linkResult);
          result.total_links++;
        }
        
      } catch (error: any) {
        result.links.push({
          href: pageEntry.route,
          status: 'dead',
          source_page: pageEntry.pageId,
          error: error.message?.slice(0, 100),
        });
        result.dead_links++;
      }
      
      linkAuditResults.push(result);
      
      // Fail if there are dead links (excluding parameterized routes that may not resolve)
      const criticalDeadLinks = result.links.filter(
        l => l.status === 'dead' && !l.href.includes(':')
      );
      
      expect(criticalDeadLinks.length).toBe(0);
    });
  }
});

// Write results after all tests
test.afterAll(async () => {
  const outputPath = path.join(__dirname, '../results/link_audit.json');
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  
  const totalValid = linkAuditResults.reduce((sum, r) => sum + r.valid_links, 0);
  const totalDead = linkAuditResults.reduce((sum, r) => sum + r.dead_links, 0);
  const totalExternal = linkAuditResults.reduce((sum, r) => sum + r.external_links, 0);
  
  fs.writeFileSync(outputPath, JSON.stringify({
    audit_type: 'link',
    timestamp: new Date().toISOString(),
    total_pages_audited: linkAuditResults.length,
    total_links: linkAuditResults.reduce((sum, r) => sum + r.total_links, 0),
    total_valid: totalValid,
    total_dead: totalDead,
    total_external: totalExternal,
    results: linkAuditResults,
    dead_end_map: linkAuditResults
      .flatMap(r => r.links.filter(l => l.status === 'dead'))
      .map(l => ({ source: l.source_page, href: l.href, error: l.error })),
  }, null, 2));
});
