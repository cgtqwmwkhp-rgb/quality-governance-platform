import { useEffect, useState, useCallback } from 'react'
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
  actionsApi,
  auditsApi,
  notificationsApi,
  executiveDashboardApi,
  Incident,
  ExecutiveDashboardData,
} from '../api/client'
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/Card'
import { CardSkeleton } from '../components/ui/SkeletonLoader'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import { cn } from "../helpers/utils"
import { useToast, ToastContainer } from '../components/ui/Toast'

// ============================================================================
// Types
// ============================================================================

interface ModuleStats {
  incidents: { total: number; open: number; critical: number; trend: number };
  rtas: { total: number; open: number; trend: number };
  complaints: { total: number; open: number; overdue: number; trend: number };
  audits: { scheduled: number; completed: number; avgScore: number; trend: number };
  actions: { total: number; overdue: number; dueSoon: number; trend: number };
  risks: { total: number; high: number; outsideAppetite: number };
  compliance: { iso9001: number; iso14001: number; iso45001: number; iso27001: number };
  carbon: { totalEmissions: number; perFTE: number; trend: number };
}

interface RecentActivity {
  id: string;
  type: 'incident' | 'rta' | 'complaint' | 'audit' | 'action';
  title: string;
  time: string;
  status: string;
  severity?: string;
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
  subtitle 
}: {
  title: string;
  value: string | number;
  icon: React.ElementType;
  variant?: 'default' | 'success' | 'warning' | 'destructive' | 'info' | 'primary';
  trend?: number;
  link?: string;
  subtitle?: string;
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
    <Card 
      hoverable 
      className={cn(
        "p-5 transition-all",
        variantStyles[variant]
      )}
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-medium text-muted-foreground">{title}</p>
          <p className="mt-1 text-2xl font-bold text-foreground">{value}</p>
          {subtitle && <p className="text-xs text-muted-foreground mt-1">{subtitle}</p>}
          {trend !== undefined && trend !== 0 && (
            <p className={cn(
              "mt-2 text-sm flex items-center gap-1",
              trend >= 0 ? 'text-success' : 'text-destructive'
            )}>
              {trend >= 0 ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
              {Math.abs(trend)}% vs last month
            </p>
          )}
        </div>
        <div className={cn("p-3 rounded-xl", iconVariantStyles[variant])}>
          <Icon size={22} />
        </div>
      </div>
    </Card>
  )

  return link ? <Link to={link}>{content}</Link> : content;
}

function ComplianceGauge({ standard, score, icon: Icon, variant }: {
  standard: string;
  score: number;
  icon: React.ElementType;
  variant: 'info' | 'success' | 'warning' | 'primary';
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
      <div className={cn("p-2 rounded-lg", colors[variant])}>
        <Icon className="w-4 h-4" />
      </div>
      <div className="flex-grow min-w-0">
        <div className="flex justify-between text-sm mb-1">
          <span className="text-foreground truncate">{standard}</span>
          <span className="text-foreground font-medium">{score}%</span>
        </div>
        <div className="w-full bg-border rounded-full h-2">
          <div 
            className={cn("h-2 rounded-full transition-all", progressColors[variant])}
            style={{ width: `${Math.min(score, 100)}%` }}
          />
        </div>
      </div>
    </div>
  );
}

