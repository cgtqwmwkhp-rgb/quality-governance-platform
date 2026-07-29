/**
 * Per-workflow result files for the workflow audit.
 *
 * The audit used to accumulate results in a module-level array and write them in
 * a single `afterAll`. That is only correct while every test runs in one worker
 * process, which Playwright does not guarantee: it retires a worker after a test
 * fails and runs the remaining tests in a fresh one. With the group's serial mode
 * lifted, a failing first journey therefore left the later journeys in a second
 * worker whose array started empty — and whichever `afterAll` ran last
 * overwrote the artifact with its own partial view.
 *
 * Each journey now writes its own file as soon as it finishes, and the merge
 * reads the directory. That survives worker recycling, retries (the last attempt
 * overwrites its own entry) and parallel workers.
 */

import * as fs from 'fs';
import * as path from 'path';

export const RESULTS_DIR = path.join(__dirname, '..', 'results');
export const ENTRIES_DIR = path.join(RESULTS_DIR, 'workflow-audit-entries');
export const OUTPUT_PATH = path.join(RESULTS_DIR, 'workflow_audit.json');

/** Filesystem-safe name for a workflow id. */
function entryFileName(workflowId: string): string {
  return `${workflowId.replace(/[^A-Za-z0-9._-]/g, '_')}.json`;
}

/**
 * Drop entries from any previous run.
 *
 * Called from global setup so it happens exactly once, before any worker starts.
 * Doing it per worker would let a later worker delete an earlier one's results.
 */
export function clearWorkflowAuditEntries(): void {
  fs.rmSync(ENTRIES_DIR, { recursive: true, force: true });
  fs.mkdirSync(ENTRIES_DIR, { recursive: true });
}

export function writeWorkflowAuditEntry(workflowId: string, entry: unknown): void {
  fs.mkdirSync(ENTRIES_DIR, { recursive: true });
  fs.writeFileSync(
    path.join(ENTRIES_DIR, entryFileName(workflowId)),
    JSON.stringify(entry, null, 2),
  );
}

export function readWorkflowAuditEntries<T>(): T[] {
  if (!fs.existsSync(ENTRIES_DIR)) return [];
  return fs
    .readdirSync(ENTRIES_DIR)
    .filter((name) => name.endsWith('.json'))
    .map((name) => {
      const raw = fs.readFileSync(path.join(ENTRIES_DIR, name), 'utf-8');
      return JSON.parse(raw) as T;
    });
}
