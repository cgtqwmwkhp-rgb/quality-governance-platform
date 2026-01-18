import { useEffect, useState } from 'react'
import { Plus, X, Car, Search } from 'lucide-react'
import { rtasApi, RTA, RTACreate } from '../api/client'

export default function RTAs() {
  const [rtas, setRtas] = useState<RTA[]>([])
  const [loading, setLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [creating, setCreating] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')
  const [formData, setFormData] = useState<RTACreate>({
    title: '',
    description: '',
    severity: 'damage_only',
    collision_date: new Date().toISOString().slice(0, 16),
    reported_date: new Date().toISOString().slice(0, 16),
    location: '',
    driver_name: '',
    company_vehicle_registration: '',
    police_attended: false,
    driver_injured: false,
  })

  useEffect(() => {
    loadRtas()
  }, [])

  const loadRtas = async () => {
    try {
      const response = await rtasApi.list(1, 50)
      setRtas(response.data.items)
    } catch (err) {
      console.error('Failed to load RTAs:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    setCreating(true)
    try {
      await rtasApi.create({
        ...formData,
        collision_date: new Date(formData.collision_date).toISOString(),
        reported_date: new Date(formData.reported_date).toISOString(),
      })
      setShowModal(false)
      setFormData({
        title: '',
        description: '',
        severity: 'damage_only',
        collision_date: new Date().toISOString().slice(0, 16),
        reported_date: new Date().toISOString().slice(0, 16),
        location: '',
        driver_name: '',
        company_vehicle_registration: '',
        police_attended: false,
        driver_injured: false,
      })
      loadRtas()
    } catch (err) {
      console.error('Failed to create RTA:', err)
    } finally {
      setCreating(false)
    }
  }

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'fatal': return 'bg-red-600/20 text-red-400 border-red-500/30'
      case 'serious_injury': return 'bg-red-500/20 text-red-400 border-red-500/30'
      case 'minor_injury': return 'bg-orange-500/20 text-orange-400 border-orange-500/30'
      case 'damage_only': return 'bg-amber-500/20 text-amber-400 border-amber-500/30'
      case 'near_miss': return 'bg-green-500/20 text-green-400 border-green-500/30'
      default: return 'bg-slate-500/20 text-slate-400 border-slate-500/30'
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'closed': return 'bg-emerald-500/20 text-emerald-400'
      case 'reported': return 'bg-blue-500/20 text-blue-400'
      case 'under_investigation': return 'bg-purple-500/20 text-purple-400'
      case 'pending_insurance': return 'bg-amber-500/20 text-amber-400'
      case 'pending_actions': return 'bg-orange-500/20 text-orange-400'
      default: return 'bg-slate-500/20 text-slate-400'
    }
  }

  const filteredRtas = rtas.filter(
    r => r.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
         r.reference_number.toLowerCase().includes(searchTerm.toLowerCase()) ||
         r.location.toLowerCase().includes(searchTerm.toLowerCase())
  )

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-orange-500"></div>
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">Road Traffic Collisions</h1>
          <p className="text-slate-400 mt-1">Manage vehicle accidents and incidents</p>
        </div>
        <button
          onClick={() => setShowModal(true)}
          className="inline-flex items-center gap-2 px-4 py-2.5 bg-gradient-to-r from-orange-500 to-red-500
            text-white font-semibold rounded-xl hover:from-orange-600 hover:to-red-600
            transition-all duration-200 shadow-lg shadow-orange-500/25"
        >
          <Plus size={20} />
          Report RTA
        </button>
      </div>

      {/* Search */}
      <div className="flex gap-4">
        <div className="flex-1 relative">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-500" />
          <input
            type="text"
            placeholder="Search RTAs..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-12 pr-4 py-3 bg-slate-900/50 border border-slate-800 rounded-xl
              text-white placeholder-slate-500 focus:outline-none focus:border-orange-500
              focus:ring-2 focus:ring-orange-500/20 transition-all duration-200"
          />
        </div>
      </div>

      {/* RTAs Table */}
      <div className="bg-slate-900/50 backdrop-blur-xl border border-slate-800 rounded-2xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-slate-800">
                <th className="px-6 py-4 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">Reference</th>
                <th className="px-6 py-4 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">Title</th>
                <th className="px-6 py-4 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">Location</th>
                <th className="px-6 py-4 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">Severity</th>
                <th className="px-6 py-4 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">Status</th>
                <th className="px-6 py-4 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">Date</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {filteredRtas.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-6 py-12 text-center text-slate-400">
                    <Car className="w-12 h-12 mx-auto mb-4 text-slate-600" />
                    <p>No RTAs found</p>
                    <p className="text-sm mt-1">Report a road traffic collision to get started</p>
                  </td>
                </tr>
              ) : (
                filteredRtas.map((rta, index) => (
                  <tr
                    key={rta.id}
                    className="hover:bg-slate-800/30 transition-colors animate-slide-in cursor-pointer"
                    style={{ animationDelay: `${index * 30}ms` }}
                  >
                    <td className="px-6 py-4">
                      <span className="font-mono text-sm text-orange-400">{rta.reference_number}</span>
                    </td>
                    <td className="px-6 py-4">
                      <p className="text-sm font-medium text-white truncate max-w-xs">{rta.title}</p>
                    </td>
                    <td className="px-6 py-4">
                      <p className="text-sm text-slate-300 truncate max-w-xs">{rta.location}</p>
                    </td>
                    <td className="px-6 py-4">
                      <span className={`px-2.5 py-1 text-xs font-medium rounded-lg border ${getSeverityColor(rta.severity)}`}>
                        {rta.severity.replace('_', ' ')}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <span className={`px-2.5 py-1 text-xs font-medium rounded-lg ${getStatusColor(rta.status)}`}>
                        {rta.status.replace('_', ' ')}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm text-slate-400">
                      {new Date(rta.collision_date).toLocaleDateString()}
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
          <div className="relative w-full max-w-lg bg-slate-900 border border-slate-800 rounded-2xl shadow-xl animate-fade-in max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between p-6 border-b border-slate-800 sticky top-0 bg-slate-900">
              <h2 className="text-lg font-semibold text-white">Report Road Traffic Collision</h2>
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
                    text-white placeholder-slate-500 focus:outline-none focus:border-orange-500
                    focus:ring-2 focus:ring-orange-500/20 transition-all duration-200"
                  placeholder="Brief description of the collision..."
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
                    text-white placeholder-slate-500 focus:outline-none focus:border-orange-500
                    focus:ring-2 focus:ring-orange-500/20 transition-all duration-200 resize-none"
                  placeholder="Full details of what happened..."
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">Location</label>
                <input
                  type="text"
                  required
                  value={formData.location}
                  onChange={(e) => setFormData({ ...formData, location: e.target.value })}
                  className="w-full px-4 py-3 bg-slate-800/50 border border-slate-700 rounded-xl
                    text-white placeholder-slate-500 focus:outline-none focus:border-orange-500
                    focus:ring-2 focus:ring-orange-500/20 transition-all duration-200"
                  placeholder="Where did the collision occur..."
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-2">Severity</label>
                  <select
                    value={formData.severity}
                    onChange={(e) => setFormData({ ...formData, severity: e.target.value })}
                    className="w-full px-4 py-3 bg-slate-800/50 border border-slate-700 rounded-xl
                      text-white focus:outline-none focus:border-orange-500
                      focus:ring-2 focus:ring-orange-500/20 transition-all duration-200"
                  >
                    <option value="near_miss">Near Miss</option>
                    <option value="damage_only">Damage Only</option>
                    <option value="minor_injury">Minor Injury</option>
                    <option value="serious_injury">Serious Injury</option>
                    <option value="fatal">Fatal</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-2">Vehicle Reg</label>
                  <input
                    type="text"
                    value={formData.company_vehicle_registration || ''}
                    onChange={(e) => setFormData({ ...formData, company_vehicle_registration: e.target.value })}
                    className="w-full px-4 py-3 bg-slate-800/50 border border-slate-700 rounded-xl
                      text-white placeholder-slate-500 focus:outline-none focus:border-orange-500
                      focus:ring-2 focus:ring-orange-500/20 transition-all duration-200"
                    placeholder="AB12 CDE"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">Driver Name</label>
                <input
                  type="text"
                  value={formData.driver_name || ''}
                  onChange={(e) => setFormData({ ...formData, driver_name: e.target.value })}
                  className="w-full px-4 py-3 bg-slate-800/50 border border-slate-700 rounded-xl
                    text-white placeholder-slate-500 focus:outline-none focus:border-orange-500
                    focus:ring-2 focus:ring-orange-500/20 transition-all duration-200"
                  placeholder="Name of the driver..."
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">Collision Date</label>
                <input
                  type="datetime-local"
                  required
                  value={formData.collision_date}
                  onChange={(e) => setFormData({ ...formData, collision_date: e.target.value })}
                  className="w-full px-4 py-3 bg-slate-800/50 border border-slate-700 rounded-xl
                    text-white focus:outline-none focus:border-orange-500
                    focus:ring-2 focus:ring-orange-500/20 transition-all duration-200"
                />
              </div>

              <div className="flex gap-4">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formData.police_attended || false}
                    onChange={(e) => setFormData({ ...formData, police_attended: e.target.checked })}
                    className="w-5 h-5 rounded bg-slate-800 border-slate-600 text-orange-500 focus:ring-orange-500"
                  />
                  <span className="text-sm text-slate-300">Police Attended</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formData.driver_injured || false}
                    onChange={(e) => setFormData({ ...formData, driver_injured: e.target.checked })}
                    className="w-5 h-5 rounded bg-slate-800 border-slate-600 text-orange-500 focus:ring-orange-500"
                  />
                  <span className="text-sm text-slate-300">Driver Injured</span>
                </label>
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
                  className="flex-1 px-4 py-3 bg-gradient-to-r from-orange-500 to-red-500
                    text-white font-semibold rounded-xl hover:from-orange-600 hover:to-red-600
                    disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
                >
                  {creating ? 'Reporting...' : 'Report RTA'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
