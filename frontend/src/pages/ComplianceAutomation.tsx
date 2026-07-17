/**
 * Compliance Automation Center
 *
 * Features:
 * - Regulatory change monitoring
 * - Gap analysis
 * - Certificate expiry tracking
 * - Scheduled audits
 * - Compliance scoring
 * - RIDDOR automation
 */

import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { buildActionDetailPath } from './actionLinks'
import {
  Bell,
  AlertTriangle,
  CheckCircle,
  Clock,
  Calendar,
  TrendingUp,
  TrendingDown,
  FileText,
  Shield,
  Award,
  Users,
  Truck,
  Building,
  ExternalLink,
  Eye,
  Inbox,
  Play,
  RefreshCw,
  Zap,
  BookOpen,
} from 'lucide-react'
import {
  auditsApi,
  complianceAutomationApi,
  getApiErrorMessage,
  knowledgeBankApi,
  type AuditRun,
  type RegulatoryImpact,
} from '../api/client'
import { cn } from '../helpers/utils'
import { Button } from '../components/ui/Button'
import { EmptyState } from '../components/ui/EmptyState'
import { toast } from '../contexts/ToastContext'
import {
  countOverdueMonitoringRuns,
  countPendingChangesInbox,
  countUnreviewedRegulatoryUpdates,
  hasLiveComplianceScore,
  isOpenWatchImpact,
  mapRiddorSubmissionsToPacks,
  mapRunsToMonitoringRows,
  MONITORING_AUDITS_HANDOFF_PATH,
  MONITORING_SCORE_HANDOFF_EVIDENCE,
  MONITORING_SCORE_HANDOFF_IMS,
  type MonitoringAuditRunRow,
  type MonitoringRiddorPack,
} from './complianceAutomationHelpers'

interface RegulatoryUpdate {
  id: number
  source: string
  source_reference: string
  title: string
  summary: string
  category: string
  impact: string
  affected_standards: string[]
  published_date: string
  effective_date: string
  is_reviewed: boolean
  requires_action: boolean
}

interface Certificate {
  id: number
  name: string
  certificate_type: string
  entity_type: string
  entity_name: string
  issuing_body: string
  expiry_date: string
  status: string
  is_critical: boolean
}

const impactColors: Record<string, string> = {
  critical: 'bg-destructive/20 text-destructive border-destructive/30',
  high: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
  medium: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  low: 'bg-green-500/20 text-green-400 border-green-500/30',
  informational: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
}

const statusColors: Record<string, string> = {
  valid: 'bg-success/10 text-success',
  expiring_soon: 'bg-warning/10 text-warning',
  expired: 'bg-destructive/10 text-destructive',
  scheduled: 'bg-info/10 text-info',
  overdue: 'bg-destructive/10 text-destructive',
}

/** Official HSE RIDDOR online reporting portal + guidance. */
const HSE_RIDDOR_PORTAL_URL = 'https://notifications.hse.gov.uk/RiddorForms/'
const HSE_RIDDOR_GUIDE_URL = 'https://www.hse.gov.uk/riddor/reporting/how-to-make-riddor-report.htm'

