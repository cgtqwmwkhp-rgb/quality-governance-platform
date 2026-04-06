import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  AlertTriangle,
  TrendingUp,
  TrendingDown,
  AlertCircle,
  Car,
  MessageSquare,
  Shield,
  ClipboardCheck,
  Target,
  Zap,
  Calendar,
  BarChart3,
  ArrowRight,
  Activity,
  Leaf,
  Lock,
  Bell,
  RefreshCw,
} from 'lucide-react'
import {
  incidentsApi,
  rtasApi,
  complaintsApi,
  risksApi,
  actionsApi,
  auditsApi,
  notificationsApi,
  type Incident,
  type RTA,
  type Complaint,
  type Risk,
  type Action,
  type AuditRun,
  type PaginatedResponse,
} from '../api/client'
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/Card'
import { CardSkeleton } from '../components/ui/SkeletonLoader'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import { cn } from '../helpers/utils'

// ============================================================================
// Types
// ============================================================================

interface ModuleStats {
  incidents: { total: number; open: number; critical: number; trend: number }
  rtas: { total: number; open: number; trend: number }
  complaints: { total: number; open: number; overdue: number; trend: number }
  audits: { scheduled: number; completed: number; avgScore: number; trend: number }
  actions: { total: number; overdue: number; dueSoon: number; trend: number }
  risks: { total: number; high: number; outsideAppetite: number }
  compliance: { iso9001: number; iso14001: number; iso45001: number; iso27001: number }
  carbon: { totalEmissions: number; perFTE: number; trend: number }
}

interface RecentActivity {
  id: string
  type: 'incident' | 'rta' | 'complaint' | 'audit' | 'action'
  title: string
  time: string
  status: string
  severity?: string
}

// ============================================================================
// Widget Components
// ============================================================================

