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
import { inDeclarationOrder, linkAuditStore } from '../utils/audit-entries';

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
  /**
   * Why this page contributed no link evidence, when it did not.
   *
   * A page that skipped for want of a token used to leave the artifact
   * altogether, which reads identically to a page with no dead links.
   */
  skipped_reason?: string;
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

/**
 * Record a page's link findings.
 *
 * This group runs in `mode: 'parallel'`, and playwright.config.ts sets
 * `fullyParallel: true` with `workers: 2` in CI — two worker *processes*, each
 * with its own copy of a module-level array, each `afterAll` writing the same
 * artifact path, last writer winning. Each page now writes its own file and the
 * merge reads the directory. See utils/audit-entries.ts.
 */
function recordResult(result: LinkAuditResult): void {
  linkAuditStore.write(result.source_page, result);
}

// Auth helper — uses addInitScript to inject token before any page JS runs,
// avoiding SSO redirects that break the navigate-then-evaluate approach.
async function setupAuth(page: Page, authType: string): Promise<boolean> {
  if (authType === 'anon') return true;

  const token =
    authType === 'portal_sso'
      ? process.env.PORTAL_TEST_TOKEN
      : authType === 'jwt_admin'
        ? process.env.ADMIN_TEST_TOKEN
        : undefined;

  if (!token) return false;

  if (authType === 'portal_sso') {
    await page.addInitScript((t: string) => {
      sessionStorage.setItem('platform_access_token', t);
      localStorage.setItem('portal_user', JSON.stringify({
        id: 'test-user-001', email: 'test@example.com',
        name: 'Test User', firstName: 'Test', lastName: 'User',
        isDemoUser: false,
      }));
      localStorage.setItem('portal_session_time', Date.now().toString());
    }, token);
  } else {
    await page.addInitScript((t: string) => {
      sessionStorage.setItem('platform_access_token', t);
    }, token);
  }

  return true;
}

// Check if URL is internal
function isInternalLink(href: string, baseUrl: string): boolean {
  if (!href) return false;
  if (href.startsWith('#')) return false; // Anchor
  if (href.startsWith('/')) return true; // Absolute path
  if (href.startsWith(baseUrl)) return true;
  return false;
}

// Known valid routes from registry (ALL routes, not just P0/P1 test pages)
const validRoutePatterns = new Set<string>();
function loadValidRoutes(): void {
  const registryPath = path.join(__dirname, '../../../docs/ops/PAGE_REGISTRY.yml');
  const content = fs.readFileSync(registryPath, 'utf-8');
  const registry = yaml.load(content) as any;
  const allRoutes: PageEntry[] = [
    ...(registry.public_routes || []),
    ...(registry.portal_routes || []),
    ...(registry.admin_routes || []),
  ];
  allRoutes.forEach(p => {
    validRoutePatterns.add(p.route);
    if (p.route.includes(':')) {
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
          // Record the skip before aborting. test.skip() throws, so a page that
          // returned here left no entry at all — and an absent entry reads
          // exactly like a page that was audited and had no dead links.
          result.skipped_reason = `Auth type ${pageEntry.auth} not configured`;
          recordResult(result);
          test.skip(true, result.skipped_reason);
          return;
        }
        
        // Navigate to page.
        // networkidle is flaky on SWA (analytics/keepalive keep the network busy on a
        // healthy SPA), so it is deliberately not used here.
        await page.goto(pageEntry.route, {
          waitUntil: 'domcontentloaded',
          timeout: 30000,
        });
        
        // Wait for the app to render something into the shell.
        //
        // frontend/index.html:24 ships `<div id="root"></div>` empty, so waiting for
        // `#root` proves only that React painted *something*. Require it to have put
        // an element there too, so a page on which React never mounts at all is
        // reported as a failure rather than as a page that happens to contain no
        // links. This does not make the link snapshot below complete — see the note
        // there.
        await page.waitForSelector('#root, #app, [data-testid="app-root"]', { timeout: 5000 });
        await page
          .locator('#root > *, #app > *, [data-testid="app-root"] > *')
          .first()
          .waitFor({ state: 'attached', timeout: 5000 });
        
        // Extract all anchor tags.
        //
        // KNOWN GAP, not fixed here (see PR body): this is an immediate snapshot
        // with no retry, taken as soon as the shell has painted, so it enumerates
        // the shell rather than the route. Measured against a local fake SPA whose
        // shell paints at once and whose route content mounts 1.5s later: 0 links
        // recorded across all 32 pages, reported as 0 dead links and a pass. The
        // same fake with content mounted synchronously recorded 256.
        //
        // Two obvious repairs do not work. Requiring at least one anchor fails the
        // portal pages, which navigate with buttons and legitimately have none.
        // Waiting for the anchor count to settle is worse than useless: a count of
        // zero is stable from the first poll, so it returns before the content
        // mounts — verified, still 0 of 256. A real fix needs an app-emitted
        // "route content rendered" marker (`<main>` is the shell's own element on
        // admin routes, so it is not one), which is a frontend change and out of
        // scope for this PR.
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
      
      recordResult(result);
      
      // Fail if there are dead links (excluding parameterized routes that may not resolve)
      const criticalDeadLinks = result.links.filter(
        l => l.status === 'dead' && !l.href.includes(':')
      );
      
      expect(criticalDeadLinks.length).toBe(0);
    });
  }
});

/**
 * Merge the per-page entry files into the artifact the aggregator reads.
 *
 * Runs in every worker, and reads the directory rather than this process's own
 * results, so the last worker to finish emits the complete set however the run
 * was split across workers or retries.
 */
test.afterAll(async () => {
  fs.mkdirSync(path.dirname(linkAuditStore.outputPath), { recursive: true });

  const results = inDeclarationOrder(
    linkAuditStore.readAll<LinkAuditResult>(),
    pages.map(p => p.pageId),
    r => r.source_page,
  );

  const totalValid = results.reduce((sum, r) => sum + r.valid_links, 0);
  const totalDead = results.reduce((sum, r) => sum + r.dead_links, 0);
  const totalExternal = results.reduce((sum, r) => sum + r.external_links, 0);

  fs.writeFileSync(linkAuditStore.outputPath, JSON.stringify({
    audit_type: 'link',
    timestamp: new Date().toISOString(),
    // How many entries the registry asked for, as opposed to how many arrived.
    // total_dead is the only number this audit contributes to the score, and an
    // entry that never reached the artifact contributes nothing to it — so a lost
    // page looks exactly like a clean one. The aggregator holds the gate when
    // this count is not met.
    expected_entries: pages.length,
    total_pages_audited: results.length,
    pages_skipped: results.filter(r => r.skipped_reason).length,
    total_links: results.reduce((sum, r) => sum + r.total_links, 0),
    total_valid: totalValid,
    total_dead: totalDead,
    total_external: totalExternal,
    results,
    dead_end_map: results
      .flatMap(r => r.links.filter(l => l.status === 'dead'))
      .map(l => ({ source: l.source_page, href: l.href, error: l.error })),
  }, null, 2));
});