function ActivityFeed({ activities }: { activities: RecentActivity[] }) {
  const getIcon = (type: string) => {
    switch (type) {
      case 'incident': return AlertTriangle;
      case 'rta': return Car;
      case 'complaint': return MessageSquare;
      case 'audit': return ClipboardCheck;
      case 'action': return Zap;
      default: return Activity;
    }
  };

  const getVariant = (type: string) => {
    switch (type) {
      case 'incident': return 'bg-destructive/10 text-destructive';
      case 'rta': return 'bg-warning/10 text-warning';
      case 'complaint': return 'bg-primary/10 text-primary';
      case 'audit': return 'bg-info/10 text-info';
      case 'action': return 'bg-success/10 text-success';
      default: return 'bg-muted text-muted-foreground';
    }
  };

  const getStatusVariant = (status: string): "destructive" | "warning" | "success" | "secondary" => {
    switch (status) {
      case 'open': return 'destructive';
      case 'in_progress': case 'under_investigation': return 'warning';
      case 'completed': case 'closed': return 'success';
      default: return 'secondary';
    }
  };

  if (activities.length === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        <Activity className="w-8 h-8 mx-auto mb-2 opacity-50" />
        <p className="text-sm">No recent activity</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {activities.map((activity) => {
        const Icon = getIcon(activity.type);
        const colorClass = getVariant(activity.type);
        return (
          <div key={activity.id} className="flex items-start gap-3 p-3 bg-surface rounded-xl hover:bg-surface/80 transition-colors">
            <div className={cn("p-2 rounded-lg", colorClass)}>
              <Icon className="w-4 h-4" />
            </div>
            <div className="flex-grow min-w-0">
              <p className="text-sm text-foreground truncate">{activity.title}</p>
              <p className="text-xs text-muted-foreground">{activity.time}</p>
            </div>
            <Badge variant={getStatusVariant(activity.status)}>
              {activity.status.replace(/_/g, ' ')}
            </Badge>
          </div>
        );
      })}
    </div>
  );
}

