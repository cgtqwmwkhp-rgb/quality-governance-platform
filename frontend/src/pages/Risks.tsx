import { useEffect, useState } from 'react'
import { Plus, X, Shield, Search } from 'lucide-react'
import { risksApi, Risk, RiskCreate } from '../api/client'

export default function Risks() {
  const [risks, setRisks] = useState<Risk[]>([])
  const [loading, setLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [creating, setCreating] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')
  const [formData, setFormData] = useState<RiskCreate>({
    title: '',
    description: '',
    category: 'operational',
    likelihood: 3,
    impact: 3,
    treatment_strategy: 'mitigate',
  })

  useEffect(() => {
    loadRisks()
  }, [])

  const loadRisks = async () => {
    try {
      const response = await risksApi.list(1, 50)
      setRisks(response.data.items)
    } catch (err) {
      console.error('Failed to load risks:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    setCreating(true)
    try {
      await risksApi.create(formData)
      setShowModal(false)
      setFormData({
        title: '',
        description: '',
        category: 'operational',
        likelihood: 3,
        impact: 3,
        treatment_strategy: 'mitigate',
      })
      loadRisks()
    } catch (err) {
      console.error('Failed to create risk:', err)
    } finally {
      setCreating(false)
    }
  }

  const getRiskLevelColor = (level: string, score: number) => {
    if (score >= 20 || level === 'critical') return 'bg-red-500/20 text-red-400 border-red-500/50'
    if (score >= 12 || level === 'high') return 'bg-orange-500/20 text-orange-400 border-orange-500/50'
    if (score >= 6 || level === 'medium') return 'bg-amber-500/20 text-amber-400 border-amber-500/50'
    return 'bg-green-500/20 text-green-400 border-green-500/50'
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'closed': return 'bg-emerald-500/20 text-emerald-400'
      case 'identified': return 'bg-blue-500/20 text-blue-400'
      case 'assessing': return 'bg-purple-500/20 text-purple-400'
      case 'treating': return 'bg-amber-500/20 text-amber-400'
      case 'monitoring': return 'bg-cyan-500/20 text-cyan-400'
      default: return 'bg-slate-500/20 text-slate-400'
    }
  }

  const getCategoryIcon = (category: string) => {
    switch (category) {
      case 'strategic': return '🎯'
      case 'operational': return '⚙️'
      case 'financial': return '💰'
      case 'compliance': return '📋'
      case 'reputational': return '🏆'
      case 'technology': return '💻'
      case 'environmental': return '🌍'
      case 'health_safety': return '🏥'
      default: return '📊'
    }
  }

  const filteredRisks = risks.filter(
    r => r.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
         r.reference_number.toLowerCase().includes(searchTerm.toLowerCase()) ||
         r.category.toLowerCase().includes(searchTerm.toLowerCase())
  )

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-rose-500"></div>
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">Risk Register</h1>
          <p className="text-slate-400 mt-1">Identify, assess, and manage organizational risks</p>
        </div>
        <button
          onClick={() => setShowModal(true)}
          className="inline-flex items-center gap-2 px-4 py-2.5 bg-gradient-to-r from-rose-500 to-pink-500
            text-white font-semibold rounded-xl hover:from-rose-600 hover:to-pink-600
            transition-all duration-200 shadow-lg shadow-rose-500/25"
        >
          <Plus size={20} />
          New Risk
        </button>
      </div>

      {/* Search */}
      <div className="flex gap-4">
        <div className="flex-1 relative">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-500" />
          <input
            type="text"
            placeholder="Search risks..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-12 pr-4 py-3 bg-slate-900/50 border border-slate-800 rounded-xl
              text-white placeholder-slate-500 focus:outline-none focus:border-rose-500
              focus:ring-2 focus:ring-rose-500/20 transition-all duration-200"
          />
        </div>
      </div>

      {/* Risk Heat Map Summary */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: 'Critical', color: 'from-red-500 to-red-600', count: risks.filter(r => r.risk_score >= 20).length },
          { label: 'High', color: 'from-orange-500 to-orange-600', count: risks.filter(r => r.risk_score >= 12 && r.risk_score < 20).length },
          { label: 'Medium', color: 'from-amber-500 to-amber-600', count: risks.filter(r => r.risk_score >= 6 && r.risk_score < 12).length },
          { label: 'Low', color: 'from-green-500 to-green-600', count: risks.filter(r => r.risk_score < 6).length },
        ].map((stat) => (
          <div key={stat.label} className="bg-slate-900/50 backdrop-blur-xl border border-slate-800 rounded-xl p-4">
            <div className={`w-10 h-10 rounded-lg bg-gradient-to-br ${stat.color} flex items-center justify-center mb-3`}>
              <span className="text-white font-bold">{stat.count}</span>
            </div>
            <p className="text-sm font-medium text-slate-400">{stat.label} Risks</p>
          </div>
        ))}
      </div>

      {/* Risks Table */}
      <div className="bg-slate-900/50 backdrop-blur-xl border border-slate-800 rounded-2xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-slate-800">
                <th className="px-6 py-4 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">Reference</th>
                <th className="px-6 py-4 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">Risk</th>
                <th className="px-6 py-4 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">Category</th>
                <th className="px-6 py-4 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">Score</th>
                <th className="px-6 py-4 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">Status</th>
                <th className="px-6 py-4 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">Treatment</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {filteredRisks.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-6 py-12 text-center text-slate-400">
                    <Shield className="w-12 h-12 mx-auto mb-4 text-slate-600" />
                    <p>No risks found</p>
                    <p className="text-sm mt-1">Add a risk to your register to get started</p>
                  </td>
                </tr>
              ) : (
                filteredRisks.map((risk, index) => (
                  <tr
                    key={risk.id}
                    className="hover:bg-slate-800/30 transition-colors animate-slide-in cursor-pointer"
                    style={{ animationDelay: `${index * 30}ms` }}
                  >
                    <td className="px-6 py-4">
                      <span className="font-mono text-sm text-rose-400">{risk.reference_number}</span>
                    </td>
                    <td className="px-6 py-4">
                      <p className="text-sm font-medium text-white truncate max-w-xs">{risk.title}</p>
                    </td>
                    <td className="px-6 py-4">
                      <span className="inline-flex items-center gap-1.5 text-sm text-slate-300">
                        <span>{getCategoryIcon(risk.category)}</span>
                        {risk.category.replace('_', ' ')}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2">
                        <span className={`px-3 py-1.5 text-sm font-bold rounded-lg border ${getRiskLevelColor(risk.risk_level, risk.risk_score)}`}>
                          {risk.risk_score}
                        </span>
                        <span className="text-xs text-slate-500">
                          ({risk.likelihood}×{risk.impact})
                        </span>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <span className={`px-2.5 py-1 text-xs font-medium rounded-lg ${getStatusColor(risk.status)}`}>
                        {risk.status.replace('_', ' ')}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <span className="text-sm text-slate-400 capitalize">
                        {risk.treatment_strategy}
                      </span>
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
              <h2 className="text-lg font-semibold text-white">New Risk</h2>
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
                    text-white placeholder-slate-500 focus:outline-none focus:border-rose-500
                    focus:ring-2 focus:ring-rose-500/20 transition-all duration-200"
                  placeholder="Brief risk title..."
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
                    text-white placeholder-slate-500 focus:outline-none focus:border-rose-500
                    focus:ring-2 focus:ring-rose-500/20 transition-all duration-200 resize-none"
                  placeholder="Detailed description of the risk..."
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-2">Category</label>
                  <select
                    value={formData.category}
                    onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                    className="w-full px-4 py-3 bg-slate-800/50 border border-slate-700 rounded-xl
                      text-white focus:outline-none focus:border-rose-500
                      focus:ring-2 focus:ring-rose-500/20 transition-all duration-200"
                  >
                    <option value="strategic">Strategic</option>
                    <option value="operational">Operational</option>
                    <option value="financial">Financial</option>
                    <option value="compliance">Compliance</option>
                    <option value="reputational">Reputational</option>
                    <option value="technology">Technology</option>
                    <option value="environmental">Environmental</option>
                    <option value="health_safety">Health & Safety</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-2">Treatment</label>
                  <select
                    value={formData.treatment_strategy}
                    onChange={(e) => setFormData({ ...formData, treatment_strategy: e.target.value })}
                    className="w-full px-4 py-3 bg-slate-800/50 border border-slate-700 rounded-xl
                      text-white focus:outline-none focus:border-rose-500
                      focus:ring-2 focus:ring-rose-500/20 transition-all duration-200"
                  >
                    <option value="accept">Accept</option>
                    <option value="mitigate">Mitigate</option>
                    <option value="transfer">Transfer</option>
                    <option value="avoid">Avoid</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-2">
                    Likelihood (1-5)
                  </label>
                  <input
                    type="range"
                    min="1"
                    max="5"
                    value={formData.likelihood}
                    onChange={(e) => setFormData({ ...formData, likelihood: parseInt(e.target.value) })}
                    className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-rose-500"
                  />
                  <div className="flex justify-between text-xs text-slate-500 mt-1">
                    <span>Rare</span>
                    <span className="text-rose-400 font-medium">{formData.likelihood}</span>
                    <span>Almost Certain</span>
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-2">
                    Impact (1-5)
                  </label>
                  <input
                    type="range"
                    min="1"
                    max="5"
                    value={formData.impact}
                    onChange={(e) => setFormData({ ...formData, impact: parseInt(e.target.value) })}
                    className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-rose-500"
                  />
                  <div className="flex justify-between text-xs text-slate-500 mt-1">
                    <span>Negligible</span>
                    <span className="text-rose-400 font-medium">{formData.impact}</span>
                    <span>Catastrophic</span>
                  </div>
                </div>
              </div>

              <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-slate-400">Calculated Risk Score:</span>
                  <span className={`px-4 py-2 text-lg font-bold rounded-lg border ${getRiskLevelColor('', formData.likelihood * formData.impact)}`}>
                    {formData.likelihood * formData.impact}
                  </span>
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
                  className="flex-1 px-4 py-3 bg-gradient-to-r from-rose-500 to-pink-500
                    text-white font-semibold rounded-xl hover:from-rose-600 hover:to-pink-600
                    disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
                >
                  {creating ? 'Creating...' : 'Create Risk'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
