import { clearWorkflowAuditEntries } from './utils/workflow-audit-artifacts';

/**
 * Runs once, before any worker. Clears the previous run's per-workflow audit
 * entries so a merged artifact can never mix runs — a stale entry would let the
 * gate count a journey that did not execute this time.
 */
export default function globalSetup(): void {
  clearWorkflowAuditEntries();
}
