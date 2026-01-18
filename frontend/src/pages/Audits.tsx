import { useEffect, useState } from 'react'
import { Plus, X, ClipboardCheck, Search, Calendar, MapPin, Target, AlertCircle, CheckCircle2, Clock, BarChart3 } from 'lucide-react'
import { auditsApi, AuditRun, AuditFinding } from '../api/client'

type ViewMode = 'kanban' | 'list' | 'findings'

const KANBAN_COLUMNS = [
  { id: 'scheduled', label: 'Scheduled', color: 'from-blue-500 to-blue-600', icon: Calendar },
  { id: 'in_progress', label: 'In Progress', color: 'from-amber-500 to-orange-500', icon: Clock },
  { id: 'pending_review', label: 'Pending Review', color: 'from-purple-500 to-pink-500', icon: Target },
  { id: 'completed', label: 'Completed', color: 'from-emerald-500 to-green-500', icon: CheckCircle2 },
]

export default function Audits() {
  const [audits, setAudits] = useState<AuditRun[]>([])
  const [findings, setFindings] = useState<AuditFinding[]>([])
  const [loading, setLoading] = useState(true)
  const [viewMode, setViewMode] = useState<ViewMode>('kanban')
  const [searchTerm, setSearchTerm] = useState('')
  const [showModal, setShowModal] = useState(false)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      const [auditsRes, findingsRes] = await Promise.all([
        auditsApi.listRuns(1, 100),
        auditsApi.listFindings(1, 100),
      ])
      setAudits(auditsRes.data.items || [])
      setFindings(findingsRes.data.items || [])
    } catch (err) {
      console.error('Failed to load audits:', err)
      setAudits([])
      setFindings([])
    } finally {
      setLoading(false)
    }
  }

  const getAuditsByStatus = (status: string) => {
    return audits.filter(a => a.status === status)
  }

  const getScoreColor = (percentage?: number) => {
    if (!percentage) return 'text-slate-400'
    if (percentage >= 90) return 'text-emerald-400'
    if (percentage >= 70) return 'text-amber-400'
    return 'text-red-400'
  }

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'critical': return 'bg-red-500/20 text-red-400 border-red-500/30'
      case 'high': return 'bg-orange-500/20 text-orange-400 border-orange-500/30'
      case 'medium': return 'bg-amber-500/20 text-amber-400 border-amber-500/30'
      case 'low': return 'bg-green-500/20 text-green-400 border-green-500/30'
      case 'observation': return 'bg-blue-500/20 text-blue-400 border-blue-500/30'
      default: return 'bg-slate-500/20 text-slate-400 border-slate-500/30'
    }
  }

  const getFindingStatusColor = (status: string) => {
    switch (status) {
      case 'closed': return 'bg-emerald-500/20 text-emerald-400'
      case 'open': return 'bg-red-500/20 text-red-400'
      case 'in_progress': return 'bg-amber-500/20 text-amber-400'
      case 'pending_verification': return 'bg-purple-500/20 text-purple-400'
      case 'deferred': return 'bg-slate-500/20 text-slate-400'
      default: return 'bg-slate-500/20 text-slate-400'
    }
  }

  const stats = {
    total: audits.length,
    inProgress: audits.filter(a => a.status === 'in_progress').length,
    completed: audits.filter(a => a.status === 'completed').length,
    avgScore: audits.filter(a => a.score_percentage).reduce((acc, a) => acc + (a.score_percentage || 0), 0) / 
              (audits.filter(a => a.score_percentage).length || 1),
    openFindings: findings.filter(f => f.status === 'open').length,
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="relative">
          <div className="animate-spin rounded-full h-16 w-16 border-4 border-indigo-500/20 border-t-indigo-500"></div>
          <ClipboardCheck className="absolute inset-0 m-auto w-6 h-6 text-indigo-400" />
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold bg-gradient-to-r from-indigo-400 via-purple-400 to-pink-400 bg-clip-text text-transparent">
            Audit Management
          </h1>
          <p className="text-slate-400 mt-1">Internal audits, inspections & compliance checks</p>
        </div>
        <div className="flex items-center gap-3">
          {/* View Toggle */}
          <div className="flex bg-slate-800/50 rounded-xl p-1">
            {(['kanban', 'list', 'findings'] as ViewMode[]).map((mode) => (
              <button
                key={mode}
                onClick={() => setViewMode(mode)}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 ${
                  viewMode === mode 
                    ? 'bg-indigo-500 text-white shadow-lg shadow-indigo-500/25' 
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                {mode === 'kanban' ? 'Board' : mode === 'findings' ? 'Findings' : 'List'}
              </button>
            ))}
          </div>
          <button
            onClick={() => setShowModal(true)}
            className="inline-flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500
              text-white font-semibold rounded-xl hover:opacity-90 transition-all duration-200 
              shadow-lg shadow-indigo-500/25 hover:shadow-xl hover:shadow-indigo-500/30 hover:-translate-y-0.5"
          >
            <Plus size={20} />
            New Audit
          </button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        {[
          { label: 'Total Audits', value: stats.total, icon: ClipboardCheck, color: 'from-indigo-500 to-purple-500' },
          { label: 'In Progress', value: stats.inProgress, icon: Clock, color: 'from-amber-500 to-orange-500' },
          { label: 'Completed', value: stats.completed, icon: CheckCircle2, color: 'from-emerald-500 to-green-500' },
          { label: 'Avg Score', value: `${stats.avgScore.toFixed(0)}%`, icon: BarChart3, color: 'from-cyan-500 to-blue-500' },
          { label: 'Open Findings', value: stats.openFindings, icon: AlertCircle, color: 'from-red-500 to-pink-500' },
        ].map((stat, index) => (
          <div 
            key={stat.label}
            className="relative overflow-hidden bg-slate-900/50 backdrop-blur-xl border border-slate-800 rounded-2xl p-5 
              hover:border-slate-700 transition-all duration-300 group animate-slide-in"
            style={{ animationDelay: `${index * 50}ms` }}
          >
            <div className={`absolute inset-0 bg-gradient-to-br ${stat.color} opacity-0 group-hover:opacity-5 transition-opacity`} />
            <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${stat.color} flex items-center justify-center mb-3`}>
              <stat.icon className="w-5 h-5 text-white" />
            </div>
            <p className="text-2xl font-bold text-white">{stat.value}</p>
            <p className="text-sm text-slate-400">{stat.label}</p>
          </div>
        ))}
      </div>

      {/* Search */}
      <div className="relative max-w-md">
        <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-500" />
        <input
          type="text"
          placeholder="Search audits..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="w-full pl-12 pr-4 py-3 bg-slate-900/50 border border-slate-800 rounded-xl
            text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500
            focus:ring-2 focus:ring-indigo-500/20 transition-all duration-200"
        />
      </div>

      {/* Kanban View */}
      {viewMode === 'kanban' && (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6">
          {KANBAN_COLUMNS.map((column, colIndex) => {
            const columnAudits = getAuditsByStatus(column.id)
            return (
              <div 
                key={column.id} 
                className="animate-slide-in"
                style={{ animationDelay: `${colIndex * 100}ms` }}
              >
                {/* Column Header */}
                <div className="flex items-center gap-3 mb-4">
                  <div className={`w-8 h-8 rounded-lg bg-gradient-to-br ${column.color} flex items-center justify-center`}>
                    <column.icon className="w-4 h-4 text-white" />
                  </div>
                  <h3 className="font-semibold text-white">{column.label}</h3>
                  <span className="ml-auto px-2.5 py-1 bg-slate-800 rounded-full text-xs font-medium text-slate-400">
                    {columnAudits.length}
                  </span>
                </div>

                {/* Column Content */}
                <div className="space-y-3 min-h-[200px] bg-slate-900/30 rounded-2xl p-3 border border-slate-800/50">
                  {columnAudits.length === 0 ? (
                    <div className="flex items-center justify-center h-32 text-slate-600">
                      <p className="text-sm">No audits</p>
                    </div>
                  ) : (
                    columnAudits.map((audit, index) => (
                      <div
                        key={audit.id}
                        className="bg-slate-800/50 backdrop-blur border border-slate-700/50 rounded-xl p-4 
                          hover:border-indigo-500/30 hover:bg-slate-800/70 transition-all duration-200 
                          cursor-pointer group animate-fade-in"
                        style={{ animationDelay: `${index * 50}ms` }}
                      >
                        <div className="flex items-start justify-between mb-2">
                          <span className="font-mono text-xs text-indigo-400">{audit.reference_number}</span>
                          {audit.score_percentage !== undefined && (
                            <span className={`text-sm font-bold ${getScoreColor(audit.score_percentage)}`}>
                              {audit.score_percentage.toFixed(0)}%
                            </span>
                          )}
                        </div>
                        <h4 className="font-medium text-white text-sm mb-2 line-clamp-2 group-hover:text-indigo-300 transition-colors">
                          {audit.title || 'Untitled Audit'}
                        </h4>
                        {audit.location && (
                          <div className="flex items-center gap-1.5 text-xs text-slate-400 mb-2">
                            <MapPin size={12} />
                            <span className="truncate">{audit.location}</span>
                          </div>
                        )}
                        {audit.scheduled_date && (
                          <div className="flex items-center gap-1.5 text-xs text-slate-500">
                            <Calendar size={12} />
                            <span>{new Date(audit.scheduled_date).toLocaleDateString()}</span>
                          </div>
                        )}
                      </div>
                    ))
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* List View */}
      {viewMode === 'list' && (
        <div className="bg-slate-900/50 backdrop-blur-xl border border-slate-800 rounded-2xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-slate-800">
                  <th className="px-6 py-4 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">Reference</th>
                  <th className="px-6 py-4 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">Title</th>
                  <th className="px-6 py-4 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">Location</th>
                  <th className="px-6 py-4 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">Status</th>
                  <th className="px-6 py-4 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">Score</th>
                  <th className="px-6 py-4 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">Date</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {audits.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-6 py-12 text-center text-slate-400">
                      <ClipboardCheck className="w-12 h-12 mx-auto mb-4 text-slate-600" />
                      <p>No audits found</p>
                    </td>
                  </tr>
                ) : (
                  audits.map((audit, index) => (
                    <tr
                      key={audit.id}
                      className="hover:bg-slate-800/30 transition-colors animate-slide-in cursor-pointer"
                      style={{ animationDelay: `${index * 30}ms` }}
                    >
                      <td className="px-6 py-4">
                        <span className="font-mono text-sm text-indigo-400">{audit.reference_number}</span>
                      </td>
                      <td className="px-6 py-4">
                        <p className="text-sm font-medium text-white truncate max-w-xs">{audit.title || 'Untitled'}</p>
                      </td>
                      <td className="px-6 py-4 text-sm text-slate-300">{audit.location || '-'}</td>
                      <td className="px-6 py-4">
                        <span className={`px-2.5 py-1 text-xs font-medium rounded-lg 
                          ${audit.status === 'completed' ? 'bg-emerald-500/20 text-emerald-400' :
                            audit.status === 'in_progress' ? 'bg-amber-500/20 text-amber-400' :
                            audit.status === 'pending_review' ? 'bg-purple-500/20 text-purple-400' :
                            'bg-blue-500/20 text-blue-400'}`}>
                          {audit.status.replace('_', ' ')}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        {audit.score_percentage !== undefined ? (
                          <span className={`font-bold ${getScoreColor(audit.score_percentage)}`}>
                            {audit.score_percentage.toFixed(0)}%
                          </span>
                        ) : (
                          <span className="text-slate-500">-</span>
                        )}
                      </td>
                      <td className="px-6 py-4 text-sm text-slate-400">
                        {audit.scheduled_date ? new Date(audit.scheduled_date).toLocaleDateString() : '-'}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Findings View */}
      {viewMode === 'findings' && (
        <div className="space-y-4">
          {findings.length === 0 ? (
            <div className="bg-slate-900/50 backdrop-blur-xl border border-slate-800 rounded-2xl p-12 text-center">
              <AlertCircle className="w-12 h-12 mx-auto mb-4 text-slate-600" />
              <p className="text-slate-400">No findings recorded</p>
            </div>
          ) : (
            findings.map((finding, index) => (
              <div
                key={finding.id}
                className="bg-slate-900/50 backdrop-blur-xl border border-slate-800 rounded-2xl p-5
                  hover:border-slate-700 transition-all duration-200 animate-slide-in"
                style={{ animationDelay: `${index * 50}ms` }}
              >
                <div className="flex items-start gap-4">
                  <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${
                    finding.severity === 'critical' ? 'bg-red-500/20' :
                    finding.severity === 'high' ? 'bg-orange-500/20' :
                    finding.severity === 'medium' ? 'bg-amber-500/20' : 'bg-green-500/20'
                  }`}>
                    <AlertCircle className={`w-6 h-6 ${
                      finding.severity === 'critical' ? 'text-red-400' :
                      finding.severity === 'high' ? 'text-orange-400' :
                      finding.severity === 'medium' ? 'text-amber-400' : 'text-green-400'
                    }`} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 mb-2">
                      <span className="font-mono text-xs text-indigo-400">{finding.reference_number}</span>
                      <span className={`px-2 py-0.5 text-xs font-medium rounded border ${getSeverityColor(finding.severity)}`}>
                        {finding.severity}
                      </span>
                      <span className={`px-2 py-0.5 text-xs font-medium rounded ${getFindingStatusColor(finding.status)}`}>
                        {finding.status.replace('_', ' ')}
                      </span>
                    </div>
                    <h3 className="font-semibold text-white mb-1">{finding.title}</h3>
                    <p className="text-sm text-slate-400 line-clamp-2">{finding.description}</p>
                    {finding.corrective_action_due_date && (
                      <div className="mt-3 flex items-center gap-2 text-xs text-slate-500">
                        <Calendar size={14} />
                        <span>Due: {new Date(finding.corrective_action_due_date).toLocaleDateString()}</span>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* Create Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setShowModal(false)} />
          <div className="relative w-full max-w-lg bg-slate-900 border border-slate-800 rounded-2xl shadow-xl animate-fade-in">
            <div className="flex items-center justify-between p-6 border-b border-slate-800">
              <h2 className="text-lg font-semibold text-white">Schedule New Audit</h2>
              <button
                onClick={() => setShowModal(false)}
                className="p-2 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
              >
                <X size={20} />
              </button>
            </div>
            <div className="p-6">
              <p className="text-slate-400 text-center py-8">
                Audit scheduling coming soon. Use the API to create audits.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
