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
  Play,
  RefreshCw,
  AlertCircle,
  BarChart3,
  Zap,
  BookOpen,
} from 'lucide-react'
import { complianceAutomationApi, getApiErrorMessage, knowledgeBankApi, type RegulatoryImpact } from '../api/client'
import { cn } from '../helpers/utils'
import { Button } from '../components/ui/Button'
import { toast } from '../contexts/ToastContext'

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

interface ScheduledAudit {
  id: number
  name: string
  audit_type: string
  frequency: string
  next_due_date: string
  status: string
  standards: string[]
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

function formatStandardCode(code: string): string {
  const labels: Record<string, string> = {
    ISO9001: 'ISO 9001',
    ISO14001: 'ISO 14001',
    ISO45001: 'ISO 45001',
    ISO27001: 'ISO 27001',
  }
  return labels[code] ?? code.replace(/([A-Z]+)(\d+)/, '$1 $2')
}

function scoreBarColor(score: number): string {
  if (score >= 80) return 'bg-success'
  if (score >= 60) return 'bg-info'
  return 'bg-primary'
}

export default function ComplianceAutomation() {
  const [activeTab, setActiveTab] = useState<
    'regulatory' | 'certificates' | 'audits' | 'scoring' | 'riddor' | 'watch'
  >('regulatory')
  const [updates, setUpdates] = useState<RegulatoryUpdate[]>([])
  const [certificates, setCertificates] = useState<Certificate[]>([])
  const [audits, setAudits] = useState<ScheduledAudit[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [complianceScore, setComplianceScore] = useState({
    overall: 0,
    previous: 0,
    change: 0,
  })
  const [scoreBreakdown, setScoreBreakdown] = useState<Array<{ code: string; label: string; score: number }>>(
    [],
  )
  const [scoreGaps, setScoreGaps] = useState<string[]>([])
  const [watchImpacts, setWatchImpacts] = useState<RegulatoryImpact[]>([])
  const [runningWatch, setRunningWatch] = useState(false)
  const [actionBusyId, setActionBusyId] = useState<number | null>(null)
  const [riddorSubmissions, setRiddorSubmissions] = useState<unknown[]>([])
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
      const [updatesRes, certificatesRes, auditsRes, scoreRes, trendRes] = await Promise.all([
        complianceAutomationApi.listRegulatoryUpdates(),
        complianceAutomationApi.listCertificates(),
        complianceAutomationApi.listScheduledAudits(),
        complianceAutomationApi.getComplianceScore({ scope_type: 'organization' }),
        complianceAutomationApi.getComplianceTrend({ scope_type: 'organization', months: 12 }),
      ])

      setUpdates((updatesRes.data.updates as RegulatoryUpdate[]) || [])

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

      const scheduledAudits = ((auditsRes.data.audits as ScheduledAudit[]) || []).map((audit) => {
        const dueDate = audit.next_due_date ? new Date(audit.next_due_date) : null
        return {
          ...audit,
          status: dueDate && dueDate < now ? 'overdue' : 'scheduled',
          standards: (audit.standards || (audit as { standard_ids?: string[] }).standard_ids || []) as string[],
        }
      })
      setAudits(scheduledAudits)

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
      setScoreBreakdown(
        Object.entries(scoreData.categories ?? {}).map(([code, score]) => ({
          code,
          label: formatStandardCode(code),
          score,
        })),
      )
      setScoreGaps(scoreData.key_gaps ?? [])
    } catch (err) {
      setError(getApiErrorMessage(err))
      setUpdates([])
      setCertificates([])
      setAudits([])
      setComplianceScore({ overall: 0, previous: 0, change: 0 })
      setScoreBreakdown([])
      setScoreGaps([])
    } finally {
      setLoading(false)
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
      setRiddorSubmissions(response.data.submissions ?? [])
    } catch (err) {
      setRiddorError(getApiErrorMessage(err))
      setRiddorSubmissions([])
    } finally {
      setRiddorLoading(false)
    }
  }

  const handleRunWatch = async () => {
    setRunningWatch(true)
    try {
      const response = await knowledgeBankApi.runRegulatoryWatch()
      toast.success(response.data.message ?? 'Regulatory watch completed')
      await loadWatchImpacts()
    } catch (err) {
      toast.error(getApiErrorMessage(err))
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
    if (activeTab === 'watch') {
      void loadWatchImpacts()
    }
    if (activeTab === 'riddor') {
      void loadRiddorSubmissions()
    }
  }, [activeTab])