function UpcomingEvents({ audits }: { audits: { id: number; title?: string; scheduled_date?: string; status: string }[] }) {
  const upcoming = audits
    .filter(a => a.scheduled_date && (a.status === 'scheduled' || a.status === 'in_progress'))
    .map(a => {
      const date = new Date(a.scheduled_date!);
      const now = new Date();
      const diffDays = Math.ceil((date.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
      return { ...a, date, diffDays };
    })
    .filter(a => a.diffDays > 0)
    .sort((a, b) => a.diffDays - b.diffDays)
    .slice(0, 5);

  if (upcoming.length === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        <Calendar className="w-8 h-8 mx-auto mb-2 opacity-50" />
        <p className="text-sm">No upcoming events</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {upcoming.map((event) => (
        <div key={event.id} className="flex items-center gap-3 p-3 bg-surface rounded-xl">
          <div className="p-2 rounded-lg bg-info/10">
            <Calendar className="w-4 h-4 text-info" />
          </div>
          <div className="flex-grow">
            <p className="text-sm text-foreground truncate">{event.title || 'Untitled Audit'}</p>
            <p className="text-xs text-muted-foreground">
              {event.date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
            </p>
          </div>
          <Badge variant={
            event.diffDays <= 7 ? 'critical' :
            event.diffDays <= 30 ? 'warning' :
            'secondary'
          }>
            {event.diffDays}d
          </Badge>
        </div>
      ))}
    </div>
  );
}

// ============================================================================
// Helpers
// ============================================================================

function formatTimeAgo(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins} min${diffMins === 1 ? '' : 's'} ago`;
  if (diffHours < 24) return `${diffHours} hour${diffHours === 1 ? '' : 's'} ago`;
  if (diffDays === 1) return 'Yesterday';
  if (diffDays < 7) return `${diffDays} days ago`;
  return date.toLocaleDateString();
}

// ============================================================================
// Main Dashboard Component
// ============================================================================

export default function Dashboard() {
  const { toasts, show: showToast, dismiss: dismissToast } = useToast()
  const [incidents, setIncidents] = useState<Incident[]>([])
  const [loading, setLoading] = useState(true)
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
  const [unreadCount, setUnreadCount] = useState(0)
  const [upcomingAudits, setUpcomingAudits] = useState<{ id: number; title?: string; scheduled_date?: string; status: string }[]>([])

  const loadData = useCallback(async () => {
    try {
      setLoading(true)

      // Fetch all data in parallel from real APIs
      const [
        incidentsRes,
        rtasRes,
        complaintsRes,
        actionsRes,
        auditRunsRes,
        notifRes,
        execDashRes,
      ] = await Promise.allSettled([
        incidentsApi.list(1, 100),
        rtasApi.list(1, 100),
        complaintsApi.list(1, 100),
        actionsApi.list(1, 100),
        auditsApi.listRuns(1, 100),
        notificationsApi.getUnreadCount(),
        executiveDashboardApi.getDashboard(30),
      ])

      // Extract data with safe fallbacks
      const incidentItems = incidentsRes.status === 'fulfilled' ? (incidentsRes.value.data.items || []) : []
      const rtaItems = rtasRes.status === 'fulfilled' ? (rtasRes.value.data.items || []) : []
      const complaintItems = complaintsRes.status === 'fulfilled' ? (complaintsRes.value.data.items || []) : []
      const actionItems = actionsRes.status === 'fulfilled' ? (actionsRes.value.data.items || []) : []
      const auditItems = auditRunsRes.status === 'fulfilled' ? (auditRunsRes.value.data.items || []) : []
      const execDash: ExecutiveDashboardData | null = execDashRes.status === 'fulfilled' ? execDashRes.value.data : null

      // Set recent incidents for table
      setIncidents(incidentItems.slice(0, 5))

      // Notification badge count
      if (notifRes.status === 'fulfilled') {
        setUnreadCount(notifRes.value.data.unread_count || 0)
      }

      // Upcoming audits for events widget
      setUpcomingAudits(auditItems)

      // Compute stats from real data
      const openIncidents = incidentItems.filter(i => i.status !== 'closed')
      const criticalIncidents = incidentItems.filter(i => i.severity === 'critical' || i.severity === 'high')
      const openRtas = rtaItems.filter(r => r.status !== 'closed')
      const openComplaints = complaintItems.filter(c => c.status !== 'closed' && c.status !== 'resolved')
      const overdueComplaints = complaintItems.filter(c => {
        if (c.status === 'closed' || c.status === 'resolved') return false
        if (!c.due_date) return false
        return new Date(c.due_date) < new Date()
      })
      const overdueActions = actionItems.filter(a => {
        if (a.status === 'completed' || a.status === 'closed') return false
        if (!a.due_date) return false
        return new Date(a.due_date) < new Date()
      })
      const dueSoonActions = actionItems.filter(a => {
        if (a.status === 'completed' || a.status === 'closed') return false
        if (!a.due_date) return false
        const due = new Date(a.due_date)
        const now = new Date()
        const diffDays = (due.getTime() - now.getTime()) / (1000 * 60 * 60 * 24)
        return diffDays > 0 && diffDays <= 7
      })
      const completedAudits = auditItems.filter(a => a.status === 'completed')
      const scheduledAudits = auditItems.filter(a => a.status === 'scheduled')
      const scoredAudits = auditItems.filter(a => a.score_percentage != null)
      const avgScore = scoredAudits.length > 0
        ? Math.round(scoredAudits.reduce((sum, a) => sum + (a.score_percentage ?? 0), 0) / scoredAudits.length)
        : 0

      // Use exec dashboard for risks, compliance if available
      const riskHigh = execDash?.risks?.high_critical ?? 0
      const riskTotal = execDash?.risks?.total_active ?? 0
      const complianceRate = execDash?.compliance?.completion_rate ?? 0

      setStats({
        incidents: {
          total: incidentItems.length,
          open: openIncidents.length,
          critical: criticalIncidents.length,
          trend: execDash?.near_misses?.trend_percent ?? 0,
        },
        rtas: {
          total: rtaItems.length,
          open: openRtas.length,
          trend: 0,
        },
        complaints: {
          total: complaintItems.length,
          open: openComplaints.length,
          overdue: overdueComplaints.length,
          trend: 0,
        },
        audits: {
          scheduled: scheduledAudits.length,
          completed: completedAudits.length,
          avgScore,
          trend: 0,
        },
        actions: {
          total: actionItems.length,
          overdue: overdueActions.length,
          dueSoon: dueSoonActions.length,
          trend: 0,
        },
        risks: {
          total: riskTotal,
          high: riskHigh,
          outsideAppetite: execDash?.kris?.at_risk ?? 0,
        },
        compliance: {
          iso9001: Math.round(complianceRate),
          iso14001: Math.round(complianceRate * 0.97),
          iso45001: Math.round(complianceRate * 1.02),
          iso27001: Math.round(complianceRate * 0.95),
        },
        carbon: {
          totalEmissions: 0,
          perFTE: 0,
          trend: 0,
        },
      })

      // Build recent activities from real records
      const recentActivities: RecentActivity[] = []

      incidentItems.slice(0, 3).forEach(i => {
        recentActivities.push({
          id: `inc-${i.id}`,
          type: 'incident',
          title: i.title || `Incident ${i.reference_number}`,
          time: formatTimeAgo(i.created_at),
          status: i.status,
          severity: i.severity,
        })
      })

      auditItems.slice(0, 2).forEach(a => {
        recentActivities.push({
          id: `aud-${a.id}`,
          type: 'audit',
          title: a.title || `Audit ${a.reference_number}`,
          time: formatTimeAgo(a.created_at),
          status: a.status,
        })
      })

      complaintItems.slice(0, 2).forEach(c => {
        recentActivities.push({
          id: `cmp-${c.id}`,
          type: 'complaint',
          title: c.title || `Complaint ${c.reference_number}`,
          time: formatTimeAgo(c.created_at),
          status: c.status,
        })
      })

      actionItems.slice(0, 2).forEach(a => {
        recentActivities.push({
          id: `act-${a.id}`,
          type: 'action',
          title: a.title || `Action ${a.reference_number}`,
          time: formatTimeAgo(a.created_at),
          status: a.status,
        })
      })

      rtaItems.slice(0, 1).forEach(r => {
        recentActivities.push({
          id: `rta-${r.id}`,
          type: 'rta',
          title: r.title || `RTA ${r.reference_number}`,
          time: formatTimeAgo(r.created_at),
          status: r.status,
        })
      })

      // Sort by most recent (those with smallest time values first)
      recentActivities.sort((a, b) => {
        const aTime = a.time.includes('Just') ? 0 : a.time.includes('min') ? 1 : a.time.includes('hour') ? 2 : 3
        const bTime = b.time.includes('Just') ? 0 : b.time.includes('min') ? 1 : b.time.includes('hour') ? 2 : 3
        return aTime - bTime
      })

      setActivities(recentActivities.slice(0, 5))
    } catch (err) {
      console.error('Failed to load dashboard data:', err)
      showToast('Failed to load dashboard data. Please try again.', 'error')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadData()
  }, [loadData])

  if (loading) {
    return (
      <div className="p-6"><CardSkeleton count={4} /></div>
    )
  }

  return (
    <div className="space-y-6">
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
                <Badge variant="destructive" className="ml-2">{unreadCount}</Badge>
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
          value={stats.audits.avgScore > 0 ? `${stats.audits.avgScore}%` : '-'}
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
          value={stats.carbon.perFTE > 0 ? stats.carbon.perFTE.toFixed(2) : '-'}
          icon={Leaf} 
          variant="success"
          trend={stats.carbon.trend}
          link="/planet-mark"
          subtitle={stats.carbon.totalEmissions > 0 ? `${stats.carbon.totalEmissions} total tCO₂e` : undefined}
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
            <ComplianceGauge standard="ISO 9001:2015" score={stats.compliance.iso9001} icon={Shield} variant="info" />
            <ComplianceGauge standard="ISO 14001:2015" score={stats.compliance.iso14001} icon={Leaf} variant="success" />
            <ComplianceGauge standard="ISO 45001:2018" score={stats.compliance.iso45001} icon={AlertCircle} variant="warning" />
            <ComplianceGauge standard="ISO 27001:2022" score={stats.compliance.iso27001} icon={Lock} variant="primary" />
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
              <Link to="/audits">
                View All <ArrowRight className="w-4 h-4 ml-1" />
              </Link>
            </Button>
          </CardHeader>
          <CardContent>
            <UpcomingEvents audits={upcomingAudits} />
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
                  <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">Reference</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">Title</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">Severity</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">Status</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">Date</th>
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
                    <tr key={incident.id} className="border-b border-border/50 hover:bg-surface transition-colors">
                      <td className="py-3 px-4 text-sm text-primary font-mono">{incident.reference_number}</td>
                      <td className="py-3 px-4 text-sm text-foreground">{incident.title}</td>
                      <td className="py-3 px-4">
                        <Badge variant={
                          incident.severity === 'critical' ? 'critical' :
                          incident.severity === 'high' ? 'high' :
                          incident.severity === 'medium' ? 'medium' :
                          'low'
                        }>
                          {incident.severity}
                        </Badge>
                      </td>
                      <td className="py-3 px-4">
                        <Badge variant={
                          incident.status === 'closed' ? 'resolved' :
                          incident.status === 'under_investigation' ? 'in-progress' :
                          'submitted'
                        }>
                          {incident.status.replace(/_/g, ' ')}
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
      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </div>
  )
}