export default function ComplianceAutomation() {
  const { t } = useTranslation()
  const [activeTab, setActiveTab] = useState<
    'changes' | 'certificates' | 'audits' | 'riddor'
  >('changes')
  const [updates, setUpdates] = useState<RegulatoryUpdate[]>([])
  const [certificates, setCertificates] = useState<Certificate[]>([])
  const [auditRuns, setAuditRuns] = useState<MonitoringAuditRunRow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [complianceScore, setComplianceScore] = useState({
    overall: 0,
    previous: 0,
    change: 0,
  })
  const [scoreCategories, setScoreCategories] = useState<Record<string, number>>({})
  const [watchImpacts, setWatchImpacts] = useState<RegulatoryImpact[]>([])
  const [runningWatch, setRunningWatch] = useState(false)
  const [actionBusyId, setActionBusyId] = useState<number | null>(null)
  const [riddorPacks, setRiddorPacks] = useState<MonitoringRiddorPack[]>([])
  const [riddorLoading, setRiddorLoading] = useState(false)
  const [riddorError, setRiddorError] = useState<string | null>(null)
  const [watchError, setWatchError] = useState<string | null>(null)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      setLoading(true)
      setError(null)
      const [updatesRes, certificatesRes, auditRunsRes, scoreRes, trendRes, impactsRes] =
        await Promise.all([
        complianceAutomationApi.listRegulatoryUpdates(),
        complianceAutomationApi.listCertificates(),
        auditsApi.listRuns(1, 100),
        complianceAutomationApi.getComplianceScore({ scope_type: 'organization' }),
        complianceAutomationApi.getComplianceTrend({ scope_type: 'organization', months: 12 }),
        knowledgeBankApi.listImpacts(),
      ])

      setUpdates((updatesRes.data.updates as RegulatoryUpdate[]) || [])
      setWatchImpacts(impactsRes.data)

      const now = new Date()
      const certs = ((certificatesRes.data.certificates as Certificate[]) || []).map((certificate) => {
        const expiry = certificate.expiry_date ? new Date(certificate.expiry_date) : null
        let status = certificate.status
        if (expiry) {
          if (expiry < now) status = 'expired'
          else if (expiry.getTime() - now.getTime() <= 30 * 24 * 60 * 60 * 1000) status = 'expiring_soon'
        }
        return { ...certificate, status }
      })
      setCertificates(certs)

      const runs = (auditRunsRes.data.items as AuditRun[]) || []
      setAuditRuns(mapRunsToMonitoringRows(runs, now))

      const trend = ((trendRes.data.trend as Array<{ score: number }>) || []).filter(
        (entry) => typeof entry.score === 'number',
      )
      const scoreData = scoreRes.data as {
        overall_score?: number
        categories?: Record<string, number>
        key_gaps?: string[]
      }
      const previous = trend.length > 1 ? trend[trend.length - 2]!.score : scoreData.overall_score ?? 0
      const overall = scoreData.overall_score ?? 0
      setComplianceScore({
        overall,
        previous,
        change: Number((overall - previous).toFixed(1)),
      })
      setScoreCategories(scoreData.categories ?? {})
    } catch (err) {
      setError(getApiErrorMessage(err))
      setUpdates([])
      setWatchImpacts([])
      setCertificates([])
      setAuditRuns([])
      setComplianceScore({ overall: 0, previous: 0, change: 0 })
      setScoreCategories({})
    } finally {
      setLoading(false)
    }
  }

  const loadChangesInbox = async () => {
    try {
      setWatchError(null)
      const [updatesRes, impactsRes] = await Promise.all([
        complianceAutomationApi.listRegulatoryUpdates(),
        knowledgeBankApi.listImpacts(),
      ])
      setUpdates((updatesRes.data.updates as RegulatoryUpdate[]) || [])
      setWatchImpacts(impactsRes.data)
    } catch (err) {
      const message = getApiErrorMessage(err)
      setWatchError(message)
      toast.error(message)
      setUpdates([])
      setWatchImpacts([])
    }
  }

  const loadWatchImpacts = async () => {
    try {
      setWatchError(null)
      const response = await knowledgeBankApi.listImpacts()
      setWatchImpacts(response.data)
    } catch (err) {
      const message = getApiErrorMessage(err)
      setWatchError(message)
      toast.error(message)
      setWatchImpacts([])
    }
  }

  const loadRiddorSubmissions = async () => {
    setRiddorLoading(true)
    setRiddorError(null)
    try {
      const response = await complianceAutomationApi.listRiddorSubmissions()
      setRiddorPacks(mapRiddorSubmissionsToPacks(response.data.submissions ?? []))
    } catch (err) {
      setRiddorError(getApiErrorMessage(err))
      setRiddorPacks([])
    } finally {
      setRiddorLoading(false)
    }
  }

  const handleRunWatch = async () => {
    setRunningWatch(true)
    setWatchError(null)
    try {
      const response = await knowledgeBankApi.runRegulatoryWatch()
      toast.success(response.data.message ?? 'Regulatory watch completed')
      // Refresh full Changes inbox (feed + impacts) so Run watch stays honest with Refresh.
      await loadChangesInbox()
    } catch (err) {
      const message = getApiErrorMessage(err)
      setWatchError(message)
      toast.error(message)
    } finally {
      setRunningWatch(false)
    }
  }

  const handleCreateWatchAction = async (impactId: number) => {
    setActionBusyId(impactId)
    try {
      const response = await knowledgeBankApi.createImpactAction(impactId)
      const ref = response.data.action?.reference_number
      toast.success(ref ? `Action ${ref} created` : 'Action created from impact')
      await loadWatchImpacts()
    } catch (err) {
      toast.error(getApiErrorMessage(err))
    } finally {
      setActionBusyId(null)
    }
  }

  const handleResolveWatchImpact = async (impactId: number, dismiss = false) => {
    setActionBusyId(impactId)
    try {
      await knowledgeBankApi.resolveImpact(impactId, {
        dismiss,
        notes: dismiss ? 'Dismissed from regulatory watch inbox' : 'Resolved from regulatory watch inbox',
        close_action: !dismiss,
      })
      toast.success(dismiss ? 'Impact dismissed' : 'Impact resolved')
      await loadWatchImpacts()
    } catch (err) {
      toast.error(getApiErrorMessage(err))
    } finally {
      setActionBusyId(null)
    }
  }

  useEffect(() => {
    if (activeTab === 'riddor') {
      void loadRiddorSubmissions()
    }
  }, [activeTab])

  const pendingChangesCount = countPendingChangesInbox(updates, watchImpacts)
  const scoreIsLive = hasLiveComplianceScore(complianceScore.overall, scoreCategories)

  const tabs = [
    {
      id: 'changes',
      label: t('compliance.automation.changes', 'Changes'),
      icon: Inbox,
      count: pendingChangesCount,
    },
    {
      id: 'certificates',
      label: 'Certificates',
      icon: Award,
      count: certificates.filter((c) => c.status === 'expiring_soon').length,
    },
    {
      id: 'audits',
      label: 'Scheduled Audits',
      icon: Calendar,
      count: countOverdueMonitoringRuns(auditRuns),
    },
    { id: 'riddor', label: 'RIDDOR', icon: FileText },
  ]

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="animate-spin rounded-full h-12 w-12 border-4 border-primary border-t-transparent" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {error && (
        <div className="rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground">
            {t('compliance.automation.title', 'Monitoring')}
          </h1>
          <p className="text-muted-foreground mt-1">
            {t(
              'compliance.automation.subtitle',
              'Regulatory watch, certificate expiry, audit handoff, and RIDDOR readiness — live scores live in IMS / Compliance Evidence',
            )}
          </p>
        </div>
        <Button onClick={() => void loadData()} variant="outline">
          <RefreshCw className="w-4 h-4 mr-2" />
          Refresh
        </Button>
      </div>

      {/* Score KPI chip — Score tab removed; hand off to IMS / Compliance Evidence */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        <div
          className="lg:col-span-1 bg-gradient-to-br from-primary to-primary-hover rounded-xl p-6 text-primary-foreground"
          data-testid="monitoring-score-overview"
        >
          <div className="flex items-center justify-between mb-4">
            <Shield className="w-8 h-8 opacity-80" />
            {scoreIsLive ? (
              <span
                className={`flex items-center gap-1 text-sm ${complianceScore.change >= 0 ? 'text-primary-foreground/80' : 'text-destructive'}`}
              >
                {complianceScore.change >= 0 ? (
                  <TrendingUp className="w-4 h-4" />
                ) : (
                  <TrendingDown className="w-4 h-4" />
                )}
                {complianceScore.change >= 0 ? '+' : ''}
                {complianceScore.change}%
              </span>
            ) : (
              <span className="text-sm text-primary-foreground/70" data-testid="monitoring-score-overview-empty">
                {t('compliance.automation.empty.score.overview', 'No live score yet')}
              </span>
            )}
          </div>
          <div className="text-4xl font-bold mb-1">
            {scoreIsLive ? `${complianceScore.overall}%` : '—'}
          </div>
          <div className="text-primary-foreground/80 text-sm mb-3">
            {t('compliance.automation.overall_score', 'Overall Compliance Score')}
          </div>
          <p className="text-xs text-primary-foreground/70 mb-3" data-testid="monitoring-score-tab-retired">
            {t(
              'compliance.automation.score.tab.retired',
              'Score breakdown tab removed — open IMS for multi-scheme scores or Compliance Evidence for coverage.',
            )}
          </p>
          <div className="flex flex-wrap gap-2">
            <Link
              to={MONITORING_SCORE_HANDOFF_IMS}
              className="inline-flex items-center gap-1 rounded-md bg-primary-foreground/15 px-2.5 py-1 text-xs font-medium text-primary-foreground hover:bg-primary-foreground/25"
              data-testid="monitoring-score-handoff-ims"
            >
              {t('compliance.automation.score.handoff.ims', 'Open IMS')}
              <ExternalLink className="w-3 h-3" />
            </Link>
            <Link
              to={MONITORING_SCORE_HANDOFF_EVIDENCE}
              className="inline-flex items-center gap-1 rounded-md bg-primary-foreground/15 px-2.5 py-1 text-xs font-medium text-primary-foreground hover:bg-primary-foreground/25"
              data-testid="monitoring-score-handoff-evidence"
            >
              {t('compliance.automation.score.handoff.evidence', 'Compliance Evidence')}
              <ExternalLink className="w-3 h-3" />
            </Link>
          </div>
        </div>

        <div className="bg-card/50 border border-border rounded-xl p-4">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 rounded-lg bg-destructive/20">
              <AlertTriangle className="w-5 h-5 text-destructive" />
            </div>
            <span className="text-muted-foreground text-sm">
              {t('compliance.automation.changes', 'Changes')}
            </span>
          </div>
          <div className="text-2xl font-bold text-foreground">{pendingChangesCount}</div>
          <div className="text-sm text-muted-foreground">
            {t('compliance.automation.pending_review', 'Pending review')}
          </div>
        </div>

        <div className="bg-card/50 border border-border rounded-xl p-4">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 rounded-lg bg-warning/20">
              <Clock className="w-5 h-5 text-warning" />
            </div>
            <span className="text-muted-foreground text-sm">Expiring Certificates</span>
          </div>
          <div className="text-2xl font-bold text-foreground">
            {certificates.filter((c) => c.status === 'expiring_soon').length}
          </div>
          <div className="text-sm text-muted-foreground">Within 60 days</div>
        </div>

        <div className="bg-card/50 border border-border rounded-xl p-4">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 rounded-lg bg-orange-500/20">
              <Calendar className="w-5 h-5 text-orange-400" />
            </div>
            <span className="text-muted-foreground text-sm">Overdue Audits</span>
          </div>
          <div className="text-2xl font-bold text-foreground">
            {countOverdueMonitoringRuns(auditRuns)}
          </div>
          <div className="text-sm text-muted-foreground">Require attention</div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-card/50 p-1 rounded-xl overflow-x-auto border border-border">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as any)}
            className={cn(
              'flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-all whitespace-nowrap',
              activeTab === tab.id
                ? 'bg-primary text-primary-foreground'
                : 'text-muted-foreground hover:text-foreground hover:bg-muted/50',
            )}
          >
            <tab.icon className="w-4 h-4" />
            {tab.label}
            {tab.count !== undefined && tab.count > 0 && (
              <span
                className={cn(
                  'px-2 py-0.5 rounded-full text-xs',
                  activeTab === tab.id ? 'bg-white/20' : 'bg-red-500/20 text-red-400',
                )}
              >
                {tab.count}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Changes inbox — regulatory feed + watch impacts (CA-W1d) */}
      {activeTab === 'changes' && (
        <div className="space-y-4" data-testid="monitoring-changes-tab">
          <div className="bg-card/50 border border-border rounded-xl p-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div>
              <h3 className="font-medium text-foreground">
                {t('compliance.automation.changes', 'Changes')}
              </h3>
              <p className="text-sm text-muted-foreground mt-1">
                {t(
                  'compliance.automation.changes.description',
                  'Regulatory feed items and watch-matched impacts in one inbox. Feed rows are ingested updates; impacts come from Run watch and can become real Actions with owner and due date.',
                )}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                variant="outline"
                onClick={() => void loadChangesInbox()}
                disabled={runningWatch}
                data-testid="monitoring-changes-refresh"
              >
                <RefreshCw className="w-4 h-4 mr-2" />
                {t('compliance.automation.changes.refresh', 'Refresh inbox')}
              </Button>
              <Button
                onClick={() => void handleRunWatch()}
                disabled={runningWatch}
                data-testid="monitoring-changes-run-watch"
              >
                {runningWatch ? (
                  <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                ) : (
                  <Play className="w-4 h-4 mr-2" />
                )}
                {t('compliance.automation.changes.run_watch', 'Run watch')}
              </Button>
            </div>
          </div>

          {watchError ? (
            <div
              className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive"
              role="alert"
              data-testid="monitoring-changes-error"
            >
              {watchError}
            </div>
          ) : null}

          {updates.length === 0 && watchImpacts.length === 0 ? (
            <div data-testid="monitoring-changes-empty">
              <EmptyState
                icon={<Inbox className="w-8 h-8 text-muted-foreground" />}
                title={t(
                  'compliance.automation.empty.changes.title',
                  'No changes in the inbox yet',
                )}
                description={t(
                  'compliance.automation.empty.changes.description',
                  'Feed items appear when ingested; matched impacts appear after Run watch. Empty means nothing pending — not fabricated alerts.',
                )}
              />
            </div>
          ) : null}

          <div
            className="bg-card/50 border border-border rounded-xl overflow-hidden"
            data-testid="monitoring-changes-feed"
          >
            <div className="p-4 border-b border-border flex items-center justify-between gap-3">
              <h4 className="font-medium text-foreground">
                {t('compliance.automation.changes.feed_section', 'Regulatory feed')}
              </h4>
              <span className="text-xs text-muted-foreground">
                {countUnreviewedRegulatoryUpdates(updates)} pending review
              </span>
            </div>
            {updates.length === 0 ? (
              <div className="p-6" data-testid="monitoring-changes-feed-empty">
                <EmptyState
                  icon={<Bell className="w-6 h-6 text-muted-foreground" />}
                  title={t(
                    'compliance.automation.empty.changes.feed.title',
                    'No feed items yet',
                  )}
                  description={t(
                    'compliance.automation.empty.changes.feed.description',
                    'Ingested regulatory feed items appear here. Empty means no feed rows yet — not sample headlines.',
                  )}
                />
              </div>
            ) : (
              <div className="divide-y divide-border">
                {updates.map((update) => (
                  <div
                    key={update.id}
                    className={cn(
                      'p-5 transition-colors',
                      update.is_reviewed ? 'bg-transparent' : 'bg-warning/5',
                    )}
                  >
                    <div className="flex items-start justify-between gap-4 mb-3">
                      <div className="flex-1">
                        <div className="flex items-center gap-3 mb-2 flex-wrap">
                          <span
                            className={`px-2 py-1 rounded text-xs font-medium border ${impactColors[update.impact]}`}
                          >
                            {update.impact.toUpperCase()}
                          </span>
                          <span className="px-2 py-1 bg-muted rounded text-xs text-muted-foreground">
                            {update.source.toUpperCase()}
                          </span>
                          <span className="text-muted-foreground text-xs">
                            {update.source_reference}
                          </span>
                          {!update.is_reviewed && (
                            <span className="px-2 py-1 bg-warning/20 text-warning rounded text-xs">
                              NEW
                            </span>
                          )}
                        </div>
                        <h3 className="font-medium text-foreground mb-1">{update.title}</h3>
                        <p className="text-sm text-muted-foreground">{update.summary}</p>
                      </div>
                    </div>

                    <div className="flex items-center justify-between flex-wrap gap-3">
                      <div className="flex items-center gap-4 text-sm flex-wrap">
                        <span className="text-muted-foreground">
                          Published: {new Date(update.published_date).toLocaleDateString()}
                        </span>
                        <span className="text-muted-foreground">
                          Effective: {new Date(update.effective_date).toLocaleDateString()}
                        </span>
                        <span className="text-muted-foreground">
                          Affects: {update.affected_standards.join(', ')}
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <button className="flex items-center gap-2 px-3 py-1.5 bg-info/20 hover:bg-info text-info hover:text-info-foreground rounded-lg text-sm transition-colors">
                          <Zap className="w-4 h-4" />
                          {t('compliance.automation.run_gap_analysis', 'Run Gap Analysis')}
                        </button>
                        {!update.is_reviewed && (
                          <button className="flex items-center gap-2 px-3 py-1.5 bg-success hover:bg-success/90 text-success-foreground rounded-lg text-sm transition-colors">
                            <CheckCircle className="w-4 h-4" />
                            {t('compliance.automation.mark_reviewed', 'Mark Reviewed')}
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div
            className="bg-card/50 border border-border rounded-xl overflow-hidden"
            data-testid="monitoring-changes-impacts"
          >
            <div className="p-4 border-b border-border flex items-center justify-between gap-3">
              <h4 className="font-medium text-foreground">
                {t('compliance.automation.changes.impacts_section', 'Matched impacts')}
              </h4>
              <span className="text-xs text-muted-foreground">
                {watchImpacts.filter(isOpenWatchImpact).length} open
              </span>
            </div>
            {watchImpacts.length === 0 ? (
              <div className="p-6" data-testid="monitoring-changes-impacts-empty">
                <EmptyState
                  icon={<Eye className="w-6 h-6 text-muted-foreground" />}
                  title={t(
                    'compliance.automation.empty.changes.impacts.title',
                    'No matched impacts yet',
                  )}
                  description={t(
                    'compliance.automation.empty.changes.impacts.description',
                    'Run watch to poll curated UK feeds and match impacts to your knowledge base. Create Action turns an open impact into a real CAPA.',
                  )}
                />
              </div>
            ) : (
              <div className="divide-y divide-border">
                {watchImpacts.map((impact) => {
                  const busy = actionBusyId === impact.id
                  const open = isOpenWatchImpact(impact)
                  return (
                    <div
                      key={impact.id}
                      className="p-4 hover:bg-accent/50 transition-colors"
                      data-testid={`monitoring-changes-impact-${impact.id}`}
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div className="min-w-0 flex-1">
                          <p className="font-medium text-foreground">Update {impact.update_id}</p>
                          {impact.rationale && (
                            <p className="text-sm text-muted-foreground mt-1">{impact.rationale}</p>
                          )}
                          <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2 text-sm text-muted-foreground">
                            {impact.document_id && (
                              <Link
                                to={`/documents/${impact.document_id}`}
                                className="text-primary hover:underline"
                              >
                                Document #{impact.document_id}
                              </Link>
                            )}
                            {impact.due_date && (
                              <span>Due {new Date(impact.due_date).toLocaleDateString()}</span>
                            )}
                            {impact.owner_id && <span>Owner #{impact.owner_id}</span>}
                            {impact.action_key && (
                              <Link
                                to={buildActionDetailPath(impact.action_key)}
                                className="text-primary hover:underline"
                                data-testid={`monitoring-changes-impact-action-${impact.id}`}
                              >
                                {impact.action_reference ?? impact.action_key}
                              </Link>
                            )}
                          </div>
                          {open && (
                            <div className="flex flex-wrap gap-2 mt-3">
                              {!impact.action_id && (
                                <Button
                                  size="sm"
                                  onClick={() => void handleCreateWatchAction(impact.id)}
                                  disabled={busy}
                                  data-testid={`monitoring-changes-create-action-${impact.id}`}
                                >
                                  {busy ? (
                                    <RefreshCw className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                                  ) : (
                                    <Zap className="w-3.5 h-3.5 mr-1.5" />
                                  )}
                                  {t(
                                    'compliance.automation.changes.create_action',
                                    'Create Action',
                                  )}
                                </Button>
                              )}
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => void handleResolveWatchImpact(impact.id, false)}
                                disabled={busy}
                              >
                                {t('compliance.automation.changes.resolve', 'Resolve')}
                              </Button>
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => void handleResolveWatchImpact(impact.id, true)}
                                disabled={busy}
                              >
                                {t('compliance.automation.changes.dismiss', 'Dismiss')}
                              </Button>
                            </div>
                          )}
                        </div>
                        <span className="px-2 py-1 rounded text-xs font-medium bg-muted text-muted-foreground whitespace-nowrap">
                          {impact.status}
                        </span>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Certificates Tab */}
      {activeTab === 'certificates' && (
        <div
          className="bg-card/50 border border-border rounded-xl overflow-hidden"
          data-testid="monitoring-certificates-tab"
        >
          <div className="p-4 border-b border-border flex items-center justify-between">
            <h3 className="font-medium text-foreground">
              {t('compliance.automation.cert_expiry_tracking', 'Certificate Expiry Tracking')}
            </h3>
            <button className="flex items-center gap-2 px-3 py-1.5 bg-success hover:bg-success/90 text-success-foreground rounded-lg text-sm transition-colors">
              <Award className="w-4 h-4" />
              {t('compliance.automation.add_certificate', 'Add Certificate')}
            </button>
          </div>
          {certificates.length === 0 ? (
            <div data-testid="monitoring-certificates-empty">
              <EmptyState
                icon={<Award className="w-8 h-8 text-muted-foreground" />}
                title={t('compliance.automation.empty.certificates.title', 'No certificates tracked yet')}
                description={t(
                  'compliance.automation.empty.certificates.description',
                  'Track training, equipment, and site certificates here once added. Empty means none on record — not sample data.',
                )}
              />
            </div>
          ) : (
          <div className="divide-y divide-border">
            {certificates.map((cert) => (
              <div key={cert.id} className="p-4 hover:bg-accent/50 transition-colors">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div
                      className={cn(
                        'p-2 rounded-lg',
                        cert.entity_type === 'user'
                          ? 'bg-info/20'
                          : cert.entity_type === 'equipment'
                            ? 'bg-purple-500/20'
                            : 'bg-success/20',
                      )}
                    >
                      {cert.entity_type === 'user' ? (
                        <Users className="w-5 h-5 text-info" />
                      ) : cert.entity_type === 'equipment' ? (
                        <Truck className="w-5 h-5 text-purple-500" />
                      ) : (
                        <Building className="w-5 h-5 text-success" />
                      )}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h4 className="font-medium text-foreground">{cert.name}</h4>
                        {cert.is_critical && (
                          <span className="px-2 py-0.5 bg-destructive/20 text-destructive rounded text-xs">
                            Critical
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-muted-foreground">
                        {cert.entity_name} • {cert.issuing_body}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    <div className="text-right">
                      <span
                        className={`px-2 py-1 rounded text-xs font-medium ${statusColors[cert.status]}`}
                      >
                        {cert.status.replace('_', ' ').toUpperCase()}
                      </span>
                      <p className="text-sm text-muted-foreground mt-1">
                        Expires: {new Date(cert.expiry_date).toLocaleDateString()}
                      </p>
                    </div>
                    <button className="p-2 text-muted-foreground hover:text-foreground rounded-lg hover:bg-accent">
                      <Eye className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
          )}
        </div>
      )}

      {/* Scheduled Audits Tab */}
      {activeTab === 'audits' && (
        <div
          className="bg-card/50 border border-border rounded-xl overflow-hidden"
          data-testid="monitoring-audits-tab"
        >
          <div className="p-4 border-b border-border flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <div>
              <h3 className="font-medium text-foreground">
                {t('compliance.automation.scheduled_inspections', 'Scheduled Audits & Inspections')}
              </h3>
              <p className="text-sm text-muted-foreground mt-1">
                {t(
                  'compliance.automation.audits.handoff_note',
                  'Reads scheduled and in-progress runs from Audits — not the legacy compliance schedule feed.',
                )}
              </p>
            </div>
            <Button variant="outline" asChild>
              <Link to={MONITORING_AUDITS_HANDOFF_PATH} data-testid="monitoring-audits-schedule-link">
                <Calendar className="w-4 h-4 mr-2" />
                {t('compliance.automation.open_audits', 'Open Audits')}
              </Link>
            </Button>
          </div>
          {auditRuns.length === 0 ? (
            <div data-testid="monitoring-audits-empty">
              <EmptyState
                icon={<Calendar className="w-8 h-8 text-muted-foreground" />}
                title={t('compliance.automation.empty.audits.title', 'No upcoming audit runs')}
                description={t(
                  'compliance.automation.empty.audits.description',
                  'Scheduled and in-progress audit runs from the Audits module appear here. Schedule new runs in Audits — empty means none queued, not demo data.',
                )}
                action={
                  <Button asChild>
                    <Link to={MONITORING_AUDITS_HANDOFF_PATH} data-testid="monitoring-audits-empty-cta">
                      {t('compliance.automation.schedule_in_audits', 'Schedule in Audits')}
                    </Link>
                  </Button>
                }
              />
            </div>
          ) : (
          <div className="divide-y divide-border">
            {auditRuns.map((run) => (
              <div key={run.id} className="p-4 hover:bg-accent/50 transition-colors">
                <div className="flex items-center justify-between gap-4">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 mb-1 flex-wrap">
                      <h4 className="font-medium text-foreground">{run.title}</h4>
                      <span
                        className={`px-2 py-0.5 rounded text-xs font-medium ${statusColors[run.status] ?? statusColors.scheduled}`}
                      >
                        {run.status.replace('_', ' ').toUpperCase()}
                      </span>
                    </div>
                    <p className="text-sm text-muted-foreground">
                      {run.referenceNumber}
                      {run.assuranceScheme ? ` • ${run.assuranceScheme}` : ''}
                      {run.location ? ` • ${run.location}` : ''}
                    </p>
                  </div>
                  <div className="flex items-center gap-4 shrink-0">
                    {run.dueDate ? (
                      <div className="text-right">
                        <p className="text-sm text-foreground">
                          {t('compliance.automation.audits.due', 'Due')}:{' '}
                          {new Date(run.dueDate).toLocaleDateString()}
                        </p>
                      </div>
                    ) : null}
                    <Button variant="outline" size="sm" asChild>
                      <Link
                        to={run.workspacePath}
                        data-testid={`monitoring-audit-run-${run.id}`}
                      >
                        <Play className="w-4 h-4 mr-1.5" />
                        {run.status === 'in_progress'
                          ? t('compliance.automation.audits.continue', 'Continue')
                          : t('compliance.automation.audits.open', 'Open')}
                      </Link>
                    </Button>
                  </div>
                </div>
              </div>
            ))}
          </div>
          )}
        </div>
      )}


      {/* RIDDOR Tab */}
      {activeTab === 'riddor' && (
        <div className="space-y-6">
          <div className="bg-gradient-to-r from-destructive/20 to-warning/20 border border-destructive/30 rounded-xl p-6">
            <div className="flex items-start gap-4">
              <div className="p-3 bg-destructive/20 rounded-lg">
                <FileText className="w-6 h-6 text-destructive" />
              </div>
              <div className="flex-1">
                <h3 className="text-lg font-semibold text-foreground mb-2">RIDDOR reporting</h3>
                <p className="text-muted-foreground mb-4">
                  Open the official HSE RIDDOR portal to submit reportable incidents. QGP flags
                  candidates from Incidents; statutory filing is completed on HSE.gov.uk.
                </p>
                <div className="flex flex-wrap items-center gap-3">
                  <a
                    href={HSE_RIDDOR_PORTAL_URL}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-2 px-4 py-2 bg-destructive hover:bg-destructive/90 text-destructive-foreground rounded-lg transition-colors"
                    data-testid="riddor-hse-portal-link"
                  >
                    <ExternalLink className="w-4 h-4" />
                    HSE RIDDOR Portal
                  </a>
                  <a
                    href={HSE_RIDDOR_GUIDE_URL}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-2 px-4 py-2 bg-muted hover:bg-accent text-foreground rounded-lg transition-colors"
                    data-testid="riddor-hse-guide-link"
                  >
                    <BookOpen className="w-4 h-4" />
                    HSE reporting guide
                  </a>
                  <Button variant="outline" asChild>
                    <Link to="/incidents">Open Incidents</Link>
                  </Button>
                </div>
              </div>
            </div>
          </div>

          <div
            className="bg-card/50 border border-border rounded-xl overflow-hidden"
            data-testid="monitoring-riddor-register"
          >
            <div className="p-4 border-b border-border flex items-center justify-between gap-3">
              <div>
                <h3 className="font-medium text-foreground">
                  {t('compliance.automation.riddor_register', 'RIDDOR register')}
                </h3>
                <p className="text-xs text-muted-foreground mt-1">
                  {t(
                    'compliance.automation.riddor_register_note',
                    'Draft packs persisted from Incidents. Filing stays on the HSE portal — QGP does not claim HSE submission.',
                  )}
                </p>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => void loadRiddorSubmissions()}
                disabled={riddorLoading}
                data-testid="monitoring-riddor-refresh"
              >
                <RefreshCw className={cn('w-4 h-4 mr-2', riddorLoading && 'animate-spin')} />
                {t('compliance.automation.changes.refresh', 'Refresh inbox')}
              </Button>
            </div>
            {riddorError ? (
              <div className="p-6 text-sm text-destructive" role="alert">
                {riddorError}
              </div>
            ) : riddorLoading ? (
              <div className="p-8 text-center text-muted-foreground text-sm">
                {t('compliance.automation.riddor_loading', 'Loading register…')}
              </div>
            ) : riddorPacks.length === 0 ? (
              <div className="p-8 text-center" data-testid="monitoring-riddor-empty">
                <CheckCircle className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
                <p className="text-foreground font-medium">
                  {t(
                    'compliance.automation.empty.riddor.title',
                    'No RIDDOR packs in QGP yet',
                  )}
                </p>
                <p className="text-muted-foreground text-sm mt-1 max-w-md mx-auto">
                  {t(
                    'compliance.automation.empty.riddor.description',
                    'When an incident is reportable, prepare the pack from Incidents; it appears here. Empty means none queued — not that HSE was already notified.',
                  )}
                </p>
              </div>
            ) : (
              <div className="divide-y divide-border" data-testid="monitoring-riddor-packs">
                {riddorPacks.map((pack) => (
                  <div
                    key={pack.id}
                    className="p-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3"
                    data-testid={`monitoring-riddor-pack-${pack.id}`}
                  >
                    <div className="min-w-0">
                      <p className="font-medium text-foreground truncate">
                        {pack.incidentReference || `Incident #${pack.incidentId}`}
                        <span className="text-muted-foreground font-normal">
                          {' '}
                          · {pack.riddorType}
                        </span>
                      </p>
                      <p className="text-sm text-muted-foreground mt-1">{pack.statusLabel}</p>
                      {pack.deadline ? (
                        <p className="text-xs text-muted-foreground mt-1">
                          {t('compliance.automation.audits.due', 'Due')}{' '}
                          {new Date(pack.deadline).toLocaleDateString()}
                          {pack.isOverdue
                            ? ` · ${t('compliance.automation.riddor_overdue', 'Overdue')}`
                            : ''}
                        </p>
                      ) : null}
                    </div>
                    <div className="flex flex-wrap gap-2 shrink-0">
                      <Button variant="outline" size="sm" asChild>
                        <Link
                          to={`/incidents/${pack.incidentId}`}
                          data-testid={`monitoring-riddor-incident-${pack.id}`}
                        >
                          {t('compliance.automation.open_incident', 'Open incident')}
                        </Link>
                      </Button>
                      <a
                        href={HSE_RIDDOR_PORTAL_URL}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm border border-border rounded-md hover:bg-accent"
                        data-testid={`monitoring-riddor-hse-${pack.id}`}
                      >
                        <ExternalLink className="w-3.5 h-3.5" />
                        {t('compliance.automation.hse_portal', 'HSE RIDDOR Portal')}
                      </a>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
