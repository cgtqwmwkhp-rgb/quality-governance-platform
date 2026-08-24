/**
 * Per-workflow result files for the workflow audit.
 *
 * A thin, named front for the shared per-entry store in ./audit-entries.ts. The
 * mechanism (and why an in-memory array cannot survive worker recycling,
 * retries or parallel workers) is documented there; the page, link and button
 * audits now use the same store.
 */

import { RESULTS_DIR as AUDIT_RESULTS_DIR, workflowAuditStore } from './audit-entries';

export const RESULTS_DIR = AUDIT_RESULTS_DIR;
export const ENTRIES_DIR = workflowAuditStore.entriesDir;
export const OUTPUT_PATH = workflowAuditStore.outputPath;

/**
 * Drop entries from any previous run.
 *
 * Called from global setup so it happens exactly once, before any worker starts.
 * Doing it per worker would let a later worker delete an earlier one's results.
 */
export function clearWorkflowAuditEntries(): void {
  workflowAuditStore.clear();
}

export function writeWorkflowAuditEntry(workflowId: string, entry: unknown): void {
  workflowAuditStore.write(workflowId, entry);
}

export function readWorkflowAuditEntries<T>(): T[] {
  return workflowAuditStore.readAll<T>();
}
