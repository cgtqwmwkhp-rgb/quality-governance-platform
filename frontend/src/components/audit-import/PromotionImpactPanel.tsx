import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/Card'

type PromotionImpactPanelProps = {
  approvedCount: number
  acceptedClauseCount: number
  acceptedActionCandidates: number
  acceptedRiskCandidates: number
  schemeAlignment?: Record<string, unknown> | null
}

export function PromotionImpactPanel({
  approvedCount,
  acceptedClauseCount,
  acceptedActionCandidates,
  acceptedRiskCandidates,
  schemeAlignment,
}: PromotionImpactPanelProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Promotion impact</CardTitle>
        <CardDescription>
          What the accepted drafts will write into the live governance system.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {approvedCount > 0 ? (
          <p
            className="text-xs text-muted-foreground"
            data-testid="import-review-impact-attest-next"
            role="status"
          >
            Next: Promote Now, then Confirm — two clicks to attest accepted drafts.
          </p>
        ) : null}
        <div className="grid gap-3 md:grid-cols-2">
          <div className="rounded-lg border border-border p-4">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">
              Accepted findings
            </p>
            <p className="mt-1 font-medium text-foreground">{approvedCount}</p>
          </div>
          <div className="rounded-lg border border-border p-4">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">
              ISO evidence links
            </p>
            <p className="mt-1 font-medium text-foreground">{acceptedClauseCount}</p>
          </div>
          <div className="rounded-lg border border-border p-4">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">
              Action candidates
            </p>
            <p className="mt-1 font-medium text-foreground">{acceptedActionCandidates}</p>
          </div>
          <div className="rounded-lg border border-border p-4">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">
              Risk candidates
            </p>
            <p className="mt-1 font-medium text-foreground">{acceptedRiskCandidates}</p>
          </div>
        </div>
        {schemeAlignment ? (
          <div className="rounded-lg border border-border p-4">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">
              Scheme alignment
            </p>
            <p className="mt-1 font-medium text-foreground">
              {String(schemeAlignment.status || 'pending').replace(/_/g, ' ')}
            </p>
            {schemeAlignment.reason ? (
              <p className="mt-1 text-xs text-muted-foreground">
                {String(schemeAlignment.reason)}
              </p>
            ) : null}
          </div>
        ) : null}
      </CardContent>
    </Card>
  )
}
