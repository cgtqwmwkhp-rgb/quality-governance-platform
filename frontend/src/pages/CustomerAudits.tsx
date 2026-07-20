import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import {
  Users,
  RefreshCw,
  XCircle,
  Plus,
  FileText,
  AlertCircle,
  CheckCircle2,
  Clock,
  ClipboardList,
  ExternalLink,
  Eye,
  AlertTriangle,
  Loader2,
  Play,
} from 'lucide-react'
import {
  auditsApi,
  externalAuditRecordsApi,
  ErrorClass,
  createApiError,
  type AuditFinding,
  type AuditRun,
  type ExternalAuditRecordSummary,
} from '../api/client'
import api from '../api/client'
import { getImportReviewPath } from '../components/audit-import/importReviewHelpers'
import {
  CUSTOMER_AUDITS_AUDITS_PATH,
  getCustomerCapaActionsPath,
  getCustomerRiskRegisterPath,
} from '../components/assuranceHubHelpers'
import { EmptyState } from '../components/ui/EmptyState'
import { Card, CardContent } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import { LoadingSkeleton } from '../components/ui/LoadingSkeleton'
import { cn } from '../helpers/utils'
import {
  CUSTOMER_AUDITS_SECTIONS,
  buildCustomerAuditsSummary,
  filterCustomerAssuranceRuns,
  getCustomerAuditWorkspacePath,
  isExternalAuditImportRun,
  parseCustomerAuditsSection,
  type CustomerAuditsSectionId,
} from './customerAuditsHelpers'

type LoadState = 'idle' | 'loading' | 'success' | 'error'

function DownstreamHandoffLinks({
  auditRef,
  findingId,
  importReviewPath,
  className = '',
}: {
  auditRef?: string | null
  findingId?: number | null
  importReviewPath?: string | null
  className?: string
}) {
  return (
    <div
      className={`flex flex-wrap gap-2 ${className}`.trim()}
      data-testid="customer-audits-downstream-handoffs"
    >
      <Link
        to={getCustomerCapaActionsPath(findingId)}
        data-testid="customer-audits-open-capa"
        className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-background px-3 py-2 text-xs font-medium text-foreground transition-colors hover:border-primary/40 hover:text-primary"
      >
        Open CAPA Actions
      </Link>
      <Link
        to={getCustomerRiskRegisterPath(auditRef)}
        data-testid="customer-audits-open-risk"
        className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-background px-3 py-2 text-xs font-medium text-foreground transition-colors hover:border-primary/40 hover:text-primary"
      >
        Open Risk Register
      </Link>
      <Link
        to={`${CUSTOMER_AUDITS_AUDITS_PATH}&view=findings`}
        data-testid="customer-audits-open-findings-board"
        className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-background px-3 py-2 text-xs font-medium text-foreground transition-colors hover:border-primary/40 hover:text-primary"
      >
        Findings on Audits board
      </Link>
      <Link
        to={CUSTOMER_AUDITS_AUDITS_PATH}
        data-testid="customer-audits-open-audits-board"
        className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-background px-3 py-2 text-xs font-medium text-foreground transition-colors hover:border-primary/40 hover:text-primary"
      >
        Customer filter on Audits
      </Link>
      {importReviewPath ? (
        <Link
          to={importReviewPath}
          data-testid="customer-audits-open-import-review"
          className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-background px-3 py-2 text-xs font-medium text-foreground transition-colors hover:border-primary/40 hover:text-primary"
        >
          Open import review
        </Link>
      ) : null}
    </div>
  )
}

function getStatusBadgeVariant(status: string) {
  switch (status) {
    case 'completed':
      return 'resolved'
    case 'in_progress':
      return 'in-progress'
    case 'pending_review':
      return 'acknowledged'
    case 'scheduled':
      return 'submitted'
    default:
      return 'secondary'
  }
}