  const tabs = [
    {
      id: 'regulatory',
      label: 'Regulatory Updates',
      icon: Bell,
      count: updates.filter((u) => !u.is_reviewed).length,
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
      count: audits.filter((a) => a.status === 'overdue').length,
    },
    { id: 'scoring', label: 'Compliance Score', icon: BarChart3 },
    { id: 'riddor', label: 'RIDDOR', icon: FileText },
    { id: 'watch', label: 'Watch', icon: Eye, count: watchImpacts.length },
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
          <h1 className="text-2xl font-bold text-foreground">Compliance Automation</h1>
          <p className="text-muted-foreground mt-1">
            Monitor regulations, track certificates, and automate compliance
          </p>
        </div>
        <Button onClick={() => void loadData()} variant="outline">
          <RefreshCw className="w-4 h-4 mr-2" />
          Refresh
        </Button>
      </div>

      {/* Score Overview */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        <div className="lg:col-span-1 bg-gradient-to-br from-primary to-primary-hover rounded-xl p-6 text-primary-foreground">
          <div className="flex items-center justify-between mb-4">
            <Shield className="w-8 h-8 opacity-80" />
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
          </div>
          <div className="text-4xl font-bold mb-1">{complianceScore.overall}%</div>
          <div className="text-primary-foreground/80 text-sm">Overall Compliance Score</div>
        </div>

        <div className="bg-card/50 border border-border rounded-xl p-4">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 rounded-lg bg-destructive/20">
              <AlertTriangle className="w-5 h-5 text-destructive" />
            </div>
            <span className="text-muted-foreground text-sm">Regulatory Updates</span>
          </div>
          <div className="text-2xl font-bold text-foreground">
            {updates.filter((u) => !u.is_reviewed).length}
          </div>
          <div className="text-sm text-muted-foreground">Pending review</div>
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
            {audits.filter((a) => a.status === 'overdue').length}
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

      {/* Regulatory Updates Tab */}
      {activeTab === 'regulatory' && (
        <div className="space-y-4">
          {updates.map((update) => (
            <div
              key={update.id}
              className={cn(
                'bg-card/50 border rounded-xl p-5 transition-colors',
                update.is_reviewed ? 'border-border' : 'border-warning/30',
              )}
            >
              <div className="flex items-start justify-between gap-4 mb-3">
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-2">
                    <span
                      className={`px-2 py-1 rounded text-xs font-medium border ${impactColors[update.impact]}`}
                    >
                      {update.impact.toUpperCase()}
                    </span>
                    <span className="px-2 py-1 bg-muted rounded text-xs text-muted-foreground">
                      {update.source.toUpperCase()}
                    </span>
                    <span className="text-muted-foreground text-xs">{update.source_reference}</span>
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

              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4 text-sm">
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
                    Run Gap Analysis
                  </button>
                  {!update.is_reviewed && (
                    <button className="flex items-center gap-2 px-3 py-1.5 bg-success hover:bg-success/90 text-success-foreground rounded-lg text-sm transition-colors">
                      <CheckCircle className="w-4 h-4" />
                      Mark Reviewed
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Certificates Tab */}
      {activeTab === 'certificates' && (
        <div className="bg-card/50 border border-border rounded-xl overflow-hidden">
          <div className="p-4 border-b border-border flex items-center justify-between">
            <h3 className="font-medium text-foreground">Certificate Expiry Tracking</h3>
            <button className="flex items-center gap-2 px-3 py-1.5 bg-success hover:bg-success/90 text-success-foreground rounded-lg text-sm transition-colors">
              <Award className="w-4 h-4" />
              Add Certificate
            </button>
          </div>
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
        </div>
      )}

      {/* Scheduled Audits Tab */}
      {activeTab === 'audits' && (
        <div className="bg-card/50 border border-border rounded-xl overflow-hidden">
          <div className="p-4 border-b border-border flex items-center justify-between">
            <h3 className="font-medium text-foreground">Scheduled Audits & Inspections</h3>
            <button className="flex items-center gap-2 px-3 py-1.5 bg-success hover:bg-success/90 text-success-foreground rounded-lg text-sm transition-colors">
              <Calendar className="w-4 h-4" />
              Schedule Audit
            </button>
          </div>
          <div className="divide-y divide-border">
            {audits.map((audit) => (
              <div key={audit.id} className="p-4 hover:bg-accent/50 transition-colors">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <h4 className="font-medium text-foreground">{audit.name}</h4>
                      <span
                        className={`px-2 py-0.5 rounded text-xs font-medium ${statusColors[audit.status]}`}
                      >
                        {audit.status.toUpperCase()}
                      </span>
                    </div>
                    <p className="text-sm text-muted-foreground">
                      {audit.frequency} • {audit.standards.join(', ')}
                    </p>
                  </div>
                  <div className="flex items-center gap-4">
                    <div className="text-right">
                      <p className="text-sm text-foreground">
                        Due: {new Date(audit.next_due_date).toLocaleDateString()}
                      </p>
                    </div>
                    <button className="flex items-center gap-2 px-3 py-1.5 bg-success hover:bg-success/90 text-success-foreground rounded-lg text-sm transition-colors">
                      <Play className="w-4 h-4" />
                      Start
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Compliance Scoring Tab */}
      {activeTab === 'scoring' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-card/50 border border-border rounded-xl p-6">
            <h3 className="font-medium text-foreground mb-4">Score Breakdown by Standard</h3>
            {scoreBreakdown.length === 0 ? (
              <div className="py-8 text-center text-muted-foreground text-sm space-y-2">
                <p>No live standard scores yet.</p>
                <p>Scores come from evidence coverage in your standards library — not demo placeholders.</p>
              </div>
            ) : (
              <div className="space-y-4">
                {scoreBreakdown.map((standard) => (
                  <div key={standard.code}>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-foreground font-medium">{standard.label}</span>
                      <span className="text-foreground">{standard.score}%</span>
                    </div>
                    <div className="h-3 bg-muted rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full ${scoreBarColor(standard.score)}`}
                        style={{ width: `${Math.min(100, Math.max(0, standard.score))}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="bg-card/50 border border-border rounded-xl p-6">
            <h3 className="font-medium text-foreground mb-4">Key Gaps</h3>
            {scoreGaps.length === 0 ? (
              <div className="py-8 text-center text-muted-foreground text-sm">
                No automated gap list yet. Run gap analysis or link evidence to standards to populate this view.
              </div>
            ) : (
              <div className="space-y-3">
                {scoreGaps.map((gap, i) => (
                  <div key={i} className="flex items-center gap-3 p-3 bg-muted/50 rounded-lg">
                    <AlertCircle className="w-5 h-5 text-warning shrink-0" />
                    <p className="text-foreground text-sm">{gap}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
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

          <div className="bg-card/50 border border-border rounded-xl overflow-hidden">
            <div className="p-4 border-b border-border flex items-center justify-between gap-3">
              <h3 className="font-medium text-foreground">RIDDOR register</h3>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => void loadRiddorSubmissions()}
                disabled={riddorLoading}
              >
                <RefreshCw className={cn('w-4 h-4 mr-2', riddorLoading && 'animate-spin')} />
                Refresh
              </Button>
            </div>
            {riddorError ? (
              <div className="p-6 text-sm text-destructive" role="alert">
                {riddorError}
              </div>
            ) : riddorLoading ? (
              <div className="p-8 text-center text-muted-foreground text-sm">Loading register…</div>
            ) : riddorSubmissions.length === 0 ? (
              <div className="p-8 text-center">
                <CheckCircle className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
                <p className="text-foreground font-medium">No RIDDOR packs in QGP yet</p>
                <p className="text-muted-foreground text-sm mt-1 max-w-md mx-auto">
                  When an incident is reportable, prepare the pack here and complete filing on the
                  HSE portal. Empty means none queued — not that HSE was already notified.
                </p>
              </div>
            ) : (
              <div className="p-4 text-sm text-muted-foreground">
                {riddorSubmissions.length} submission(s) recorded.
              </div>
            )}
          </div>
        </div>
      )}

      {/* Regulatory Watch Tab */}
      {activeTab === 'watch' && (
        <div className="space-y-4">
          <div className="bg-card/50 border border-border rounded-xl p-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div>
              <h3 className="font-medium text-foreground">Regulatory Watch</h3>
              <p className="text-sm text-muted-foreground mt-1">
                Poll curated UK feeds, match impacts to your knowledge base, create Actions with
                owner and due date, then resolve closed-loop.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" onClick={() => void loadWatchImpacts()} disabled={runningWatch}>
                <RefreshCw className="w-4 h-4 mr-2" />
                Refresh
              </Button>
              <Button onClick={() => void handleRunWatch()} disabled={runningWatch}>
                {runningWatch ? (
                  <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                ) : (
                  <Play className="w-4 h-4 mr-2" />
                )}
                Run watch
              </Button>
            </div>
          </div>

          {watchError ? (
            <div
              className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive"
              role="alert"
            >
              {watchError}
            </div>
          ) : null}

          <div className="bg-card/50 border border-border rounded-xl overflow-hidden">
            <div className="p-4 border-b border-border">
              <h3 className="font-medium text-foreground">Impacts ({watchImpacts.length})</h3>
            </div>
            {watchImpacts.length === 0 ? (
              <div className="p-8 text-center text-muted-foreground text-sm space-y-2">
                <p>No open impacts yet.</p>
                <p>
                  Click <strong>Run watch</strong> to poll feeds and create matched impacts. Create
                  Action turns an impact into a real CAPA with owner and due date.
                </p>
              </div>
            ) : (
              <div className="divide-y divide-border">
                {watchImpacts.map((impact) => {
                  const busy = actionBusyId === impact.id
                  const open =
                    impact.status !== 'resolved' && impact.status !== 'dismissed'
                  return (
                    <div key={impact.id} className="p-4 hover:bg-accent/50 transition-colors">
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
                                >
                                  {busy ? (
                                    <RefreshCw className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                                  ) : (
                                    <Zap className="w-3.5 h-3.5 mr-1.5" />
                                  )}
                                  Create Action
                                </Button>
                              )}
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => void handleResolveWatchImpact(impact.id, false)}
                                disabled={busy}
                              >
                                Resolve
                              </Button>
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => void handleResolveWatchImpact(impact.id, true)}
                                disabled={busy}
                              >
                                Dismiss
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
    </div>
  )
}
