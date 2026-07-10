import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ChevronDown,
  ChevronUp,
  ClipboardList,
  ExternalLink,
  Info,
  Loader2,
  Shield,
} from 'lucide-react'
import {
  type ExternalAuditImportDraft,
  type ExternalAuditImportJob,
} from '../../api/client'
import { Button } from '../ui/Button'
import { Card, CardContent, CardHeader, CardTitle } from '../ui/Card'
import { Badge } from '../ui/Badge'

function getSeverityVariant(severity: string) {
  if (severity === 'critical') return 'critical'
  if (severity === 'high') return 'high'
  if (severity === 'low') return 'low'
  return 'medium'
}

/** Deep-link to Compliance & evidence with optional standard filter (matches listClauses API slugs). */
function buildComplianceClauseUrl(mapping: Record<string, unknown>): string {
  const clauseRaw =
    (typeof mapping.clause_number === 'string' && mapping.clause_number) ||
    (typeof mapping.clause === 'string' && mapping.clause) ||
    ''
  const clause = clauseRaw.trim()
  const stdRaw = (typeof mapping.standard === 'string' ? mapping.standard : '').toLowerCase()
  const sp = new URLSearchParams()
  if (clause) sp.set('clause', clause)
  const compact = stdRaw.replace(/\s+/g, '').replace(/\//g, '')
  if (compact.includes('9001')) sp.set('standard', 'iso9001')
  else if (compact.includes('14001')) sp.set('standard', 'iso14001')
  else if (compact.includes('45001')) sp.set('standard', 'iso45001')
  else if (compact.includes('27001')) sp.set('standard', 'iso27001')
  const q = sp.toString()
  return q ? `/compliance?${q}` : '/compliance'
}

function getFindingTypeStyle(findingType: string): {
  label: string
  badgeClasses: string
  cardBorderClass: string
  iconColor: string
} {
  const ft = findingType.toLowerCase().replace(/\s+/g, '_')
  if (ft === 'positive_practice') {
    return {
      label: 'Good Practice',
      badgeClasses:
        'bg-emerald-100 text-emerald-800 border-emerald-300 dark:bg-emerald-900/30 dark:text-emerald-300 dark:border-emerald-700',
      cardBorderClass: 'border-l-4 border-l-emerald-500',
      iconColor: 'text-emerald-600',
    }
  }
  if (
    ft === 'nonconformity' ||
    ft === 'major_nonconformity' ||
    ft === 'minor_nonconformity' ||
    ft === 'competence_gap'
  ) {
    return {
      label: ft === 'major_nonconformity' ? 'Major NC' : ft === 'minor_nonconformity' ? 'Minor NC' : ft === 'competence_gap' ? 'Competence Gap' : 'Non-Conformity',
      badgeClasses:
        'bg-red-100 text-red-800 border-red-300 dark:bg-red-900/30 dark:text-red-300 dark:border-red-700',
      cardBorderClass: 'border-l-4 border-l-red-500',
      iconColor: 'text-red-600',
    }
  }
  if (ft === 'observation' || ft === 'opportunity_for_improvement') {
    return {
      label: ft === 'observation' ? 'Observation' : 'Opportunity for Improvement',
      badgeClasses:
        'bg-amber-100 text-amber-800 border-amber-300 dark:bg-amber-900/30 dark:text-amber-300 dark:border-amber-700',
      cardBorderClass: 'border-l-4 border-l-amber-500',
      iconColor: 'text-amber-600',
    }
  }
  if (ft === 'flagged_item' || ft === 'question_answered_no') {
    return {
      label: ft === 'flagged_item' ? 'Flagged Item' : 'Answered No',
      badgeClasses:
        'bg-orange-100 text-orange-800 border-orange-300 dark:bg-orange-900/30 dark:text-orange-300 dark:border-orange-700',
      cardBorderClass: 'border-l-4 border-l-orange-500',
      iconColor: 'text-orange-600',
    }
  }
  return {
    label: findingType.replace(/_/g, ' '),
    badgeClasses: 'bg-slate-100 text-slate-700 border-slate-300',
    cardBorderClass: '',
    iconColor: 'text-slate-500',
  }
}

function getConfidenceTier(confidence: number | null | undefined): {
  label: string
  color: string
  bgColor: string
  borderColor: string
} {
  if (confidence == null)
    return {
      label: 'Unknown',
      color: 'text-slate-500',
      bgColor: 'bg-slate-50',
      borderColor: 'border-slate-200',
    }
  const pct = Math.round(confidence * 100)
  if (pct >= 85)
    return {
      label: `${pct}%`,
      color: 'text-emerald-700',
      bgColor: 'bg-emerald-50',
      borderColor: 'border-emerald-200',
    }
  if (pct >= 60)
    return {
      label: `${pct}%`,
      color: 'text-amber-700',
      bgColor: 'bg-amber-50',
      borderColor: 'border-amber-200',
    }
  return {
    label: `${pct}%`,
    color: 'text-red-700',
    bgColor: 'bg-red-50',
    borderColor: 'border-red-200',
  }
}

function getAnalysisMethodLabel(provenance: Record<string, unknown> | null | undefined): string {
  if (!provenance) return 'rule-based'
  const method = String(provenance.analysis_method || '')
  if (method.includes('ai_confirmed')) return 'AI confirmed'
  if (method.includes('consensus') || method.includes('ai_structured')) return 'AI analysis'
  if (method.includes('mistral')) return 'Mistral AI'
  if (method.includes('gemini')) return 'Gemini AI'
  if (method.includes('rule_based')) return 'rule-based'
  if (method.includes('normalized')) return 'rule-based'
  return method || 'rule-based'
}

function getMethodBadgeVariant(
  label: string,
): 'default' | 'secondary' | 'info' | 'success' | 'destructive' | 'outline' {
  if (label.includes('AI confirmed')) return 'success'
  if (label.includes('AI')) return 'info'
  return 'secondary'
}

function buildConfidenceTooltip(provenance: Record<string, unknown> | null | undefined): string {
  if (!provenance) return ''
  const parts: string[] = []
  const method = String(provenance.analysis_method || '')
  if (method) parts.push(`Method: ${method.replace(/_/g, ' ')}`)
  const provider = provenance.ai_provider
  if (provider) parts.push(`Provider: ${String(provider)}`)
  const aiConf = provenance.ai_confidence
  if (aiConf != null) parts.push(`AI confidence: ${Math.round(Number(aiConf) * 100)}%`)
  const trigger = provenance.trigger
  if (trigger) parts.push(`Rule trigger: ${String(trigger)}`)
  const clause = provenance.clause_reference
  if (clause) parts.push(`Clause: ${String(clause)}`)
  return parts.join('\n')
}

const SEVERITY_WEIGHT: Record<string, number> = {
  critical: 4,
  high: 3,
  medium: 2,
  low: 1,
}

function reviewUrgency(draft: ExternalAuditImportDraft): number {
  const confidenceInverse = 1 - (draft.confidence_score ?? 0.5)
  const severityScore = SEVERITY_WEIGHT[draft.severity] ?? 2
  return confidenceInverse * 10 + severityScore
}

export function DraftFindingsList({
  drafts,
  job,
  error,
  busyDraftId,
  isBulkReviewing,
  specialistHome,
  onDecision,
  onLoad,
}: {
  drafts: ExternalAuditImportDraft[]
  job: ExternalAuditImportJob | null
  error: string | null
  busyDraftId: number | null
  isBulkReviewing: boolean
  specialistHome: { path: string; label: string }
  onDecision: (
    id: number,
    status: 'accepted' | 'rejected' | 'draft',
    extras?: Record<string, string>,
  ) => void
  onLoad: () => void
}) {
  const [expandedProvenance, setExpandedProvenance] = useState<Set<number>>(new Set())
  const [editingDraft, setEditingDraft] = useState<number | null>(null)
  const [editFields, setEditFields] = useState<Record<string, string>>({})
  const [filterStatus, setFilterStatus] = useState<string>('all')
  const [sortBy, setSortBy] = useState<string>('urgency')

  const filteredAndSorted = useMemo(() => {
    let filtered = drafts
    if (filterStatus !== 'all') {
      filtered = drafts.filter((d) => d.status === filterStatus)
    }
    const sorted = [...filtered]
    if (sortBy === 'severity') {
      const order: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 }
      sorted.sort((a, b) => (order[a.severity] ?? 2) - (order[b.severity] ?? 2))
    } else if (sortBy === 'confidence') {
      sorted.sort((a, b) => (a.confidence_score ?? 0) - (b.confidence_score ?? 0))
    } else {
      sorted.sort((a, b) => reviewUrgency(b) - reviewUrgency(a))
    }
    return sorted
  }, [drafts, filterStatus, sortBy])
  const sortedDrafts = filteredAndSorted

  const toggleProvenance = (id: number) => {
    setExpandedProvenance((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  if (drafts.length === 0) {
    return (
      <div className="grid gap-4">
        <Card>
          <CardContent className="p-8 text-center text-muted-foreground">
            {job?.status === 'processing' || job?.status === 'promoting'
              ? 'Processing is still running. This workspace refreshes automatically while analysis is in progress.'
              : job?.status === 'queued'
                ? 'Waiting for processing to start. Click Retry Queue above if this persists.'
                : error
                  ? 'The latest import state could not be refreshed. Retry to continue reviewing this workspace.'
                  : 'No draft findings were produced for this import. Review the source document and processing warnings before promoting.'}
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-muted-foreground">
          {filteredAndSorted.length} of {drafts.length} finding(s)
        </p>
        <div className="flex flex-wrap items-center gap-2">
          <label htmlFor="draft-filter-status" className="sr-only">Filter by status</label>
          <select
            id="draft-filter-status"
            className="rounded border border-border bg-background px-2 py-1 text-xs"
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            aria-label="Filter draft findings by status"
          >
            <option value="all">All statuses</option>
            <option value="draft">Pending</option>
            <option value="accepted">Accepted</option>
            <option value="rejected">Rejected</option>
            <option value="promoted">Promoted</option>
          </select>
          <label htmlFor="draft-sort-by" className="sr-only">Sort findings</label>
          <select
            id="draft-sort-by"
            className="rounded border border-border bg-background px-2 py-1 text-xs"
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            aria-label="Sort draft findings"
          >
            <option value="urgency">Sort: Urgency</option>
            <option value="severity">Sort: Severity</option>
            <option value="confidence">Sort: Confidence</option>
          </select>
          <Button variant="outline" size="sm" onClick={onLoad}>
            Refresh
          </Button>
        </div>
      </div>
      {sortedDrafts.map((draft) => {
        const tier = getConfidenceTier(draft.confidence_score)
        const methodLabel = getAnalysisMethodLabel(draft.provenance_json ?? null)
        const isExpanded = expandedProvenance.has(draft.id)
        const ftStyle = getFindingTypeStyle(draft.finding_type)

        return (
          <Card key={draft.id} className={ftStyle.cardBorderClass}>
            <CardHeader>
              <div className="flex flex-wrap items-center gap-2">
                <CardTitle className="text-xl">{draft.title}</CardTitle>
                <span
                  className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-semibold ${ftStyle.badgeClasses}`}
                >
                  {ftStyle.label}
                </span>
                <Badge variant={getSeverityVariant(draft.severity)}>{draft.severity}</Badge>
                <Badge variant="outline">{draft.status.replace(/_/g, ' ')}</Badge>
                <span
                  className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-semibold ${tier.color} ${tier.bgColor} ${tier.borderColor} cursor-help`}
                  title={buildConfidenceTooltip(draft.provenance_json ?? null)}
                >
                  {tier.label} confidence
                </span>
                <Badge variant={getMethodBadgeVariant(methodLabel)}>{methodLabel}</Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-foreground whitespace-pre-wrap">{draft.description}</p>

              {(() => {
                const snippets = draft.evidence_snippets_json?.filter(
                  (s) => String(s).trim() && String(s).trim() !== draft.description?.trim()
                ) || []
                if (!snippets.length) return null
                const allPipes = snippets.every((s) => String(s).includes(' | '))
                if (allPipes) {
                  const rows = snippets.map((s) => String(s))
                  const getOutcomeStyle = (val: string) => {
                    const v = val.trim().toLowerCase()
                    if (['yes', 'pass', 'compliant', 'met', 'satisfactory'].includes(v))
                      return 'text-emerald-700 dark:text-emerald-400 font-semibold'
                    if (['no', 'fail', 'non-compliant', 'not met', 'unsatisfactory'].includes(v))
                      return 'text-red-700 dark:text-red-400 font-semibold'
                    if (['n/a', 'not applicable', 'excluded'].includes(v))
                      return 'text-muted-foreground italic'
                    return 'text-foreground'
                  }
                  return (
                    <div className="rounded-lg border border-border bg-slate-50 dark:bg-slate-900/50 p-4 text-sm space-y-3">
                      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                        Source Evidence
                      </p>
                      <div className="overflow-x-auto rounded border border-border">
                        <table className="w-full text-xs">
                          <thead>
                            <tr className="bg-slate-100 dark:bg-slate-800">
                              <th className="px-3 py-2 text-left text-xs font-semibold text-muted-foreground border-b border-border">Inspection Requirement</th>
                              <th className="px-3 py-2 text-left text-xs font-semibold text-muted-foreground border-b border-border">Outcome</th>
                              {rows.some((r) => r.split(' | ').length > 2) && (
                                <th className="px-3 py-2 text-left text-xs font-semibold text-muted-foreground border-b border-border">Score</th>
                              )}
                            </tr>
                          </thead>
                          <tbody>
                            {rows.map((row, ri) => {
                              const cells = row.split(' | ')
                              return (
                                <tr
                                  key={`erow-${draft.id}-${ri}`}
                                  className={ri % 2 === 0 ? 'bg-white dark:bg-slate-800/50' : 'bg-slate-50 dark:bg-slate-900'}
                                >
                                  <td className="px-3 py-1.5 border-b border-border text-foreground">{cells[0]?.trim()}</td>
                                  <td className={`px-3 py-1.5 border-b border-border ${getOutcomeStyle(cells[1] || '')}`}>{cells[1]?.trim()}</td>
                                  {cells.length > 2 && (
                                    <td className="px-3 py-1.5 border-b border-border text-foreground">{cells[2]?.trim()}</td>
                                  )}
                                </tr>
                              )
                            })}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )
                }
                return (
                  <div className="rounded-lg border border-border bg-slate-50 dark:bg-slate-900/50 p-4 text-sm space-y-3">
                    <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                      Source Evidence
                    </p>
                    {snippets.map((snippet, si) => (
                      <p
                        key={`snippet-${draft.id}-${si}`}
                        className="whitespace-pre-wrap text-xs text-foreground leading-relaxed"
                      >
                        {String(snippet)}
                      </p>
                    ))}
                  </div>
                )
              })()}

              <div className="space-y-3">
                {draft.mapped_frameworks_json && draft.mapped_frameworks_json.length > 0 ? (
                  <div>
                    <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground mb-2">
                      Frameworks &amp; schemes
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {draft.mapped_frameworks_json.map((mapping, index) => (
                        <Badge key={`framework-${draft.id}-${index}`} variant="info">
                          {String(mapping.framework || 'Framework')}
                          {mapping.confidence != null
                            ? ` · ${Math.round(Number(mapping.confidence) * 100)}%`
                            : ''}
                        </Badge>
                      ))}
                    </div>
                  </div>
                ) : null}

                {draft.mapped_standards_json && draft.mapped_standards_json.length > 0 ? (
                  <div className="rounded-lg border border-border bg-surface/40 overflow-hidden">
                    <div className="flex items-center justify-between px-3 py-2 border-b border-border bg-surface/60">
                      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                        Cross-standard evidence (ISO &amp; clauses)
                      </p>
                      <Link
                        to="/compliance"
                        className="text-xs text-primary hover:underline flex items-center gap-1"
                      >
                        Open compliance <ExternalLink size={10} />
                      </Link>
                    </div>
                    <div className="overflow-x-auto">
                      <table className="w-full text-xs">
                        <thead>
                          <tr className="text-left text-muted-foreground border-b border-border">
                            <th className="px-3 py-2 font-medium">Standard / reference</th>
                            <th className="px-3 py-2 font-medium">Clause</th>
                            <th className="px-3 py-2 font-medium">Confidence</th>
                            <th className="px-3 py-2 font-medium">Basis</th>
                            <th className="px-3 py-2 font-medium w-28"><span className="sr-only">Action</span></th>
                          </tr>
                        </thead>
                        <tbody>
                          {draft.mapped_standards_json.map((mapping, index) => {
                            const row = mapping as Record<string, unknown>
                            const label =
                              String(row.standard || row.clause_number || row.clause || 'Mapping')
                            const clause =
                              String(row.clause_number || row.clause || '—')
                            const conf =
                              row.confidence != null
                                ? `${Math.round(Number(row.confidence) * 100)}%`
                                : '—'
                            const basis = String(row.basis || '—')
                            const href = buildComplianceClauseUrl(row)
                            return (
                              <tr key={`std-map-${draft.id}-${index}`} className="border-b border-border/80">
                                <td className="px-3 py-2 text-foreground">{label}</td>
                                <td className="px-3 py-2 font-mono text-foreground">{clause}</td>
                                <td className="px-3 py-2 text-muted-foreground">{conf}</td>
                                <td className="px-3 py-2 text-muted-foreground max-w-[200px] truncate" title={basis}>
                                  {basis}
                                </td>
                                <td className="px-3 py-2">
                                  <Link
                                    to={href}
                                    className="text-primary hover:underline inline-flex items-center gap-0.5"
                                  >
                                    View <ExternalLink size={10} />
                                  </Link>
                                </td>
                              </tr>
                            )
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>
                ) : null}
              </div>

              {(draft.suggested_action_title || draft.suggested_risk_title) && (
                <div className="grid gap-3 md:grid-cols-2">
                  {draft.suggested_action_title ? (
                    <div className="rounded-lg border border-blue-200 bg-blue-50/50 dark:border-blue-800 dark:bg-blue-900/20 p-3">
                      <div className="flex items-center justify-between">
                        <p className="text-xs uppercase tracking-wide text-blue-700 dark:text-blue-400 flex items-center gap-1">
                          <ClipboardList size={12} />
                          Corrective Action
                        </p>
                        {draft.status === 'promoted' ? (
                          <Link
                            to="/actions"
                            className="flex items-center gap-1 text-xs text-blue-600 hover:underline"
                          >
                            View in Actions <ExternalLink size={10} />
                          </Link>
                        ) : (
                          <span className="text-xs text-blue-500">Created on promotion</span>
                        )}
                      </div>
                      <p className="mt-1.5 text-sm font-medium text-foreground">
                        {draft.suggested_action_title}
                      </p>
                      {draft.suggested_action_description ? (
                        <p className="mt-1 text-xs text-muted-foreground line-clamp-2">
                          {draft.suggested_action_description}
                        </p>
                      ) : null}
                    </div>
                  ) : null}
                  {draft.suggested_risk_title ? (
                    <div className="rounded-lg border border-rose-200 bg-rose-50/50 dark:border-rose-800 dark:bg-rose-900/20 p-3">
                      <div className="flex items-center justify-between">
                        <p className="text-xs uppercase tracking-wide text-rose-700 dark:text-rose-400 flex items-center gap-1">
                          <Shield size={12} />
                          Risk Escalation
                        </p>
                        {draft.status === 'promoted' ? (
                          <Link
                            to="/risk-register"
                            className="flex items-center gap-1 text-xs text-rose-600 hover:underline"
                          >
                            View in Risk Register <ExternalLink size={10} />
                          </Link>
                        ) : (
                          <span className="text-xs text-rose-500">
                            Queued for risk register triage on promotion
                          </span>
                        )}
                      </div>
                      <p className="mt-1.5 text-sm font-medium text-foreground">
                        {draft.suggested_risk_title}
                      </p>
                    </div>
                  ) : null}
                </div>
              )}

              {draft.provenance_json ? (
                <div className="rounded-lg border border-border">
                  <button
                    type="button"
                    className="flex w-full items-center justify-between p-3 text-left text-xs text-muted-foreground hover:bg-surface"
                    onClick={() => toggleProvenance(draft.id)}
                    aria-expanded={isExpanded}
                    aria-controls={`provenance-detail-${draft.id}`}
                    aria-label={`Toggle provenance detail for: ${draft.title}`}
                  >
                    <span className="flex items-center gap-1">
                      <Info size={12} />
                      Provenance &amp; confidence detail
                    </span>
                    {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                  </button>
                  {isExpanded ? (
                    <div id={`provenance-detail-${draft.id}`}>
                      <ProvenanceDetail provenance={draft.provenance_json} />
                    </div>
                  ) : null}
                </div>
              ) : null}

              {editingDraft === draft.id ? (
                <div className="space-y-3 rounded-lg border border-border p-4 bg-surface/50">
                  <div>
                    <label htmlFor={`edit-title-${draft.id}`} className="text-xs font-medium text-muted-foreground">Title</label>
                    <input
                      id={`edit-title-${draft.id}`}
                      className="mt-1 w-full rounded border border-border bg-background px-3 py-1.5 text-sm"
                      value={editFields.title ?? draft.title}
                      onChange={(e) => setEditFields((f) => ({ ...f, title: e.target.value }))}
                    />
                  </div>
                  <div>
                    <label htmlFor={`edit-desc-${draft.id}`} className="text-xs font-medium text-muted-foreground">Description</label>
                    <textarea
                      id={`edit-desc-${draft.id}`}
                      className="mt-1 w-full rounded border border-border bg-background px-3 py-1.5 text-sm"
                      rows={3}
                      value={editFields.description ?? draft.description}
                      onChange={(e) => setEditFields((f) => ({ ...f, description: e.target.value }))}
                    />
                  </div>
                  <div className="flex gap-3">
                    <div className="flex-1">
                      <label htmlFor={`edit-sev-${draft.id}`} className="text-xs font-medium text-muted-foreground">Severity</label>
                      <select
                        id={`edit-sev-${draft.id}`}
                        className="mt-1 w-full rounded border border-border bg-background px-3 py-1.5 text-sm"
                        value={editFields.severity ?? draft.severity}
                        onChange={(e) => setEditFields((f) => ({ ...f, severity: e.target.value }))}
                      >
                        <option value="low">Low</option>
                        <option value="medium">Medium</option>
                        <option value="high">High</option>
                        <option value="critical">Critical</option>
                      </select>
                    </div>
                  </div>
                  <div>
                    <label htmlFor={`edit-notes-${draft.id}`} className="text-xs font-medium text-muted-foreground">Review notes</label>
                    <textarea
                      id={`edit-notes-${draft.id}`}
                      className="mt-1 w-full rounded border border-border bg-background px-3 py-1.5 text-sm"
                      rows={2}
                      placeholder="Add notes for the audit trail..."
                      value={editFields.review_notes ?? (draft.review_notes || '')}
                      onChange={(e) => setEditFields((f) => ({ ...f, review_notes: e.target.value }))}
                    />
                  </div>
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      variant="success"
                      onClick={() => {
                        void onDecision(draft.id, 'accepted', editFields)
                        setEditingDraft(null)
                        setEditFields({})
                      }}
                      disabled={busyDraftId === draft.id || isBulkReviewing}
                    >
                      Save &amp; Accept
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        void onDecision(draft.id, 'rejected', editFields)
                        setEditingDraft(null)
                        setEditFields({})
                      }}
                      disabled={busyDraftId === draft.id || isBulkReviewing}
                    >
                      Save &amp; Reject
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        setEditingDraft(null)
                        setEditFields({})
                      }}
                    >
                      Cancel
                    </Button>
                  </div>
                </div>
              ) : null}

              <div className="flex flex-wrap gap-3">
                <Button
                  variant="success"
                  onClick={() => void onDecision(draft.id, 'accepted')}
                  disabled={busyDraftId === draft.id || isBulkReviewing || draft.status === 'promoted'}
                  aria-label={`Accept finding: ${draft.title}`}
                >
                  {busyDraftId === draft.id ? (
                    <Loader2 size={16} className="animate-spin" />
                  ) : null}
                  Accept
                </Button>
                <Button
                  variant="outline"
                  onClick={() => void onDecision(draft.id, 'rejected')}
                  disabled={busyDraftId === draft.id || isBulkReviewing || draft.status === 'promoted'}
                  aria-label={`Reject finding: ${draft.title}`}
                >
                  Reject
                </Button>
                {(draft.status === 'accepted' || draft.status === 'rejected') && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => void onDecision(draft.id, 'draft')}
                    disabled={busyDraftId === draft.id || isBulkReviewing}
                    aria-label={`Reset finding to draft: ${draft.title}`}
                  >
                    Reset
                  </Button>
                )}
                {draft.status !== 'promoted' ? (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setEditingDraft(draft.id)
                      setEditFields({})
                    }}
                    disabled={isBulkReviewing}
                  >
                    Edit
                  </Button>
                ) : null}
                {draft.promoted_finding_id ? (
                  <Link
                    to={`${specialistHome.path}?findingId=${draft.promoted_finding_id}`}
                    className="inline-flex items-center text-sm font-medium text-primary hover:underline"
                  >
                    View promoted finding #{draft.promoted_finding_id}
                  </Link>
                ) : null}
              </div>
            </CardContent>
          </Card>
        )
      })}

    </div>
  )
}

