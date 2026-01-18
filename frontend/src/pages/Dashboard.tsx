import { useEffect, useState } from 'react'
import { AlertTriangle, CheckCircle, Clock, TrendingUp, AlertCircle } from 'lucide-react'
import { incidentsApi, Incident } from '../api/client'

interface StatCardProps {
  title: string
  value: string | number
  icon: React.ElementType
  color: 'emerald' | 'amber' | 'red' | 'blue'
  trend?: string
}

function StatCard({ title, value, icon: Icon, color, trend }: StatCardProps) {
  const colors = {
    emerald: 'from-emerald-500/20 to-emerald-600/20 border-emerald-500/30 text-emerald-400',
    amber: 'from-amber-500/20 to-amber-600/20 border-amber-500/30 text-amber-400',
    red: 'from-red-500/20 to-red-600/20 border-red-500/30 text-red-400',
    blue: 'from-blue-500/20 to-blue-600/20 border-blue-500/30 text-blue-400',
  }

  return (
    <div className={`
      relative overflow-hidden rounded-2xl border bg-gradient-to-br p-6
      ${colors[color]} backdrop-blur-xl
    `}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-medium text-slate-400">{title}</p>
          <p className="mt-2 text-3xl font-bold text-white">{value}</p>
          {trend && (
            <p className="mt-2 text-sm text-slate-400 flex items-center gap-1">
              <TrendingUp size={14} />
              {trend}
            </p>
          )}
        </div>
        <div className={`p-3 rounded-xl bg-gradient-to-br ${colors[color].replace('text-', 'from-').replace('-400', '-500/20')} ${colors[color].replace('text-', 'to-').replace('-400', '-600/20')}`}>
          <Icon size={24} className={colors[color].split(' ').pop()} />
        </div>
      </div>
    </div>
  )
}

export default function Dashboard() {
  const [incidents, setIncidents] = useState<Incident[]>([])
  const [loading, setLoading] = useState(true)
  const [stats, setStats] = useState({
    total: 0,
    open: 0,
    closed: 0,
    critical: 0,
  })

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      const response = await incidentsApi.list(1, 100)
      const items = response.data.items
      setIncidents(items.slice(0, 5))
      setStats({
        total: response.data.total,
        open: items.filter(i => i.status !== 'closed').length,
        closed: items.filter(i => i.status === 'closed').length,
        critical: items.filter(i => i.severity === 'critical' || i.severity === 'high').length,
      })
    } catch (err) {
      console.error('Failed to load incidents:', err)
    } finally {
      setLoading(false)
    }
  }

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'critical': return 'bg-red-500/20 text-red-400 border-red-500/30'
      case 'high': return 'bg-orange-500/20 text-orange-400 border-orange-500/30'
      case 'medium': return 'bg-amber-500/20 text-amber-400 border-amber-500/30'
      default: return 'bg-slate-500/20 text-slate-400 border-slate-500/30'
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'closed': return 'bg-emerald-500/20 text-emerald-400'
      case 'reported': return 'bg-blue-500/20 text-blue-400'
      case 'under_investigation': return 'bg-amber-500/20 text-amber-400'
      default: return 'bg-slate-500/20 text-slate-400'
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-emerald-500"></div>
      </div>
    )
  }

  return (
    <div className="space-y-8 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold text-white">Dashboard</h1>
        <p className="text-slate-400 mt-1">Welcome to Quality Governance Platform</p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard
          title="Total Incidents"
          value={stats.total}
          icon={AlertTriangle}
          color="blue"
        />
        <StatCard
          title="Open Incidents"
          value={stats.open}
          icon={Clock}
          color="amber"
        />
        <StatCard
          title="Closed"
          value={stats.closed}
          icon={CheckCircle}
          color="emerald"
        />
        <StatCard
          title="High/Critical"
          value={stats.critical}
          icon={AlertCircle}
          color="red"
        />
      </div>

      {/* Recent Incidents */}
      <div className="bg-slate-900/50 backdrop-blur-xl border border-slate-800 rounded-2xl overflow-hidden">
        <div className="p-6 border-b border-slate-800">
          <h2 className="text-lg font-semibold text-white">Recent Incidents</h2>
        </div>
        <div className="divide-y divide-slate-800">
          {incidents.length === 0 ? (
            <div className="p-8 text-center text-slate-400">
              No incidents found. Create your first incident to get started.
            </div>
          ) : (
            incidents.map((incident, index) => (
              <div
                key={incident.id}
                className="p-4 hover:bg-slate-800/30 transition-colors animate-slide-in"
                style={{ animationDelay: `${index * 50}ms` }}
              >
                <div className="flex items-center justify-between">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3">
                      <span className="text-xs font-mono text-slate-500">{incident.reference_number}</span>
                      <span className={`px-2 py-0.5 text-xs rounded-full border ${getSeverityColor(incident.severity)}`}>
                        {incident.severity}
                      </span>
                    </div>
                    <h3 className="mt-1 text-sm font-medium text-white truncate">{incident.title}</h3>
                    <p className="mt-1 text-xs text-slate-500">
                      {new Date(incident.incident_date).toLocaleDateString()}
                    </p>
                  </div>
                  <span className={`px-3 py-1 text-xs rounded-lg ${getStatusColor(incident.status)}`}>
                    {incident.status.replace('_', ' ')}
                  </span>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
