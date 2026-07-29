/**
 * Per-entry result files for the UX coverage audits.
 *
 * Every audit used to accumulate its results in a module-level array and write
 * them in a single `afterAll`. That is only correct while every test in the file
 * runs in one process, which Playwright does not guarantee:
 *
 *  - `fullyParallel: true` with `workers: 2` (playwright.config.ts) runs a
 *    `mode: 'parallel'` group across two worker *processes*. Each holds its own
 *    array, each `afterAll` writes the same path, and the last writer wins — so
 *    the page audit reported 18 entries for 36 declared P0/P1 pages.
 *  - Playwright retires a worker after a test fails, so the tests after a
 *    failure run in a fresh process whose array starts empty.
 *  - A retry re-runs the test in a new process too.
 *
 * Each test now writes its own file as soon as it finishes and the merge reads
 * the directory, so entries are merged rather than overwritten however the run
 * was split. Writes go via a temporary file and `rename`, which is atomic on
 * POSIX: a merge running concurrently in another worker can only ever see a
 * complete file, never a half-written one.
 */

import * as crypto from 'crypto';
import * as fs from 'fs';
import * as path from 'path';

export const RESULTS_DIR = path.join(__dirname, '..', 'results');

export interface AuditEntryStore {
  /** Directory holding this audit's per-entry files. */
  readonly entriesDir: string;
  /** The merged artifact the aggregator reads. */
  readonly outputPath: string;
  /** Drop entries from any previous run. Call once, before any worker starts. */
  clear(): void;
  /** Record one entry. Writing the same id again replaces it (retries). */
  write(entryId: string, entry: unknown): void;
  /** Every entry recorded by any worker in this run. */
  readAll<T>(): T[];
}

/**
 * A readable filename that is still unique per entry id.
 *
 * The readable part is lossy — `a::b` and `a__b` both sanitise to `a__b` — so a
 * digest of the original id is appended. Two entries collapsing into one file
 * would silently shrink the artifact, which is the failure mode this module
 * exists to prevent.
 */
function entryFileName(entryId: string): string {
  const readable = entryId.replace(/[^A-Za-z0-9._-]/g, '_').slice(0, 80);
  const digest = crypto.createHash('sha1').update(entryId).digest('hex').slice(0, 8);
  return `${readable}-${digest}.json`;
}

export function createAuditEntryStore(name: string, outputFileName: string): AuditEntryStore {
  const entriesDir = path.join(RESULTS_DIR, `${name}-entries`);
  const outputPath = path.join(RESULTS_DIR, outputFileName);

  return {
    entriesDir,
    outputPath,

    clear(): void {
      fs.rmSync(entriesDir, { recursive: true, force: true });
      fs.mkdirSync(entriesDir, { recursive: true });
    },

    write(entryId: string, entry: unknown): void {
      fs.mkdirSync(entriesDir, { recursive: true });
      const target = path.join(entriesDir, entryFileName(entryId));
      const temp = `${target}.${process.pid}.tmp`;
      fs.writeFileSync(temp, JSON.stringify(entry, null, 2));
      fs.renameSync(temp, target);
    },

    readAll<T>(): T[] {
      if (!fs.existsSync(entriesDir)) return [];
      return fs
        .readdirSync(entriesDir)
        .filter((name) => name.endsWith('.json'))
        .map((name) => JSON.parse(fs.readFileSync(path.join(entriesDir, name), 'utf-8')) as T);
    },
  };
}

export const pageAuditStore = createAuditEntryStore('page-audit', 'page_audit.json');
export const linkAuditStore = createAuditEntryStore('link-audit', 'link_audit.json');
export const buttonAuditStore = createAuditEntryStore('button-audit', 'button_audit.json');
export const workflowAuditStore = createAuditEntryStore('workflow-audit', 'workflow_audit.json');

export const ALL_AUDIT_STORES: AuditEntryStore[] = [
  pageAuditStore,
  linkAuditStore,
  buttonAuditStore,
  workflowAuditStore,
];

/**
 * Order entries as the registry declares them, so the artifact reads the same
 * way whichever worker happened to write which entry.
 */
export function inDeclarationOrder<T>(entries: T[], declared: string[], idOf: (entry: T) => string): T[] {
  const position = new Map(declared.map((id, index) => [id, index]));
  return [...entries].sort(
    (a, b) =>
      (position.get(idOf(a)) ?? Number.MAX_SAFE_INTEGER) -
      (position.get(idOf(b)) ?? Number.MAX_SAFE_INTEGER),
  );
}