function StatCard({
  title,
  value,
  icon: Icon,
  variant = 'default',
  trend,
  link,
  subtitle,
}: {
  title: string
  value: string | number
  icon: React.ElementType
  variant?: 'default' | 'success' | 'warning' | 'destructive' | 'info' | 'primary'
  trend?: number
  link?: string
  subtitle?: string
}) {
  const variantStyles = {
    default: 'bg-card border-border',
    success: 'bg-success/5 border-success/20',
    warning: 'bg-warning/5 border-warning/20',
    destructive: 'bg-destructive/5 border-destructive/20',
    info: 'bg-info/5 border-info/20',
    primary: 'bg-primary/5 border-primary/20',
  }

  const iconVariantStyles = {
    default: 'bg-surface text-muted-foreground',
    success: 'bg-success/10 text-success',
    warning: 'bg-warning/10 text-warning',
    destructive: 'bg-destructive/10 text-destructive',
    info: 'bg-info/10 text-info',
    primary: 'bg-primary/10 text-primary',
  }

  const content = (
    <Card hoverable className={cn('p-5 transition-all', variantStyles[variant])}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-medium text-muted-foreground">{title}</p>
          <p className="mt-1 text-2xl font-bold text-foreground">{value}</p>
          {subtitle && <p className="text-xs text-muted-foreground mt-1">{subtitle}</p>}
          {trend !== undefined && (
            <p
              className={cn(
                'mt-2 text-sm flex items-center gap-1',
                trend >= 0 ? 'text-success' : 'text-destructive',
              )}
            >
              {trend >= 0 ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
              {Math.abs(trend)}% vs last month
            </p>
          )}
        </div>
        <div className={cn('p-3 rounded-xl', iconVariantStyles[variant])}>
          <Icon size={22} />
        </div>
      </div>
    </Card>
  )

  return link ? <Link to={link}>{content}</Link> : content
}

function ComplianceGauge({
  standard,
  score,
  icon: Icon,
  variant,
}: {
  standard: string
  score: number
  icon: React.ElementType
  variant: 'info' | 'success' | 'warning' | 'primary'
}) {
  const colors = {
    info: 'bg-info text-info-foreground',
    success: 'bg-success text-success-foreground',
    warning: 'bg-warning text-warning-foreground',
    primary: 'bg-primary text-primary-foreground',
  }

  const progressColors = {
    info: 'bg-info',
    success: 'bg-success',
    warning: 'bg-warning',
    primary: 'bg-primary',
  }

  return (
    <div className="flex items-center gap-3 p-3 bg-surface rounded-xl">
      <div className={cn('p-2 rounded-lg', colors[variant])}>
        <Icon className="w-4 h-4" />
      </div>
      <div className="flex-grow min-w-0">
        <div className="flex justify-between text-sm mb-1">
          <span className="text-foreground truncate">{standard}</span>
          <span className="text-foreground font-medium">{score}%</span>
        </div>
        <div className="w-full bg-border rounded-full h-2">
          <div
            className={cn('h-2 rounded-full transition-all', progressColors[variant])}
            style={{ width: `${score}%` }}
          />
        </div>
      </div>
    </div>
  )
}

function ActivityFeed({ activities }: { activities: RecentActivity[] }) {
  if (activities.length === 0) {
    return <div className="text-center py-6 text-muted-foreground text-sm">No recent activity</div>
  }

  const getIcon = (type: string) => {
    switch (type) {
      case 'incident':
        return AlertTriangle
      case 'rta':
        return Car
      case 'complaint':
        return MessageSquare
      case 'audit':
        return ClipboardCheck
      case 'action':
        return Zap
      default:
        return Activity
    }
  }

  const getVariant = (type: string) => {
    switch (type) {
      case 'incident':
        return 'bg-destructive/10 text-destructive'
      case 'rta':
        return 'bg-warning/10 text-warning'
      case 'complaint':
        return 'bg-primary/10 text-primary'
      case 'audit':
        return 'bg-info/10 text-info'
      case 'action':
        return 'bg-success/10 text-success'
      default:
        return 'bg-muted text-muted-foreground'
    }
  }

  const getStatusVariant = (status: string) => {
    switch (status) {
      case 'open':
        return 'destructive'
      case 'in_progress':
        return 'warning'
      case 'completed':
        return 'success'
      default:
        return 'secondary'
    }
  }

  return (
    <div className="space-y-3">
      {activities.map((activity) => {
        const Icon = getIcon(activity.type)
        const colorClass = getVariant(activity.type)
        return (
          <div
            key={activity.id}
            className="flex items-start gap-3 p-3 bg-surface rounded-xl hover:bg-surface/80 transition-colors"
          >
            <div className={cn('p-2 rounded-lg', colorClass)}>
              <Icon className="w-4 h-4" />
            </div>
            <div className="flex-grow min-w-0">
              <p className="text-sm text-foreground truncate">{activity.title}</p>
              <p className="text-xs text-muted-foreground">{activity.time}</p>
            </div>
            <Badge variant={getStatusVariant(activity.status) as any}>
              {activity.status.replace('_', ' ')}
            </Badge>
          </div>
        )
      })}
    </div>
  )
}

function UpcomingEvents({
  events,
}: {
  events: { id: number; title: string; date: string; type: string; days: number }[]
}) {
  if (events.length === 0) {
    return <div className="text-center py-6 text-muted-foreground text-sm">No upcoming events</div>
  }

  return (
    <div className="space-y-2">
      {events.map((event) => (
        <div key={event.id} className="flex items-center gap-3 p-3 bg-surface rounded-xl">
          <div className="p-2 rounded-lg bg-info/10">
            <Calendar className="w-4 h-4 text-info" />
          </div>
          <div className="flex-grow">
            <p className="text-sm text-foreground">{event.title}</p>
            <p className="text-xs text-muted-foreground">{event.date}</p>
          </div>
          <Badge
            variant={event.days <= 7 ? 'critical' : event.days <= 30 ? 'warning' : 'secondary'}
          >
            {event.days}d
          </Badge>
        </div>
      ))}
    </div>
  )
}

// ============================================================================
// Main Dashboard Component
// ============================================================================

const today = () => new Date().toISOString().slice(0, 10)
const daysFromNow = (days: number) => {
  const d = new Date()
  d.setDate(d.getDate() + days)
  return d.toISOString().slice(0, 10)
}

export default function Dashboard() {
  const [incidents, setIncidents] = useState<Incident[]>([])
  const [loading, setLoading] = useState(true)
  const [unreadCount, setUnreadCount] = useState(0)
  const [stats, setStats] = useState<ModuleStats>({
    incidents: { total: 0, open: 0, critical: 0, trend: 0 },
    rtas: { total: 0, open: 0, trend: 0 },
    complaints: { total: 0, open: 0, overdue: 0, trend: 0 },
    audits: { scheduled: 0, completed: 0, avgScore: 0, trend: 0 },
    actions: { total: 0, overdue: 0, dueSoon: 0, trend: 0 },
    risks: { total: 0, high: 0, outsideAppetite: 0 },
    compliance: { iso9001: 0, iso14001: 0, iso45001: 0, iso27001: 0 },
    carbon: { totalEmissions: 0, perFTE: 0, trend: 0 },
  })
  const [activities, setActivities] = useState<RecentActivity[]>([])
  const [upcomingEvents] = useState<
    { id: number; title: string; date: string; type: string; days: number }[]
  >([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    setError(null)
    setLoading(true)
    try {
      const results = await Promise.allSettled([
        incidentsApi.list(1, 100),
        rtasApi.list(1, 100),
        complaintsApi.list(1, 100),
        risksApi.list(1, 100),
        actionsApi.list(1, 100),
        auditsApi.listRuns(1, 100),
        notificationsApi.getUnreadCount(),
      ])

      const getData = <T,>(r: PromiseSettledResult<{ data: T }>, def: T): T =>
        r.status === 'fulfilled' ? (r.value?.data ?? def) : def

      const incidentsRes = results[0]
      const incidentsData = incidentsRes.status === 'fulfilled' ? incidentsRes.value?.data : null
      const incidentItems = incidentsData?.items ?? []
      const incidentTotal = incidentsData?.total ?? 0
      setIncidents(incidentItems.slice(0, 5))

      const rtaData = getData(
        results[1] as PromiseSettledResult<{ data: PaginatedResponse<RTA> }>,
        { items: [], total: 0, page: 1, page_size: 50, pages: 0 } as PaginatedResponse<RTA>,
      )
      const rtaItems = rtaData?.items ?? []
      const rtaTotal = rtaData?.total ?? 0
      const rtaOpen = rtaItems.filter((r) => r.status !== 'closed').length

      const complaintData = getData(
        results[2] as PromiseSettledResult<{ data: PaginatedResponse<Complaint> }>,
        { items: [], total: 0, page: 1, page_size: 50, pages: 0 } as PaginatedResponse<Complaint>,
      )
      const complaintItems = complaintData?.items ?? []
      const complaintTotal = complaintData?.total ?? 0
      const complaintOpen = complaintItems.filter(
        (c) => c.status !== 'closed' && c.status !== 'resolved',
      ).length
      const complaintOverdue = complaintItems.filter(
        (c) =>
          c.due_date && c.due_date < today() && c.status !== 'closed' && c.status !== 'resolved',
      ).length

      const riskData = getData(
        results[3] as PromiseSettledResult<{ data: PaginatedResponse<Risk> }>,
        { items: [], total: 0, page: 1, page_size: 50, pages: 0 } as PaginatedResponse<Risk>,
      )
      const riskItems = riskData?.items ?? []
      const riskTotal = riskData?.total ?? 0
      const riskHigh = riskItems.filter(
        (r) => r.risk_level === 'high' || r.risk_level === 'critical',
      ).length

      const actionData = getData(
        results[4] as PromiseSettledResult<{ data: PaginatedResponse<Action> }>,
        { items: [], total: 0, page: 1, page_size: 50, pages: 0 } as PaginatedResponse<Action>,
      )
      const actionItems = actionData?.items ?? []
      const actionTotal = actionData?.total ?? 0
      const openStatuses = ['open', 'in_progress', 'pending_verification']
      const actionOverdue = actionItems.filter(
        (a) => a.due_date && a.due_date < today() && openStatuses.includes(a.display_status),
      ).length
      const actionDueSoon = actionItems.filter(
        (a) =>
          a.due_date &&
          a.due_date >= today() &&
          a.due_date <= daysFromNow(7) &&
          openStatuses.includes(a.display_status),
      ).length

      const auditData = getData(
        results[5] as PromiseSettledResult<{ data: PaginatedResponse<AuditRun> }>,
        { items: [], total: 0, page: 1, page_size: 50, pages: 0 } as PaginatedResponse<AuditRun>,
      )
      const auditItems = auditData?.items ?? []
      const auditScheduled = auditItems.filter((a) => a.status === 'scheduled').length
      const auditCompleted = auditItems.filter((a) => a.status === 'completed').length
      const completedWithScores = auditItems.filter(
        (a) => a.status === 'completed' && a.score_percentage != null,
      )
      const auditAvgScore =
        completedWithScores.length > 0
          ? Math.round(
              completedWithScores.reduce((sum, a) => sum + (a.score_percentage ?? 0), 0) /
                completedWithScores.length,
            )
          : 0

      const unreadRes = results[6]
      const unreadData = unreadRes.status === 'fulfilled' ? unreadRes.value?.data : null
      setUnreadCount(unreadData?.unread_count ?? 0)

      // Build recent activity from combined recent items
      const activityItems: Array<{
        id: string
        type: RecentActivity['type']
        title: string
        time: string
        status: string
        severity?: string
        created_at: string
      }> = []
      incidentItems.slice(0, 5).forEach((i) =>
        activityItems.push({
          id: `incident-${i.id}`,
          type: 'incident',
          title: i.title,
          time: new Date(i.created_at).toLocaleDateString(),
          status: i.status,
          severity: i.severity,
          created_at: i.created_at,
        }),
      )
      rtaItems.slice(0, 5).forEach((r) =>
        activityItems.push({
          id: `rta-${r.id}`,
          type: 'rta',
          title: r.title,
          time: new Date(r.created_at).toLocaleDateString(),
          status: r.status,
          created_at: r.created_at,
        }),
      )
      complaintItems.slice(0, 5).forEach((c) =>
        activityItems.push({
          id: `complaint-${c.id}`,
          type: 'complaint',
          title: c.title,
          time: new Date(c.created_at).toLocaleDateString(),
          status: c.status,
          created_at: c.created_at,
        }),
      )
      auditItems.slice(0, 5).forEach((a) =>
        activityItems.push({
          id: `audit-${a.id}`,
          type: 'audit',
          title: a.title ?? a.reference_number ?? `Audit ${a.id}`,
          time: new Date(a.created_at).toLocaleDateString(),
          status: a.status,
          created_at: a.created_at,
        }),
      )
      actionItems.slice(0, 5).forEach((a) =>
        activityItems.push({
          id: `action-${a.id}`,
          type: 'action',
          title: a.title,
          time: new Date(a.created_at).toLocaleDateString(),
          status: a.status,
          created_at: a.created_at,
        }),
      )
      activityItems.sort(
        (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
      )
      setActivities(activityItems.slice(0, 15).map(({ created_at: _created_at, ...rest }) => rest))

      setStats({
        incidents: {
          total: incidentTotal,
          open: incidentItems.filter((i) => i.status !== 'closed').length,
          critical: incidentItems.filter((i) => i.severity === 'critical' || i.severity === 'high')
            .length,
          trend: 0,
        },
        rtas: { total: rtaTotal, open: rtaOpen, trend: 0 },
        complaints: {
          total: complaintTotal,
          open: complaintOpen,
          overdue: complaintOverdue,
          trend: 0,
        },
        audits: {
          scheduled: auditScheduled,
          completed: auditCompleted,
          avgScore: auditAvgScore,
          trend: 0,
        },
        actions: { total: actionTotal, overdue: actionOverdue, dueSoon: actionDueSoon, trend: 0 },
        risks: { total: riskTotal, high: riskHigh, outsideAppetite: 0 },
        compliance: { iso9001: 0, iso14001: 0, iso45001: 0, iso27001: 0 },
        carbon: { totalEmissions: 0, perFTE: 0, trend: 0 },
      })
    } catch (err) {
      if (import.meta.env.DEV) console.error('Failed to load dashboard data:', err)
      setError('Failed to load data. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div className="space-y-2">
            <div className="h-9 w-48 rounded bg-muted animate-pulse" />
            <div className="h-4 w-64 rounded bg-muted/70 animate-pulse" />
          </div>
        </div>
        <CardSkeleton count={4} className="grid-cols-2 md:grid-cols-4" />
        <CardSkeleton count={3} className="grid-cols-1 md:grid-cols-3" />
        <CardSkeleton count={3} className="grid-cols-1 lg:grid-cols-3 gap-6" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {error && (
        <div className="mx-4 mt-4 p-4 bg-destructive/10 border border-destructive/20 rounded-lg flex items-center justify-between">
          <p className="text-sm text-destructive">{error}</p>
          <button
            onClick={() => {
              setError(null)
              loadData()
            }}
            className="text-sm font-medium text-destructive hover:underline"
          >
            Try Again
          </button>
        </div>
      )}

      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-foreground">Dashboard</h1>
          <p className="text-muted-foreground">Quality Governance Platform Overview</p>
        </div>
        <div className="flex gap-3">
          <Button variant="outline" asChild>
            <Link to="/notifications">
              <Bell className="w-4 h-4" />
              <span className="hidden sm:inline">Notifications</span>
              {unreadCount > 0 && (
                <Badge variant="destructive" className="ml-2">
                  {unreadCount}
                </Badge>
              )}
            </Link>
          </Button>
          <Button onClick={loadData}>
            <RefreshCw className="w-4 h-4" />
            Refresh
          </Button>
        </div>
      </div>

      {/* Primary Stats Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          title="Open Incidents"
          value={stats.incidents.open}
          icon={AlertTriangle}
          variant="destructive"
          trend={stats.incidents.trend}
          link="/incidents"
          subtitle={`${stats.incidents.critical} critical`}
        />
        <StatCard
          title="Open RTAs"
          value={stats.rtas.open}
          icon={Car}
          variant="warning"
          trend={stats.rtas.trend}
          link="/rtas"
        />
        <StatCard
          title="Open Complaints"
          value={stats.complaints.open}
          icon={MessageSquare}
          variant="primary"
          trend={stats.complaints.trend}
          link="/complaints"
          subtitle={`${stats.complaints.overdue} overdue`}
        />
        <StatCard
          title="Overdue Actions"
          value={stats.actions.overdue}
          icon={Zap}
          variant="warning"
          trend={stats.actions.trend}
          link="/actions"
          subtitle={`${stats.actions.dueSoon} due soon`}
        />
      </div>

      {/* Secondary Row: Audits, Risks, Carbon */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <StatCard
          title="Audit Score (Avg)"
          value={`${stats.audits.avgScore}%`}
          icon={ClipboardCheck}
          variant="info"
          trend={stats.audits.trend}
          link="/audits"
          subtitle={`${stats.audits.completed} completed this year`}
        />
        <StatCard
          title="High Risks"
          value={stats.risks.high}
          icon={Target}
          variant="destructive"
          link="/risk-register"
          subtitle={`${stats.risks.outsideAppetite} outside appetite`}
        />
        <StatCard
          title="Carbon (tCO₂e/FTE)"
          value={stats.carbon.perFTE.toFixed(2)}
          icon={Leaf}
          variant="success"
          trend={stats.carbon.trend}
          link="/planet-mark"
          subtitle={`${stats.carbon.totalEmissions} total tCO₂e`}
        />
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Compliance Overview */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>IMS Compliance</CardTitle>
            <Button variant="link" size="sm" asChild>
              <Link to="/ims">
                View All <ArrowRight className="w-4 h-4 ml-1" />
              </Link>
            </Button>
          </CardHeader>
          <CardContent className="space-y-3">
            <ComplianceGauge
              standard="ISO 9001:2015"
              score={stats.compliance.iso9001}
              icon={Shield}
              variant="info"
            />
            <ComplianceGauge
              standard="ISO 14001:2015"
              score={stats.compliance.iso14001}
              icon={Leaf}
              variant="success"
            />
            <ComplianceGauge
              standard="ISO 45001:2018"
              score={stats.compliance.iso45001}
              icon={AlertCircle}
              variant="warning"
            />
            <ComplianceGauge
              standard="ISO 27001:2022"
              score={stats.compliance.iso27001}
              icon={Lock}
              variant="primary"
            />
          </CardContent>
        </Card>

        {/* Recent Activity */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>Recent Activity</CardTitle>
            <Button variant="link" size="sm" asChild>
              <Link to="/audit-trail">
                View All <ArrowRight className="w-4 h-4 ml-1" />
              </Link>
            </Button>
          </CardHeader>
          <CardContent>
            <ActivityFeed activities={activities} />
          </CardContent>
        </Card>

        {/* Upcoming Events */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>Upcoming Events</CardTitle>
            <Button variant="link" size="sm" asChild>
              <Link to="/calendar">
                View All <ArrowRight className="w-4 h-4 ml-1" />
              </Link>
            </Button>
          </CardHeader>
          <CardContent>
            <UpcomingEvents events={upcomingEvents} />
          </CardContent>
        </Card>
      </div>

      {/* Recent Incidents Table */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Recent Incidents</CardTitle>
          <Button variant="link" size="sm" asChild>
            <Link to="/incidents">
              View All <ArrowRight className="w-4 h-4 ml-1" />
            </Link>
          </Button>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">
                    Reference
                  </th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">
                    Title
                  </th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">
                    Severity
                  </th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">
                    Status
                  </th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">
                    Date
                  </th>
                </tr>
              </thead>
              <tbody>
                {incidents.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="text-center py-8 text-muted-foreground">
                      No incidents found
                    </td>
                  </tr>
                ) : (
                  incidents.map((incident) => (
                    <tr
                      key={incident.id}
                      className="border-b border-border/50 hover:bg-surface transition-colors"
                    >
                      <td className="py-3 px-4 text-sm text-primary font-mono">
                        {incident.reference_number}
                      </td>
                      <td className="py-3 px-4 text-sm text-foreground">{incident.title}</td>
                      <td className="py-3 px-4">
                        <Badge
                          variant={
                            incident.severity === 'critical'
                              ? 'critical'
                              : incident.severity === 'high'
                                ? 'high'
                                : incident.severity === 'medium'
                                  ? 'medium'
                                  : 'low'
                          }
                        >
                          {incident.severity}
                        </Badge>
                      </td>
                      <td className="py-3 px-4">
                        <Badge
                          variant={
                            incident.status === 'closed'
                              ? 'resolved'
                              : incident.status === 'under_investigation'
                                ? 'in-progress'
                                : 'submitted'
                          }
                        >
                          {incident.status.replace('_', ' ')}
                        </Badge>
                      </td>
                      <td className="py-3 px-4 text-sm text-muted-foreground">
                        {new Date(incident.created_at).toLocaleDateString()}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Quick Actions */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Link to="/incidents">
          <Card hoverable className="p-4 bg-destructive/5 border-destructive/20">
            <div className="flex items-center gap-3">
              <AlertTriangle className="w-5 h-5 text-destructive" />
              <span className="text-foreground font-medium">New Incident</span>
            </div>
          </Card>
        </Link>
        <Link to="/audits">
          <Card hoverable className="p-4 bg-info/5 border-info/20">
            <div className="flex items-center gap-3">
              <ClipboardCheck className="w-5 h-5 text-info" />
              <span className="text-foreground font-medium">Start Audit</span>
            </div>
          </Card>
        </Link>
        <Link to="/analytics">
          <Card hoverable className="p-4 bg-primary/5 border-primary/20">
            <div className="flex items-center gap-3">
              <BarChart3 className="w-5 h-5 text-primary" />
              <span className="text-foreground font-medium">View Analytics</span>
            </div>
          </Card>
        </Link>
        <Link to="/compliance">
          <Card hoverable className="p-4 bg-success/5 border-success/20">
            <div className="flex items-center gap-3">
              <Shield className="w-5 h-5 text-success" />
              <span className="text-foreground font-medium">Compliance</span>
            </div>
          </Card>
        </Link>
      </div>
    </div>
  )
}
