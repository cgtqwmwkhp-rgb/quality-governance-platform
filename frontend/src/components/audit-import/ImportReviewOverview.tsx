import { CheckCircle2 } from 'lucide-react'
import type { ExternalAuditImportDraft, ExternalAuditImportJob } from '../../api/client'
import { Badge } from '../ui/Badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/Card'
import { formatDate, humanizeLabel } from './importReviewHelpers'

interface ImportReviewOverviewProps {
  job: ExternalAuditImportJob
  drafts: ExternalAuditImportDraft[]
  declaredProgramLabel: string
  declaredSourceOrigin?: string | null
  declaredScheme?: string | null
  resolvedTemplateName?: string | null
  resolvedTemplateId?: number | null
  resolvedTemplateVersion?: number | null
  declaredExternalBody?: string | null
  declaredExternalReference?: string | null
  approvedCount: number
  promoteableCount: number
  isProcessing: boolean
  lastUpdatedAt: Date | null
  isDocumentHidden: boolean
}

export function ImportReviewOverview({
  job,
  drafts,
  declaredProgramLabel,
  declaredSourceOrigin,
  declaredScheme,
  resolvedTemplateName,
  resolvedTemplateId,
  resolvedTemplateVersion,
  declaredExternalBody,
  declaredExternalReference,
  approvedCount,
  promoteableCount,
  isProcessing,
  lastUpdatedAt,
  isDocumentHidden,
}: ImportReviewOverviewProps) {
  const reviewedCount = approvedCount + drafts.filter((draft) => draft.status === 'rejected').length
  const rejectedCount = drafts.filter((draft) => draft.status === 'rejected').length
  const promotionProgress =
    job.status === 'promoting' && job.promote_total != null
      ? `${job.promote_succeeded ?? 0} of ${job.promote_total} materialized${
          job.promote_failed ? `; ${job.promote_failed} need review` : ''
        }`
      : null

  return (
    <div className="grid gap-4 xl:grid-cols-[1.4fr_1fr]">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <CheckCircle2 className="h-5 w-5 text-primary" />
            {job.reference_number}
          </CardTitle>
          <CardDescription>
            Status: {job.status.replace(/_/g, ' ')}.{' '}
            {job.analysis_summary || 'Analysis summary pending.'}
            {['processing', 'promoting'].includes(job.status) || isProcessing ? (
              <span className="mt-1 block text-xs">
                {job.status === 'promoting'
                  ? `Promotion in progress${promotionProgress ? ` — ${promotionProgress}` : ''}. This workspace refreshes automatically; an expired worker lease returns accepted drafts here for retry.`
                  : isProcessing || job.status === 'processing'
                    ? 'Processing in progress — this workspace refreshes automatically.'
                    : null}
                {lastUpdatedAt
                  ? ` Last updated ${new Intl.DateTimeFormat('en-GB', {
                      hour: '2-digit',
                      minute: '2-digit',
                      second: '2-digit',
                    }).format(lastUpdatedAt)}.`
                  : ''}
                {isDocumentHidden ? ' Updates paused while this tab is hidden.' : ''}
              </span>
            ) : lastUpdatedAt ? (
              <span className="mt-1 block text-xs">
                Last updated{' '}
                {new Intl.DateTimeFormat('en-GB', {
                  hour: '2-digit',
                  minute: '2-digit',
                  second: '2-digit',
                }).format(lastUpdatedAt)}
                .
              </span>
            ) : null}
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <div className="rounded-lg border border-border p-4">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Declared intake</p>
            <p className="mt-1 font-medium text-foreground">{declaredProgramLabel}</p>
            <p className="mt-1 text-xs text-muted-foreground">
              {declaredSourceOrigin
                ? `Source: ${humanizeLabel(declaredSourceOrigin)}`
                : 'Source pending'}
              {declaredScheme ? ` · Scheme: ${declaredScheme}` : ''}
            </p>
          </div>
          <div className="rounded-lg border border-border p-4">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">
              Processing template
            </p>
            <p className="mt-1 font-medium text-foreground">
              {(() => {
                const raw = resolvedTemplateName || ''
                if (raw.startsWith('ZZZ') || raw.includes('(System)')) {
                  const schemeLabel = job.detected_scheme || ''
                  return schemeLabel ? `${schemeLabel} Intake` : 'External Audit Intake'
                }
                return (
                  raw ||
                  (resolvedTemplateId ? `Template ${resolvedTemplateId}` : 'Pending resolution')
                )
              })()}
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              {resolvedTemplateVersion != null
                ? `Version ${resolvedTemplateVersion}`
                : 'Version pending'}
            </p>
          </div>
          <div className="rounded-lg border border-border p-4">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Source file</p>
            <p className="mt-1 font-medium text-foreground">
              {job.source_filename || 'Source document'}
            </p>
            {(declaredExternalBody || declaredExternalReference) && (
              <p className="mt-1 text-xs text-muted-foreground">
                {[declaredExternalBody, declaredExternalReference].filter(Boolean).join(' · ')}
              </p>
            )}
          </div>
          <div className="rounded-lg border border-border p-4">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Extraction</p>
            <p className="mt-1 font-medium text-foreground">{job.extraction_method || 'pending'}</p>
            <p className="mt-1 text-xs text-muted-foreground">
              {job.page_count ? `${job.page_count} page(s)` : 'Pages pending'}
              {job.source_sheet_count ? `, ${job.source_sheet_count} sheet(s)` : ''}
            </p>
          </div>
          <div className="rounded-lg border border-border p-4">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Classification</p>
            <p className="mt-1 font-medium text-foreground">
              {humanizeLabel(job.detected_scheme) || 'Pending classification'}
            </p>
            {job.detected_scheme_confidence != null ? (
              <p className="mt-1 text-xs text-muted-foreground">
                {Math.round(job.detected_scheme_confidence * 100)}% confidence
              </p>
            ) : null}
          </div>
          <div className="rounded-lg border border-border p-4">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">OCR provider</p>
            <p className="mt-1 font-medium text-foreground">
              {job.provider_name || 'Pending provider'}
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              {job.provider_model || 'Model pending'}
            </p>
          </div>
          <div className="rounded-lg border border-border p-4">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Review progress</p>
            <p className="mt-1 font-medium text-foreground">
              {reviewedCount} / {drafts.length} reviewed
            </p>
            {drafts.length > 0 ? (
              <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-slate-100">
                <div
                  className="h-full rounded-full bg-emerald-500 transition-all"
                  style={{
                    width: `${Math.round((reviewedCount / drafts.length) * 100)}%`,
                  }}
                />
              </div>
            ) : null}
            <p className="mt-1 text-xs text-muted-foreground">
              {approvedCount} accepted, {rejectedCount} rejected, {promoteableCount} awaiting promotion
            </p>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Scorecard</CardTitle>
          <CardDescription>
            Normalized audit interpretation before any live promotion happens.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="rounded-lg border border-border p-4">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Outcome</p>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <Badge variant="outline">
                {job.outcome_status?.replace(/_/g, ' ') || 'review required'}
              </Badge>
              {job.scheme_version ? <Badge variant="secondary">{job.scheme_version}</Badge> : null}
              {job.has_tabular_data ? (
                <Badge variant="info">Tabular evidence detected</Badge>
              ) : null}
            </div>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            <div className="rounded-lg border border-border p-4">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">Overall score</p>
              {job.score_percentage != null ? (
                <>
                  <p className="mt-1 text-2xl font-bold text-foreground">
                    {job.score_percentage.toFixed(1)}%
                  </p>
                  <div className="mt-2 h-3 w-full overflow-hidden rounded-full bg-slate-100">
                    <div
                      className={`h-full rounded-full transition-all ${
                        job.score_percentage >= 80
                          ? 'bg-emerald-500'
                          : job.score_percentage >= 50
                            ? 'bg-amber-500'
                            : 'bg-red-500'
                      }`}
                      style={{ width: `${Math.min(job.score_percentage, 100)}%` }}
                    />
                  </div>
                </>
              ) : (
                <p className="mt-1 font-medium text-foreground">No explicit score extracted</p>
              )}
              {job.overall_score != null && job.max_score != null ? (
                <p className="mt-1 text-xs text-muted-foreground">
                  {job.overall_score} / {job.max_score}
                </p>
              ) : null}
              <p className="mt-1 text-xs text-muted-foreground italic">
                Weighted composite from audit body — see pillar breakdown below
              </p>
            </div>
            <div className="rounded-lg border border-border p-4">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">Issuer</p>
              <p className="mt-1 font-medium text-foreground">
                {job.issuer_name || 'Reviewer confirmation required'}
              </p>
              {job.report_date ? (
                <p className="mt-1 text-xs text-muted-foreground">
                  Report date: {formatDate(job.report_date as unknown as string)}
                </p>
              ) : null}
            </div>
          </div>
          {job.score_breakdown_json?.length ? (
            <div className="rounded-lg border border-border p-4">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">
                Score breakdown
              </p>
              <div className="mt-3 grid gap-2">
                {job.score_breakdown_json.map((item, index) => {
                  const pct = Number(item.percentage ?? 0)
                  return (
                    <div key={`score-breakdown-${index}`} className="space-y-1">
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-foreground">
                          {String(item.label || `Section ${index + 1}`)}
                        </span>
                        <span className="text-muted-foreground">
                          {String(item.score ?? '-')} / {String(item.max_score ?? '-')} (
                          {String(item.percentage ?? '-')}%)
                        </span>
                      </div>
                      <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
                        <div
                          className={`h-full rounded-full ${
                            pct >= 80 ? 'bg-emerald-500' : pct >= 50 ? 'bg-amber-500' : 'bg-red-500'
                          }`}
                          style={{ width: `${Math.min(pct, 100)}%` }}
                        />
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          ) : null}
        </CardContent>
      </Card>
    </div>
  )
}
