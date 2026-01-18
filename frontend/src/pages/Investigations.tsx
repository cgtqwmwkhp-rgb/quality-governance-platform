import { useEffect, useState } from 'react'
import { Plus, X, Search, FlaskConical, ArrowRight, FileQuestion, GitBranch, CheckCircle, Clock, AlertTriangle, Car, MessageSquare } from 'lucide-react'
import { investigationsApi, Investigation } from '../api/client'

const STATUS_STEPS = [
  { id: 'draft', label: 'Draft', icon: FileQuestion },
  { id: 'in_progress', label: 'In Progress', icon: Clock },
  { id: 'under_review', label: 'Under Review', icon: GitBranch },
  { id: 'completed', label: 'Completed', icon: CheckCircle },
]

const ENTITY_ICONS: Record<string, typeof AlertTriangle> = {
  road_traffic_collision: Car,
  reporting_incident: AlertTriangle,
  complaint: MessageSquare,
}

const ENTITY_COLORS: Record<string, string> = {
  road_traffic_collision: 'from-orange-500 to-red-500',
  reporting_incident: 'from-emerald-500 to-teal-500',
  complaint: 'from-purple-500 to-pink-500',
}

export default function Investigations() {
  const [investigations, setInvestigations] = useState<Investigation[]>([])
  const [loading, setLoading] = useState(true)
  const [searchTerm, setSearchTerm] = useState('')
  const [showModal, setShowModal] = useState(false)
  const [selectedInvestigation, setSelectedInvestigation] = useState<Investigation | null>(null)

  useEffect(() => {
    loadInvestigations()
  }, [])

  const loadInvestigations = async () => {
    try {
      const response = await investigationsApi.list(1, 100)
      setInvestigations(response.data.items || [])
    } catch (err) {
      console.error('Failed to load investigations:', err)
      setInvestigations([])
    } finally {
      setLoading(false)
    }
  }

  const getStatusIndex = (status: string) => {
    return STATUS_STEPS.findIndex(s => s.id === status)
  }

  const getEntityIcon = (type: string) => {
    return ENTITY_ICONS[type] || AlertTriangle
  }

  const getEntityColor = (type: string) => {
    return ENTITY_COLORS[type] || 'from-slate-500 to-slate-600'
  }

  const filteredInvestigations = investigations.filter(
    i => i.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
         i.reference_number.toLowerCase().includes(searchTerm.toLowerCase())
  )

  const stats = {
    total: investigations.length,
    inProgress: investigations.filter(i => i.status === 'in_progress').length,
    underReview: investigations.filter(i => i.status === 'under_review').length,
    completed: investigations.filter(i => i.status === 'completed').length,
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="relative">
          <div className="animate-spin rounded-full h-16 w-16 border-4 border-violet-500/20 border-t-violet-500"></div>
          <FlaskConical className="absolute inset-0 m-auto w-6 h-6 text-violet-400" />
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold bg-gradient-to-r from-violet-400 via-fuchsia-400 to-pink-400 bg-clip-text text-transparent">
            Root Cause Investigations
          </h1>
          <p className="text-slate-400 mt-1">5-Whys analysis, RCA workflows & corrective actions</p>
        </div>
        <button
          onClick={() => setShowModal(true)}
          className="inline-flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-violet-500 via-fuchsia-500 to-pink-500
            text-white font-semibold rounded-xl hover:opacity-90 transition-all duration-200 
            shadow-lg shadow-violet-500/25 hover:shadow-xl hover:shadow-violet-500/30 hover:-translate-y-0.5"
        >
          <Plus size={20} />
          New Investigation
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: 'Total', value: stats.total, color: 'from-violet-500 to-fuchsia-500' },
          { label: 'In Progress', value: stats.inProgress, color: 'from-amber-500 to-orange-500' },
          { label: 'Under Review', value: stats.underReview, color: 'from-purple-500 to-pink-500' },
          { label: 'Completed', value: stats.completed, color: 'from-emerald-500 to-green-500' },
        ].map((stat, index) => (
          <div 
            key={stat.label}
            className="bg-slate-900/50 backdrop-blur-xl border border-slate-800 rounded-2xl p-5 animate-slide-in"
            style={{ animationDelay: `${index * 50}ms` }}
          >
            <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${stat.color} flex items-center justify-center mb-3`}>
              <span className="text-xl font-bold text-white">{stat.value}</span>
            </div>
            <p className="text-sm text-slate-400">{stat.label}</p>
          </div>
        ))}
      </div>

      {/* Search */}
      <div className="relative max-w-md">
        <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-500" />
        <input
          type="text"
          placeholder="Search investigations..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="w-full pl-12 pr-4 py-3 bg-slate-900/50 border border-slate-800 rounded-xl
            text-white placeholder-slate-500 focus:outline-none focus:border-violet-500
            focus:ring-2 focus:ring-violet-500/20 transition-all duration-200"
        />
      </div>

      {/* Investigation Cards */}
      <div className="space-y-4">
        {filteredInvestigations.length === 0 ? (
          <div className="bg-slate-900/50 backdrop-blur-xl border border-slate-800 rounded-2xl p-12 text-center">
            <FlaskConical className="w-16 h-16 mx-auto mb-4 text-slate-600" />
            <h3 className="text-lg font-semibold text-white mb-2">No Investigations Found</h3>
            <p className="text-slate-400 max-w-md mx-auto">
              Start a root cause investigation to analyze incidents, RTAs, or complaints.
            </p>
          </div>
        ) : (
          filteredInvestigations.map((investigation, index) => {
            const EntityIcon = getEntityIcon(investigation.assigned_entity_type)
            const statusIndex = getStatusIndex(investigation.status)
            
            return (
              <div
                key={investigation.id}
                onClick={() => setSelectedInvestigation(investigation)}
                className="bg-slate-900/50 backdrop-blur-xl border border-slate-800 rounded-2xl p-6
                  hover:border-violet-500/30 transition-all duration-300 cursor-pointer group animate-slide-in"
                style={{ animationDelay: `${index * 50}ms` }}
              >
                <div className="flex flex-col lg:flex-row lg:items-center gap-6">
                  {/* Entity Icon */}
                  <div className={`w-16 h-16 rounded-2xl bg-gradient-to-br ${getEntityColor(investigation.assigned_entity_type)} 
                    flex items-center justify-center flex-shrink-0 shadow-lg`}>
                    <EntityIcon className="w-8 h-8 text-white" />
                  </div>

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 mb-2">
                      <span className="font-mono text-sm text-violet-400">{investigation.reference_number}</span>
                      <span className="px-2 py-0.5 text-xs font-medium rounded bg-slate-800 text-slate-400 capitalize">
                        {investigation.assigned_entity_type.replace(/_/g, ' ')}
                      </span>
                    </div>
                    <h3 className="text-lg font-semibold text-white group-hover:text-violet-300 transition-colors mb-1">
                      {investigation.title}
                    </h3>
                    {investigation.description && (
                      <p className="text-sm text-slate-400 line-clamp-2">{investigation.description}</p>
                    )}
                  </div>

                  {/* Status Timeline */}
                  <div className="flex items-center gap-2 lg:w-80">
                    {STATUS_STEPS.map((step, stepIndex) => {
                      const isActive = stepIndex <= statusIndex
                      const isCurrent = stepIndex === statusIndex
                      return (
                        <div key={step.id} className="flex items-center">
                          <div className={`
                            relative flex items-center justify-center w-10 h-10 rounded-xl transition-all duration-300
                            ${isCurrent 
                              ? 'bg-gradient-to-br from-violet-500 to-fuchsia-500 shadow-lg shadow-violet-500/30' 
                              : isActive 
                                ? 'bg-violet-500/20' 
                                : 'bg-slate-800'
                            }
                          `}>
                            <step.icon className={`w-5 h-5 ${isActive ? 'text-white' : 'text-slate-600'}`} />
                            {isCurrent && (
                              <div className="absolute inset-0 rounded-xl animate-pulse bg-violet-500/30" />
                            )}
                          </div>
                          {stepIndex < STATUS_STEPS.length - 1 && (
                            <ArrowRight className={`w-4 h-4 mx-1 ${isActive ? 'text-violet-400' : 'text-slate-700'}`} />
                          )}
                        </div>
                      )
                    })}
                  </div>
                </div>

                {/* RCA Preview (if data exists) */}
                {investigation.data && Object.keys(investigation.data).length > 0 && (
                  <div className="mt-6 pt-6 border-t border-slate-800">
                    <div className="flex items-center gap-2 mb-3">
                      <GitBranch className="w-4 h-4 text-violet-400" />
                      <span className="text-sm font-medium text-violet-400">Root Cause Analysis</span>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      {['Why 1', 'Why 2', 'Why 3'].map((why, i) => (
                        <div key={i} className="bg-slate-800/50 rounded-xl p-3">
                          <span className="text-xs text-slate-500">{why}</span>
                          <p className="text-sm text-slate-300 mt-1">
                            {typeof investigation.data === 'object' && 
                              (investigation.data as Record<string, unknown>)[`why_${i + 1}`] as string || 
                              'Not documented'}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )
          })
        )}
      </div>

      {/* Detail Modal */}
      {selectedInvestigation && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setSelectedInvestigation(null)} />
          <div className="relative w-full max-w-4xl bg-slate-900 border border-slate-800 rounded-2xl shadow-xl animate-fade-in max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between p-6 border-b border-slate-800 sticky top-0 bg-slate-900 z-10">
              <div>
                <span className="font-mono text-sm text-violet-400">{selectedInvestigation.reference_number}</span>
                <h2 className="text-xl font-semibold text-white mt-1">{selectedInvestigation.title}</h2>
              </div>
              <button
                onClick={() => setSelectedInvestigation(null)}
                className="p-2 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
              >
                <X size={24} />
              </button>
            </div>
            <div className="p-6 space-y-6">
              {/* 5 Whys Analysis */}
              <div>
                <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                  <GitBranch className="w-5 h-5 text-violet-400" />
                  5 Whys Analysis
                </h3>
                <div className="space-y-4">
                  {[1, 2, 3, 4, 5].map((num) => (
                    <div key={num} className="flex items-start gap-4">
                      <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500 to-fuchsia-500 
                        flex items-center justify-center flex-shrink-0 font-bold text-white">
                        {num}
                      </div>
                      <div className="flex-1">
                        <label className="block text-sm font-medium text-slate-300 mb-2">
                          Why {num}?
                        </label>
                        <textarea
                          rows={2}
                          placeholder={`Enter the ${num === 1 ? 'initial' : 'deeper'} cause...`}
                          className="w-full px-4 py-3 bg-slate-800/50 border border-slate-700 rounded-xl
                            text-white placeholder-slate-500 focus:outline-none focus:border-violet-500
                            focus:ring-2 focus:ring-violet-500/20 transition-all duration-200 resize-none"
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Root Cause */}
              <div className="bg-gradient-to-br from-violet-500/10 to-fuchsia-500/10 border border-violet-500/20 rounded-2xl p-6">
                <h3 className="text-lg font-semibold text-white mb-4">Root Cause Identified</h3>
                <textarea
                  rows={3}
                  placeholder="Document the root cause based on your 5 Whys analysis..."
                  className="w-full px-4 py-3 bg-slate-800/50 border border-slate-700 rounded-xl
                    text-white placeholder-slate-500 focus:outline-none focus:border-violet-500
                    focus:ring-2 focus:ring-violet-500/20 transition-all duration-200 resize-none"
                />
              </div>

              {/* Corrective Actions */}
              <div>
                <h3 className="text-lg font-semibold text-white mb-4">Corrective Actions</h3>
                <button className="w-full py-3 border-2 border-dashed border-slate-700 rounded-xl
                  text-slate-400 hover:border-violet-500 hover:text-violet-400 transition-colors">
                  <Plus className="w-5 h-5 mx-auto" />
                  Add Corrective Action
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Create Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setShowModal(false)} />
          <div className="relative w-full max-w-lg bg-slate-900 border border-slate-800 rounded-2xl shadow-xl animate-fade-in">
            <div className="flex items-center justify-between p-6 border-b border-slate-800">
              <h2 className="text-lg font-semibold text-white">Start New Investigation</h2>
              <button
                onClick={() => setShowModal(false)}
                className="p-2 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
              >
                <X size={20} />
              </button>
            </div>
            <div className="p-6">
              <p className="text-slate-400 text-center py-8">
                Investigation creation coming soon. Use the API to create investigations.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
