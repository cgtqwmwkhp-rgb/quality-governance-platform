import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Shield,
  Leaf,
  HardHat,
  CheckCircle2,
  AlertTriangle,
  Clock,
  TrendingUp,
  Calendar,
  Users,
  Target,
  BarChart3,
  Link2,
  ChevronRight,
  RefreshCw,
  GitMerge,
  FileText,
  ClipboardList,
  Lock,
  Server,
  ShieldCheck,
  Bug,
  Building2,
  Laptop,
  Key,
  AlertOctagon,
  Award,
  AlertCircle,
  Download,
  UserCheck,
} from 'lucide-react'
import { cn } from '../helpers/utils'
import { Button } from '../components/ui/Button'
import { imsDashboardApi, type IMSDashboardResponse, getApiErrorMessage } from '../api/client'

type StandardDisplay = {
  id: string
  name: string
  version: string
  icon: React.ElementType
  color: string
  compliance: number
  totalControls: number
  implemented: number
  partial: number
  notImplemented: number
  setupRequired: boolean
}

const STANDARD_META: Record<string, { icon: React.ElementType; color: string; label: string }> = {
  'ISO9001': { icon: Shield, color: 'bg-blue-500', label: 'Quality Management' },
  'ISO14001': { icon: Leaf, color: 'bg-emerald-500', label: 'Environmental Management' },
  'ISO45001': { icon: HardHat, color: 'bg-orange-500', label: 'OH&S Management' },
  'ISO27001': { icon: Lock, color: 'bg-purple-500', label: 'Information Security' },
}

function getStandardMeta(code: string) {
  const normalized = code.replace(/[:\s-]/g, '').toUpperCase()
  for (const [key, meta] of Object.entries(STANDARD_META)) {
    if (normalized.includes(key)) return meta
  }
  return { icon: Shield, color: 'bg-gray-500', label: code }
}

const DOMAIN_ICONS: Record<string, React.ElementType> = {
  organizational: Building2,
  people: UserCheck,
  physical: Key,
  technological: Laptop,
}

const DOMAIN_COLORS: Record<string, string> = {
  organizational: 'bg-blue-500',
  people: 'bg-green-500',
  physical: 'bg-orange-500',
  technological: 'bg-purple-500',
}

