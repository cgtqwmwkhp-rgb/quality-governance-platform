import React, { useState, useEffect, useCallback, useMemo } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import {
  imsDashboardApi,
  crossStandardMappingsApi,
  getApiErrorMessage,
  type IMSDashboardResponse,
  type CrossStandardMappingRecord,
} from '../api/client'
import {
  Shield,
  CheckCircle2,
  AlertTriangle,
  Clock,
  TrendingUp,
  Calendar,
  Users,
  BarChart3,
  Link2,
  ChevronRight,
  RefreshCw,
  GitMerge,
  FileText,
  BookOpen,
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
  MAP_W1_SCHEME_CHIPS,
  detectSchemesInMappings,
  isDemoSchemeReviewSource,
} from './imsMapHonesty'
import {
  IMS_DEFAULT_SECTION,
  IMS_SECTIONS,
  imsSectionQueryValue,
  parseImsSection,
  type ImsSectionId,
} from './imsDashboardHelpers'
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

type ComplianceHubDestination = {
  id: string
  title?: string
  description?: string
  titleKey?: string
  descriptionKey?: string
  icon: React.ElementType
  colorBg: string
  path?: string
  tab?: ImsSectionId
}

const complianceHubDestinations: ComplianceHubDestination[] = [
  {
    id: 'standards',
    title: 'Standards & Controls',
    description: 'Drill into control implementation by standard — canonical scores live here.',
    icon: BookOpen,
    colorBg: 'bg-blue-500',
    path: '/standards',
  },
  {
    id: 'knowledge-exceptions',
    title: 'Operational signals',
    description: 'Inbound case→clause exceptions from Standards assessor — filter by clause from the library.',
    icon: AlertTriangle,
    colorBg: 'bg-amber-500',
    path: '/knowledge-exceptions?operational=1',
  },
  {
    id: 'evidence',
    title: 'Evidence & Coverage',
    description: 'Link evidence, view coverage gaps, and export compliance reports.',
    icon: Shield,
    colorBg: 'bg-emerald-500',
    path: '/compliance',
  },
  {
    id: 'monitoring',
    titleKey: 'ims.hub.monitoring.title',
    descriptionKey: 'ims.hub.monitoring.description',
    icon: ShieldCheck,
    colorBg: 'bg-orange-500',
    path: '/compliance-automation',
  },
  {
    id: 'isms',
    title: 'ISO 27001 ISMS',
    description: 'Annex A controls, information assets, and security incident posture.',
    icon: Lock,
    colorBg: 'bg-purple-500',
    tab: 'isms',
  },
]

