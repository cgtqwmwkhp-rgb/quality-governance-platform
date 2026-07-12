import type { ExternalAuditPromotionReconciliation } from '../../api/client'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/Card'

type DownstreamWorkflowLinks = {
  actions?: string
  riskRegister?: string
  uvdb?: string
}

type DownstreamWorkflowProofProps = {
  reconciliation?: ExternalAuditPromotionReconciliation
  findingsCount?: number
  actionsCount?: number
  risksCount?: number
  links?: DownstreamWorkflowLinks
  onNavigate: (path: string) => void
}

export function isCompleteReconciliation(
  reconciliation: ExternalAuditPromotionReconciliation | null | undefined,
): reconciliation is ExternalAuditPromotionReconciliation {
  return Boolean(
    reconciliation &&
      typeof reconciliation.canonical_read_model === 'string' &&
      reconciliation.materialized &&
      Array.isArray(reconciliation.proof_matrix) &&
      reconciliation.view_links &&
      typeof reconciliation.view_links === 'object',
  )
}

export function DownstreamWorkflowProof({
  reconciliation,
  findingsCount,
  actionsCount,
  risksCount,
  links,
  onNavigate,
}: DownstreamWorkflowProofProps) {
  const importProof = isCompleteReconciliation(reconciliation) ? reconciliation : null
  const hasLiveCounts =
    typeof findingsCount === 'number' &&
    typeof actionsCount === 'number' &&
    typeof risksCount === 'number'

  if (!importProof && !hasLiveCounts) {
    return null
  }

  const counts = importProof
    ? {
        findings: importProof.materialized.audit_findings,
        actions: importProof.materialized.capa_actions,
        risks: importProof.materialized.enterprise_risks,
      }
    : {
        findings: findingsCount as number,
        actions: actionsCount as number,
        risks: risksCount as number,
      }
  const viewLinks: DownstreamWorkflowLinks = importProof
    ? {
        actions: importProof.view_links.actions,
        riskRegister: importProof.view_links.risk_register,
        uvdb: importProof.view_links.uvdb,
      }
    : links || {}

  return (
    <Card className="border-border/70">
      <CardHeader>
        <CardTitle className="text-base">Downstream Workflow Proof</CardTitle>
        {importProof ? (
          <CardDescription>
            Canonical read model: {importProof.canonical_read_model.replace(/_/g, ' ')}.
            {importProof.failed_total > 0
              ? ` ${importProof.failed_total} accepted draft(s) still need recovery before the workflow is complete.`
              : ' All downstream workflow steps are traceable from this import.'}{' '}
            UVDB and unified registry rows appear here only after findings materialize; if promotion did
            not finish, sync or registry proof may show as missing—that usually reflects sequencing, not
            a separate outage.
          </CardDescription>
        ) : (
          <CardDescription>
            This completed inspection is live in the findings, actions, and risk workflows.
          </CardDescription>
        )}
      </CardHeader>
      <CardContent className="space-y-4">
        <div className={`grid gap-3 ${importProof ? 'md:grid-cols-4' : 'md:grid-cols-3'}`}>
          <div className="rounded-lg border border-border p-3">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Findings</p>
            <p className="mt-1 text-lg font-semibold text-foreground">{counts.findings}</p>
          </div>
          <div className="rounded-lg border border-border p-3">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">CAPA Actions</p>
            <p className="mt-1 text-lg font-semibold text-foreground">{counts.actions}</p>
          </div>
          <div className="rounded-lg border border-border p-3">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Enterprise Risks</p>
            <p className="mt-1 text-lg font-semibold text-foreground">{counts.risks}</p>
          </div>
          {importProof ? (
            <div className="rounded-lg border border-border p-3">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">UVDB Sync</p>
              <p className="mt-1 text-lg font-semibold text-foreground">
                {importProof.materialized.uvdb_audit_id
                  ? `Row #${importProof.materialized.uvdb_audit_id}`
                  : 'Not visible'}
              </p>
            </div>
          ) : null}
        </div>

        {importProof ? (
          <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-4">
            {importProof.proof_matrix.map((step) => (
              <div key={step.step} className="rounded-lg border border-border p-3">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-sm font-medium text-foreground">
                    {step.step.replace(/_/g, ' ')}
                  </p>
                  <Badge
                    variant={
                      step.status === 'ok'
                        ? 'success'
                        : step.status === 'partial'
                          ? 'warning'
                          : step.status === 'none' || step.status === 'n/a'
                            ? 'secondary'
                            : 'destructive'
                    }
                  >
                    {step.status}
                  </Badge>
                </div>
                <p className="mt-1 text-xs text-muted-foreground">{step.detail}</p>
              </div>
            ))}
          </div>
        ) : null}

        {importProof && importProof.failed_total > 0 ? (
          <div className="rounded-lg border border-amber-300 bg-amber-50 p-4">
            <p className="text-sm font-medium text-amber-800">
              Accepted drafts still pending recovery
            </p>
            <p
              className="mt-1 text-xs text-amber-900"
              data-testid="import-review-proof-recover-next"
              role="status"
            >
              Next: Open failed draft, then Retry — two clicks to recover promotion.
            </p>
            <div className="mt-2 space-y-1 text-xs text-amber-900">
              {importProof.failed_drafts.map((draft, index) => (
                <p key={`failed-draft-${index}`}>
                  Draft #{String(draft.draft_id ?? '?')}:{' '}
                  {String(draft.title || draft.error || 'Promotion failed')}
                </p>
              ))}
            </div>
          </div>
        ) : null}

        <div className="flex flex-wrap gap-2">
          {viewLinks.actions ? (
            <Button
              variant="outline"
              size="sm"
              onClick={() => onNavigate(viewLinks.actions as string)}
            >
              View Audit Actions
            </Button>
          ) : null}
          {viewLinks.riskRegister ? (
            <Button
              variant="outline"
              size="sm"
              onClick={() => onNavigate(viewLinks.riskRegister as string)}
            >
              View Audit Risks
            </Button>
          ) : null}
          {viewLinks.uvdb ? (
            <Button
              variant="outline"
              size="sm"
              onClick={() => onNavigate(viewLinks.uvdb as string)}
            >
              View UVDB Sync
            </Button>
          ) : null}
        </div>

        {importProof &&
        (importProof.materialized.capa_actions > 0 ||
          importProof.materialized.enterprise_risks > 0) ? (
          <div className="mt-4 rounded-lg border border-border/80 bg-muted/30 p-4 text-sm text-muted-foreground">
            <p className="font-medium text-foreground">Governance hand-off after promotion</p>
            <p className="mt-2">
              CAPA actions from this import are live in <span className="text-foreground">Actions</span>{' '}
              as usual. Enterprise risk suggestions from the same import may appear under{' '}
              <span className="text-foreground">Risk Register → Import triage</span> until accepted or
              rejected.
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={() =>
                  onNavigate(
                    importProof.view_links.actions || '/actions?sourceType=audit_finding',
                  )
                }
              >
                Open audit-sourced actions
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => onNavigate('/risk-register?triage=import')}
              >
                Open import risk triage
              </Button>
            </div>
          </div>
        ) : null}
      </CardContent>
    </Card>
  )
}