export default function IMSDashboard() {
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState<'overview' | 'mapping' | 'audit' | 'review' | 'isms'>('overview')
  const [selectedStandard, setSelectedStandard] = useState<string | null>(null)
  const [dashboardData, setDashboardData] = useState<IMSDashboardResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [syncing, setSyncing] = useState(false)
  const [toastMessage, setToastMessage] = useState<string | null>(null)

  const loadDashboard = useCallback(async () => {
    try {
      setError(null)
      const response = await imsDashboardApi.getDashboard()
      setDashboardData(response.data)
    } catch (err) {
      setError(getApiErrorMessage(err))
    } finally {
      setLoading(false)
      setSyncing(false)
    }
  }, [])

  useEffect(() => {
    loadDashboard()
  }, [loadDashboard])

  useEffect(() => {
    if (toastMessage) {
      const timer = setTimeout(() => setToastMessage(null), 3000)
      return () => clearTimeout(timer)
    }
  }, [toastMessage])

  const handleSync = () => {
    setSyncing(true)
    loadDashboard()
  }

  const handleGenerateReport = () => {
    if (!dashboardData) return
    const blob = new Blob([JSON.stringify(dashboardData, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `ims-report-${new Date().toISOString().slice(0, 10)}.json`
    a.click()
    URL.revokeObjectURL(url)
    setToastMessage('Report downloaded')
  }

  const handleExportSoA = () => {
    if (!dashboardData?.isms) {
      setToastMessage('No ISMS data to export')
      return
    }
    const soaData = {
      generated_at: dashboardData.generated_at,
      controls: dashboardData.isms.controls,
      domains: dashboardData.isms.domains,
      compliance_score: dashboardData.isms.compliance_score,
    }
    const blob = new Blob([JSON.stringify(soaData, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `soa-export-${new Date().toISOString().slice(0, 10)}.json`
    a.click()
    URL.revokeObjectURL(url)
    setToastMessage('SoA exported')
  }

  // Map API standards to display format
  const standards: StandardDisplay[] = (dashboardData?.standards ?? []).map((s) => {
    const meta = getStandardMeta(s.standard_code)
    return {
      id: s.standard_code,
      name: s.standard_code,
      version: meta.label || s.standard_name,
      icon: meta.icon,
      color: meta.color,
      compliance: s.compliance_percentage,
      totalControls: s.total_controls,
      implemented: s.implemented_count,
      partial: s.partial_count,
      notImplemented: s.not_implemented_count,
      setupRequired: s.setup_required,
    }
  })

  const overallCompliance = dashboardData?.overall_compliance ?? 0
  const isms = dashboardData?.isms
  const uvdb = dashboardData?.uvdb
  const planetMark = dashboardData?.planet_mark
  const complianceCoverage = dashboardData?.compliance_coverage
  const auditSchedule = dashboardData?.audit_schedule ?? []

  if (loading) {
    return (
      <div className="min-h-screen bg-background text-foreground flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <RefreshCw className="w-10 h-10 text-primary animate-spin" />
          <p className="text-muted-foreground">Loading IMS Dashboard...</p>
        </div>
      </div>
    )
  }

  if (error && !dashboardData) {
    return (
      <div className="min-h-screen bg-background text-foreground flex items-center justify-center">
        <div className="flex flex-col items-center gap-4 max-w-md text-center">
          <AlertCircle className="w-10 h-10 text-destructive" />
          <p className="text-foreground font-medium">Failed to load dashboard</p>
          <p className="text-muted-foreground text-sm">{error}</p>
          <Button onClick={handleSync}>
            <RefreshCw className="w-4 h-4 mr-2" />
            Retry
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background text-foreground p-6">
      {/* Toast */}
      {toastMessage && (
        <div className="fixed top-4 right-4 z-50 bg-card border border-border rounded-lg px-4 py-3 shadow-lg flex items-center gap-2 animate-in fade-in slide-in-from-top-2">
          <CheckCircle2 className="w-4 h-4 text-success" />
          <span className="text-sm text-foreground">{toastMessage}</span>
        </div>
      )}

      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-foreground mb-2 flex items-center gap-3">
            <GitMerge className="w-8 h-8 text-primary" />
            Integrated Management System
          </h1>
          <p className="text-muted-foreground">
            Unified compliance dashboard across all management standards
          </p>
        </div>
        <div className="flex gap-3 mt-4 md:mt-0">
          <Button variant="outline" onClick={handleSync} disabled={syncing}>
            <RefreshCw className={cn("w-4 h-4 mr-2", syncing && "animate-spin")} />
            Sync
          </Button>
          <Button onClick={handleGenerateReport} disabled={!dashboardData}>
            <FileText className="w-4 h-4 mr-2" />
            Generate Report
          </Button>
        </div>
      </div>

      {/* Overall Compliance Indicator */}
      <div className="bg-gradient-to-r from-primary to-primary-hover rounded-xl p-6 mb-8">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold text-primary-foreground mb-1">Overall IMS Compliance</h2>
            <p className="text-primary-foreground/80">Across all management system standards</p>
          </div>
          <div className="text-right">
            <div className="text-5xl font-bold text-primary-foreground">{overallCompliance}%</div>
            {complianceCoverage && (
              <div className="flex items-center gap-1 text-primary-foreground/80 mt-1">
                <Target className="w-4 h-4" />
                <span>{complianceCoverage.coverage_percentage}% evidence coverage</span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Standards Cards */}
      {standards.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          {standards.map((standard) => {
            const Icon = standard.icon
            return (
              <div
                key={standard.id}
                className={`bg-card rounded-xl p-6 border border-border hover:border-border-strong transition-colors cursor-pointer ${
                  selectedStandard === standard.id ? 'ring-2 ring-primary' : ''
                }`}
                onClick={() => setSelectedStandard(standard.id)}
              >
                <div className="flex items-start justify-between mb-4">
                  <div className={`p-3 rounded-xl ${standard.color}`}>
                    <Icon className="w-6 h-6 text-white" />
                  </div>
                  <div className="text-right">
                    {standard.setupRequired ? (
                      <div className="text-sm text-muted-foreground">Setup required</div>
                    ) : (
                      <>
                        <div className="text-3xl font-bold text-foreground">{standard.compliance}%</div>
                        <div className="text-xs text-muted-foreground">Compliance</div>
                      </>
                    )}
                  </div>
                </div>

                <h3 className="text-lg font-bold text-foreground mb-1">{standard.name}</h3>
                <p className="text-sm text-muted-foreground mb-4">{standard.version}</p>

                {!standard.setupRequired && (
                  <>
                    <div className="w-full bg-surface rounded-full h-2 mb-4">
                      <div
                        className={`h-2 rounded-full ${standard.color}`}
                        style={{ width: `${standard.compliance}%` }}
                      ></div>
                    </div>

                    <div className="flex justify-between text-sm">
                      <div className="flex items-center gap-1">
                        <span className="w-2 h-2 bg-success rounded-full"></span>
                        <span className="text-muted-foreground">Impl: {standard.implemented}</span>
                      </div>
                      <div className="flex items-center gap-1">
                        <span className="w-2 h-2 bg-warning rounded-full"></span>
                        <span className="text-muted-foreground">Partial: {standard.partial}</span>
                      </div>
                      <div className="flex items-center gap-1">
                        <span className="w-2 h-2 bg-destructive rounded-full"></span>
                        <span className="text-muted-foreground">Gap: {standard.notImplemented}</span>
                      </div>
                    </div>
                  </>
                )}

                {standard.setupRequired && (
                  <p className="text-xs text-muted-foreground mt-2">
                    No controls configured yet. Add controls to track compliance.
                  </p>
                )}
              </div>
            )
          })}

          {/* UVDB Card */}
          {uvdb && (
            <div className="bg-card rounded-xl p-6 border border-border hover:border-border-strong transition-colors">
              <div className="flex items-start justify-between mb-4">
                <div className="p-3 rounded-xl bg-yellow-500">
                  <Award className="w-6 h-6 text-white" />
                </div>
                <div className="text-right">
                  {uvdb.status === 'not_started' ? (
                    <div className="text-sm text-muted-foreground">Not started</div>
                  ) : (
                    <>
                      <div className="text-3xl font-bold text-foreground">
                        {uvdb.latest_score ?? uvdb.average_score}%
                      </div>
                      <div className="text-xs text-muted-foreground">Score</div>
                    </>
                  )}
                </div>
              </div>
              <h3 className="text-lg font-bold text-foreground mb-1">UVDB Achilles</h3>
              <p className="text-sm text-muted-foreground mb-4">Verify B2 Audit</p>
              {uvdb.status !== 'not_started' && (
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">{uvdb.completed_audits} completed</span>
                  <span className="text-muted-foreground">{uvdb.active_audits} active</span>
                </div>
              )}
            </div>
          )}

          {/* Planet Mark Card */}
          {planetMark && (
            <div className="bg-card rounded-xl p-6 border border-border hover:border-border-strong transition-colors">
              <div className="flex items-start justify-between mb-4">
                <div className="p-3 rounded-xl bg-teal-500">
                  <Leaf className="w-6 h-6 text-white" />
                </div>
                <div className="text-right">
                  {planetMark.status === 'not_configured' ? (
                    <div className="text-sm text-muted-foreground">Setup required</div>
                  ) : (
                    <>
                      <div className="text-2xl font-bold text-foreground">
                        {planetMark.total_emissions?.toFixed(1)}
                      </div>
                      <div className="text-xs text-muted-foreground">tCO2e</div>
                    </>
                  )}
                </div>
              </div>
              <h3 className="text-lg font-bold text-foreground mb-1">Planet Mark</h3>
              <p className="text-sm text-muted-foreground mb-4">Carbon Certification</p>
              {planetMark.status !== 'not_configured' && (
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground capitalize">{planetMark.certification_status}</span>
                  {planetMark.reduction_vs_previous !== null && (
                    <span className={planetMark.reduction_vs_previous > 0 ? 'text-success' : 'text-destructive'}>
                      {planetMark.reduction_vs_previous > 0 ? '-' : '+'}{Math.abs(planetMark.reduction_vs_previous)}%
                    </span>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      ) : (
        <div className="bg-card rounded-xl p-8 border border-border mb-8 text-center">
          <AlertCircle className="w-8 h-8 text-muted-foreground mx-auto mb-3" />
          <p className="text-foreground font-medium">No standards configured</p>
          <p className="text-muted-foreground text-sm mt-1">
            Add standards in the Standards Library to start tracking compliance.
          </p>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-2 mb-6 border-b border-border pb-2 overflow-x-auto">
        {[
          { id: 'overview', label: 'Overview', icon: BarChart3 },
          { id: 'mapping', label: 'Cross-Standard Mapping', icon: Link2 },
          { id: 'audit', label: 'Unified Audit Plan', icon: ClipboardList },
          { id: 'review', label: 'Management Review', icon: Users },
          { id: 'isms', label: 'ISO 27001 ISMS', icon: Lock },
        ].map((tab) => {
          const Icon = tab.icon
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as typeof activeTab)}
              className={cn(
                "flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors whitespace-nowrap",
                activeTab === tab.id
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:bg-muted hover:text-foreground'
              )}
            >
              <Icon className="w-4 h-4" />
              {tab.label}
            </button>
          )
        })}
      </div>

      {/* Tab Content */}
      {activeTab === 'overview' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Key Metrics */}
          <div className="bg-card rounded-xl p-6 border border-border">
            <h3 className="text-lg font-bold text-foreground mb-4">Key Performance Metrics</h3>
            <div className="space-y-4">
              {[
                {
                  label: 'Standards Tracked',
                  value: standards.length,
                  target: null,
                  unit: '',
                  status: 'good' as const,
                },
                {
                  label: 'Overall Compliance',
                  value: overallCompliance,
                  target: 100,
                  unit: '%',
                  status: overallCompliance >= 90 ? 'good' as const : overallCompliance >= 70 ? 'warning' as const : 'critical' as const,
                },
                {
                  label: 'Evidence Coverage',
                  value: complianceCoverage?.coverage_percentage ?? 0,
                  target: 100,
                  unit: '%',
                  status: (complianceCoverage?.coverage_percentage ?? 0) >= 80 ? 'good' as const : 'warning' as const,
                },
                {
                  label: 'Compliance Gaps',
                  value: complianceCoverage?.gaps ?? 0,
                  target: 0,
                  unit: '',
                  status: (complianceCoverage?.gaps ?? 0) === 0 ? 'good' as const : 'warning' as const,
                },
                {
                  label: 'Upcoming Audits',
                  value: auditSchedule.length,
                  target: null,
                  unit: '',
                  status: 'good' as const,
                },
              ].map((metric, i) => (
                <div key={i} className="flex items-center justify-between">
                  <span className="text-foreground">{metric.label}</span>
                  <div className="flex items-center gap-2">
                    <span
                      className={`font-bold ${
                        metric.status === 'good'
                          ? 'text-success'
                          : metric.status === 'warning'
                          ? 'text-warning'
                          : 'text-destructive'
                      }`}
                    >
                      {metric.value}
                      {metric.unit}
                    </span>
                    {metric.target !== null && (
                      <span className="text-muted-foreground text-sm">/ {metric.target}{metric.unit}</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Module Status */}
          <div className="bg-card rounded-xl p-6 border border-border">
            <h3 className="text-lg font-bold text-foreground mb-4">Module Status</h3>
            <div className="space-y-3">
              {[
                {
                  name: 'Standards Library',
                  status: standards.length > 0 ? 'active' : 'not_configured',
                  detail: standards.length > 0 ? `${standards.length} standards tracked` : 'No standards configured',
                  icon: Shield,
                  color: 'text-blue-500',
                },
                {
                  name: 'ISO 27001 ISMS',
                  status: isms ? 'active' : 'not_configured',
                  detail: isms ? `${isms.controls.implemented}/${isms.controls.applicable} controls implemented` : (dashboardData?.isms_error ?? 'Not configured'),
                  icon: Lock,
                  color: 'text-purple-500',
                },
                {
                  name: 'UVDB Achilles',
                  status: uvdb && uvdb.status !== 'not_started' ? 'active' : 'not_configured',
                  detail: uvdb && uvdb.status !== 'not_started' ? `${uvdb.completed_audits} audits completed` : 'No audits yet',
                  icon: Award,
                  color: 'text-yellow-500',
                },
                {
                  name: 'Planet Mark',
                  status: planetMark && planetMark.status !== 'not_configured' ? 'active' : 'not_configured',
                  detail: planetMark && planetMark.status !== 'not_configured' ? `${planetMark.total_emissions?.toFixed(1)} tCO2e` : 'Not configured',
                  icon: Leaf,
                  color: 'text-teal-500',
                },
                {
                  name: 'Compliance Evidence',
                  status: complianceCoverage ? 'active' : 'not_configured',
                  detail: complianceCoverage ? `${complianceCoverage.total_evidence_links} evidence links` : 'Not configured',
                  icon: CheckCircle2,
                  color: 'text-success',
                },
              ].map((mod, i) => {
                const Icon = mod.icon
                return (
                  <div key={i} className="flex items-start gap-3 p-2 hover:bg-surface rounded-lg transition-colors">
                    <Icon className={`w-5 h-5 mt-0.5 ${mod.color}`} />
                    <div className="flex-grow">
                      <div className="text-foreground text-sm font-medium">{mod.name}</div>
                      <div className="text-muted-foreground text-xs">{mod.detail}</div>
                    </div>
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                      mod.status === 'active'
                        ? 'bg-success/20 text-success'
                        : 'bg-muted text-muted-foreground'
                    }`}>
                      {mod.status === 'active' ? 'Active' : 'Setup required'}
                    </span>
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      )}

      {activeTab === 'mapping' && (
        <div className="bg-card rounded-xl border border-border overflow-hidden">
          <div className="p-4 bg-muted border-b border-border">
            <h3 className="font-bold text-foreground">Annex SL Cross-Standard Mapping</h3>
            <p className="text-sm text-muted-foreground">Common requirements across ISO management system standards</p>
          </div>
          {standards.length >= 2 ? (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-muted/50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase">Common Clause</th>
                    {standards.slice(0, 4).map((s) => (
                      <th key={s.id} className="px-4 py-3 text-center text-xs font-semibold text-muted-foreground uppercase">{s.name}</th>
                    ))}
                    <th className="px-4 py-3 text-center text-xs font-semibold text-muted-foreground uppercase">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {[
                    { clause: '4.1 Context of the Organization', desc: 'Understanding the organization and its context' },
                    { clause: '5.1 Leadership & Commitment', desc: 'Top management commitment' },
                    { clause: '6.1 Risks & Opportunities', desc: 'Actions to address risks and opportunities' },
                    { clause: '7.2 Competence', desc: 'Determining necessary competence' },
                    { clause: '9.2 Internal Audit', desc: 'Planning and conducting internal audits' },
                    { clause: '10.2 Nonconformity & Corrective Action', desc: 'Reacting to nonconformities' },
                  ].map((mapping, i) => (
                    <tr key={i} className="hover:bg-muted/30">
                      <td className="px-4 py-3">
                        <div className="font-medium text-foreground">{mapping.clause}</div>
                        <div className="text-xs text-muted-foreground">{mapping.desc}</div>
                      </td>
                      {standards.slice(0, 4).map((s) => (
                        <td key={s.id} className="px-4 py-3 text-center">
                          <span className="px-2 py-1 bg-primary/10 text-primary rounded text-xs">
                            {mapping.clause.split(' ')[0]}
                          </span>
                        </td>
                      ))}
                      <td className="px-4 py-3 text-center">
                        <span className="px-2 py-1 bg-success/20 text-success rounded-full text-xs font-medium">
                          Mapped
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="p-8 text-center">
              <p className="text-muted-foreground">Add at least 2 standards to view cross-standard mapping.</p>
            </div>
          )}
        </div>
      )}

      {activeTab === 'audit' && (
        <div className="bg-card rounded-xl border border-border">
          <div className="p-4 bg-muted border-b border-border flex items-center justify-between">
            <div>
              <h3 className="font-bold text-foreground">Unified Audit Schedule</h3>
              <p className="text-sm text-muted-foreground">Integrated audit program covering all standards</p>
            </div>
            <Button onClick={() => navigate('/audits')}>
              Plan New Audit
            </Button>
          </div>
          <div className="p-4 space-y-4">
            {auditSchedule.length > 0 ? (
              auditSchedule.map((audit) => (
                <div
                  key={audit.id}
                  className="flex items-center justify-between p-4 bg-surface rounded-lg hover:bg-muted transition-colors cursor-pointer"
                  onClick={() => navigate('/audits')}
                >
                  <div className="flex items-center gap-4">
                    <div className="p-3 bg-muted rounded-lg">
                      <Calendar className="w-5 h-5 text-primary" />
                    </div>
                    <div>
                      <div className="font-medium text-foreground">
                        {audit.title || audit.reference_number}
                      </div>
                      <div className="text-sm text-muted-foreground">
                        {audit.scheduled_date
                          ? `Scheduled: ${new Date(audit.scheduled_date).toLocaleDateString()}`
                          : 'Not scheduled'}
                        {audit.due_date && ` | Due: ${new Date(audit.due_date).toLocaleDateString()}`}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <span
                      className={`px-3 py-1 rounded-full text-xs font-medium ${
                        audit.status === 'scheduled'
                          ? 'bg-success/20 text-success'
                          : audit.status === 'in_progress'
                          ? 'bg-info/20 text-info'
                          : 'bg-muted text-muted-foreground'
                      }`}
                    >
                      {audit.status}
                    </span>
                    <ChevronRight className="w-5 h-5 text-muted-foreground" />
                  </div>
                </div>
              ))
            ) : (
              <div className="p-8 text-center">
                <Calendar className="w-8 h-8 text-muted-foreground mx-auto mb-3" />
                <p className="text-foreground font-medium">No upcoming audits</p>
                <p className="text-muted-foreground text-sm mt-1">Plan an audit to get started.</p>
              </div>
            )}
          </div>
        </div>
      )}

      {activeTab === 'review' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 bg-card rounded-xl border border-border">
            <div className="p-4 bg-muted border-b border-border">
              <h3 className="font-bold text-foreground">Management Review Inputs</h3>
              <p className="text-sm text-muted-foreground">Data readiness across all modules</p>
            </div>
            <div className="p-4 space-y-3">
              {[
                {
                  category: 'Standards Compliance',
                  status: standards.length > 0 ? 'Complete' : 'Pending',
                  source: 'Standards Library',
                  trend: overallCompliance >= 80 ? 'improving' : 'stable',
                },
                {
                  category: 'Information Security',
                  status: isms ? 'Complete' : 'Pending',
                  source: 'ISO 27001',
                  trend: isms && isms.compliance_score >= 80 ? 'improving' : 'stable',
                },
                {
                  category: 'UVDB Qualification',
                  status: uvdb && uvdb.status !== 'not_started' ? 'Complete' : 'Pending',
                  source: 'UVDB Achilles',
                  trend: 'stable',
                },
                {
                  category: 'Carbon Footprint',
                  status: planetMark && planetMark.status !== 'not_configured' ? 'Complete' : 'Pending',
                  source: 'Planet Mark',
                  trend: planetMark?.reduction_vs_previous && planetMark.reduction_vs_previous > 0 ? 'improving' : 'stable',
                },
                {
                  category: 'Compliance Evidence',
                  status: complianceCoverage && complianceCoverage.total_evidence_links > 0 ? 'Complete' : 'Pending',
                  source: 'Compliance Module',
                  trend: 'stable',
                },
                {
                  category: 'Audit Results',
                  status: auditSchedule.length > 0 ? 'In Progress' : 'Pending',
                  source: 'Audit Programme',
                  trend: 'stable',
                },
              ].map((input, i) => (
                <div
                  key={i}
                  className="flex items-center justify-between p-3 bg-surface rounded-lg"
                >
                  <div className="flex items-center gap-3">
                    {input.status === 'Complete' ? (
                      <CheckCircle2 className="w-5 h-5 text-success" />
                    ) : input.status === 'In Progress' ? (
                      <Clock className="w-5 h-5 text-warning" />
                    ) : (
                      <AlertTriangle className="w-5 h-5 text-muted-foreground" />
                    )}
                    <div>
                      <div className="font-medium text-foreground">{input.category}</div>
                      <div className="text-xs text-muted-foreground">{input.source}</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className={`flex items-center gap-1 text-sm ${
                      input.trend === 'improving' ? 'text-success' : 'text-muted-foreground'
                    }`}>
                      {input.trend === 'improving' ? (
                        <TrendingUp className="w-4 h-4" />
                      ) : (
                        <span className="text-lg">—</span>
                      )}
                    </div>
                    <span
                      className={`px-2 py-1 rounded text-xs font-medium ${
                        input.status === 'Complete'
                          ? 'bg-success/20 text-success'
                          : input.status === 'In Progress'
                          ? 'bg-warning/20 text-warning'
                          : 'bg-muted text-muted-foreground'
                      }`}
                    >
                      {input.status}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-card rounded-xl border border-border p-6">
            <h3 className="font-bold text-foreground mb-4">Review Readiness</h3>

            {(() => {
              const inputs = [
                standards.length > 0,
                !!isms,
                uvdb && uvdb.status !== 'not_started',
                planetMark && planetMark.status !== 'not_configured',
                complianceCoverage && complianceCoverage.total_evidence_links > 0,
                auditSchedule.length > 0,
              ]
              const completed = inputs.filter(Boolean).length
              const total = inputs.length
              const pct = Math.round((completed / total) * 100)

              return (
                <>
                  <div className="relative w-40 h-40 mx-auto mb-6">
                    <svg className="w-full h-full transform -rotate-90">
                      <circle cx="80" cy="80" r="70" stroke="currentColor" strokeWidth="10" fill="transparent" className="text-surface" />
                      <circle cx="80" cy="80" r="70" stroke="currentColor" strokeWidth="10" fill="transparent" strokeDasharray={`${(completed / total) * 440} 440`} className="text-primary" />
                    </svg>
                    <div className="absolute inset-0 flex flex-col items-center justify-center">
                      <span className="text-3xl font-bold text-foreground">{pct}%</span>
                      <span className="text-sm text-muted-foreground">Complete</span>
                    </div>
                  </div>

                  <div className="space-y-3">
                    <div className="flex justify-between text-sm">
                      <span className="text-muted-foreground">Inputs Complete</span>
                      <span className="text-foreground font-medium">{completed} / {total}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-muted-foreground">Overall Compliance</span>
                      <span className="text-foreground font-medium">{overallCompliance}%</span>
                    </div>
                  </div>
                </>
              )
            })()}

            <button
              className="w-full mt-6 px-4 py-2 bg-primary hover:bg-primary-hover text-primary-foreground rounded-lg text-sm font-medium transition-colors"
              onClick={() => setToastMessage('Feature coming soon')}
            >
              Schedule Review Meeting
            </button>
          </div>
        </div>
      )}

      {/* ISO 27001 ISMS Tab */}
      {activeTab === 'isms' && (
        <div className="space-y-6">
          {!isms ? (
            <div className="bg-card rounded-xl border border-border p-8 text-center">
              <Lock className="w-10 h-10 text-muted-foreground mx-auto mb-3" />
              <p className="text-foreground font-medium">ISO 27001 ISMS Not Configured</p>
              <p className="text-muted-foreground text-sm mt-1">
                {dashboardData?.isms_error || 'The ISMS module needs to be set up to display data here.'}
              </p>
            </div>
          ) : (
            <>
              {/* ISMS Compliance Score */}
              <div className="bg-gradient-to-r from-purple-600 to-indigo-600 rounded-xl p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-2xl font-bold text-white mb-1">ISO 27001:2022 ISMS Compliance</h2>
                    <p className="text-purple-100">Information Security Management System</p>
                  </div>
                  <div className="text-right">
                    <div className="text-5xl font-bold text-white">{isms.compliance_score}%</div>
                    <div className="flex items-center gap-1 text-purple-100 mt-1">
                      <ShieldCheck className="w-4 h-4" />
                      <span>Annex A Controls Implemented</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* ISMS Summary Cards */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
                <div className="bg-card rounded-xl p-5 border border-border">
                  <div className="flex items-center gap-3 mb-3">
                    <div className="p-2 bg-blue-500/20 rounded-lg">
                      <Server className="w-5 h-5 text-blue-400" />
                    </div>
                    <span className="text-muted-foreground text-sm">Information Assets</span>
                  </div>
                  <div className="text-3xl font-bold text-foreground">{isms.assets.total}</div>
                  <div className="text-sm text-warning mt-1">{isms.assets.critical} Critical</div>
                </div>

                <div className="bg-card rounded-xl p-5 border border-border">
                  <div className="flex items-center gap-3 mb-3">
                    <div className="p-2 bg-emerald-500/20 rounded-lg">
                      <ShieldCheck className="w-5 h-5 text-emerald-400" />
                    </div>
                    <span className="text-muted-foreground text-sm">Annex A Controls</span>
                  </div>
                  <div className="text-3xl font-bold text-foreground">{isms.controls.implemented}/{isms.controls.applicable}</div>
                  <div className="text-sm text-success mt-1">{isms.controls.implementation_percentage}% Implemented</div>
                </div>

                <div className="bg-card rounded-xl p-5 border border-border">
                  <div className="flex items-center gap-3 mb-3">
                    <div className="p-2 bg-orange-500/20 rounded-lg">
                      <AlertOctagon className="w-5 h-5 text-orange-400" />
                    </div>
                    <span className="text-muted-foreground text-sm">Security Risks</span>
                  </div>
                  <div className="text-3xl font-bold text-foreground">{isms.risks.open}</div>
                  <div className="text-sm text-destructive mt-1">{isms.risks.high_critical} High/Critical</div>
                </div>

                <div className="bg-card rounded-xl p-5 border border-border">
                  <div className="flex items-center gap-3 mb-3">
                    <div className="p-2 bg-red-500/20 rounded-lg">
                      <Bug className="w-5 h-5 text-red-400" />
                    </div>
                    <span className="text-muted-foreground text-sm">Security Incidents</span>
                  </div>
                  <div className="text-3xl font-bold text-foreground">{isms.incidents.open}</div>
                  <div className="text-sm text-muted-foreground mt-1">{isms.incidents.last_30_days} in last 30 days</div>
                </div>

                <div className="bg-card rounded-xl p-5 border border-border">
                  <div className="flex items-center gap-3 mb-3">
                    <div className="p-2 bg-purple-500/20 rounded-lg">
                      <Building2 className="w-5 h-5 text-purple-400" />
                    </div>
                    <span className="text-muted-foreground text-sm">Supplier Risk</span>
                  </div>
                  <div className="text-3xl font-bold text-foreground">{isms.suppliers.high_risk}</div>
                  <div className="text-sm text-warning mt-1">High Risk Suppliers</div>
                </div>
              </div>

              {/* Annex A Control Domains */}
              {isms.domains.length > 0 && (
                <div className="bg-card rounded-xl border border-border">
                  <div className="p-4 bg-muted border-b border-border">
                    <h3 className="font-bold text-foreground">Annex A Control Domains (ISO 27001:2022)</h3>
                    <p className="text-sm text-muted-foreground">{isms.controls.total} controls across {isms.domains.length} themes</p>
                  </div>
                  <div className="p-6 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                    {isms.domains.map((domain, i) => {
                      const domainKey = domain.domain.toLowerCase()
                      const Icon = DOMAIN_ICONS[domainKey] || Shield
                      const color = DOMAIN_COLORS[domainKey] || 'bg-gray-500'
                      return (
                        <div key={i} className="bg-surface rounded-lg p-4">
                          <div className="flex items-center gap-3 mb-3">
                            <div className={`p-2 rounded-lg ${color}`}>
                              <Icon className="w-5 h-5 text-white" />
                            </div>
                            <div>
                              <div className="font-medium text-foreground capitalize">{domain.domain}</div>
                              <div className="text-xs text-muted-foreground">{domain.total} controls</div>
                            </div>
                          </div>
                          <div className="flex justify-between text-sm mb-2">
                            <span className="text-muted-foreground">Implemented</span>
                            <span className="text-foreground font-medium">{domain.implemented}/{domain.total}</span>
                          </div>
                          <div className="w-full bg-muted rounded-full h-2">
                            <div
                              className={`h-2 rounded-full ${color}`}
                              style={{ width: `${domain.percentage}%` }}
                            ></div>
                          </div>
                          <div className="text-right text-xs text-muted-foreground mt-1">{domain.percentage}%</div>
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}

              {/* Recent Security Incidents & SoA */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="bg-card rounded-xl border border-border">
                  <div className="p-4 bg-muted border-b border-border">
                    <h3 className="font-bold text-foreground">Recent Security Incidents</h3>
                    <p className="text-sm text-muted-foreground">Last 30 days</p>
                  </div>
                  <div className="p-4 space-y-3">
                    {isms.recent_incidents.length > 0 ? (
                      isms.recent_incidents.map((incident, i) => (
                        <div key={i} className="flex items-center justify-between p-3 bg-surface rounded-lg">
                          <div className="flex items-center gap-3">
                            <Bug className={`w-5 h-5 ${
                              incident.severity === 'high' || incident.severity === 'critical' ? 'text-destructive' :
                              incident.severity === 'medium' ? 'text-warning' : 'text-info'
                            }`} />
                            <div>
                              <div className="font-medium text-foreground text-sm">{incident.title}</div>
                              <div className="text-xs text-muted-foreground">
                                {incident.id} {incident.date && `\u2022 ${new Date(incident.date).toLocaleDateString()}`}
                              </div>
                            </div>
                          </div>
                          <span className={`px-2 py-1 rounded text-xs font-medium ${
                            incident.status === 'investigating' || incident.status === 'open' ? 'bg-warning/20 text-warning' :
                            incident.status === 'contained' ? 'bg-info/20 text-info' :
                            'bg-success/20 text-success'
                          }`}>
                            {incident.status}
                          </span>
                        </div>
                      ))
                    ) : (
                      <div className="p-4 text-center text-muted-foreground text-sm">
                        No security incidents in the last 30 days
                      </div>
                    )}
                  </div>
                </div>

                {/* Statement of Applicability */}
                <div className="bg-card rounded-xl border border-border">
                  <div className="p-4 bg-muted border-b border-border flex items-center justify-between">
                    <div>
                      <h3 className="font-bold text-foreground">Statement of Applicability (SoA)</h3>
                      <p className="text-sm text-muted-foreground">Control applicability summary</p>
                    </div>
                    <Button variant="outline" size="sm" onClick={handleExportSoA}>
                      <Download className="w-4 h-4 mr-2" />
                      Export SoA
                    </Button>
                  </div>
                  <div className="p-6">
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                      <div className="text-center p-4 bg-surface rounded-lg">
                        <div className="text-3xl font-bold text-foreground">{isms.controls.total}</div>
                        <div className="text-sm text-muted-foreground">Total Controls</div>
                      </div>
                      <div className="text-center p-4 bg-success/10 rounded-lg border border-success/30">
                        <div className="text-3xl font-bold text-success">{isms.controls.applicable}</div>
                        <div className="text-sm text-muted-foreground">Applicable</div>
                      </div>
                      <div className="text-center p-4 bg-info/10 rounded-lg border border-info/30">
                        <div className="text-3xl font-bold text-info">{isms.controls.implemented}</div>
                        <div className="text-sm text-muted-foreground">Implemented</div>
                      </div>
                      <div className="text-center p-4 bg-muted rounded-lg border border-border">
                        <div className="text-3xl font-bold text-muted-foreground">{isms.controls.total - isms.controls.applicable}</div>
                        <div className="text-sm text-muted-foreground">Excluded</div>
                      </div>
                    </div>
                    <div className="text-center">
                      <p className="text-muted-foreground text-sm">
                        The Statement of Applicability documents all {isms.controls.total} Annex A controls,
                        their applicability status, implementation status, and justification for exclusions.
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}
