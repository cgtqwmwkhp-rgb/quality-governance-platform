import { useEffect, useState } from 'react'
import { Plus, X, FileText, Search } from 'lucide-react'
import { policiesApi, Policy, PolicyCreate } from '../api/client'

export default function Policies() {
  const [policies, setPolicies] = useState<Policy[]>([])
  const [loading, setLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [creating, setCreating] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')
  const [formData, setFormData] = useState<PolicyCreate>({
    title: '',
    description: '',
    document_type: 'policy',
    category: '',
    department: '',
    review_frequency_months: 12,
  })

  useEffect(() => {
    loadPolicies()
  }, [])

  const loadPolicies = async () => {
    try {
      const response = await policiesApi.list(1, 50)
      setPolicies(response.data.items)
    } catch (err) {
      console.error('Failed to load policies:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    setCreating(true)
    try {
      await policiesApi.create(formData)
      setShowModal(false)
      setFormData({
        title: '',
        description: '',
        document_type: 'policy',
        category: '',
        department: '',
        review_frequency_months: 12,
      })
      loadPolicies()
    } catch (err) {
      console.error('Failed to create policy:', err)
    } finally {
      setCreating(false)
    }
  }

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'policy': return '📜'
      case 'procedure': return '📋'
      case 'work_instruction': return '📝'
      case 'sop': return '📘'
      case 'form': return '📄'
      case 'template': return '📑'
      case 'guideline': return '📖'
      case 'manual': return '📚'
      case 'record': return '🗂️'
      default: return '📎'
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'published': return 'bg-emerald-500/20 text-emerald-400'
      case 'approved': return 'bg-green-500/20 text-green-400'
      case 'under_review': return 'bg-amber-500/20 text-amber-400'
      case 'draft': return 'bg-blue-500/20 text-blue-400'
      case 'superseded': return 'bg-slate-500/20 text-slate-400'
      case 'retired': return 'bg-red-500/20 text-red-400'
      default: return 'bg-slate-500/20 text-slate-400'
    }
  }

  const filteredPolicies = policies.filter(
    p => p.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
         p.reference_number.toLowerCase().includes(searchTerm.toLowerCase()) ||
         (p.category || '').toLowerCase().includes(searchTerm.toLowerCase())
  )

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-cyan-500"></div>
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">Policies & Documents</h1>
          <p className="text-slate-400 mt-1">Manage policies, procedures, and documents</p>
        </div>
        <button
          onClick={() => setShowModal(true)}
          className="inline-flex items-center gap-2 px-4 py-2.5 bg-gradient-to-r from-cyan-500 to-blue-500
            text-white font-semibold rounded-xl hover:from-cyan-600 hover:to-blue-600
            transition-all duration-200 shadow-lg shadow-cyan-500/25"
        >
          <Plus size={20} />
          New Document
        </button>
      </div>

      {/* Search */}
      <div className="flex gap-4">
        <div className="flex-1 relative">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-500" />
          <input
            type="text"
            placeholder="Search documents..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-12 pr-4 py-3 bg-slate-900/50 border border-slate-800 rounded-xl
              text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500
              focus:ring-2 focus:ring-cyan-500/20 transition-all duration-200"
          />
        </div>
      </div>

      {/* Policies Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filteredPolicies.length === 0 ? (
          <div className="col-span-full bg-slate-900/50 backdrop-blur-xl border border-slate-800 rounded-2xl p-12 text-center">
            <FileText className="w-12 h-12 mx-auto mb-4 text-slate-600" />
            <p className="text-slate-400">No documents found</p>
            <p className="text-sm text-slate-500 mt-1">Create your first document to get started</p>
          </div>
        ) : (
          filteredPolicies.map((policy, index) => (
            <div
              key={policy.id}
              className="bg-slate-900/50 backdrop-blur-xl border border-slate-800 rounded-2xl p-5
                hover:border-cyan-500/50 transition-all duration-200 cursor-pointer animate-slide-in"
              style={{ animationDelay: `${index * 50}ms` }}
            >
              <div className="flex items-start gap-4">
                <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-cyan-500/20 to-blue-500/20 
                  flex items-center justify-center text-2xl">
                  {getTypeIcon(policy.document_type)}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-mono text-xs text-cyan-400 mb-1">{policy.reference_number}</p>
                  <h3 className="font-semibold text-white truncate">{policy.title}</h3>
                  {policy.description && (
                    <p className="text-sm text-slate-400 mt-1 line-clamp-2">{policy.description}</p>
                  )}
                </div>
              </div>
              <div className="mt-4 flex items-center justify-between">
                <span className={`px-2.5 py-1 text-xs font-medium rounded-lg ${getStatusColor(policy.status)}`}>
                  {policy.status.replace('_', ' ')}
                </span>
                <span className="text-xs text-slate-500">
                  {policy.document_type.replace('_', ' ')}
                </span>
              </div>
              {policy.next_review_date && (
                <div className="mt-3 pt-3 border-t border-slate-800">
                  <p className="text-xs text-slate-500">
                    Review due: {new Date(policy.next_review_date).toLocaleDateString()}
                  </p>
                </div>
              )}
            </div>
          ))
        )}
      </div>

      {/* Create Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setShowModal(false)} />
          <div className="relative w-full max-w-lg bg-slate-900 border border-slate-800 rounded-2xl shadow-xl animate-fade-in">
            <div className="flex items-center justify-between p-6 border-b border-slate-800">
              <h2 className="text-lg font-semibold text-white">New Document</h2>
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
                    text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500
                    focus:ring-2 focus:ring-cyan-500/20 transition-all duration-200"
                  placeholder="Document title..."
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">Description</label>
                <textarea
                  rows={3}
                  value={formData.description || ''}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  className="w-full px-4 py-3 bg-slate-800/50 border border-slate-700 rounded-xl
                    text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500
                    focus:ring-2 focus:ring-cyan-500/20 transition-all duration-200 resize-none"
                  placeholder="Brief description of the document..."
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-2">Type</label>
                  <select
                    value={formData.document_type}
                    onChange={(e) => setFormData({ ...formData, document_type: e.target.value })}
                    className="w-full px-4 py-3 bg-slate-800/50 border border-slate-700 rounded-xl
                      text-white focus:outline-none focus:border-cyan-500
                      focus:ring-2 focus:ring-cyan-500/20 transition-all duration-200"
                  >
                    <option value="policy">Policy</option>
                    <option value="procedure">Procedure</option>
                    <option value="work_instruction">Work Instruction</option>
                    <option value="sop">SOP</option>
                    <option value="form">Form</option>
                    <option value="template">Template</option>
                    <option value="guideline">Guideline</option>
                    <option value="manual">Manual</option>
                    <option value="record">Record</option>
                    <option value="other">Other</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-2">Review Frequency</label>
                  <select
                    value={formData.review_frequency_months}
                    onChange={(e) => setFormData({ ...formData, review_frequency_months: parseInt(e.target.value) })}
                    className="w-full px-4 py-3 bg-slate-800/50 border border-slate-700 rounded-xl
                      text-white focus:outline-none focus:border-cyan-500
                      focus:ring-2 focus:ring-cyan-500/20 transition-all duration-200"
                  >
                    <option value={6}>6 months</option>
                    <option value={12}>12 months</option>
                    <option value={24}>24 months</option>
                    <option value={36}>36 months</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-2">Category</label>
                  <input
                    type="text"
                    value={formData.category || ''}
                    onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                    className="w-full px-4 py-3 bg-slate-800/50 border border-slate-700 rounded-xl
                      text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500
                      focus:ring-2 focus:ring-cyan-500/20 transition-all duration-200"
                    placeholder="e.g., Health & Safety"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-2">Department</label>
                  <input
                    type="text"
                    value={formData.department || ''}
                    onChange={(e) => setFormData({ ...formData, department: e.target.value })}
                    className="w-full px-4 py-3 bg-slate-800/50 border border-slate-700 rounded-xl
                      text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500
                      focus:ring-2 focus:ring-cyan-500/20 transition-all duration-200"
                    placeholder="e.g., Operations"
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
                  disabled={creating}
                  className="flex-1 px-4 py-3 bg-gradient-to-r from-cyan-500 to-blue-500
                    text-white font-semibold rounded-xl hover:from-cyan-600 hover:to-blue-600
                    disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
                >
                  {creating ? 'Creating...' : 'Create Document'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
