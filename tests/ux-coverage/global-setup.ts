import { ALL_AUDIT_STORES } from './utils/audit-entries';

/**
 * Runs once, before any worker. Clears the previous run's per-entry audit files
 * so a merged artifact can never mix runs — a stale entry would let the gate
 * count an entry that did not execute this time.
 *
 * Every audit is cleared on every run, not just the audit about to execute. Each
 * audit runs as its own CI job with its own checkout, so clearing the others
 * costs nothing; locally it stops a previous `--project`/single-file run from
 * leaving entries behind for the next one to merge.
 */
export default function globalSetup(): void {
  for (const store of ALL_AUDIT_STORES) {
    store.clear();
  }
}