export default function CustomerAudits() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const section = parseCustomerAuditsSection(searchParams.get('section'))

  const [runs, setRuns] = useState<AuditRun[]>([])
  const [findings, setFindings] = useState<AuditFinding[]>([])
  const [records, setRecords] = useState<ExternalAuditRecordSummary[]>([])
  const [recordsAvailable, setRecordsAvailable] = useState<boolean | null>(null)
  const [loadState, setLoadState] = useState<LoadState>('idle')
  const [errorClass, setErrorClass] = useState<ErrorClass | null>(null)
  const [documentError, setDocumentError] = useState<string | null>(null)
  const [openingAssetId, setOpeningAssetId] = useState<number | null>(null)

  const setSection = useCallback(
    (next: CustomerAuditsSectionId) => {
      const nextParams = new URLSearchParams(searchParams)
      if (next === 'runs') {
        nextParams.delete('section')
      } else {
        nextParams.set('section', next)
      }
      setSearchParams(nextParams, { replace: true })
    },
    [searchParams, setSearchParams],
  )

  const loadData = useCallback(async (isRetry = false) => {
    setLoadState('loading')
    setErrorClass(null)

    try {
      const [auditsRes, findingsRes, recordsRes] = await Promise.allSettled([
        auditsApi.listRuns(1, 100),
        auditsApi.listFindings(1, 100),
        externalAuditRecordsApi.list({ scheme: 'customer_other', limit: 50 }),
      ])

      const allRuns =
        auditsRes.status === 'fulfilled' ? auditsRes.value.data.items || [] : []
      const scopedRuns = filterCustomerAssuranceRuns(allRuns)
      setRuns(scopedRuns)

      const allFindings =
        findingsRes.status === 'fulfilled' ? findingsRes.value.data.items || [] : []
      const scopedRunIds = new Set(scopedRuns.map((run) => run.id))
      setFindings(allFindings.filter((finding) => scopedRunIds.has(finding.run_id)))

      if (recordsRes.status === 'fulfilled') {
        setRecords(recordsRes.value.data.records || [])
        setRecordsAvailable(true)
      } else {
        setRecords([])
        setRecordsAvailable(false)
      }

      if (auditsRes.status === 'rejected' && findingsRes.status === 'rejected') {
        throw auditsRes.reason
      }

      setLoadState('success')
    } catch (err) {
      const apiError = createApiError(err)
      setErrorClass(apiError.error_class)

      if (
        !isRetry &&
        (apiError.error_class === ErrorClass.NETWORK_ERROR ||
          apiError.error_class === ErrorClass.SERVER_ERROR)
      ) {
        await loadData(true)
        return
      }

      setLoadState('error')
    }
  }, [])

  useEffect(() => {
    void loadData()
  }, [loadData])

  const summary = useMemo(
    () => buildCustomerAuditsSummary(runs, findings.filter((f) => f.status === 'open').length),
    [runs, findings],
  )

  const openFindings = useMemo(
    () => findings.filter((finding) => finding.status === 'open'),
    [findings],
  )

  const runsWithSourceDocs = useMemo(
    () =>
      runs.filter(
        (run) => run.source_document_asset_id != null && Number(run.source_document_asset_id) > 0,
      ),
    [runs],
  )

  const primaryRun = runs[0] ?? null
  const primaryImportReviewPath = primaryRun
    ? getImportReviewPath(primaryRun.id, null)
    : null

  const handleViewSourceDocument = async (assetId: number) => {
    setDocumentError(null)
    setOpeningAssetId(assetId)
    try {
      const response = await api.get(`/api/v1/evidence-assets/${assetId}/signed-url`)
      const rawUrl = response.data.signed_url as string
      const fullUrl = new URL(rawUrl, api.defaults.baseURL || window.location.origin).toString()
      window.open(fullUrl, '_blank', 'noopener,noreferrer')
    } catch {
      setDocumentError('The source document could not be opened. Please try again.')
    } finally {
      setOpeningAssetId(null)
    }
  }

  if (loadState === 'loading') {
    return (
      <div className="p-6">
        <LoadingSkeleton variant="table" rows={5} columns={4} />
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-fade-in p-6" data-testid="customer-audits-programme">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h1 className="text-3xl font-bold text-foreground flex items-center gap-3">
            <Users className="h-8 w-8 text-primary" />
            {t('customer_audits.shell.title', 'Customer Audits')}
          </h1>
          <p className="mt-1 text-muted-foreground">
            {t(
              'customer_audits.shell.subtitle',
              'Customer-raised and imported external audit runs — programme overview with honest hand-offs to the shared Audits workspace, findings, and CAPA.',
            )}
          </p>
        </div>
        <div className="flex flex-col gap-3 lg:items-end">
          <DownstreamHandoffLinks
            auditRef={primaryRun?.reference_number}
            importReviewPath={primaryImportReviewPath}
          />
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => navigate(`${CUSTOMER_AUDITS_AUDITS_PATH}`)}>
              <ClipboardList className="h-4 w-4" />
              Open Audits board
            </Button>
            <Button onClick={() => navigate('/audits')}>
              <Plus className="h-4 w-4" />
              Import external audit
            </Button>
          </div>
        </div>
      </div>

      {documentError ? (
        <div
          className="rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive"
          role="alert"
        >
          {documentError}
        </div>
      ) : null}

      {loadState === 'error' ? (
        <Card>
          <CardContent className="py-12 text-center">
            <XCircle className="mx-auto h-12 w-12 text-destructive mb-4" />
            <h2 className="text-lg font-semibold text-foreground">
              {t('customer_audits.shell.load_error_title', 'Customer audits unavailable')}
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">
              {errorClass === ErrorClass.NETWORK_ERROR
                ? t('customer_audits.shell.load_error_network', 'Network error — check connectivity.')
                : t(
                    'customer_audits.shell.load_error_generic',
                    'Audit data could not be loaded. This is not an empty programme.',
                  )}
            </p>
            <Button className="mt-4" onClick={() => void loadData()}>
              <RefreshCw className="h-4 w-4" />
              {t('retry', 'Retry')}
            </Button>
          </CardContent>
        </Card>
      ) : (
        <>
          <div className="rounded-xl border border-primary/20 bg-gradient-to-r from-primary/10 to-primary/5 p-6">
            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
              <div>
                <p className="text-sm font-semibold uppercase tracking-wide text-primary">
                  {t('customer_audits.shell.programme_band', 'Customer assurance programme')}
                </p>
                <p className="mt-1 text-sm text-muted-foreground">
                  {t(
                    'customer_audits.shell.programme_honesty',
                    'Thin programme shell — full board, import review, and NC→CAPA loops live on the shared Audits workspace.',
                  )}
                </p>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                {[
                  { label: 'Runs', value: summary.total, icon: ClipboardList },
                  { label: 'In progress', value: summary.inProgress, icon: Clock },
                  { label: 'Open findings', value: summary.openFindings, icon: AlertCircle },
                  { label: 'Source docs', value: summary.withSourceDoc, icon: FileText },
                ].map((kpi) => (
                  <div key={kpi.label} className="rounded-lg border border-border/60 bg-card/80 p-3">
                    <kpi.icon className="h-4 w-4 text-primary mb-1" />
                    <p className="text-2xl font-bold tabular-nums">{kpi.value}</p>
                    <p className="text-xs text-muted-foreground">{kpi.label}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {recordsAvailable === false ? (
            <div
              className="rounded-xl border border-border bg-muted/30 px-4 py-3 text-sm text-muted-foreground"
              data-testid="customer-audits-records-unavailable"
            >
              Cross-scheme external audit records are unavailable on this backend — run list uses
              the Audits API only.
            </div>
          ) : records.length > 0 ? (
            <div
              className="rounded-xl border border-border bg-card px-4 py-3 text-sm text-muted-foreground"
              data-testid="customer-audits-records-banner"
            >
              {records.length} promoted external record
              {records.length === 1 ? '' : 's'} synced for customer_other scheme.
            </div>
          ) : null}

          <div
            className="flex bg-surface rounded-xl p-1 border border-border overflow-x-auto"
            role="tablist"
            aria-label={t('customer_audits.shell.tabs_aria', 'Customer audits sections')}
          >
            {CUSTOMER_AUDITS_SECTIONS.map(({ id, labelKey, icon: Icon }) => (
              <button
                key={id}
                type="button"
                role="tab"
                aria-selected={section === id}
                data-testid={`customer-audits-tab-${id}`}
                onClick={() => setSection(id)}
                className={cn(
                  'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 whitespace-nowrap',
                  section === id
                    ? 'bg-primary text-primary-foreground shadow-sm'
                    : 'text-muted-foreground hover:text-foreground',
                )}
              >
                <Icon className="w-4 h-4" />
                {t(labelKey)}
              </button>
            ))}
          </div>

          {section === 'runs' && (
            <div className="space-y-4" data-testid="customer-audits-section-runs">
              {runs.length === 0 ? (
                <EmptyState
                  icon={<Users className="h-8 w-8 text-muted-foreground" />}
                  title={t('customer_audits.shell.empty_runs_title', 'No customer audit runs yet')}
                  description={t(
                    'customer_audits.shell.empty_runs_description',
                    'Import a customer audit report or schedule a customer-raised audit from the Audits workspace. This programme lists runs tagged customer / external — not an Achilles or UVDB replacement.',
                  )}
                  action={
                    <div className="flex flex-wrap justify-center gap-2">
                      <Button variant="outline" onClick={() => navigate(CUSTOMER_AUDITS_AUDITS_PATH)}>
                        Open Audits board
                      </Button>
                      <Button onClick={() => navigate('/audits')}>
                        <Plus className="h-4 w-4" />
                        Schedule or import
                      </Button>
                    </div>
                  }
                />
              ) : (
                <Card>
                  <CardContent className="p-0">
                    <div className="overflow-x-auto">
                      <table className="w-full">
                        <thead>
                          <tr className="border-b border-border">
                            <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-muted-foreground">
                              Reference
                            </th>
                            <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-muted-foreground">
                              Title / customer
                            </th>
                            <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-muted-foreground">
                              Scheme
                            </th>
                            <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-muted-foreground">
                              Status
                            </th>
                            <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-muted-foreground">
                              Date
                            </th>
                            <th className="px-4 py-3 text-right text-xs font-semibold uppercase text-muted-foreground">
                              Actions
                            </th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-border">
                          {runs.map((run) => {
                            const importReviewPath = getImportReviewPath(run.id, null)
                            return (
                              <tr key={run.id} className="hover:bg-surface/50">
                                <td className="px-4 py-3 font-mono text-sm text-primary">
                                  {run.reference_number}
                                </td>
                                <td className="px-4 py-3">
                                  <p className="text-sm font-medium text-foreground">
                                    {run.title || 'Untitled audit'}
                                  </p>
                                  {run.external_body_name ? (
                                    <p className="text-xs text-muted-foreground">
                                      {run.external_body_name}
                                    </p>
                                  ) : null}
                                </td>
                                <td className="px-4 py-3">
                                  <div className="flex flex-wrap gap-1">
                                    {run.source_origin ? (
                                      <Badge variant="outline" className="text-[10px] uppercase">
                                        {run.source_origin.replace(/_/g, ' ')}
                                      </Badge>
                                    ) : null}
                                    {run.assurance_scheme ? (
                                      <Badge variant="secondary" className="text-[10px]">
                                        {run.assurance_scheme}
                                      </Badge>
                                    ) : null}
                                  </div>
                                </td>
                                <td className="px-4 py-3">
                                  <Badge variant={getStatusBadgeVariant(run.status)}>
                                    {run.status.replace(/_/g, ' ')}
                                  </Badge>
                                </td>
                                <td className="px-4 py-3 text-sm text-muted-foreground">
                                  {run.scheduled_date
                                    ? new Date(run.scheduled_date).toLocaleDateString()
                                    : '—'}
                                </td>
                                <td className="px-4 py-3">
                                  <div className="flex flex-wrap justify-end gap-2">
                                    <Button
                                      size="sm"
                                      variant="outline"
                                      onClick={() =>
                                        navigate(getCustomerAuditWorkspacePath(run))
                                      }
                                    >
                                      <Play className="h-3 w-3" />
                                      {isExternalAuditImportRun(run) ? 'Review' : 'Open'}
                                    </Button>
                                    {importReviewPath && isExternalAuditImportRun(run) ? (
                                      <Button
                                        size="sm"
                                        variant="ghost"
                                        onClick={() => navigate(importReviewPath)}
                                      >
                                        Import
                                      </Button>
                                    ) : null}
                                  </div>
                                </td>
                              </tr>
                            )
                          })}
                        </tbody>
                      </table>
                    </div>
                  </CardContent>
                </Card>
              )}
            </div>
          )}

          {section === 'findings' && (
            <div className="space-y-4" data-testid="customer-audits-section-findings">
              <DownstreamHandoffLinks
                auditRef={openFindings[0]?.reference_number || primaryRun?.reference_number}
                findingId={openFindings[0]?.id}
              />
              {openFindings.length === 0 ? (
                <EmptyState
                  icon={<CheckCircle2 className="h-8 w-8 text-success" />}
                  title={t(
                    'customer_audits.shell.empty_findings_title',
                    'No open findings in customer audits',
                  )}
                  description={t(
                    'customer_audits.shell.empty_findings_description',
                    'When customer audit runs produce nonconformities, they appear here and on the Audits findings tab with NC→CAPA hand-off.',
                  )}
                  action={
                    <Button
                      variant="outline"
                      onClick={() => navigate(`${CUSTOMER_AUDITS_AUDITS_PATH}&view=findings`)}
                    >
                      Open findings on Audits board
                    </Button>
                  }
                />
              ) : (
                <div className="space-y-3">
                  {openFindings.slice(0, 20).map((finding) => (
                    <Card key={finding.id} className="p-4">
                      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                        <div>
                          <div className="flex flex-wrap items-center gap-2 mb-1">
                            <span className="font-mono text-xs text-primary">
                              {finding.reference_number}
                            </span>
                            <Badge variant="destructive">{finding.severity}</Badge>
                            <Badge variant="outline">{finding.finding_type.replace(/_/g, ' ')}</Badge>
                          </div>
                          <h3 className="font-semibold text-foreground">{finding.title}</h3>
                          <p className="text-sm text-muted-foreground line-clamp-2">
                            {finding.description}
                          </p>
                        </div>
                        <div className="flex flex-wrap gap-2">
                          <Button
                            size="sm"
                            variant="secondary"
                            onClick={() =>
                              navigate(
                                `/actions?sourceType=audit_finding&sourceId=${finding.id}`,
                              )
                            }
                          >
                            Open CAPA
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() =>
                              navigate(
                                `${CUSTOMER_AUDITS_AUDITS_PATH}&view=findings&findingId=${finding.id}`,
                              )
                            }
                          >
                            On Audits board
                          </Button>
                        </div>
                      </div>
                    </Card>
                  ))}
                  {openFindings.length > 20 ? (
                    <p className="text-sm text-muted-foreground">
                      Showing 20 of {openFindings.length} open findings — use the Audits findings
                      tab for the full list.
                    </p>
                  ) : null}
                </div>
              )}
            </div>
          )}

          {section === 'sources' && (
            <div className="space-y-4" data-testid="customer-audits-section-sources">
              <p className="text-sm text-muted-foreground">
                {t(
                  'customer_audits.shell.sources_honesty',
                  'Source reports linked at intake appear here via the shared evidence layer. Branded customer pack export is not offered in this slice.',
                )}
              </p>
              {runsWithSourceDocs.length === 0 ? (
                <EmptyState
                  icon={<FileText className="h-8 w-8 text-muted-foreground" />}
                  title={t(
                    'customer_audits.shell.empty_sources_title',
                    'No source documents linked yet',
                  )}
                  description={t(
                    'customer_audits.shell.empty_sources_description',
                    'Upload the customer audit report when creating an external audit intake — it links to Evidence Assets automatically.',
                  )}
                  action={
                    <Button variant="outline" onClick={() => navigate('/audits')}>
                      Import external audit
                    </Button>
                  }
                />
              ) : (
                <div className="space-y-3">
                  {runsWithSourceDocs.map((run) => (
                    <Card key={run.id} className="p-4">
                      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                        <div>
                          <p className="font-mono text-xs text-primary">{run.reference_number}</p>
                          <p className="font-medium text-foreground">
                            {run.source_document_label || 'Source audit report'}
                          </p>
                          <p className="text-sm text-muted-foreground">
                            {run.external_body_name || run.title || 'Customer audit run'}
                          </p>
                        </div>
                        <div className="flex flex-wrap gap-2">
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={openingAssetId === run.source_document_asset_id}
                            onClick={() =>
                              void handleViewSourceDocument(run.source_document_asset_id!)
                            }
                          >
                            {openingAssetId === run.source_document_asset_id ? (
                              <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                              <Eye className="h-4 w-4" />
                            )}
                            View source
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => navigate(getCustomerAuditWorkspacePath(run))}
                          >
                            <ExternalLink className="h-4 w-4" />
                            Open run
                          </Button>
                        </div>
                      </div>
                    </Card>
                  ))}
                </div>
              )}
            </div>
          )}
        </>
      )}

      {summary.pendingReview > 0 ? (
        <div
          className="rounded-xl border border-warning/30 bg-warning/10 px-4 py-3 flex items-start gap-3"
          role="status"
        >
          <AlertTriangle className="h-5 w-5 text-warning shrink-0 mt-0.5" />
          <p className="text-sm text-foreground">
            {summary.pendingReview} customer audit run
            {summary.pendingReview === 1 ? '' : 's'} need import review before findings can close
            the loop.
          </p>
        </div>
      ) : null}
    </div>
  )
}
