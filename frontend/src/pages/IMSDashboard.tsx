import React, { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  imsDashboardApi,
  crossStandardMappingsApi,
  getApiErrorMessage,
  type IMSDashboardResponse,
  type CrossStandardMappingRecord,
} from '../api/client'
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
  Database,
  Globe,
  UserCheck,
  Key,
  AlertOctagon,
} from 'lucide-react'
import { cn } from '../helpers/utils'
import {
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Badge,
  EmptyState,
  TableSkeleton,
} from '../components/ui'

type ActiveTab = 'overview' | 'mapping' | 'audit' | 'review' | 'isms'

export default function IMSDashboard() {
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState<ActiveTab>('overview')
  const [selectedStandard, setSelectedStandard] = useState<string | null>(null)

  // Live dashboard data
  const [dashData, setDashData] = useState<IMSDashboardResponse | null>(null)
  const [dashLoading, setDashLoading] = useState(true)
  const [dashError, setDashError] = useState<string | null>(null)

  // Cross-standard mapping tab
  const [mappings, setMappings] = useState<CrossStandardMappingRecord[]>([])
  const [mappingsLoading, setMappingsLoading] = useState(false)
  const [mappingsError, setMappingsError] = useState<string | null>(null)

  const fetchDashboard = useCallback(async () => {
    setDashLoading(true)
    setDashError(null)
    try {
      const res = await imsDashboardApi.getDashboard()
      setDashData(res.data)
    } catch (err) {
      setDashError(getApiErrorMessage(err))
    } finally {
      setDashLoading(false)
    }
  }, [])

  const fetchMappings = useCallback(async () => {
    setMappingsLoading(true)
    setMappingsError(null)
    try {
      const res = await crossStandardMappingsApi.list({ limit: 500 })
      setMappings(res.data)
    } catch (err) {
      setMappingsError(getApiErrorMessage(err))
      setMappings([])
    } finally {
      setMappingsLoading(false)
    }
  }, [])

  useEffect(() => {
    void fetchDashboard()
  }, [fetchDashboard])

  useEffect(() => {
    if (activeTab === 'mapping' && mappings.length === 0 && !mappingsLoading) {
      void fetchMappings()
    }
  }, [activeTab, fetchMappings, mappings.length, mappingsLoading])

  // Derive live standard cards from API data; fall back to static metadata when API is loading
  const standardMeta: Record<string, { icon: React.ElementType; color: string; colorBg: string; label: string; version: string }> = {
    iso9001: { icon: Shield, color: 'text-blue-400', colorBg: 'bg-blue-500', label: 'ISO 9001:2015', version: 'Quality Management' },
    iso14001: { icon: Leaf, color: 'text-emerald-400', colorBg: 'bg-emerald-500', label: 'ISO 14001:2015', version: 'Environmental Management' },
    iso45001: { icon: HardHat, color: 'text-orange-400', colorBg: 'bg-orange-500', label: 'ISO 45001:2018', version: 'OH&S Management' },
    iso27001: { icon: Lock, color: 'text-purple-400', colorBg: 'bg-purple-500', label: 'ISO 27001:2022', version: 'Information Security' },
  }

  const liveStandards = dashData?.standards ?? []
  const overallCompliance = dashData?.overall_compliance ?? 0
  const ismsData = dashData?.isms ?? null

  // ISMS domain metadata
  const domainMeta: Record<string, { label: string; icon: React.ElementType; colorBg: string }> = {
    organizational: { label: 'Organizational', icon: Building2, colorBg: 'bg-blue-500' },
    people: { label: 'People', icon: UserCheck, colorBg: 'bg-green-500' },
    physical: { label: 'Physical', icon: Key, colorBg: 'bg-orange-500' },
    technological: { label: 'Technological', icon: Laptop, colorBg: 'bg-purple-500' },
  }

  // Management review inputs (static — no API exists for this data yet)
  const managementReviewInputs = [
    { category: 'Audit Results', status: 'Complete', source: 'All Standards', trend: 'improving' },
    { category: 'Customer Feedback', status: 'Complete', source: 'ISO 9001', trend: 'stable' },
    { category: 'Process Performance', status: 'In Progress', source: 'All Standards', trend: 'improving' },
    { category: 'Environmental Performance', status: 'Complete', source: 'ISO 14001', trend: 'improving' },
    { category: 'OH&S Performance', status: 'Complete', source: 'ISO 45001', trend: 'stable' },
    { category: 'Information Security', status: 'Complete', source: 'ISO 27001', trend: 'improving' },
    { category: 'Carbon Footprint', status: 'Complete', source: 'Planet Mark', trend: 'improving' },
    { category: 'UVDB Qualification', status: 'Complete', source: 'UVDB Achilles', trend: 'stable' },
    { category: 'Objectives Achievement', status: 'Pending', source: 'All Standards', trend: 'stable' },
    { category: 'Risks & Opportunities', status: 'In Progress', source: 'All Standards', trend: 'stable' },
    { category: 'Resource Adequacy', status: 'Pending', source: 'All Standards', trend: 'stable' },
  ]

  const reviewComplete = managementReviewInputs.filter((i) => i.status === 'Complete').length
  const reviewReadiness = Math.round((reviewComplete / managementReviewInputs.length) * 100)

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground flex items-center gap-2">
            <GitMerge className="w-6 h-6 text-primary" aria-hidden="true" />
            Integrated Management System
          </h1>
          <p className="text-muted-foreground">Unified ISO 9001, 14001, 45001 &amp; 27001 Dashboard</p>
        </div>
        <div className="flex gap-3">
          <Button
            variant="outline"
            onClick={() => void fetchDashboard()}
            disabled={dashLoading}
          >
            <RefreshCw className={cn('w-4 h-4 mr-2', dashLoading && 'animate-spin')} aria-hidden="true" />
            Sync
          </Button>
          <Button>
            <FileText className="w-4 h-4 mr-2" aria-hidden="true" />
            Generate Report
          </Button>
        </div>
      </div>

      {/* Dashboard error */}
      {dashError && !dashLoading && (
        <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 flex-shrink-0" aria-hidden="true" />
          {dashError} —{' '}
          <Button variant="link" size="sm" className="p-0 h-auto" onClick={() => void fetchDashboard()}>
            Retry
          </Button>
        </div>
      )}

      {/* Overall Compliance Banner */}
      <div className="bg-gradient-to-r from-primary to-primary-hover rounded-xl p-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold text-primary-foreground mb-1">
              Overall IMS Compliance
            </h2>
            <p className="text-primary-foreground/80">Across all management system standards</p>
          </div>
          <div className="text-right">
            {dashLoading ? (
              <div className="text-5xl font-bold text-primary-foreground/50 animate-pulse">—%</div>
            ) : (
              <div className="text-5xl font-bold text-primary-foreground" aria-label={`${overallCompliance}% overall IMS compliance`}>
                {Math.round(overallCompliance)}%
              </div>
            )}
            <div className="flex items-center gap-1 text-primary-foreground/80 mt-1">
              <TrendingUp className="w-4 h-4" aria-hidden="true" />
              <span>Live from management system controls</span>
            </div>
          </div>
        </div>
      </div>

      {/* Standard Cards */}
      {dashLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {[1, 2, 3, 4].map((i) => (
            <Card key={i}><CardContent className="p-6"><TableSkeleton rows={4} columns={1} /></CardContent></Card>
          ))}
        </div>
      ) : liveStandards.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {liveStandards.map((standard) => {
            const key = standard.standard_code?.toLowerCase().replace(/[^a-z0-9]/g, '') ?? ''
            const meta = standardMeta[key] ?? {
              icon: Shield,
              color: 'text-primary',
              colorBg: 'bg-primary',
              label: standard.standard_name ?? standard.standard_code,
              version: standard.full_name ?? '',
            }
            const Icon = meta.icon
            const compliance = Math.round(standard.compliance_percentage)

            return (
              <Card
                key={standard.standard_id}
                role="button"
                tabIndex={0}
                className={cn(
                  'cursor-pointer transition-colors hover:border-border-strong',
                  selectedStandard === standard.standard_code && 'ring-2 ring-primary',
                )}
                onClick={() => setSelectedStandard(standard.standard_code)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') setSelectedStandard(standard.standard_code)
                }}
                aria-pressed={selectedStandard === standard.standard_code}
              >
                <CardContent className="p-6">
                  <div className="flex items-start justify-between mb-4">
                    <div className={cn('p-3 rounded-xl', meta.colorBg)}>
                      <Icon className="w-6 h-6 text-white" aria-hidden="true" />
                    </div>
                    <div className="text-right">
                      {standard.setup_required ? (
                        <Badge variant="outline" className="text-muted-foreground">Setup required</Badge>
                      ) : (
                        <>
                          <div className="text-3xl font-bold text-foreground" aria-label={`${compliance}% compliance`}>{compliance}%</div>
                          <div className="text-xs text-muted-foreground">Compliance</div>
                        </>
                      )}
                    </div>
                  </div>

                  <h3 className="text-base font-bold text-foreground mb-1">{meta.label}</h3>
                  <p className="text-sm text-muted-foreground mb-4">{meta.version}</p>

                  <div
                    className="w-full bg-surface rounded-full h-2 mb-4"
                    role="progressbar"
                    aria-valuenow={compliance}
                    aria-valuemin={0}
                    aria-valuemax={100}
                  >
                    <div
                      className={cn('h-2 rounded-full', meta.colorBg)}
                      style={{ width: `${compliance}%` }}
                    />
                  </div>

                  <div className="flex justify-between text-xs text-muted-foreground">
                    <span>{standard.implemented_count} implemented</span>
                    <span>{standard.partial_count} partial</span>
                    <span>{standard.not_implemented_count} gap</span>
                  </div>
                </CardContent>
              </Card>
            )
          })}
        </div>
      ) : !dashError ? (
        <EmptyState
          icon={<Shield className="w-8 h-8 text-muted-foreground" />}
          title="No standards configured"
          description="Standards and controls need to be set up before compliance data appears here."
        />
      ) : null}

      {/* Tab Bar */}
      <div className="flex gap-2 border-b border-border pb-2 overflow-x-auto" role="tablist" aria-label="IMS sections">
        {([
          { id: 'overview', label: 'Overview', icon: BarChart3 },
          { id: 'mapping', label: 'Cross-Standard Mapping', icon: Link2 },
          { id: 'audit', label: 'Unified Audit Plan', icon: ClipboardList },
          { id: 'review', label: 'Management Review', icon: Users },
          { id: 'isms', label: 'ISO 27001 ISMS', icon: Lock },
        ] as { id: ActiveTab; label: string; icon: React.ElementType }[]).map((tab) => {
          const Icon = tab.icon
          return (
            <Button
              key={tab.id}
              variant={activeTab === tab.id ? 'default' : 'ghost'}
              size="sm"
              onClick={() => setActiveTab(tab.id)}
              role="tab"
              aria-selected={activeTab === tab.id}
              className="flex-shrink-0"
            >
              <Icon className="w-4 h-4 mr-2" aria-hidden="true" />
              {tab.label}
            </Button>
          )
        })}
      </div>

      {/* ── Overview Tab ── */}
      {activeTab === 'overview' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card>
            <CardHeader>
              <CardTitle>Key Performance Metrics</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {[
                  { label: 'Open Actions', value: 12, target: 0, unit: '', status: 'warning' },
                  { label: 'Overdue Actions', value: 2, target: 0, unit: '', status: 'critical' },
                  { label: 'Document Review Compliance', value: 94, target: 100, unit: '%', status: 'good' },
                  { label: 'Training Completion', value: 98, target: 100, unit: '%', status: 'good' },
                  { label: 'Audit Completion', value: 75, target: 100, unit: '%', status: 'warning' },
                ].map((metric, i) => (
                  <div key={i} className="flex items-center justify-between">
                    <span className="text-foreground text-sm">{metric.label}</span>
                    <div className="flex items-center gap-2">
                      <span
                        className={cn(
                          'font-bold',
                          metric.status === 'good'
                            ? 'text-success'
                            : metric.status === 'warning'
                              ? 'text-warning'
                              : 'text-destructive',
                        )}
                      >
                        {metric.value}{metric.unit}
                      </span>
                      <span className="text-muted-foreground text-sm">/ {metric.target}{metric.unit}</span>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Recent Activity</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {[
                  { action: 'Audit Finding Closed', detail: 'Minor NC #2024-015', time: '2 hours ago', icon: CheckCircle2, color: 'text-success' },
                  { action: 'Document Updated', detail: 'Environmental Aspects Register', time: '4 hours ago', icon: FileText, color: 'text-info' },
                  { action: 'Risk Assessment Completed', detail: 'New Contractor Activity', time: '1 day ago', icon: Shield, color: 'text-purple-500' },
                  { action: 'Training Completed', detail: 'ISO 45001 Awareness - 15 staff', time: '2 days ago', icon: Users, color: 'text-warning' },
                  { action: 'Objective Updated', detail: 'Q4 Recycling Target Achieved', time: '3 days ago', icon: Target, color: 'text-success' },
                ].map((activity, i) => {
                  const Icon = activity.icon
                  return (
                    <div key={i} className="flex items-start gap-3 p-2 hover:bg-surface rounded-lg transition-colors">
                      <Icon className={cn('w-5 h-5 mt-0.5 flex-shrink-0', activity.color)} aria-hidden="true" />
                      <div className="flex-grow min-w-0">
                        <div className="text-foreground text-sm">{activity.action}</div>
                        <div className="text-muted-foreground text-xs">{activity.detail}</div>
                      </div>
                      <span className="text-muted-foreground text-xs flex-shrink-0">{activity.time}</span>
                    </div>
                  )
                })}
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* ── Cross-Standard Mapping Tab ── */}
      {activeTab === 'mapping' && (
        <Card>
          <CardHeader>
            <CardTitle>Cross-Standard Clause Mappings</CardTitle>
            <p className="text-sm text-muted-foreground">Live from cross-standard mappings database</p>
          </CardHeader>
          <CardContent className="p-0">
            {mappingsLoading ? (
              <div className="p-6">
                <TableSkeleton rows={6} columns={5} />
              </div>
            ) : mappingsError ? (
              <div className="p-6">
                <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
                  {mappingsError}
                </div>
              </div>
            ) : mappings.length === 0 ? (
              <div className="p-6">
                <EmptyState
                  icon={<Link2 className="w-8 h-8 text-muted-foreground" />}
                  title="No cross-standard mappings"
                  description="Create clause mappings between standards in the ISO Compliance module."
                  action={
                    <Button variant="outline" onClick={() => navigate('/compliance')}>
                      Open ISO Compliance <ChevronRight className="w-4 h-4 ml-1" aria-hidden="true" />
                    </Button>
                  }
                />
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-border">
                      <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                        Primary Standard
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                        Clause
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                        Mapped To
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                        Mapped Clause
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                        Type / Strength
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                        Annex SL
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {mappings.map((mapping) => (
                      <tr key={mapping.id} className="hover:bg-surface transition-colors">
                        <td className="px-4 py-3 text-sm font-medium text-foreground">{mapping.primary_standard}</td>
                        <td className="px-4 py-3 text-sm text-foreground">{mapping.primary_clause}</td>
                        <td className="px-4 py-3 text-sm text-foreground">{mapping.mapped_standard}</td>
                        <td className="px-4 py-3 text-sm text-foreground">{mapping.mapped_clause}</td>
                        <td className="px-4 py-3 text-sm text-muted-foreground">
                          {mapping.mapping_type} · {mapping.mapping_strength}
                        </td>
                        <td className="px-4 py-3">
                          {mapping.annex_sl_element ? (
                            <Badge variant="secondary">{mapping.annex_sl_element}</Badge>
                          ) : (
                            <span className="text-xs text-muted-foreground">—</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* ── Unified Audit Plan Tab ── */}
      {activeTab === 'audit' && (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle>Unified Audit Schedule</CardTitle>
              <p className="text-sm text-muted-foreground">Integrated audit program covering all standards</p>
            </div>
            <Button onClick={() => navigate('/audits/new')}>
              <Calendar className="w-4 h-4 mr-2" aria-hidden="true" />
              Plan New Audit
            </Button>
          </CardHeader>
          <CardContent className={dashData?.audit_schedule?.length ? 'p-0' : undefined}>
            {dashLoading ? (
              <div className="p-6"><TableSkeleton rows={4} columns={4} /></div>
            ) : (dashData?.audit_schedule ?? []).length === 0 ? (
              <EmptyState
                icon={<Calendar className="w-8 h-8 text-muted-foreground" />}
                title="No audit schedule configured"
                description="Create audits in the Audits module and they will appear here when scheduled."
                action={
                  <Button variant="outline" onClick={() => navigate('/audits')}>
                    <ClipboardList className="w-4 h-4 mr-2" aria-hidden="true" />
                    View Audits
                  </Button>
                }
              />
            ) : (
              <table className="w-full">
                <thead>
                  <tr className="border-b border-border">
                    <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase">Reference</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase">Title</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase">Scheduled</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase">Status</th>
                    <th className="px-4 py-3" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {(dashData?.audit_schedule ?? []).map((audit) => (
                    <tr key={audit.id} className="hover:bg-surface transition-colors">
                      <td className="px-4 py-3 text-sm font-medium text-foreground">{audit.reference_number}</td>
                      <td className="px-4 py-3 text-sm text-foreground">{audit.title ?? '—'}</td>
                      <td className="px-4 py-3 text-sm text-muted-foreground">
                        {audit.scheduled_date ? new Date(audit.scheduled_date).toLocaleDateString() : '—'}
                      </td>
                      <td className="px-4 py-3">
                        <Badge variant={audit.status === 'completed' ? 'default' : audit.status === 'in_progress' ? 'secondary' : 'outline'}>
                          {audit.status}
                        </Badge>
                      </td>
                      <td className="px-4 py-3">
                        <Button variant="ghost" size="sm" onClick={() => navigate(`/audits/${audit.id}`)}>
                          <ChevronRight className="w-4 h-4" aria-hidden="true" />
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </CardContent>
        </Card>
      )}

      {/* ── Management Review Tab ── */}
      {activeTab === 'review' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle>Management Review Inputs</CardTitle>
              <p className="text-sm text-muted-foreground">Next Review: March 2026</p>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {managementReviewInputs.map((input, i) => (
                  <div
                    key={i}
                    className="flex items-center justify-between p-3 bg-surface rounded-lg border border-border"
                  >
                    <div className="flex items-center gap-3">
                      {input.status === 'Complete' ? (
                        <CheckCircle2 className="w-5 h-5 text-success" aria-hidden="true" />
                      ) : input.status === 'In Progress' ? (
                        <Clock className="w-5 h-5 text-warning" aria-hidden="true" />
                      ) : (
                        <AlertTriangle className="w-5 h-5 text-muted-foreground" aria-hidden="true" />
                      )}
                      <div>
                        <div className="font-medium text-foreground text-sm">{input.category}</div>
                        <div className="text-xs text-muted-foreground">{input.source}</div>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <div className={cn('flex items-center gap-1 text-sm', input.trend === 'improving' ? 'text-success' : 'text-muted-foreground')}>
                        {input.trend === 'improving' ? (
                          <TrendingUp className="w-4 h-4" aria-label="Improving trend" />
                        ) : (
                          <span aria-label="Stable trend">—</span>
                        )}
                      </div>
                      <Badge
                        variant={
                          input.status === 'Complete'
                            ? 'default'
                            : input.status === 'In Progress'
                              ? 'secondary'
                              : 'outline'
                        }
                      >
                        {input.status}
                      </Badge>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Review Readiness</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="relative w-40 h-40 mx-auto mb-6" aria-label={`${reviewReadiness}% review readiness`}>
                <svg className="w-full h-full transform -rotate-90" aria-hidden="true">
                  <circle cx="80" cy="80" r="70" stroke="currentColor" strokeWidth="10" fill="transparent" className="text-border" />
                  <circle
                    cx="80"
                    cy="80"
                    r="70"
                    stroke="currentColor"
                    strokeWidth="10"
                    fill="transparent"
                    strokeDasharray={`${(reviewComplete / managementReviewInputs.length) * 440} 440`}
                    className="text-success"
                  />
                </svg>
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                  <span className="text-3xl font-bold text-foreground">{reviewReadiness}%</span>
                  <span className="text-sm text-muted-foreground">Complete</span>
                </div>
              </div>

              <div className="space-y-3">
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Inputs Complete</span>
                  <span className="text-foreground font-medium">{reviewComplete} / {managementReviewInputs.length}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Days to Review</span>
                  <span className="text-foreground font-medium">54</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Attendees Confirmed</span>
                  <span className="text-foreground font-medium">6 / 8</span>
                </div>
              </div>

              <Button className="w-full mt-6" variant="outline">
                Schedule Review Meeting
              </Button>
            </CardContent>
          </Card>
        </div>
      )}

      {/* ── ISO 27001 ISMS Tab ── */}
      {activeTab === 'isms' && (
        <div className="space-y-6">
          {dashLoading ? (
            <Card>
              <CardContent className="p-6">
                <TableSkeleton rows={8} columns={1} />
              </CardContent>
            </Card>
          ) : dashError ? (
            <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-6 text-destructive flex flex-col items-center gap-3">
              <AlertTriangle className="w-8 h-8" aria-hidden="true" />
              <p className="font-medium">{dashError}</p>
              <Button onClick={() => void fetchDashboard()}>Retry</Button>
            </div>
          ) : ismsData ? (
            <>
              {/* ISMS Compliance Score Banner */}
              <div className="bg-gradient-to-r from-purple-600 to-indigo-600 rounded-xl p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-2xl font-bold text-white mb-1">ISO 27001:2022 ISMS Compliance</h2>
                    <p className="text-purple-100">Information Security Management System</p>
                  </div>
                  <div className="text-right">
                    <div className="text-5xl font-bold text-white" aria-label={`${ismsData.compliance_score}% ISMS compliance`}>
                      {ismsData.compliance_score}%
                    </div>
                    <div className="flex items-center gap-1 text-purple-100 mt-1">
                      <ShieldCheck className="w-4 h-4" aria-hidden="true" />
                      <span>Annex A Controls Implemented</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* ISMS Summary Cards */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
                {[
                  { label: 'Information Assets', icon: Server, colorBg: 'bg-info/20', colorText: 'text-info', value: ismsData.assets.total, sub: `${ismsData.assets.critical} Critical`, subColor: 'text-warning' },
                  { label: 'Annex A Controls', icon: ShieldCheck, colorBg: 'bg-success/20', colorText: 'text-success', value: `${ismsData.controls.implemented}/${ismsData.controls.applicable}`, sub: `${ismsData.controls.implementation_percentage}% Implemented`, subColor: 'text-success' },
                  { label: 'Security Risks', icon: AlertOctagon, colorBg: 'bg-warning/20', colorText: 'text-warning', value: ismsData.risks.open, sub: `${ismsData.risks.high_critical} High/Critical`, subColor: 'text-destructive' },
                  { label: 'Security Incidents', icon: Bug, colorBg: 'bg-destructive/20', colorText: 'text-destructive', value: ismsData.incidents.open, sub: `${ismsData.incidents.last_30_days} in last 30 days`, subColor: 'text-muted-foreground' },
                  { label: 'Supplier Risk', icon: Building2, colorBg: 'bg-purple-500/20', colorText: 'text-purple-400', value: ismsData.suppliers.high_risk, sub: 'High Risk Suppliers', subColor: 'text-warning' },
                ].map((card, i) => {
                  const Icon = card.icon
                  return (
                    <Card key={i}>
                      <CardContent className="p-5">
                        <div className="flex items-center gap-3 mb-3">
                          <div className={cn('p-2 rounded-lg', card.colorBg)}>
                            <Icon className={cn('w-5 h-5', card.colorText)} aria-hidden="true" />
                          </div>
                          <span className="text-muted-foreground text-sm">{card.label}</span>
                        </div>
                        <div className="text-3xl font-bold text-foreground">{card.value}</div>
                        <div className={cn('text-sm mt-1', card.subColor)}>{card.sub}</div>
                      </CardContent>
                    </Card>
                  )
                })}
              </div>

              {/* Annex A Control Domains */}
              <Card>
                <CardHeader>
                  <CardTitle>Annex A Control Domains (ISO 27001:2022)</CardTitle>
                  <p className="text-sm text-muted-foreground">93 controls across 4 themes</p>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                    {(ismsData.domains.length > 0
                      ? ismsData.domains
                      : [
                          { domain: 'organizational', total: 37, implemented: 0, percentage: 0 },
                          { domain: 'people', total: 8, implemented: 0, percentage: 0 },
                          { domain: 'physical', total: 14, implemented: 0, percentage: 0 },
                          { domain: 'technological', total: 34, implemented: 0, percentage: 0 },
                        ]
                    ).map((d, i) => {
                      const meta = domainMeta[d.domain] ?? { label: d.domain, icon: Building2, colorBg: 'bg-muted' }
                      const Icon = meta.icon
                      return (
                        <div key={i} className="bg-surface rounded-lg p-4 border border-border">
                          <div className="flex items-center gap-3 mb-3">
                            <div className={cn('p-2 rounded-lg', meta.colorBg)}>
                              <Icon className="w-5 h-5 text-white" aria-hidden="true" />
                            </div>
                            <div>
                              <div className="font-medium text-foreground text-sm">{meta.label}</div>
                              <div className="text-xs text-muted-foreground">{d.total} controls</div>
                            </div>
                          </div>
                          <div className="flex justify-between text-sm mb-2">
                            <span className="text-muted-foreground">Implemented</span>
                            <span className="text-foreground font-medium">{d.implemented}/{d.total}</span>
                          </div>
                          <div className="w-full bg-muted rounded-full h-2" role="progressbar" aria-valuenow={d.percentage} aria-valuemin={0} aria-valuemax={100}>
                            <div
                              className={cn('h-2 rounded-full', meta.colorBg)}
                              style={{ width: `${d.percentage}%` }}
                            />
                          </div>
                          <div className="text-right text-xs text-muted-foreground mt-1">{d.percentage}%</div>
                        </div>
                      )
                    })}
                  </div>
                </CardContent>
              </Card>

              {/* Asset Categories + Recent Incidents */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <Card>
                  <CardHeader>
                    <CardTitle>Information Asset Categories</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-3">
                      {[
                        { key: 'hardware', label: 'Hardware', icon: Server },
                        { key: 'software', label: 'Software', icon: Laptop },
                        { key: 'data', label: 'Data', icon: Database },
                        { key: 'service', label: 'Services', icon: Globe },
                        { key: 'people', label: 'People', icon: Users },
                        { key: 'physical', label: 'Physical', icon: Key },
                      ].map((cat) => {
                        const Icon = cat.icon
                        // Asset counts come from a separate API call (iso27001Api.getAssets)
                        // The dashboard endpoint does not include per-category counts.
                        // Navigate to /ims for detail or use iso27001Api directly.
                        return (
                          <div
                            key={cat.key}
                            className="flex items-center justify-between p-3 bg-surface rounded-lg border border-border hover:border-border-strong transition-colors cursor-pointer"
                            role="button"
                            tabIndex={0}
                            onClick={() => navigate('/ims')}
                            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') navigate('/ims') }}
                          >
                            <div className="flex items-center gap-3">
                              <div className="p-2 bg-muted rounded-lg">
                                <Icon className="w-4 h-4 text-muted-foreground" aria-hidden="true" />
                              </div>
                              <span className="text-foreground font-medium text-sm">{cat.label}</span>
                            </div>
                            <ChevronRight className="w-4 h-4 text-muted-foreground" aria-hidden="true" />
                          </div>
                        )
                      })}
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="flex flex-row items-center justify-between">
                    <div>
                      <CardTitle>Recent Security Incidents</CardTitle>
                      <p className="text-sm text-muted-foreground">Last 30 days</p>
                    </div>
                    <Button
                      size="sm"
                      variant="destructive"
                      onClick={() => navigate('/incidents/new?source=isms')}
                    >
                      Report Incident
                    </Button>
                  </CardHeader>
                  <CardContent>
                    {ismsData.recent_incidents.length === 0 ? (
                      <EmptyState
                        icon={<ShieldCheck className="w-8 h-8 text-success" />}
                        title="No incidents recorded"
                        description="No security incidents in the last 30 days."
                      />
                    ) : (
                      <div className="space-y-3">
                        {ismsData.recent_incidents.map((incident, i) => (
                          <div
                            key={i}
                            className="flex items-center justify-between p-3 bg-surface rounded-lg border border-border"
                          >
                            <div className="flex items-center gap-3 min-w-0">
                              <Bug
                                className={cn(
                                  'w-5 h-5 flex-shrink-0',
                                  incident.severity === 'critical'
                                    ? 'text-destructive'
                                    : incident.severity === 'high'
                                      ? 'text-destructive/80'
                                      : incident.severity === 'medium'
                                        ? 'text-warning'
                                        : 'text-info',
                                )}
                                aria-hidden="true"
                              />
                              <div className="min-w-0">
                                <div className="font-medium text-foreground text-sm truncate">{incident.title}</div>
                                <div className="text-xs text-muted-foreground">
                                  {incident.id} • {incident.date}
                                </div>
                              </div>
                            </div>
                            <Badge
                              variant={
                                incident.status === 'investigating'
                                  ? 'secondary'
                                  : incident.status === 'contained'
                                    ? 'outline'
                                    : 'default'
                              }
                              className="flex-shrink-0"
                            >
                              {incident.status}
                            </Badge>
                          </div>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>
              </div>

              {/* Statement of Applicability */}
              <Card>
                <CardHeader className="flex flex-row items-center justify-between">
                  <div>
                    <CardTitle>Statement of Applicability (SoA)</CardTitle>
                    <p className="text-sm text-muted-foreground">
                      Controls data from the ISO 27001 ISMS module
                    </p>
                  </div>
                  <Button
                    variant="outline"
                    onClick={() => window.open('/api/v1/iso27001/soa?format=pdf', '_blank')}
                  >
                    <FileText className="w-4 h-4 mr-2" aria-hidden="true" />
                    Export SoA
                  </Button>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                    {[
                      { label: 'Total Controls', value: ismsData.controls.total, variant: 'default' as const },
                      { label: 'Applicable', value: ismsData.controls.applicable, variant: 'success' as const },
                      { label: 'Implemented', value: ismsData.controls.implemented, variant: 'info' as const },
                      { label: 'Excluded', value: ismsData.controls.total - ismsData.controls.applicable, variant: 'muted' as const },
                    ].map((stat, i) => (
                      <div key={i} className={cn(
                        'text-center p-4 rounded-lg border',
                        stat.variant === 'success' ? 'bg-success/10 border-success/30' :
                        stat.variant === 'info' ? 'bg-info/10 border-info/30' :
                        stat.variant === 'muted' ? 'bg-muted border-border' :
                        'bg-surface border-border',
                      )}>
                        <div className={cn(
                          'text-3xl font-bold',
                          stat.variant === 'success' ? 'text-success' :
                          stat.variant === 'info' ? 'text-info' :
                          'text-foreground',
                        )}>{stat.value}</div>
                        <div className="text-sm text-muted-foreground">{stat.label}</div>
                      </div>
                    ))}
                  </div>
                  <p className="text-muted-foreground text-sm text-center">
                    The Statement of Applicability documents all 93 Annex A controls from ISO 27001:2022,
                    their applicability status, implementation status, and justification for exclusions.
                  </p>
                </CardContent>
              </Card>
            </>
          ) : (
            <EmptyState
              icon={<Lock className="w-8 h-8 text-muted-foreground" />}
              title="ISMS data not available"
              description="ISO 27001 ISMS controls need to be set up before dashboard data appears here."
              action={
                <Button variant="outline" onClick={() => void fetchDashboard()}>
                  <RefreshCw className="w-4 h-4 mr-2" />
                  Retry
                </Button>
              }
            />
          )}
        </div>
      )}
    </div>
  )
}
