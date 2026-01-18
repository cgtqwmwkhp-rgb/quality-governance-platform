import { useEffect, useState } from 'react'
import { Search, ListTodo, Plus, X, Calendar, User, Flag, CheckCircle2, Clock, AlertCircle, ArrowUpRight, Filter } from 'lucide-react'

// Mock data for actions - will be replaced with API calls
interface Action {
  id: number
  reference_number: string
  title: string
  description: string
  action_type: string
  priority: 'critical' | 'high' | 'medium' | 'low'
  status: 'open' | 'in_progress' | 'pending_verification' | 'completed' | 'cancelled'
  due_date?: string
  completed_at?: string
  source_type: string
  source_ref: string
  owner?: string
  created_at: string
}

type ViewMode = 'all' | 'my' | 'overdue'
type FilterStatus = 'all' | 'open' | 'in_progress' | 'pending_verification' | 'completed'

const MOCK_ACTIONS: Action[] = [
  {
    id: 1,
    reference_number: 'ACT-2026-0001',
    title: 'Update fire safety procedures',
    description: 'Review and update all fire safety procedures following the recent incident',
    action_type: 'corrective',
    priority: 'high',
    status: 'in_progress',
    due_date: '2026-02-15',
    source_type: 'incident',
    source_ref: 'INC-2026-0042',
    owner: 'John Smith',
    created_at: '2026-01-10',
  },
  {
    id: 2,
    reference_number: 'ACT-2026-0002',
    title: 'Install additional CCTV cameras',
    description: 'Install CCTV coverage in blind spots identified during security audit',
    action_type: 'preventive',
    priority: 'medium',
    status: 'open',
    due_date: '2026-03-01',
    source_type: 'audit',
    source_ref: 'AUD-2026-0015',
    owner: 'Security Team',
    created_at: '2026-01-12',
  },
  {
    id: 3,
    reference_number: 'ACT-2026-0003',
    title: 'Driver re-training program',
    description: 'Mandatory defensive driving training for all fleet drivers',
    action_type: 'corrective',
    priority: 'critical',
    status: 'pending_verification',
    due_date: '2026-01-25',
    source_type: 'rta',
    source_ref: 'RTA-2026-0008',
    owner: 'Fleet Manager',
    created_at: '2026-01-08',
  },
  {
    id: 4,
    reference_number: 'ACT-2026-0004',
    title: 'Customer communication protocol review',
    description: 'Update customer communication templates and response SLAs',
    action_type: 'improvement',
    priority: 'low',
    status: 'completed',
    due_date: '2026-01-20',
    completed_at: '2026-01-18',
    source_type: 'complaint',
    source_ref: 'CMP-2026-0023',
    owner: 'Customer Service',
    created_at: '2026-01-05',
  },
]

