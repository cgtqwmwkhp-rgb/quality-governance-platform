import { useEffect, useState } from 'react'
import { Search, BookOpen, ChevronRight, ChevronDown, CheckCircle2, Circle, AlertCircle, Shield, Award } from 'lucide-react'
import { standardsApi, Standard, Clause } from '../api/client'

interface ExpandedState {
  [key: number]: boolean
}

const ISO_ICONS: Record<string, string> = {
  'ISO9001': '🏆',
  'ISO14001': '🌍',
  'ISO27001': '🔐',
  'ISO45001': '⛑️',
  'ISO22000': '🍽️',
}

export default function Standards() {
  const [standards, setStandards] = useState<Standard[]>([])
  const [selectedStandard, setSelectedStandard] = useState<Standard | null>(null)
  const [clauses, setClauses] = useState<Clause[]>([])
  const [loading, setLoading] = useState(true)
  const [loadingClauses, setLoadingClauses] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')
  const [expanded, setExpanded] = useState<ExpandedState>({})

  useEffect(() => {
    loadStandards()
  }, [])

  const loadStandards = async () => {
    try {
      const response = await standardsApi.list(1, 50)
      setStandards(response.data.items || [])
    } catch (err) {
      console.error('Failed to load standards:', err)
      setStandards([])
    } finally {
      setLoading(false)
    }
  }

  const loadClauses = async (standard: Standard) => {
    setLoadingClauses(true)
    setSelectedStandard(standard)
    try {
      const response = await standardsApi.get(standard.id)
      setClauses(response.data.clauses || [])
    } catch (err) {
      console.error('Failed to load clauses:', err)
      setClauses([])
    } finally {
      setLoadingClauses(false)
    }
  }

  const toggleExpanded = (id: number) => {
    setExpanded(prev => ({ ...prev, [id]: !prev[id] }))
  }

  const getComplianceColor = (percentage: number) => {
    if (percentage >= 90) return 'from-emerald-500 to-green-500'
    if (percentage >= 70) return 'from-amber-500 to-yellow-500'
    if (percentage >= 50) return 'from-orange-500 to-red-500'
    return 'from-red-500 to-pink-500'
  }

  const getComplianceTextColor = (percentage: number) => {
    if (percentage >= 90) return 'text-emerald-400'
    if (percentage >= 70) return 'text-amber-400'
    return 'text-red-400'
  }

  // Mock compliance data for demo
  const mockCompliance: Record<string, number> = {
    'ISO9001': 87,
    'ISO14001': 72,
    'ISO27001': 94,
    'ISO45001': 81,
  }

  const filteredStandards = standards.filter(
    s => s.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
         s.code.toLowerCase().includes(searchTerm.toLowerCase())
  )

  // Group clauses by level
  const topLevelClauses = clauses.filter(c => c.level === 1)

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="relative">
          <div className="animate-spin rounded-full h-16 w-16 border-4 border-cyan-500/20 border-t-cyan-500"></div>
          <BookOpen className="absolute inset-0 m-auto w-6 h-6 text-cyan-400" />
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold bg-gradient-to-r from-cyan-400 via-blue-400 to-indigo-400 bg-clip-text text-transparent">
            Standards & Compliance
          </h1>
          <p className="text-slate-400 mt-1">ISO standards library, clauses & implementation tracking</p>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Standards List */}
        <div className="xl:col-span-1 space-y-4">
          {/* Search */}
          <div className="relative">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-500" />
            <input
              type="text"
              placeholder="Search standards..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-12 pr-4 py-3 bg-slate-900/50 border border-slate-800 rounded-xl
                text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500
                focus:ring-2 focus:ring-cyan-500/20 transition-all duration-200"
            />
          </div>

          {/* Standards Cards */}
          <div className="space-y-3">
            {filteredStandards.length === 0 ? (
              <div className="bg-slate-900/50 backdrop-blur-xl border border-slate-800 rounded-2xl p-8 text-center">
                <BookOpen className="w-12 h-12 mx-auto mb-4 text-slate-600" />
                <p className="text-slate-400">No standards found</p>
              </div>
            ) : (
              filteredStandards.map((standard, index) => {
                const compliance = mockCompliance[standard.code] || 0
                const isSelected = selectedStandard?.id === standard.id
                
                return (
                  <div
                    key={standard.id}
                    onClick={() => loadClauses(standard)}
                    className={`bg-slate-900/50 backdrop-blur-xl border rounded-2xl p-5 cursor-pointer
                      transition-all duration-300 animate-slide-in group
                      ${isSelected 
                        ? 'border-cyan-500 shadow-lg shadow-cyan-500/20' 
                        : 'border-slate-800 hover:border-slate-700'
                      }`}
                    style={{ animationDelay: `${index * 50}ms` }}
                  >
                    <div className="flex items-start gap-4">
                      <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-cyan-500/20 to-blue-500/20 
                        flex items-center justify-center text-2xl flex-shrink-0
                        group-hover:from-cyan-500/30 group-hover:to-blue-500/30 transition-colors">
                        {ISO_ICONS[standard.code] || '📋'}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="font-mono text-sm text-cyan-400">{standard.code}</span>
                          {standard.is_active && (
                            <span className="px-1.5 py-0.5 text-xs bg-emerald-500/20 text-emerald-400 rounded">
                              Active
                            </span>
                          )}
                        </div>
                        <h3 className="font-semibold text-white truncate">{standard.name}</h3>
                        <p className="text-xs text-slate-500 mt-1">Version {standard.version}</p>
                      </div>
                    </div>

                    {/* Compliance Bar */}
                    <div className="mt-4">
                      <div className="flex items-center justify-between text-xs mb-2">
                        <span className="text-slate-400">Compliance</span>
                        <span className={`font-bold ${getComplianceTextColor(compliance)}`}>{compliance}%</span>
                      </div>
                      <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
                        <div 
                          className={`h-full bg-gradient-to-r ${getComplianceColor(compliance)} transition-all duration-500`}
                          style={{ width: `${compliance}%` }}
                        />
                      </div>
                    </div>
                  </div>
                )
              })
            )}
          </div>
        </div>

        {/* Clauses Panel */}
        <div className="xl:col-span-2">
          {!selectedStandard ? (
            <div className="bg-slate-900/50 backdrop-blur-xl border border-slate-800 rounded-2xl p-12 text-center h-full flex flex-col items-center justify-center">
              <div className="w-20 h-20 rounded-full bg-gradient-to-br from-cyan-500/20 to-blue-500/20 
                flex items-center justify-center mb-6">
                <Award className="w-10 h-10 text-cyan-400" />
              </div>
              <h3 className="text-xl font-semibold text-white mb-2">Select a Standard</h3>
              <p className="text-slate-400 max-w-md">
                Choose a standard from the list to view its clauses, controls, and implementation status.
              </p>
            </div>
          ) : loadingClauses ? (
            <div className="bg-slate-900/50 backdrop-blur-xl border border-slate-800 rounded-2xl p-12 text-center">
              <div className="animate-spin rounded-full h-12 w-12 border-4 border-cyan-500/20 border-t-cyan-500 mx-auto"></div>
            </div>
          ) : (
            <div className="bg-slate-900/50 backdrop-blur-xl border border-slate-800 rounded-2xl overflow-hidden">
              {/* Header */}
              <div className="p-6 border-b border-slate-800 bg-gradient-to-r from-cyan-500/10 to-blue-500/10">
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-cyan-500 to-blue-500 
                    flex items-center justify-center text-xl shadow-lg shadow-cyan-500/25">
                    {ISO_ICONS[selectedStandard.code] || '📋'}
                  </div>
                  <div>
                    <h2 className="text-xl font-bold text-white">{selectedStandard.name}</h2>
                    <p className="text-sm text-slate-400">{selectedStandard.full_name}</p>
                  </div>
                </div>
              </div>

              {/* Clauses Tree */}
              <div className="p-4 max-h-[600px] overflow-y-auto">
                {topLevelClauses.length === 0 ? (
                  <div className="text-center py-8 text-slate-400">
                    <BookOpen className="w-10 h-10 mx-auto mb-3 text-slate-600" />
                    <p>No clauses defined for this standard</p>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {topLevelClauses.map((clause, index) => {
                      const isExpanded = expanded[clause.id]
                      const subClauses = clauses.filter(c => c.level === 2)
                      const hasChildren = subClauses.length > 0
                      
                      // Mock implementation status
                      const mockStatus = ['implemented', 'partial', 'planned', 'not_implemented'][index % 4]
                      
                      return (
                        <div 
                          key={clause.id}
                          className="animate-slide-in"
                          style={{ animationDelay: `${index * 30}ms` }}
                        >
                          <div 
                            onClick={() => hasChildren && toggleExpanded(clause.id)}
                            className={`flex items-center gap-3 p-4 rounded-xl transition-all duration-200 
                              ${hasChildren ? 'cursor-pointer hover:bg-slate-800/50' : ''}`}
                          >
                            {hasChildren ? (
                              isExpanded ? (
                                <ChevronDown className="w-5 h-5 text-cyan-400" />
                              ) : (
                                <ChevronRight className="w-5 h-5 text-slate-500" />
                              )
                            ) : (
                              <div className="w-5" />
                            )}
                            
                            <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${
                              mockStatus === 'implemented' ? 'bg-emerald-500/20' :
                              mockStatus === 'partial' ? 'bg-amber-500/20' :
                              mockStatus === 'planned' ? 'bg-blue-500/20' : 'bg-red-500/20'
                            }`}>
                              {mockStatus === 'implemented' ? (
                                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                              ) : mockStatus === 'partial' ? (
                                <Circle className="w-4 h-4 text-amber-400" />
                              ) : mockStatus === 'planned' ? (
                                <Circle className="w-4 h-4 text-blue-400" />
                              ) : (
                                <AlertCircle className="w-4 h-4 text-red-400" />
                              )}
                            </div>

                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2">
                                <span className="font-mono text-sm text-cyan-400">{clause.clause_number}</span>
                                <h4 className="font-medium text-white truncate">{clause.title}</h4>
                              </div>
                            </div>

                            <span className={`px-2 py-1 text-xs font-medium rounded capitalize ${
                              mockStatus === 'implemented' ? 'bg-emerald-500/20 text-emerald-400' :
                              mockStatus === 'partial' ? 'bg-amber-500/20 text-amber-400' :
                              mockStatus === 'planned' ? 'bg-blue-500/20 text-blue-400' : 'bg-red-500/20 text-red-400'
                            }`}>
                              {mockStatus.replace('_', ' ')}
                            </span>
                          </div>

                          {/* Sub-clauses */}
                          {isExpanded && hasChildren && (
                            <div className="ml-8 pl-4 border-l-2 border-slate-800 space-y-1 mt-2">
                              {subClauses.slice(0, 5).map((subClause) => (
                                <div 
                                  key={subClause.id}
                                  className="flex items-center gap-3 p-3 rounded-lg hover:bg-slate-800/30 transition-colors"
                                >
                                  <Shield className="w-4 h-4 text-slate-500" />
                                  <span className="font-mono text-xs text-cyan-400">{subClause.clause_number}</span>
                                  <span className="text-sm text-slate-300 truncate">{subClause.title}</span>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
