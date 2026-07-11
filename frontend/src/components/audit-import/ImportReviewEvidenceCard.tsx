import type { ExternalAuditImportJob } from '../../api/client'
import { Badge } from '../ui/Badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/Card'
import { PromotionImpactPanel } from './PromotionImpactPanel'

type ImportReviewEvidenceCardProps = {
  job: ExternalAuditImportJob
  approvedCount: number
  acceptedClauseCount: number
  acceptedActionCandidates: number
  acceptedRiskCandidates: number
  schemeAlignment?: Record<string, unknown> | null
}

export function ImportReviewEvidenceCard({
  job,
  approvedCount,
  acceptedClauseCount,
  acceptedActionCandidates,
  acceptedRiskCandidates,
  schemeAlignment,
}: ImportReviewEvidenceCardProps) {
  return (
    <div className="grid gap-4 xl:grid-cols-[1.1fr_1fr]">
      <Card>
        <CardHeader>
          <CardTitle>Evidence and mappings</CardTitle>
          <CardDescription>
            ISO evidence candidates and scheme mappings extracted from the source document.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap gap-2">
            {job.evidence_preview_json?.length ? (
              job.evidence_preview_json.slice(0, 8).map((mapping, index) => (
                <Badge key={`evidence-${index}`} variant="secondary">
                  {String(mapping.clause_number || mapping.clause_id || 'Clause')}{' '}
                  {String(mapping.standard || '')}
                </Badge>
              ))
            ) : (
              <div
                className="w-full rounded-lg border border-dashed border-border bg-muted/30 p-4"
                role="status"
                data-testid="import-review-evidence-empty"
              >
                <p className="text-sm font-medium text-foreground">
                  No clause-level evidence preview yet
                </p>
                <p className="mt-1 text-sm text-muted-foreground">
                  {job.positive_summary_json?.length ||
                  job.nonconformity_summary_json?.length ||
                  job.improvement_summary_json?.length
                    ? 'Summary counts are available below. Clause badges appear when the extractor maps ISO clauses from the source document.'
                    : 'Mappings appear after OCR/analysis extracts clause references. Continue reviewing draft findings — evidence badges will populate when available.'}
                </p>
              </div>
            )}
          </div>
          <div className="grid gap-3 md:grid-cols-3">
            <div className="rounded-lg border border-border p-4">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">
                Positive evidence
              </p>
              <p className="mt-1 font-medium text-foreground">
                {job.positive_summary_json?.length || 0}
              </p>
            </div>
            <div className="rounded-lg border border-border p-4">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">Non-compliances</p>
              <p className="mt-1 font-medium text-foreground">
                {job.nonconformity_summary_json?.length || 0}
              </p>
            </div>
            <div className="rounded-lg border border-border p-4">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">Improvements</p>
              <p className="mt-1 font-medium text-foreground">
                {job.improvement_summary_json?.length || 0}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      <PromotionImpactPanel
        approvedCount={approvedCount}
        acceptedClauseCount={acceptedClauseCount}
        acceptedActionCandidates={acceptedActionCandidates}
        acceptedRiskCandidates={acceptedRiskCandidates}
        schemeAlignment={schemeAlignment}
      />
    </div>
  )
}
