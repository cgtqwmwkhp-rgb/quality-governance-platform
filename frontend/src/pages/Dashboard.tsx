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
import { incidentsApi, Incident } from '../api/client'

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
  color, 
  trend, 
  link,
  subtitle 
}: {
  title: string;
  value: string | number;
  icon: React.ElementType;
  color: 'emerald' | 'amber' | 'red' | 'blue' | 'purple' | 'orange' | 'teal';
  trend?: number;
  link?: string;
  subtitle?: string;
}) {
  const colors = {
    emerald: 'from-emerald-500/20 to-emerald-600/20 border-emerald-500/30 text-emerald-400',
    amber: 'from-amber-500/20 to-amber-600/20 border-amber-500/30 text-amber-400',
    red: 'from-red-500/20 to-red-600/20 border-red-500/30 text-red-400',
    blue: 'from-blue-500/20 to-blue-600/20 border-blue-500/30 text-blue-400',
    purple: 'from-purple-500/20 to-purple-600/20 border-purple-500/30 text-purple-400',
    orange: 'from-orange-500/20 to-orange-600/20 border-orange-500/30 text-orange-400',
    teal: 'from-teal-500/20 to-teal-600/20 border-teal-500/30 text-teal-400',
  }

  const content = (
    <div className={`
      relative overflow-hidden rounded-2xl border bg-gradient-to-br p-5
      ${colors[color]} backdrop-blur-xl hover:scale-[1.02] transition-transform
    `}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-medium text-slate-400">{title}</p>
          <p className="mt-1 text-2xl font-bold text-white">{value}</p>
          {subtitle && <p className="text-xs text-slate-500 mt-1">{subtitle}</p>}
          {trend !== undefined && (
            <p className={`mt-2 text-sm flex items-center gap-1 ${
              trend >= 0 ? 'text-emerald-400' : 'text-red-400'
            }`}>
              {trend >= 0 ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
              {Math.abs(trend)}% vs last month
            </p>
          )}
        </div>
        <div className={`p-3 rounded-xl bg-gradient-to-br ${colors[color].replace('text-', 'from-').replace('-400', '-500/20')} ${colors[color].replace('text-', 'to-').replace('-400', '-600/20')}`}>
          <Icon size={22} className={colors[color].split(' ').pop()} />
        </div>
      </div>
    </div>
  )

  return link ? <Link to={link}>{content}</Link> : content;
}

function ComplianceGauge({ standard, score, icon: Icon, color }: {
  standard: string;
  score: number;
  icon: React.ElementType;
  color: string;
}) {
  return (
    <div className="flex items-center gap-3 p-3 bg-slate-800/50 rounded-xl">
      <div className={`p-2 rounded-lg ${color}`}>
        <Icon className="w-4 h-4 text-white" />
      </div>
      <div className="flex-grow min-w-0">
        <div className="flex justify-between text-sm mb-1">
          <span className="text-slate-300 truncate">{standard}</span>
          <span className="text-white font-medium">{score}%</span>
        </div>
        <div className="w-full bg-slate-700 rounded-full h-2">
          <div 
            className={`h-2 rounded-full ${color}`}
            style={{ width: `${score}%` }}
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

  const getColor = (type: string) => {
    switch (type) {
      case 'incident': return 'text-red-400 bg-red-500/20';
      case 'rta': return 'text-orange-400 bg-orange-500/20';
      case 'complaint': return 'text-purple-400 bg-purple-500/20';
      case 'audit': return 'text-blue-400 bg-blue-500/20';
      case 'action': return 'text-teal-400 bg-teal-500/20';
      default: return 'text-slate-400 bg-slate-500/20';
    }
  };

  return (
    <div className="space-y-3">
      {activities.map((activity) => {
        const Icon = getIcon(activity.type);
        const colorClass = getColor(activity.type);
        return (
          <div key={activity.id} className="flex items-start gap-3 p-3 bg-slate-800/30 rounded-xl hover:bg-slate-800/50 transition-colors">
            <div className={`p-2 rounded-lg ${colorClass}`}>
              <Icon className="w-4 h-4" />
            </div>
            <div className="flex-grow min-w-0">
              <p className="text-sm text-white truncate">{activity.title}</p>
              <p className="text-xs text-slate-500">{activity.time}</p>
            </div>
            <span className={`text-xs px-2 py-1 rounded-full ${
              activity.status === 'open' ? 'bg-red-500/20 text-red-400' :
              activity.status === 'in_progress' ? 'bg-amber-500/20 text-amber-400' :
              'bg-emerald-500/20 text-emerald-400'
            }`}>
              {activity.status}
            </span>
          </div>
        );
      })}
    </div>
  );
}

function UpcomingEvents() {
  const events = [
    { id: 1, title: 'UVDB B2 Audit', date: 'Mar 15', type: 'audit', days: 54 },
    { id: 2, title: 'ISO Surveillance Audit', date: 'Mar 15', type: 'audit', days: 54 },
    { id: 3, title: 'Management Review', date: 'Feb 28', type: 'meeting', days: 39 },
    { id: 4, title: 'Planet Mark Submission', date: 'Jun 30', type: 'deadline', days: 161 },
  ];

  return (
    <div className="space-y-2">
      {events.map((event) => (
        <div key={event.id} className="flex items-center gap-3 p-3 bg-slate-800/30 rounded-xl">
          <div className="p-2 rounded-lg bg-blue-500/20">
            <Calendar className="w-4 h-4 text-blue-400" />
          </div>
          <div className="flex-grow">
            <p className="text-sm text-white">{event.title}</p>
            <p className="text-xs text-slate-500">{event.date}</p>
          </div>
          <span className={`text-xs px-2 py-1 rounded-full ${
            event.days <= 7 ? 'bg-red-500/20 text-red-400' :
            event.days <= 30 ? 'bg-amber-500/20 text-amber-400' :
            'bg-slate-500/20 text-slate-400'
          }`}>
            {event.days}d
          </span>
        </div>
      ))}
    </div>
  );
}

// ============================================================================
// Main Dashboard Component
// ============================================================================

export default function Dashboard() {
  const [incidents, setIncidents] = useState<Incident[]>([])
  const [loading, setLoading] = useState(true)
  const [stats, setStats] = useState<ModuleStats>({
    incidents: { total: 0, open: 0, critical: 0, trend: 0 },
    rtas: { total: 0, open: 0, trend: 0 },
    complaints: { total: 0, open: 0, overdue: 0, trend: 0 },
    audits: { scheduled: 0, completed: 0, avgScore: 0, trend: 0 },
    actions: { total: 0, overdue: 0, dueSoon: 0, trend: 0 },
    risks: { total: 0, high: 0, outsideAppetite: 0 },
    compliance: { iso9001: 94, iso14001: 91, iso45001: 96, iso27001: 89 },
    carbon: { totalEmissions: 278.5, perFTE: 4.06, trend: -5 },
  })
  const [activities, setActivities] = useState<RecentActivity[]>([])

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      const response = await incidentsApi.list(1, 100)
      const items = response.data.items
      setIncidents(items.slice(0, 5))
      
      // Calculate stats from real data + simulated for other modules
      setStats({
        incidents: {
          total: response.data.total,
          open: items.filter(i => i.status !== 'closed').length,
          critical: items.filter(i => i.severity === 'critical' || i.severity === 'high').length,
          trend: -12,
        },
        rtas: { total: 15, open: 3, trend: -8 },
        complaints: { total: 42, open: 8, overdue: 2, trend: 5 },
        audits: { scheduled: 7, completed: 23, avgScore: 87, trend: 3 },
        actions: { total: 156, overdue: 12, dueSoon: 24, trend: -15 },
        risks: { total: 67, high: 8, outsideAppetite: 3 },
        compliance: { iso9001: 94, iso14001: 91, iso45001: 96, iso27001: 89 },
        carbon: { totalEmissions: 278.5, perFTE: 4.06, trend: -5 },
      })

      // Generate recent activities
      setActivities([
        { id: '1', type: 'incident', title: 'Slip hazard reported - Warehouse B', time: '10 mins ago', status: 'open', severity: 'medium' },
        { id: '2', type: 'audit', title: 'ISO 9001 Internal Audit completed', time: '2 hours ago', status: 'completed' },
        { id: '3', type: 'action', title: 'CAPA-2026-015 marked complete', time: '3 hours ago', status: 'completed' },
        { id: '4', type: 'complaint', title: 'Customer delivery delay complaint', time: '5 hours ago', status: 'in_progress' },
        { id: '5', type: 'rta', title: 'Minor vehicle incident - PLT-042', time: 'Yesterday', status: 'in_progress' },
      ])
    } catch (err) {
      console.error('Failed to load dashboard data:', err)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-8 h-8 text-emerald-500 animate-spin" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-white">Dashboard</h1>
          <p className="text-slate-400">Quality Governance Platform Overview</p>
        </div>
        <div className="flex gap-3">
          <Link 
            to="/notifications" 
            className="flex items-center gap-2 px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg transition-colors"
          >
            <Bell className="w-4 h-4" />
            <span className="hidden sm:inline">Notifications</span>
            <span className="px-2 py-0.5 bg-red-500 text-white text-xs rounded-full">5</span>
          </Link>
          <button 
            onClick={loadData}
            className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 rounded-lg transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
        </div>
      </div>

      {/* Primary Stats Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard 
          title="Open Incidents" 
          value={stats.incidents.open}
          icon={AlertTriangle} 
          color="red"
          trend={stats.incidents.trend}
          link="/incidents"
          subtitle={`${stats.incidents.critical} critical`}
        />
        <StatCard 
          title="Open RTAs" 
          value={stats.rtas.open}
          icon={Car} 
          color="orange"
          trend={stats.rtas.trend}
          link="/rtas"
        />
        <StatCard 
          title="Open Complaints" 
          value={stats.complaints.open}
          icon={MessageSquare} 
          color="purple"
          trend={stats.complaints.trend}
          link="/complaints"
          subtitle={`${stats.complaints.overdue} overdue`}
        />
        <StatCard 
          title="Overdue Actions" 
          value={stats.actions.overdue}
          icon={Zap} 
          color="amber"
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
          color="blue"
          trend={stats.audits.trend}
          link="/audits"
          subtitle={`${stats.audits.completed} completed this year`}
        />
        <StatCard 
          title="High Risks" 
          value={stats.risks.high}
          icon={Target} 
          color="red"
          link="/risk-register"
          subtitle={`${stats.risks.outsideAppetite} outside appetite`}
        />
        <StatCard 
          title="Carbon (tCO₂e/FTE)" 
          value={stats.carbon.perFTE.toFixed(2)}
          icon={Leaf} 
          color="teal"
          trend={stats.carbon.trend}
          link="/planet-mark"
          subtitle={`${stats.carbon.totalEmissions} total tCO₂e`}
        />
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Compliance Overview */}
        <div className="bg-slate-800/50 backdrop-blur-xl rounded-2xl border border-slate-700 p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-white">IMS Compliance</h2>
            <Link to="/ims" className="text-emerald-400 hover:text-emerald-300 text-sm flex items-center gap-1">
              View All <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
          <div className="space-y-3">
            <ComplianceGauge standard="ISO 9001:2015" score={stats.compliance.iso9001} icon={Shield} color="bg-blue-500" />
            <ComplianceGauge standard="ISO 14001:2015" score={stats.compliance.iso14001} icon={Leaf} color="bg-emerald-500" />
            <ComplianceGauge standard="ISO 45001:2018" score={stats.compliance.iso45001} icon={AlertCircle} color="bg-orange-500" />
            <ComplianceGauge standard="ISO 27001:2022" score={stats.compliance.iso27001} icon={Lock} color="bg-purple-500" />
          </div>
        </div>

        {/* Recent Activity */}
        <div className="bg-slate-800/50 backdrop-blur-xl rounded-2xl border border-slate-700 p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-white">Recent Activity</h2>
            <Link to="/audit-trail" className="text-emerald-400 hover:text-emerald-300 text-sm flex items-center gap-1">
              View All <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
          <ActivityFeed activities={activities} />
        </div>

        {/* Upcoming Events */}
        <div className="bg-slate-800/50 backdrop-blur-xl rounded-2xl border border-slate-700 p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-white">Upcoming Events</h2>
            <Link to="/calendar" className="text-emerald-400 hover:text-emerald-300 text-sm flex items-center gap-1">
              View All <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
          <UpcomingEvents />
        </div>
      </div>

      {/* Recent Incidents Table */}
      <div className="bg-slate-800/50 backdrop-blur-xl rounded-2xl border border-slate-700 p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-white">Recent Incidents</h2>
          <Link to="/incidents" className="text-emerald-400 hover:text-emerald-300 text-sm flex items-center gap-1">
            View All <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-slate-700">
                <th className="text-left py-3 px-4 text-sm font-medium text-slate-400">Reference</th>
                <th className="text-left py-3 px-4 text-sm font-medium text-slate-400">Title</th>
                <th className="text-left py-3 px-4 text-sm font-medium text-slate-400">Severity</th>
                <th className="text-left py-3 px-4 text-sm font-medium text-slate-400">Status</th>
                <th className="text-left py-3 px-4 text-sm font-medium text-slate-400">Date</th>
              </tr>
            </thead>
            <tbody>
              {incidents.length === 0 ? (
                <tr>
                  <td colSpan={5} className="text-center py-8 text-slate-500">
                    No incidents found
                  </td>
                </tr>
              ) : (
                incidents.map((incident) => (
                  <tr key={incident.id} className="border-b border-slate-700/50 hover:bg-slate-700/30">
                    <td className="py-3 px-4 text-sm text-emerald-400 font-mono">{incident.reference_number}</td>
                    <td className="py-3 px-4 text-sm text-white">{incident.title}</td>
                    <td className="py-3 px-4">
                      <span className={`text-xs px-2 py-1 rounded-full ${
                        incident.severity === 'critical' ? 'bg-red-500/20 text-red-400' :
                        incident.severity === 'high' ? 'bg-orange-500/20 text-orange-400' :
                        incident.severity === 'medium' ? 'bg-amber-500/20 text-amber-400' :
                        'bg-slate-500/20 text-slate-400'
                      }`}>
                        {incident.severity}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span className={`text-xs px-2 py-1 rounded-full ${
                        incident.status === 'closed' ? 'bg-emerald-500/20 text-emerald-400' :
                        incident.status === 'under_investigation' ? 'bg-amber-500/20 text-amber-400' :
                        'bg-blue-500/20 text-blue-400'
                      }`}>
                        {incident.status.replace('_', ' ')}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-sm text-slate-400">
                      {new Date(incident.created_at).toLocaleDateString()}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Link 
          to="/incidents" 
          className="flex items-center gap-3 p-4 bg-gradient-to-br from-red-500/20 to-red-600/20 border border-red-500/30 rounded-xl hover:bg-red-500/30 transition-colors"
        >
          <AlertTriangle className="w-5 h-5 text-red-400" />
          <span className="text-white font-medium">New Incident</span>
        </Link>
        <Link 
          to="/audits" 
          className="flex items-center gap-3 p-4 bg-gradient-to-br from-blue-500/20 to-blue-600/20 border border-blue-500/30 rounded-xl hover:bg-blue-500/30 transition-colors"
        >
          <ClipboardCheck className="w-5 h-5 text-blue-400" />
          <span className="text-white font-medium">Start Audit</span>
        </Link>
        <Link 
          to="/analytics" 
          className="flex items-center gap-3 p-4 bg-gradient-to-br from-purple-500/20 to-purple-600/20 border border-purple-500/30 rounded-xl hover:bg-purple-500/30 transition-colors"
        >
          <BarChart3 className="w-5 h-5 text-purple-400" />
          <span className="text-white font-medium">View Analytics</span>
        </Link>
        <Link 
          to="/compliance" 
          className="flex items-center gap-3 p-4 bg-gradient-to-br from-emerald-500/20 to-emerald-600/20 border border-emerald-500/30 rounded-xl hover:bg-emerald-500/30 transition-colors"
        >
          <Shield className="w-5 h-5 text-emerald-400" />
          <span className="text-white font-medium">Compliance</span>
        </Link>
      </div>
    </div>
  )
}
