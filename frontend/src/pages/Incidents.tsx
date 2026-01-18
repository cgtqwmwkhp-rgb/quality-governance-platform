import { useEffect, useState } from 'react'
import { Plus, X, AlertTriangle, Search, Filter } from 'lucide-react'
import { incidentsApi, Incident, IncidentCreate } from '../api/client'

export default function Incidents() {
  const [incidents, setIncidents] = useState<Incident[]>([])
  const [loading, setLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [creating, setCreating] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')
  const [formData, setFormData] = useState<IncidentCreate>({
    title: '',
    description: '',
    incident_type: 'other',
    severity: 'medium',
    incident_date: new Date().toISOString().slice(0, 16),
    reported_date: new Date().toISOString().slice(0, 16),
  })

  useEffect(() => {
    loadIncidents()
  }, [])

  const loadIncidents = async () => {
    try {
      const response = await incidentsApi.list(1, 50)
      setIncidents(response.data.items)
    } catch (err) {
      console.error('Failed to load incidents:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    setCreating(true)
    try {
      await incidentsApi.create({
        ...formData,
        incident_date: new Date(formData.incident_date).toISOString(),
        reported_date: new Date(formData.reported_date).toISOString(),
      })
      setShowModal(false)
      setFormData({
        title: '',
        description: '',
        incident_type: 'other',
        severity: 'medium',
        incident_date: new Date().toISOString().slice(0, 16),
        reported_date: new Date().toISOString().slice(0, 16),
      })
      loadIncidents()
    } catch (err) {
      console.error('Failed to create incident:', err)
    } finally {
      setCreating(false)
    }
  }

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'critical': return 'bg-red-500/20 text-red-400 border-red-500/30'
      case 'high': return 'bg-orange-500/20 text-orange-400 border-orange-500/30'
      case 'medium': return 'bg-amber-500/20 text-amber-400 border-amber-500/30'
      case 'low': return 'bg-green-500/20 text-green-400 border-green-500/30'
      default: return 'bg-slate-500/20 text-slate-400 border-slate-500/30'
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'closed': return 'bg-emerald-500/20 text-emerald-400'
      case 'reported': return 'bg-blue-500/20 text-blue-400'
      case 'under_investigation': return 'bg-purple-500/20 text-purple-400'
      case 'pending_actions': return 'bg-amber-500/20 text-amber-400'
      default: return 'bg-slate-500/20 text-slate-400'
    }
  }

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'injury': return '🩹'
      case 'near_miss': return '⚠️'
      case 'hazard': return '☢️'
      case 'quality': return '✓'
      case 'security': return '🔒'
      case 'environmental': return '🌿'
      default: return '📋'
    }
  }

  const filteredIncidents = incidents.filter(
    i => i.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
         i.reference_number.toLowerCase().includes(searchTerm.toLowerCase())
  )

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-emerald-500"></div>
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">Incidents</h1>
          <p className="text-slate-400 mt-1">Manage and track incidents</p>
        </div>
        <button
          onClick={() => setShowModal(true)}
          className="inline-flex items-center gap-2 px-4 py-2.5 bg-gradient-to-r from-emerald-500 to-teal-500
            text-white font-semibold rounded-xl hover:from-emerald-600 hover:to-teal-600
            transition-all duration-200 shadow-lg shadow-emerald-500/25"
        >
          <Plus size={20} />
          New Incident
        </button>
      </div>

      {/* Search & Filter */}
      <div className="flex gap-4">
        <div className="flex-1 relative">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-500" />
          <input
            type="text"
            placeholder="Search incidents..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-12 pr-4 py-3 bg-slate-900/50 border border-slate-800 rounded-xl
              text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500
              focus:ring-2 focus:ring-emerald-500/20 transition-all duration-200"
          />
        </div>
      </div>

      {/* Incidents Table */}
      <div className="bg-slate-900/50 backdrop-blur-xl border border-slate-800 rounded-2xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-slate-800">
                <th className="px-6 py-4 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">Reference</th>
                <th className="px-6 py-4 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">Title</th>
                <th className="px-6 py-4 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">Type</th>
                <th className="px-6 py-4 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">Severity</th>
                <th className="px-6 py-4 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">Status</th>
                <th className="px-6 py-4 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">Date</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {filteredIncidents.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-6 py-12 text-center text-slate-400">
                    <AlertTriangle className="w-12 h-12 mx-auto mb-4 text-slate-600" />
                    <p>No incidents found</p>
                    <p className="text-sm mt-1">Create your first incident to get started</p>
                  </td>
                </tr>
              ) : (
                filteredIncidents.map((incident, index) => (
                  <tr
                    key={incident.id}
                    className="hover:bg-slate-800/30 transition-colors animate-slide-in cursor-pointer"
                    style={{ animationDelay: `${index * 30}ms` }}
                  >
                    <td className="px-6 py-4">
                      <span className="font-mono text-sm text-emerald-400">{incident.reference_number}</span>
                    </td>
                    <td className="px-6 py-4">
                      <p className="text-sm font-medium text-white truncate max-w-xs">{incident.title}</p>
                    </td>
                    <td className="px-6 py-4">
                      <span className="inline-flex items-center gap-1.5 text-sm text-slate-300">
                        <span>{getTypeIcon(incident.incident_type)}</span>
                        {incident.incident_type.replace('_', ' ')}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <span className={`px-2.5 py-1 text-xs font-medium rounded-lg border ${getSeverityColor(incident.severity)}`}>
                        {incident.severity}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <span className={`px-2.5 py-1 text-xs font-medium rounded-lg ${getStatusColor(incident.status)}`}>
                        {incident.status.replace('_', ' ')}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm text-slate-400">
                      {new Date(incident.incident_date).toLocaleDateString()}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Create Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setShowModal(false)} />
          <div className="relative w-full max-w-lg bg-slate-900 border border-slate-800 rounded-2xl shadow-xl animate-fade-in">
            <div className="flex items-center justify-between p-6 border-b border-slate-800">
              <h2 className="text-lg font-semibold text-white">New Incident</h2>
              <button
                onClick={() => setShowModal(false)}
                className="p-2 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
              >
                <X size={20} />
              </button>
            </div>
            <form onSubmit={handleCreate} className="p-6 space-y-5">
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">Title</label>
                <input
                  type="text"
                  required
                  value={formData.title}
                  onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                  className="w-full px-4 py-3 bg-slate-800/50 border border-slate-700 rounded-xl
                    text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500
                    focus:ring-2 focus:ring-emerald-500/20 transition-all duration-200"
                  placeholder="Describe the incident..."
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">Description</label>
                <textarea
                  required
                  rows={3}
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  className="w-full px-4 py-3 bg-slate-800/50 border border-slate-700 rounded-xl
                    text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500
                    focus:ring-2 focus:ring-emerald-500/20 transition-all duration-200 resize-none"
                  placeholder="Provide details about what happened..."
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-2">Type</label>
                  <select
                    value={formData.incident_type}
                    onChange={(e) => setFormData({ ...formData, incident_type: e.target.value })}
                    className="w-full px-4 py-3 bg-slate-800/50 border border-slate-700 rounded-xl
                      text-white focus:outline-none focus:border-emerald-500
                      focus:ring-2 focus:ring-emerald-500/20 transition-all duration-200"
                  >
                    <option value="injury">Injury</option>
                    <option value="near_miss">Near Miss</option>
                    <option value="hazard">Hazard</option>
                    <option value="property_damage">Property Damage</option>
                    <option value="environmental">Environmental</option>
                    <option value="security">Security</option>
                    <option value="quality">Quality</option>
                    <option value="other">Other</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-2">Severity</label>
                  <select
                    value={formData.severity}
                    onChange={(e) => setFormData({ ...formData, severity: e.target.value })}
                    className="w-full px-4 py-3 bg-slate-800/50 border border-slate-700 rounded-xl
                      text-white focus:outline-none focus:border-emerald-500
                      focus:ring-2 focus:ring-emerald-500/20 transition-all duration-200"
                  >
                    <option value="critical">Critical</option>
                    <option value="high">High</option>
                    <option value="medium">Medium</option>
                    <option value="low">Low</option>
                    <option value="negligible">Negligible</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">Incident Date</label>
                <input
                  type="datetime-local"
                  required
                  value={formData.incident_date}
                  onChange={(e) => setFormData({ ...formData, incident_date: e.target.value })}
                  className="w-full px-4 py-3 bg-slate-800/50 border border-slate-700 rounded-xl
                    text-white focus:outline-none focus:border-emerald-500
                    focus:ring-2 focus:ring-emerald-500/20 transition-all duration-200"
                />
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
                  disabled={creating}
                  className="flex-1 px-4 py-3 bg-gradient-to-r from-emerald-500 to-teal-500
                    text-white font-semibold rounded-xl hover:from-emerald-600 hover:to-teal-600
                    disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
                >
                  {creating ? 'Creating...' : 'Create Incident'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
