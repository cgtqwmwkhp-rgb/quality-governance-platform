import { useEffect, useState } from 'react'
import { Plus, X, MessageSquare, Search } from 'lucide-react'
import { complaintsApi, Complaint, ComplaintCreate } from '../api/client'

export default function Complaints() {
  const [complaints, setComplaints] = useState<Complaint[]>([])
  const [loading, setLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [creating, setCreating] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')
  const [formData, setFormData] = useState<ComplaintCreate>({
    title: '',
    description: '',
    complaint_type: 'other',
    priority: 'medium',
    received_date: new Date().toISOString().slice(0, 16),
    complainant_name: '',
    complainant_email: '',
    complainant_phone: '',
  })

  useEffect(() => {
    loadComplaints()
  }, [])

  const loadComplaints = async () => {
    try {
      const response = await complaintsApi.list(1, 50)
      setComplaints(response.data.items)
    } catch (err) {
      console.error('Failed to load complaints:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    setCreating(true)
    try {
      await complaintsApi.create({
        ...formData,
        received_date: new Date(formData.received_date).toISOString(),
      })
      setShowModal(false)
      setFormData({
        title: '',
        description: '',
        complaint_type: 'other',
        priority: 'medium',
        received_date: new Date().toISOString().slice(0, 16),
        complainant_name: '',
        complainant_email: '',
        complainant_phone: '',
      })
      loadComplaints()
    } catch (err) {
      console.error('Failed to create complaint:', err)
    } finally {
      setCreating(false)
    }
  }

  const getPriorityColor = (priority: string) => {
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
      case 'closed': case 'resolved': return 'bg-emerald-500/20 text-emerald-400'
      case 'received': return 'bg-blue-500/20 text-blue-400'
      case 'acknowledged': return 'bg-cyan-500/20 text-cyan-400'
      case 'under_investigation': return 'bg-purple-500/20 text-purple-400'
      case 'pending_response': return 'bg-amber-500/20 text-amber-400'
      case 'awaiting_customer': return 'bg-orange-500/20 text-orange-400'
      case 'escalated': return 'bg-red-500/20 text-red-400'
      default: return 'bg-slate-500/20 text-slate-400'
    }
  }

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'product': return '📦'
      case 'service': return '🛠️'
      case 'delivery': return '🚚'
      case 'communication': return '📞'
      case 'billing': return '💳'
      case 'staff': return '👤'
      case 'environmental': return '🌿'
      case 'safety': return '⚠️'
      default: return '📋'
    }
  }

  const filteredComplaints = complaints.filter(
    c => c.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
         c.reference_number.toLowerCase().includes(searchTerm.toLowerCase()) ||
         c.complainant_name.toLowerCase().includes(searchTerm.toLowerCase())
  )

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-purple-500"></div>
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">Complaints</h1>
          <p className="text-slate-400 mt-1">Manage customer complaints and feedback</p>
        </div>
        <button
          onClick={() => setShowModal(true)}
          className="inline-flex items-center gap-2 px-4 py-2.5 bg-gradient-to-r from-purple-500 to-pink-500
            text-white font-semibold rounded-xl hover:from-purple-600 hover:to-pink-600
            transition-all duration-200 shadow-lg shadow-purple-500/25"
        >
          <Plus size={20} />
          New Complaint
        </button>
      </div>

      {/* Search */}
      <div className="flex gap-4">
        <div className="flex-1 relative">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-500" />
          <input
            type="text"
            placeholder="Search complaints..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-12 pr-4 py-3 bg-slate-900/50 border border-slate-800 rounded-xl
              text-white placeholder-slate-500 focus:outline-none focus:border-purple-500
              focus:ring-2 focus:ring-purple-500/20 transition-all duration-200"
          />
        </div>
      </div>

      {/* Complaints Table */}
      <div className="bg-slate-900/50 backdrop-blur-xl border border-slate-800 rounded-2xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-slate-800">
                <th className="px-6 py-4 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">Reference</th>
                <th className="px-6 py-4 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">Title</th>
                <th className="px-6 py-4 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">Type</th>
                <th className="px-6 py-4 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">Complainant</th>
                <th className="px-6 py-4 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">Priority</th>
                <th className="px-6 py-4 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">Status</th>
                <th className="px-6 py-4 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">Received</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {filteredComplaints.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-6 py-12 text-center text-slate-400">
                    <MessageSquare className="w-12 h-12 mx-auto mb-4 text-slate-600" />
                    <p>No complaints found</p>
                    <p className="text-sm mt-1">Record a complaint to get started</p>
                  </td>
                </tr>
              ) : (
                filteredComplaints.map((complaint, index) => (
                  <tr
                    key={complaint.id}
                    className="hover:bg-slate-800/30 transition-colors animate-slide-in cursor-pointer"
                    style={{ animationDelay: `${index * 30}ms` }}
                  >
                    <td className="px-6 py-4">
                      <span className="font-mono text-sm text-purple-400">{complaint.reference_number}</span>
                    </td>
                    <td className="px-6 py-4">
                      <p className="text-sm font-medium text-white truncate max-w-xs">{complaint.title}</p>
                    </td>
                    <td className="px-6 py-4">
                      <span className="inline-flex items-center gap-1.5 text-sm text-slate-300">
                        <span>{getTypeIcon(complaint.complaint_type)}</span>
                        {complaint.complaint_type}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <p className="text-sm text-slate-300">{complaint.complainant_name}</p>
                    </td>
                    <td className="px-6 py-4">
                      <span className={`px-2.5 py-1 text-xs font-medium rounded-lg border ${getPriorityColor(complaint.priority)}`}>
                        {complaint.priority}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <span className={`px-2.5 py-1 text-xs font-medium rounded-lg ${getStatusColor(complaint.status)}`}>
                        {complaint.status.replace('_', ' ')}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm text-slate-400">
                      {new Date(complaint.received_date).toLocaleDateString()}
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
              <h2 className="text-lg font-semibold text-white">New Complaint</h2>
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
                    text-white placeholder-slate-500 focus:outline-none focus:border-purple-500
                    focus:ring-2 focus:ring-purple-500/20 transition-all duration-200"
                  placeholder="Brief summary of the complaint..."
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
                    text-white placeholder-slate-500 focus:outline-none focus:border-purple-500
                    focus:ring-2 focus:ring-purple-500/20 transition-all duration-200 resize-none"
                  placeholder="Full details of the complaint..."
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-2">Type</label>
                  <select
                    value={formData.complaint_type}
                    onChange={(e) => setFormData({ ...formData, complaint_type: e.target.value })}
                    className="w-full px-4 py-3 bg-slate-800/50 border border-slate-700 rounded-xl
                      text-white focus:outline-none focus:border-purple-500
                      focus:ring-2 focus:ring-purple-500/20 transition-all duration-200"
                  >
                    <option value="product">Product</option>
                    <option value="service">Service</option>
                    <option value="delivery">Delivery</option>
                    <option value="communication">Communication</option>
                    <option value="billing">Billing</option>
                    <option value="staff">Staff</option>
                    <option value="environmental">Environmental</option>
                    <option value="safety">Safety</option>
                    <option value="other">Other</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-2">Priority</label>
                  <select
                    value={formData.priority}
                    onChange={(e) => setFormData({ ...formData, priority: e.target.value })}
                    className="w-full px-4 py-3 bg-slate-800/50 border border-slate-700 rounded-xl
                      text-white focus:outline-none focus:border-purple-500
                      focus:ring-2 focus:ring-purple-500/20 transition-all duration-200"
                  >
                    <option value="critical">Critical</option>
                    <option value="high">High</option>
                    <option value="medium">Medium</option>
                    <option value="low">Low</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">Complainant Name</label>
                <input
                  type="text"
                  required
                  value={formData.complainant_name}
                  onChange={(e) => setFormData({ ...formData, complainant_name: e.target.value })}
                  className="w-full px-4 py-3 bg-slate-800/50 border border-slate-700 rounded-xl
                    text-white placeholder-slate-500 focus:outline-none focus:border-purple-500
                    focus:ring-2 focus:ring-purple-500/20 transition-all duration-200"
                  placeholder="Name of the person making the complaint..."
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-2">Email</label>
                  <input
                    type="email"
                    value={formData.complainant_email || ''}
                    onChange={(e) => setFormData({ ...formData, complainant_email: e.target.value })}
                    className="w-full px-4 py-3 bg-slate-800/50 border border-slate-700 rounded-xl
                      text-white placeholder-slate-500 focus:outline-none focus:border-purple-500
                      focus:ring-2 focus:ring-purple-500/20 transition-all duration-200"
                    placeholder="email@example.com"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-2">Phone</label>
                  <input
                    type="tel"
                    value={formData.complainant_phone || ''}
                    onChange={(e) => setFormData({ ...formData, complainant_phone: e.target.value })}
                    className="w-full px-4 py-3 bg-slate-800/50 border border-slate-700 rounded-xl
                      text-white placeholder-slate-500 focus:outline-none focus:border-purple-500
                      focus:ring-2 focus:ring-purple-500/20 transition-all duration-200"
                    placeholder="+44 123 456 7890"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">Received Date</label>
                <input
                  type="datetime-local"
                  required
                  value={formData.received_date}
                  onChange={(e) => setFormData({ ...formData, received_date: e.target.value })}
                  className="w-full px-4 py-3 bg-slate-800/50 border border-slate-700 rounded-xl
                    text-white focus:outline-none focus:border-purple-500
                    focus:ring-2 focus:ring-purple-500/20 transition-all duration-200"
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
                  className="flex-1 px-4 py-3 bg-gradient-to-r from-purple-500 to-pink-500
                    text-white font-semibold rounded-xl hover:from-purple-600 hover:to-pink-600
                    disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
                >
                  {creating ? 'Creating...' : 'Create Complaint'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