export default function IMSDashboard() {
  const navigate = useNavigate()
  const { t } = useTranslation()
  const [searchParams, setSearchParams] = useSearchParams()
  const section = parseImsSection(searchParams.get('section'))

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

  const setQuery = useCallback(
    (patch: Record<string, string | null>) => {
      const next = new URLSearchParams(searchParams)
      Object.entries(patch).forEach(([key, value]) => {
        if (
          value == null ||
          value === '' ||
          (key === 'section' && value === IMS_DEFAULT_SECTION)
        ) {
          if (key === 'section' && value === IMS_DEFAULT_SECTION) next.delete(key)
          else if (value == null || value === '') next.delete(key)
          else next.set(key, value)
        } else {
          next.set(key, value)
        }
      })
      setSearchParams(next, { replace: true })
    },
    [searchParams, setSearchParams],
  )

  const setSection = useCallback(
    (nextSection: ImsSectionId) => {
      setQuery({ section: imsSectionQueryValue(nextSection) })
    },
    [setQuery],
  )

  useEffect(() => {
    void fetchDashboard()
  }, [fetchDashboard])

  useEffect(() => {
    if (section === 'mapping' && mappings.length === 0 && !mappingsLoading) {
      void fetchMappings()
    }
  }, [section, fetchMappings, mappings.length, mappingsLoading])

  // ISMS domain metadata
  const liveStandards = dashData?.standards ?? []
  const overallCompliance = dashData?.overall_compliance ?? 0
  const evidenceCoveragePct = dashData?.compliance_coverage?.coverage_percentage
  const showDualMetrics = evidenceCoveragePct != null && !dashData?.compliance_coverage_error
  const ismsData = dashData?.isms ?? null
  const trackedStandardCount = liveStandards.filter((standard) => !standard.setup_required).length

  const openComplianceHubDestination = (destination: ComplianceHubDestination) => {
    if (destination.path) {
      navigate(destination.path)
      return
    }
    if (destination.tab) {
      setSection(destination.tab)
    }
  }

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
    { category: 'Carbon Footprint', status: 'Pending', source: 'Planet Mark', trend: 'stable' },
    { category: 'UVDB Qualification', status: 'Pending', source: 'UVDB Achilles', trend: 'stable' },
    { category: 'Objectives Achievement', status: 'Pending', source: 'All Standards', trend: 'stable' },
    { category: 'Risks & Opportunities', status: 'In Progress', source: 'All Standards', trend: 'stable' },
    { category: 'Resource Adequacy', status: 'Pending', source: 'All Standards', trend: 'stable' },
  ]

  const detectedSchemes = useMemo(() => detectSchemesInMappings(mappings), [mappings])

  const reviewComplete = managementReviewInputs.filter((i) => i.status === 'Complete').length
  const reviewReadiness = Math.round((reviewComplete / managementReviewInputs.length) * 100)

  const auditSchedule = useMemo(
    () => dashData?.audit_schedule ?? [],
    [dashData?.audit_schedule],
  )
  const openScheduledAudits = auditSchedule.filter((a) => a.status !== 'completed').length
  const inProgressAudits = auditSchedule.filter((a) => a.status === 'in_progress').length

  const overviewKpis = useMemo(() => {
    const controlStatus =
      overallCompliance >= 80 ? 'good' : overallCompliance >= 50 ? 'warning' : 'critical'
    const metrics: {
      label: string
      value: number
      target?: number
      unit: string
      status: 'good' | 'warning' | 'critical'
    }[] = [
      {
        label: 'Standards tracked',
        value: trackedStandardCount,
        unit: '',
        status: trackedStandardCount > 0 ? 'good' : 'warning',
      },
      {
        label: 'Open scheduled audits',
        value: openScheduledAudits,
        unit: '',
        status: openScheduledAudits > 0 ? 'warning' : 'good',
      },
      {
        label: 'In-progress audits',
        value: inProgressAudits,
        unit: '',
        status: inProgressAudits > 0 ? 'warning' : 'good',
      },
      {
        label: 'Control implementation',
        value: Math.round(overallCompliance),
        target: 100,
        unit: '%',
        status: controlStatus,
      },
    ]
    if (evidenceCoveragePct != null && !dashData?.compliance_coverage_error) {
      metrics.push({
        label: 'Evidence coverage',
        value: Math.round(evidenceCoveragePct),
        target: 100,
        unit: '%',
        status: evidenceCoveragePct >= 80 ? 'good' : evidenceCoveragePct >= 50 ? 'warning' : 'critical',
      })
    }
    return metrics
  }, [
    dashData?.compliance_coverage_error,
    evidenceCoveragePct,
    inProgressAudits,
    openScheduledAudits,
    overallCompliance,
    trackedStandardCount,
  ])

  const overviewActivity = useMemo(() => {
    return [...auditSchedule]
      .sort((a, b) => {
        const aTime = a.scheduled_date ? new Date(a.scheduled_date).getTime() : 0
        const bTime = b.scheduled_date ? new Date(b.scheduled_date).getTime() : 0
        return bTime - aTime
      })
      .slice(0, 5)
      .map((audit) => ({
        id: audit.id,
        action:
          audit.status === 'in_progress'
            ? 'Audit in progress'
            : audit.status === 'completed'
              ? 'Audit completed'
              : 'Audit scheduled',
        detail: `${audit.reference_number}${audit.title ? ` · ${audit.title}` : ''}`,
        time: audit.scheduled_date
          ? new Date(audit.scheduled_date).toLocaleDateString()
          : audit.due_date
            ? new Date(audit.due_date).toLocaleDateString()
            : 'Date TBD',
        icon: audit.status === 'completed' ? CheckCircle2 : Calendar,
        color:
          audit.status === 'completed'
            ? 'text-success'
            : audit.status === 'in_progress'
              ? 'text-warning'
              : 'text-info',
      }))
  }, [auditSchedule])

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground flex items-center gap-2">
            <GitMerge className="w-6 h-6 text-primary" aria-hidden="true" />
            {t('ims.title')}
          </h1>
          <p className="text-muted-foreground">
            Compliance hub orientation — jump to Standards, Evidence, or Monitoring for detail.
          </p>
        </div>
        <div className="flex flex-wrap gap-3 items-center">
          <select
            value={section}
            onChange={(e) => setSection(e.target.value as ImsSectionId)}
            aria-label={t('ims.shell.tabs_aria')}
            data-testid="ims-section-filter"
            className="rounded-lg border border-border bg-card px-3 py-2 text-sm font-medium text-foreground"
          >
            {IMS_SECTIONS.map(({ id, labelKey }) => (
              <option key={id} value={id}>
                {t(labelKey)}
              </option>
            ))}
          </select>
          <Button
            variant="outline"
            onClick={() => void fetchDashboard()}
            disabled={dashLoading}
          >
            <RefreshCw className={cn('w-4 h-4 mr-2', dashLoading && 'animate-spin')} aria-hidden="true" />
            {t('ims.sync')}
          </Button>
          <Button type="button" variant="outline" data-testid="ims-filter-apply">
            Filter
          </Button>
          <Button onClick={() => navigate('/compliance')}>
            <FileText className="w-4 h-4 mr-2" aria-hidden="true" />
            {t('ims.generate_report')}
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

      {/* Overall Compliance Banner — control % vs evidence % honesty when both are live */}
      <div className="bg-gradient-to-r from-primary to-primary-hover rounded-xl p-6">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <h2 className="text-2xl font-bold text-primary-foreground mb-1">
              {t('ims.overall_compliance')}
            </h2>
            <p className="text-primary-foreground/80">{t('ims.across_standards')}</p>
          </div>
          {dashLoading ? (
            <div className="text-5xl font-bold text-primary-foreground/50 animate-pulse">—%</div>
          ) : showDualMetrics ? (
            <div className="flex flex-col gap-4 sm:flex-row sm:gap-8">
              <div className="text-right" data-testid="ims-metric-control-implementation">
                <div
                  className="text-4xl font-bold text-primary-foreground"
                  aria-label={`${overallCompliance}% control implementation`}
                >
                  {Math.round(overallCompliance)}%
                </div>
                <div className="flex items-center justify-end gap-1 text-primary-foreground/80 mt-1 text-sm">
                  <TrendingUp className="w-4 h-4" aria-hidden="true" />
                  <span>Control implementation</span>
                </div>
              </div>
              <div className="text-right" data-testid="ims-metric-evidence-coverage">
                <div
                  className="text-4xl font-bold text-primary-foreground"
                  aria-label={`${evidenceCoveragePct}% evidence coverage`}
                >
                  {Math.round(evidenceCoveragePct)}%
                </div>
                <div className="flex items-center justify-end gap-1 text-primary-foreground/80 mt-1 text-sm">
                  <Shield className="w-4 h-4" aria-hidden="true" />
                  <span>Evidence coverage</span>
                </div>
              </div>
            </div>
          ) : (
            <div className="text-right">
              <div
                className="text-5xl font-bold text-primary-foreground"
                aria-label={`${overallCompliance}% control implementation`}
              >
                {Math.round(overallCompliance)}%
              </div>
              <div className="flex items-center justify-end gap-1 text-primary-foreground/80 mt-1">
                <TrendingUp className="w-4 h-4" aria-hidden="true" />
                <span>Control implementation — live from management system controls</span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Compliance hub orientation — no per-standard score gallery (see Standards module) */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-foreground">Compliance hub</h2>
          {!dashLoading && trackedStandardCount > 0 && (
            <Badge variant="secondary" aria-label={`${trackedStandardCount} standards tracked`}>
              {trackedStandardCount} standards tracked
            </Badge>
          )}
        </div>
        {dashLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {[1, 2, 3, 4].map((i) => (
              <Card key={i}>
                <CardContent className="p-6">
                  <TableSkeleton rows={3} columns={1} />
                </CardContent>
              </Card>
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {complianceHubDestinations.map((destination) => {
              const Icon = destination.icon
              return (
                <Card
                  key={destination.id}
                  role="button"
                  tabIndex={0}
                  data-testid={`compliance-hub-${destination.id}`}
                  className="cursor-pointer transition-colors hover:border-border-strong"
                  onClick={() => openComplianceHubDestination(destination)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') openComplianceHubDestination(destination)
                  }}
                >
                  <CardContent className="p-6">
                    <div className="flex items-start gap-4">
                      <div className={cn('p-3 rounded-xl flex-shrink-0', destination.colorBg)}>
                        <Icon className="w-6 h-6 text-white" aria-hidden="true" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <h3 className="text-base font-bold text-foreground mb-1">
                          {destination.titleKey
                            ? t(destination.titleKey, destination.title ?? '')
                            : destination.title}
                        </h3>
                        <p className="text-sm text-muted-foreground">
                          {destination.descriptionKey
                            ? t(destination.descriptionKey, destination.description ?? '')
                            : destination.description}
                        </p>
                      </div>
                      <ChevronRight className="w-5 h-5 text-muted-foreground flex-shrink-0 mt-1" aria-hidden="true" />
                    </div>
                  </CardContent>
                </Card>
              )
            })}
          </div>
        )}
      </div>

      {/* Section pills */}
      <div
        className="flex bg-surface rounded-xl p-1 border border-border overflow-x-auto"
        role="tablist"
        aria-label={t('ims.shell.tabs_aria')}
      >
        {IMS_SECTIONS.map(({ id, labelKey, icon: Icon }) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={section === id}
            onClick={() => setSection(id)}
            className={cn(
              'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 whitespace-nowrap',
              section === id
                ? 'bg-primary text-primary-foreground shadow-sm'
                : 'text-muted-foreground hover:text-foreground',
            )}
          >
            <Icon className="w-4 h-4" aria-hidden="true" />
            {t(labelKey)}
          </button>
        ))}
      </div>

      {/* ── Overview Tab ── */}
      {section === 'overview' && (
        <div data-testid="ims-section-overview">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card data-testid="ims-overview-kpi-card">
            <CardHeader>
              <CardTitle>Key Performance Metrics</CardTitle>
              <p className="text-sm text-muted-foreground" data-testid="ims-overview-kpi-honesty">
                Live from the IMS dashboard API — not demo targets. Targets show only when a real goal applies.
              </p>
            </CardHeader>
            <CardContent>
              {dashLoading ? (
                <TableSkeleton rows={5} columns={2} />
              ) : (
                <div className="space-y-4">
                  {overviewKpis.map((metric) => (
                    <div key={metric.label} className="flex items-center justify-between">
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
                          {metric.value}
                          {metric.unit}
                        </span>
                        {metric.target != null ? (
                          <span className="text-muted-foreground text-sm">
                            / {metric.target}
                            {metric.unit}
                          </span>
                        ) : null}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          <Card data-testid="ims-overview-activity-card">
            <CardHeader>
              <CardTitle>Recent Activity</CardTitle>
              <p className="text-sm text-muted-foreground" data-testid="ims-overview-activity-honesty">
                Pulled from the live audit schedule — empty means none scheduled, not a demo feed.
              </p>
            </CardHeader>
            <CardContent>
              {dashLoading ? (
                <TableSkeleton rows={4} columns={1} />
              ) : overviewActivity.length === 0 ? (
                <EmptyState
                  icon={<ClipboardList className="w-8 h-8 text-muted-foreground" />}
                  title="No scheduled audit activity yet"
                  description="When audits are scheduled in Audits, the next items appear here. This panel never invents demo findings."
                  action={
                    <Button variant="outline" onClick={() => navigate('/audits')}>
                      Open Audits <ChevronRight className="w-4 h-4 ml-1" aria-hidden="true" />
                    </Button>
                  }
                />
              ) : (
                <div className="space-y-3">
                  {overviewActivity.map((activity) => {
                    const Icon = activity.icon
                    return (
                      <button
                        key={activity.id}
                        type="button"
                        className="flex w-full items-start gap-3 rounded-lg p-2 text-left transition-colors hover:bg-surface"
                        onClick={() => navigate(`/audits/${activity.id}/execute`)}
                      >
                        <Icon
                          className={cn('mt-0.5 h-5 w-5 flex-shrink-0', activity.color)}
                          aria-hidden="true"
                        />
                        <div className="min-w-0 flex-grow">
                          <div className="text-sm text-foreground">{activity.action}</div>
                          <div className="text-xs text-muted-foreground">{activity.detail}</div>
                        </div>
                        <span className="flex-shrink-0 text-xs text-muted-foreground">
                          {activity.time}
                        </span>
                      </button>
                    )
                  })}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
        </div>
      )}

      {/* ── Cross-Standard Mapping Tab ── */}
      {section === 'mapping' && (
        <div data-testid="ims-section-mapping">
        <Card data-testid="ims-map-w1-panel">
          <CardHeader>
            <CardTitle>{t('ims.map_w1.title')}</CardTitle>
            <p className="text-sm text-muted-foreground" data-testid="ims-map-w1-honesty">
              {t('ims.map_w1.honesty')}
            </p>
            <div className="flex flex-wrap gap-2 mt-3" data-testid="ims-map-w1-scheme-chips">
              {MAP_W1_SCHEME_CHIPS.map((scheme) => {
                const live = detectedSchemes.includes(scheme)
                return (
                  <Badge
                    key={scheme}
                    variant={live ? 'success' : 'secondary'}
                    data-testid={`ims-map-w1-scheme-${scheme.replace(/\s+/g, '-').toLowerCase()}`}
                  >
                    {scheme}
                    {live
                      ? ` · ${t('ims.map_w1.scheme_live')}`
                      : ` · ${t('ims.map_w1.scheme_awaiting')}`}
                  </Badge>
                )
              })}
            </div>
            <p className="text-xs text-muted-foreground mt-2">{t('ims.map_w1.builder_followon')}</p>
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
                  title={t('ims.map_w1.empty_title')}
                  description={t('ims.map_w1.empty_desc')}
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
        </div>
      )}

      {/* ── Unified Audit Plan Tab ── */}
      {section === 'audit' && (
        <div data-testid="ims-section-audit">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle>Unified Audit Schedule</CardTitle>
              <p className="text-sm text-muted-foreground">Integrated audit program covering all standards</p>
            </div>
            <Button onClick={() => navigate('/audits')}>
              <Calendar className="w-4 h-4 mr-2" aria-hidden="true" />
              {t('ims.plan_new_audit')}
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
                        <Button
                          variant="ghost"
                          size="sm"
                          aria-label={`Open audit ${audit.reference_number}`}
                          onClick={() => navigate(`/audits/${audit.id}/execute`)}
                        >
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
        </div>
      )}

      {/* ── Management Review Tab ── */}
      {section === 'review' && (
        <div data-testid="ims-section-review">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle>Management Review Inputs</CardTitle>
              <p className="text-sm text-muted-foreground">Next Review: March 2026</p>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {managementReviewInputs.map((input, i) => {
                  const demoScheme = isDemoSchemeReviewSource(input.source)
                  const statusLabel = demoScheme ? t('ims.map_w1.demo_status') : input.status
                  return (
                  <div
                    key={i}
                    className="flex items-center justify-between p-3 bg-surface rounded-lg border border-border"
                    data-testid={demoScheme ? 'ims-map-w1-demo-review-row' : undefined}
                  >
                    <div className="flex items-center gap-3">
                      {demoScheme ? (
                        <AlertTriangle className="w-5 h-5 text-warning" aria-hidden="true" />
                      ) : input.status === 'Complete' ? (
                        <CheckCircle2 className="w-5 h-5 text-success" aria-hidden="true" />
                      ) : input.status === 'In Progress' ? (
                        <Clock className="w-5 h-5 text-warning" aria-hidden="true" />
                      ) : (
                        <AlertTriangle className="w-5 h-5 text-muted-foreground" aria-hidden="true" />
                      )}
                      <div>
                        <div className="font-medium text-foreground text-sm">{input.category}</div>
                        <div className="text-xs text-muted-foreground">
                          {input.source}
                          {demoScheme ? ` · ${t('ims.map_w1.demo_source_hint')}` : ''}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <div className={cn('flex items-center gap-1 text-sm', !demoScheme && input.trend === 'improving' ? 'text-success' : 'text-muted-foreground')}>
                        {!demoScheme && input.trend === 'improving' ? (
                          <TrendingUp className="w-4 h-4" aria-label="Improving trend" />
                        ) : (
                          <span aria-label="Stable trend">—</span>
                        )}
                      </div>
                      <Badge
                        variant={
                          demoScheme
                            ? 'warning'
                            : input.status === 'Complete'
                            ? 'default'
                            : input.status === 'In Progress'
                              ? 'secondary'
                              : 'outline'
                        }
                      >
                        {statusLabel}
                      </Badge>
                    </div>
                  </div>
                  )
                })}
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
        </div>
      )}

      {/* ── ISO 27001 ISMS Tab ── */}
      {section === 'isms' && (
        <div data-testid="ims-section-isms">
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
              <Card data-testid="ims-isms-domains-card">
                <CardHeader>
                  <CardTitle>Annex A Control Domains (ISO 27001:2022)</CardTitle>
                  <p className="text-sm text-muted-foreground" data-testid="ims-isms-domains-honesty">
                    {ismsData.domains.length > 0
                      ? `${ismsData.controls.applicable || ismsData.domains.reduce((n, d) => n + d.total, 0)} controls across live domain scores`
                      : 'Domain scores appear when Annex A controls are seeded — zeros below are not invented.'}
                  </p>
                </CardHeader>
                <CardContent>
                  {ismsData.domains.length === 0 ? (
                    <EmptyState
                      icon={<Lock className="w-8 h-8 text-muted-foreground" />}
                      title="No Annex A domain scores yet"
                      description="Connect or seed ISO 27001 controls to populate Organizational, People, Physical, and Technological themes. This view does not show placeholder 0/37 rows."
                    />
                  ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                      {ismsData.domains.map((d, i) => {
                        const meta = domainMeta[d.domain] ?? {
                          label: d.domain,
                          icon: Building2,
                          colorBg: 'bg-muted',
                        }
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
                              <span className="text-foreground font-medium">
                                {d.implemented}/{d.total}
                              </span>
                            </div>
                            <div
                              className="w-full bg-muted rounded-full h-2"
                              role="progressbar"
                              aria-valuenow={d.percentage}
                              aria-valuemin={0}
                              aria-valuemax={100}
                            >
                              <div
                                className={cn('h-2 rounded-full', meta.colorBg)}
                                style={{ width: `${d.percentage}%` }}
                              />
                            </div>
                            <div className="text-right text-xs text-muted-foreground mt-1">
                              {d.percentage}%
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  )}
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
                        return (
                          <div
                            key={cat.key}
                            className="flex items-center justify-between p-3 bg-surface rounded-lg border border-border hover:border-border-strong transition-colors cursor-pointer"
                            role="button"
                            tabIndex={0}
                            onClick={() => setSection('isms')}
                            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') setSection('isms') }}
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
                      onClick={() => navigate('/incidents')}
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
        </div>
      )}
    </div>
  )
}