function ProvenanceDetail({ provenance }: { provenance: Record<string, unknown> }) {
  const pageNumber = provenance.page_number != null ? String(provenance.page_number) : null
  const analysisMethod = String(provenance.analysis_method || 'unknown')
  const trigger = provenance.trigger ? String(provenance.trigger) : null
  const aiConfidence = provenance.ai_confidence != null ? String(provenance.ai_confidence) : null
  const aiProvider = provenance.ai_provider ? String(provenance.ai_provider) : null
  const clauseRef = provenance.clause_reference ? String(provenance.clause_reference) : null
  const cadDeadline = provenance.corrective_action_deadline
    ? String(provenance.corrective_action_deadline)
    : null
  const consensus = provenance._consensus ? String(provenance._consensus) : null
  const providers = Array.isArray(provenance._providers)
    ? (provenance._providers as string[]).join(', ')
    : null

  return (
    <div className="border-t border-border p-3 text-xs text-muted-foreground space-y-1">
      {pageNumber && <p>Source page: {pageNumber}</p>}
      <p>Analysis method: {analysisMethod}</p>
      {trigger && (
        <p>
          Trigger phrase: &quot;{trigger}&quot;
        </p>
      )}
      {aiConfidence && <p>AI raw confidence: {aiConfidence}</p>}
      {aiProvider && <p>AI provider: {aiProvider}</p>}
      {clauseRef && <p>Clause reference: {clauseRef}</p>}
      {cadDeadline && <p>Corrective action deadline: {cadDeadline}</p>}
      {consensus && (
        <p>
          Consensus:{' '}
          <span
            className={
              consensus === 'agreed'
                ? 'font-semibold text-emerald-600'
                : 'font-semibold text-amber-600'
            }
          >
            {consensus === 'agreed' ? 'Confirmed by multiple providers' : 'Single source'}
          </span>
        </p>
      )}
      {providers && <p>Providers: {providers}</p>}
    </div>
  )
}