export default function Actions() {
  const [actions, setActions] = useState<Action[]>(MOCK_ACTIONS)
  const [loading, setLoading] = useState(false)
  const [viewMode, setViewMode] = useState<ViewMode>('all')
  const [filterStatus, setFilterStatus] = useState<FilterStatus>('all')
  const [searchTerm, setSearchTerm] = useState('')
  const [showModal, setShowModal] = useState(false)

  useEffect(() => {
    // Load actions from API when available
    setLoading(false)
  }, [])

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'critical': return 'from-red-500 to-pink-500'
      case 'high': return 'from-orange-500 to-red-500'
      case 'medium': return 'from-amber-500 to-orange-500'
      case 'low': return 'from-green-500 to-emerald-500'
      default: return 'from-slate-500 to-slate-600'
    }
  }

  const getPriorityBadgeColor = (priority: string) => {
    switch (priority) {
      case 'critical': return 'bg-red-500/20 text-red-400 border-red-500/30'
      case 'high': return 'bg-orange-500/20 text-orange-400 border-orange-500/30'
      case 'medium': return 'bg-amber-500/20 text-amber-400 border-amber-500/30'
      case 'low': return 'bg-green-500/20 text-green-400 border-green-500/30'
      default: return 'bg-slate-500/20 text-slate-400 border-slate-500/30'
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'bg-emerald-500/20 text-emerald-400'
      case 'open': return 'bg-blue-500/20 text-blue-400'
      case 'in_progress': return 'bg-amber-500/20 text-amber-400'
      case 'pending_verification': return 'bg-purple-500/20 text-purple-400'
      case 'cancelled': return 'bg-slate-500/20 text-slate-400'
      default: return 'bg-slate-500/20 text-slate-400'
    }
  }

  const getSourceIcon = (type: string) => {
    switch (type) {
      case 'incident': return '🔥'
      case 'audit': return '📋'
      case 'rta': return '🚗'
      case 'complaint': return '💬'
      case 'risk': return '⚠️'
      default: return '📌'
    }
  }

  const isOverdue = (dueDate?: string, status?: string) => {
    if (!dueDate || status === 'completed' || status === 'cancelled') return false
    return new Date(dueDate) < new Date()
  }

  const filteredActions = actions.filter(action => {
    // Search filter
    if (searchTerm && !action.title.toLowerCase().includes(searchTerm.toLowerCase()) &&
        !action.reference_number.toLowerCase().includes(searchTerm.toLowerCase())) {
      return false
    }
    // Status filter
    if (filterStatus !== 'all' && action.status !== filterStatus) {
      return false
    }
    // View mode filter
    if (viewMode === 'overdue' && !isOverdue(action.due_date, action.status)) {
      return false
    }
    return true
  })

  const stats = {
    total: actions.length,
    open: actions.filter(a => a.status === 'open').length,
    inProgress: actions.filter(a => a.status === 'in_progress').length,
    overdue: actions.filter(a => isOverdue(a.due_date, a.status)).length,
    completed: actions.filter(a => a.status === 'completed').length,
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="relative">
          <div className="animate-spin rounded-full h-16 w-16 border-4 border-teal-500/20 border-t-teal-500"></div>
          <ListTodo className="absolute inset-0 m-auto w-6 h-6 text-teal-400" />
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold bg-gradient-to-r from-teal-400 via-cyan-400 to-blue-400 bg-clip-text text-transparent">
            Action Center
          </h1>
          <p className="text-slate-400 mt-1">Cross-module corrective & preventive actions</p>
        </div>
        <button
          onClick={() => setShowModal(true)}
          className="inline-flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-teal-500 via-cyan-500 to-blue-500
            text-white font-semibold rounded-xl hover:opacity-90 transition-all duration-200 
            shadow-lg shadow-teal-500/25 hover:shadow-xl hover:shadow-teal-500/30 hover:-translate-y-0.5"
        >
          <Plus size={20} />
          New Action
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        {[
          { label: 'Total Actions', value: stats.total, icon: ListTodo, color: 'from-teal-500 to-cyan-500' },
          { label: 'Open', value: stats.open, icon: AlertCircle, color: 'from-blue-500 to-indigo-500' },
          { label: 'In Progress', value: stats.inProgress, icon: Clock, color: 'from-amber-500 to-orange-500' },
          { label: 'Overdue', value: stats.overdue, icon: Flag, color: 'from-red-500 to-pink-500' },
          { label: 'Completed', value: stats.completed, icon: CheckCircle2, color: 'from-emerald-500 to-green-500' },
        ].map((stat, index) => (
          <div 
            key={stat.label}
            className={`relative overflow-hidden bg-slate-900/50 backdrop-blur-xl border border-slate-800 rounded-2xl p-5 
              hover:border-slate-700 transition-all duration-300 cursor-pointer group animate-slide-in
              ${stat.label === 'Overdue' && stats.overdue > 0 ? 'border-red-500/30' : ''}`}
            style={{ animationDelay: `${index * 50}ms` }}
          >
            <div className={`absolute inset-0 bg-gradient-to-br ${stat.color} opacity-0 group-hover:opacity-5 transition-opacity`} />
            <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${stat.color} flex items-center justify-center mb-3`}>
              <stat.icon className="w-5 h-5 text-white" />
            </div>
            <p className="text-2xl font-bold text-white">{stat.value}</p>
            <p className="text-sm text-slate-400">{stat.label}</p>
            {stat.label === 'Overdue' && stats.overdue > 0 && (
              <div className="absolute top-3 right-3 w-3 h-3 bg-red-500 rounded-full animate-pulse" />
            )}
          </div>
        ))}
      </div>

      {/* Filters */}
      <div className="flex flex-col lg:flex-row gap-4">
        {/* Search */}
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-500" />
          <input
            type="text"
            placeholder="Search actions..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-12 pr-4 py-3 bg-slate-900/50 border border-slate-800 rounded-xl
              text-white placeholder-slate-500 focus:outline-none focus:border-teal-500
              focus:ring-2 focus:ring-teal-500/20 transition-all duration-200"
          />
        </div>

        {/* View Mode Toggle */}
        <div className="flex bg-slate-800/50 rounded-xl p-1">
          {(['all', 'my', 'overdue'] as ViewMode[]).map((mode) => (
            <button
              key={mode}
              onClick={() => setViewMode(mode)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 ${
                viewMode === mode 
                  ? 'bg-teal-500 text-white shadow-lg shadow-teal-500/25' 
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              {mode === 'my' ? 'My Actions' : mode.charAt(0).toUpperCase() + mode.slice(1)}
            </button>
          ))}
        </div>

        {/* Status Filter */}
        <div className="relative">
          <Filter className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value as FilterStatus)}
            className="pl-10 pr-8 py-3 bg-slate-900/50 border border-slate-800 rounded-xl
              text-white focus:outline-none focus:border-teal-500 appearance-none cursor-pointer"
          >
            <option value="all">All Status</option>
            <option value="open">Open</option>
            <option value="in_progress">In Progress</option>
            <option value="pending_verification">Pending Verification</option>
            <option value="completed">Completed</option>
          </select>
        </div>
      </div>

      {/* Actions List */}
      <div className="space-y-4">
        {filteredActions.length === 0 ? (
          <div className="bg-slate-900/50 backdrop-blur-xl border border-slate-800 rounded-2xl p-12 text-center">
            <ListTodo className="w-16 h-16 mx-auto mb-4 text-slate-600" />
            <h3 className="text-lg font-semibold text-white mb-2">No Actions Found</h3>
            <p className="text-slate-400">
              {filterStatus !== 'all' || viewMode !== 'all' 
                ? 'Try adjusting your filters' 
                : 'Actions from incidents, audits, and investigations will appear here'}
            </p>
          </div>
        ) : (
          filteredActions.map((action, index) => {
            const overdue = isOverdue(action.due_date, action.status)
            
            return (
              <div
                key={action.id}
                className={`bg-slate-900/50 backdrop-blur-xl border rounded-2xl overflow-hidden
                  hover:shadow-lg transition-all duration-300 cursor-pointer group animate-slide-in
                  ${overdue ? 'border-red-500/30 hover:border-red-500/50' : 'border-slate-800 hover:border-slate-700'}`}
                style={{ animationDelay: `${index * 50}ms` }}
              >
                <div className="flex items-stretch">
                  {/* Priority Bar */}
                  <div className={`w-1.5 bg-gradient-to-b ${getPriorityColor(action.priority)}`} />
                  
                  <div className="flex-1 p-5">
                    <div className="flex flex-col lg:flex-row lg:items-center gap-4">
                      {/* Main Content */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-3 mb-2">
                          <span className="font-mono text-sm text-teal-400">{action.reference_number}</span>
                          <span className={`px-2 py-0.5 text-xs font-medium rounded border ${getPriorityBadgeColor(action.priority)}`}>
                            {action.priority}
                          </span>
                          <span className={`px-2 py-0.5 text-xs font-medium rounded ${getStatusColor(action.status)}`}>
                            {action.status.replace('_', ' ')}
                          </span>
                          {overdue && (
                            <span className="px-2 py-0.5 text-xs font-medium rounded bg-red-500/20 text-red-400 animate-pulse">
                              OVERDUE
                            </span>
                          )}
                        </div>
                        <h3 className="text-lg font-semibold text-white group-hover:text-teal-300 transition-colors mb-1">
                          {action.title}
                        </h3>
                        <p className="text-sm text-slate-400 line-clamp-1">{action.description}</p>
                      </div>

                      {/* Meta Info */}
                      <div className="flex flex-wrap lg:flex-col items-start lg:items-end gap-2 lg:gap-1 lg:w-48 flex-shrink-0">
                        {/* Source */}
                        <div className="flex items-center gap-2 px-3 py-1.5 bg-slate-800/50 rounded-lg">
                          <span className="text-lg">{getSourceIcon(action.source_type)}</span>
                          <span className="text-xs font-mono text-slate-400">{action.source_ref}</span>
                          <ArrowUpRight className="w-3 h-3 text-slate-500" />
                        </div>

                        {/* Due Date */}
                        {action.due_date && (
                          <div className={`flex items-center gap-2 text-sm ${overdue ? 'text-red-400' : 'text-slate-400'}`}>
                            <Calendar className="w-4 h-4" />
                            <span>Due {new Date(action.due_date).toLocaleDateString()}</span>
                          </div>
                        )}

                        {/* Owner */}
                        {action.owner && (
                          <div className="flex items-center gap-2 text-sm text-slate-500">
                            <User className="w-4 h-4" />
                            <span>{action.owner}</span>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )
          })
        )}
      </div>

      {/* Create Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setShowModal(false)} />
          <div className="relative w-full max-w-lg bg-slate-900 border border-slate-800 rounded-2xl shadow-xl animate-fade-in">
            <div className="flex items-center justify-between p-6 border-b border-slate-800">
              <h2 className="text-lg font-semibold text-white">Create New Action</h2>
              <button
                onClick={() => setShowModal(false)}
                className="p-2 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
              >
                <X size={20} />
              </button>
            </div>
            <form className="p-6 space-y-5">
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">Title</label>
                <input
                  type="text"
                  placeholder="Action title..."
                  className="w-full px-4 py-3 bg-slate-800/50 border border-slate-700 rounded-xl
                    text-white placeholder-slate-500 focus:outline-none focus:border-teal-500
                    focus:ring-2 focus:ring-teal-500/20 transition-all duration-200"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">Description</label>
                <textarea
                  rows={3}
                  placeholder="Describe the action required..."
                  className="w-full px-4 py-3 bg-slate-800/50 border border-slate-700 rounded-xl
                    text-white placeholder-slate-500 focus:outline-none focus:border-teal-500
                    focus:ring-2 focus:ring-teal-500/20 transition-all duration-200 resize-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-2">Priority</label>
                  <select className="w-full px-4 py-3 bg-slate-800/50 border border-slate-700 rounded-xl
                    text-white focus:outline-none focus:border-teal-500">
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                    <option value="critical">Critical</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-2">Due Date</label>
                  <input
                    type="date"
                    className="w-full px-4 py-3 bg-slate-800/50 border border-slate-700 rounded-xl
                      text-white focus:outline-none focus:border-teal-500"
                  />
                </div>
              </div>

              <div className="flex gap-3 pt-4">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="flex-1 px-4 py-3 bg-slate-800 text-slate-300 font-medium rounded-xl
                    hover:bg-slate-700 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="flex-1 px-4 py-3 bg-gradient-to-r from-teal-500 to-cyan-500
                    text-white font-semibold rounded-xl hover:opacity-90 transition-all duration-200"
                >
                  Create Action
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
