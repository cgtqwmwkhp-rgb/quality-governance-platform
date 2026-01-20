import { useState, useEffect } from 'react'
import {
  AlertTriangle,
  Shield,
  Plus,
  Eye,
  Edit2,
  BarChart3,
  Target,
  Layers,
  Activity,
  AlertCircle,
  Filter,
  Download,
  Zap,
  GitBranch,
  Clock,
  User,
} from 'lucide-react'

interface Risk {
  id: number
  reference: string
  title: string
  category: string
  department: string
  inherent_score: number
  residual_score: number
  risk_level: string
  risk_color: string
  treatment_strategy: string
  status: string
  is_within_appetite: boolean
  risk_owner_name: string
  next_review_date: string | null
}

interface MatrixCell {
  likelihood: number
  impact: number
  score: number
  level: string
  color: string
  risk_count: number
  risk_ids: number[]
  risk_titles: string[]
}

interface HeatMapData {
  matrix: MatrixCell[][]
  summary: {
    total_risks: number
    critical_risks: number
    high_risks: number
    outside_appetite: number
    average_inherent_score: number
    average_residual_score: number
  }
  likelihood_labels: Record<number, string>
  impact_labels: Record<number, string>
}

const CATEGORIES = [
  { id: 'strategic', label: 'Strategic', color: 'bg-purple-500' },
  { id: 'operational', label: 'Operational', color: 'bg-blue-500' },
  { id: 'financial', label: 'Financial', color: 'bg-green-500' },
  { id: 'compliance', label: 'Compliance', color: 'bg-yellow-500' },
  { id: 'reputational', label: 'Reputational', color: 'bg-pink-500' },
  { id: 'health_safety', label: 'Health & Safety', color: 'bg-red-500' },
  { id: 'environmental', label: 'Environmental', color: 'bg-emerald-500' },
]

const TREATMENT_STRATEGIES = [
  { id: 'treat', label: 'Treat', icon: '🛠️' },
  { id: 'tolerate', label: 'Tolerate', icon: '✅' },
  { id: 'transfer', label: 'Transfer', icon: '↗️' },
  { id: 'terminate', label: 'Terminate', icon: '🚫' },
]

export default function RiskRegister() {
  const [view, setView] = useState<'register' | 'heatmap' | 'bowtie'>('register')
  const [risks, setRisks] = useState<Risk[]>([])
  const [heatMapData, setHeatMapData] = useState<HeatMapData | null>(null)
  const [selectedRisk, setSelectedRisk] = useState<Risk | null>(null)
  const [loading, setLoading] = useState(true)
  const [_filters] = useState({
    category: '',
    department: '',
    status: '',
  })
  const [showFilters, setShowFilters] = useState(false)
  const [summary, setSummary] = useState({
    total_risks: 0,
    by_level: { critical: 0, high: 0, medium: 0, low: 0 },
    outside_appetite: 0,
    overdue_review: 0,
    escalated: 0,
  })

  useEffect(() => {
    // Simulate data loading
    setTimeout(() => {
      // Mock data
      const mockRisks: Risk[] = [
        {
          id: 1,
          reference: 'RISK-0001',
          title: 'Supply chain disruption affecting critical components',
          category: 'operational',
          department: 'Operations',
          inherent_score: 20,
          residual_score: 12,
          risk_level: 'high',
          risk_color: '#f97316',
          treatment_strategy: 'treat',
          status: 'monitoring',
          is_within_appetite: true,
          risk_owner_name: 'John Smith',
          next_review_date: '2026-03-15',
        },
        {
          id: 2,
          reference: 'RISK-0002',
          title: 'Regulatory compliance failure - Environmental permits',
          category: 'compliance',
          department: 'QHSE',
          inherent_score: 25,
          residual_score: 15,
          risk_level: 'high',
          risk_color: '#f97316',
          treatment_strategy: 'treat',
          status: 'treating',
          is_within_appetite: false,
          risk_owner_name: 'Sarah Johnson',
          next_review_date: '2026-02-28',
        },
        {
          id: 3,
          reference: 'RISK-0003',
          title: 'Key personnel departure without succession plan',
          category: 'strategic',
          department: 'HR',
          inherent_score: 16,
          residual_score: 8,
          risk_level: 'medium',
          risk_color: '#eab308',
          treatment_strategy: 'treat',
          status: 'monitoring',
          is_within_appetite: true,
          risk_owner_name: 'Mike Davis',
          next_review_date: '2026-04-01',
        },
        {
          id: 4,
          reference: 'RISK-0004',
          title: 'Cybersecurity breach leading to data loss',
          category: 'technological',
          department: 'IT',
          inherent_score: 25,
          residual_score: 9,
          risk_level: 'medium',
          risk_color: '#eab308',
          treatment_strategy: 'treat',
          status: 'monitoring',
          is_within_appetite: true,
          risk_owner_name: 'Alex Chen',
          next_review_date: '2026-02-15',
        },
        {
          id: 5,
          reference: 'RISK-0005',
          title: 'Workplace accident resulting in serious injury',
          category: 'health_safety',
          department: 'Operations',
          inherent_score: 20,
          residual_score: 6,
          risk_level: 'medium',
          risk_color: '#eab308',
          treatment_strategy: 'treat',
          status: 'monitoring',
          is_within_appetite: true,
          risk_owner_name: 'Emma Wilson',
          next_review_date: '2026-03-01',
        },
      ]

      setRisks(mockRisks)
      setSummary({
        total_risks: 5,
        by_level: { critical: 0, high: 2, medium: 3, low: 0 },
        outside_appetite: 1,
        overdue_review: 0,
        escalated: 0,
      })

      // Mock heat map
      const mockHeatMap: HeatMapData = {
        matrix: [],
        summary: {
          total_risks: 5,
          critical_risks: 0,
          high_risks: 2,
          outside_appetite: 1,
          average_inherent_score: 21.2,
          average_residual_score: 10.0,
        },
        likelihood_labels: {
          1: 'Rare',
          2: 'Unlikely',
          3: 'Possible',
          4: 'Likely',
          5: 'Almost Certain',
        },
        impact_labels: {
          1: 'Insignificant',
          2: 'Minor',
          3: 'Moderate',
          4: 'Major',
          5: 'Catastrophic',
        },
      }

      // Generate matrix
      for (let likelihood = 5; likelihood >= 1; likelihood--) {
        const row: MatrixCell[] = []
        for (let impact = 1; impact <= 5; impact++) {
          const score = likelihood * impact
          let level = 'low'
          let color = '#22c55e'
          if (score > 16) {
            level = 'critical'
            color = '#ef4444'
          } else if (score > 9) {
            level = 'high'
            color = '#f97316'
          } else if (score > 4) {
            level = 'medium'
            color = '#eab308'
          }

          const cellRisks = mockRisks.filter(
            (r) =>
              Math.ceil(r.residual_score / 5) === likelihood &&
              ((r.residual_score - 1) % 5) + 1 === impact
          )

          row.push({
            likelihood,
            impact,
            score,
            level,
            color,
            risk_count: cellRisks.length,
            risk_ids: cellRisks.map((r) => r.id),
            risk_titles: cellRisks.map((r) => r.title.substring(0, 30)),
          })
        }
        mockHeatMap.matrix.push(row)
      }

      setHeatMapData(mockHeatMap)
      setLoading(false)
    }, 500)
  }, [])

  const getRiskLevelBadge = (level: string, color: string) => {
    return (
      <span
        className="px-2 py-1 rounded-full text-xs font-bold uppercase"
        style={{ backgroundColor: color, color: 'white' }}
      >
        {level}
      </span>
    )
  }

  const getTreatmentBadge = (strategy: string) => {
    const s = TREATMENT_STRATEGIES.find((t) => t.id === strategy)
    return (
      <span className="px-2 py-1 bg-slate-700 rounded-full text-xs">
        {s?.icon} {s?.label}
      </span>
    )
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen bg-slate-900">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-emerald-500"></div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-slate-900 text-white p-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">Enterprise Risk Register</h1>
          <p className="text-gray-400">ISO 31000 Compliant Risk Management</p>
        </div>
        <div className="flex gap-3 mt-4 md:mt-0">
          <button
            onClick={() => setShowFilters(!showFilters)}
            className="flex items-center gap-2 px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg transition-colors"
          >
            <Filter className="w-4 h-4" />
            Filters
          </button>
          <button className="flex items-center gap-2 px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg transition-colors">
            <Download className="w-4 h-4" />
            Export
          </button>
          <button className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 rounded-lg transition-colors">
            <Plus className="w-4 h-4" />
            Add Risk
          </button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4 mb-8">
        <div className="bg-slate-800 rounded-xl p-4 border border-slate-700">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 bg-blue-500/20 rounded-lg">
              <Layers className="w-5 h-5 text-blue-400" />
            </div>
            <span className="text-2xl font-bold">{summary.total_risks}</span>
          </div>
          <p className="text-sm text-gray-400">Total Risks</p>
        </div>

        <div className="bg-slate-800 rounded-xl p-4 border border-red-500/30">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 bg-red-500/20 rounded-lg">
              <AlertTriangle className="w-5 h-5 text-red-400" />
            </div>
            <span className="text-2xl font-bold text-red-400">{summary.by_level.critical}</span>
          </div>
          <p className="text-sm text-gray-400">Critical</p>
        </div>

        <div className="bg-slate-800 rounded-xl p-4 border border-orange-500/30">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 bg-orange-500/20 rounded-lg">
              <AlertCircle className="w-5 h-5 text-orange-400" />
            </div>
            <span className="text-2xl font-bold text-orange-400">{summary.by_level.high}</span>
          </div>
          <p className="text-sm text-gray-400">High</p>
        </div>

        <div className="bg-slate-800 rounded-xl p-4 border border-yellow-500/30">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 bg-yellow-500/20 rounded-lg">
              <Activity className="w-5 h-5 text-yellow-400" />
            </div>
            <span className="text-2xl font-bold text-yellow-400">{summary.by_level.medium}</span>
          </div>
          <p className="text-sm text-gray-400">Medium</p>
        </div>

        <div className="bg-slate-800 rounded-xl p-4 border border-purple-500/30">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 bg-purple-500/20 rounded-lg">
              <Target className="w-5 h-5 text-purple-400" />
            </div>
            <span className="text-2xl font-bold text-purple-400">{summary.outside_appetite}</span>
          </div>
          <p className="text-sm text-gray-400">Outside Appetite</p>
        </div>

        <div className="bg-slate-800 rounded-xl p-4 border border-slate-700">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 bg-slate-600 rounded-lg">
              <Clock className="w-5 h-5 text-gray-400" />
            </div>
            <span className="text-2xl font-bold">{summary.overdue_review}</span>
          </div>
          <p className="text-sm text-gray-400">Overdue Review</p>
        </div>
      </div>

      {/* View Toggle */}
      <div className="flex gap-2 mb-6">
        <button
          onClick={() => setView('register')}
          className={`px-4 py-2 rounded-lg font-medium transition-colors ${
            view === 'register'
              ? 'bg-emerald-600 text-white'
              : 'bg-slate-700 text-gray-300 hover:bg-slate-600'
          }`}
        >
          <Layers className="w-4 h-4 inline-block mr-2" />
          Risk Register
        </button>
        <button
          onClick={() => setView('heatmap')}
          className={`px-4 py-2 rounded-lg font-medium transition-colors ${
            view === 'heatmap'
              ? 'bg-emerald-600 text-white'
              : 'bg-slate-700 text-gray-300 hover:bg-slate-600'
          }`}
        >
          <BarChart3 className="w-4 h-4 inline-block mr-2" />
          Heat Map
        </button>
        <button
          onClick={() => setView('bowtie')}
          className={`px-4 py-2 rounded-lg font-medium transition-colors ${
            view === 'bowtie'
              ? 'bg-emerald-600 text-white'
              : 'bg-slate-700 text-gray-300 hover:bg-slate-600'
          }`}
        >
          <GitBranch className="w-4 h-4 inline-block mr-2" />
          Bow-Tie Analysis
        </button>
      </div>

      {/* Register View */}
      {view === 'register' && (
        <div className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-slate-700">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-300 uppercase">
                    Reference
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-300 uppercase">
                    Risk Title
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-300 uppercase">
                    Category
                  </th>
                  <th className="px-4 py-3 text-center text-xs font-semibold text-gray-300 uppercase">
                    Inherent
                  </th>
                  <th className="px-4 py-3 text-center text-xs font-semibold text-gray-300 uppercase">
                    Residual
                  </th>
                  <th className="px-4 py-3 text-center text-xs font-semibold text-gray-300 uppercase">
                    Level
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-300 uppercase">
                    Treatment
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-300 uppercase">
                    Owner
                  </th>
                  <th className="px-4 py-3 text-center text-xs font-semibold text-gray-300 uppercase">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-700">
                {risks.map((risk) => (
                  <tr
                    key={risk.id}
                    className="hover:bg-slate-700/50 transition-colors cursor-pointer"
                    onClick={() => setSelectedRisk(risk)}
                  >
                    <td className="px-4 py-4">
                      <span className="font-mono text-emerald-400">{risk.reference}</span>
                    </td>
                    <td className="px-4 py-4">
                      <div className="flex items-center gap-2">
                        {!risk.is_within_appetite && (
                          <span className="w-2 h-2 bg-red-500 rounded-full animate-pulse" title="Outside Risk Appetite"></span>
                        )}
                        <span className="text-white">{risk.title}</span>
                      </div>
                    </td>
                    <td className="px-4 py-4">
                      <span
                        className={`px-2 py-1 rounded-full text-xs font-medium ${
                          CATEGORIES.find((c) => c.id === risk.category)?.color || 'bg-gray-500'
                        }`}
                      >
                        {CATEGORIES.find((c) => c.id === risk.category)?.label || risk.category}
                      </span>
                    </td>
                    <td className="px-4 py-4 text-center">
                      <span className="text-xl font-bold text-gray-400">{risk.inherent_score}</span>
                    </td>
                    <td className="px-4 py-4 text-center">
                      <span
                        className="text-xl font-bold"
                        style={{ color: risk.risk_color }}
                      >
                        {risk.residual_score}
                      </span>
                    </td>
                    <td className="px-4 py-4 text-center">
                      {getRiskLevelBadge(risk.risk_level, risk.risk_color)}
                    </td>
                    <td className="px-4 py-4">{getTreatmentBadge(risk.treatment_strategy)}</td>
                    <td className="px-4 py-4">
                      <div className="flex items-center gap-2">
                        <User className="w-4 h-4 text-gray-400" />
                        <span className="text-sm text-gray-300">{risk.risk_owner_name}</span>
                      </div>
                    </td>
                    <td className="px-4 py-4 text-center">
                      <div className="flex items-center justify-center gap-2">
                        <button className="p-2 hover:bg-slate-600 rounded-lg transition-colors">
                          <Eye className="w-4 h-4 text-gray-400" />
                        </button>
                        <button className="p-2 hover:bg-slate-600 rounded-lg transition-colors">
                          <Edit2 className="w-4 h-4 text-gray-400" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Heat Map View */}
      {view === 'heatmap' && heatMapData && (
        <div className="bg-slate-800 rounded-xl border border-slate-700 p-6">
          <h2 className="text-xl font-bold mb-6 text-white">5×5 Risk Heat Map (Residual Risk)</h2>

          <div className="flex gap-8">
            {/* Matrix */}
            <div className="flex-grow">
              <div className="flex">
                {/* Y-axis label */}
                <div className="flex flex-col items-center justify-center pr-4">
                  <span
                    className="text-gray-400 text-sm font-medium"
                    style={{ writingMode: 'vertical-rl', transform: 'rotate(180deg)' }}
                  >
                    LIKELIHOOD →
                  </span>
                </div>

                <div>
                  {/* Y-axis labels */}
                  <div className="flex">
                    <div className="w-24"></div>
                    {[1, 2, 3, 4, 5].map((impact) => (
                      <div
                        key={impact}
                        className="w-20 text-center text-xs text-gray-400 mb-2"
                      >
                        {heatMapData.impact_labels[impact]}
                      </div>
                    ))}
                  </div>

                  {/* Matrix Grid */}
                  {heatMapData.matrix.map((row, rowIndex) => (
                    <div key={rowIndex} className="flex items-center">
                      {/* Row label */}
                      <div className="w-24 text-right pr-4 text-xs text-gray-400">
                        {heatMapData.likelihood_labels[5 - rowIndex]}
                      </div>

                      {/* Cells */}
                      {row.map((cell, cellIndex) => (
                        <div
                          key={cellIndex}
                          className="w-20 h-16 m-0.5 rounded-lg flex flex-col items-center justify-center cursor-pointer hover:ring-2 hover:ring-white/50 transition-all"
                          style={{ backgroundColor: cell.color }}
                        >
                          <span className="text-white font-bold text-lg">{cell.score}</span>
                          {cell.risk_count > 0 && (
                            <span className="text-white/80 text-xs">
                              ({cell.risk_count} risk{cell.risk_count > 1 ? 's' : ''})
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  ))}

                  {/* X-axis label */}
                  <div className="text-center mt-4 text-gray-400 text-sm font-medium">
                    IMPACT →
                  </div>
                </div>
              </div>
            </div>

            {/* Legend & Stats */}
            <div className="w-64">
              <div className="bg-slate-700 rounded-lg p-4 mb-4">
                <h3 className="font-semibold text-white mb-3">Risk Levels</h3>
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <div className="w-4 h-4 rounded bg-red-500"></div>
                    <span className="text-sm text-gray-300">Critical (17-25)</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-4 h-4 rounded bg-orange-500"></div>
                    <span className="text-sm text-gray-300">High (10-16)</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-4 h-4 rounded bg-yellow-500"></div>
                    <span className="text-sm text-gray-300">Medium (5-9)</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-4 h-4 rounded bg-green-500"></div>
                    <span className="text-sm text-gray-300">Low (1-4)</span>
                  </div>
                </div>
              </div>

              <div className="bg-slate-700 rounded-lg p-4">
                <h3 className="font-semibold text-white mb-3">Summary</h3>
                <div className="space-y-3">
                  <div className="flex justify-between">
                    <span className="text-gray-400">Total Risks</span>
                    <span className="font-bold text-white">{heatMapData.summary.total_risks}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">Avg Inherent</span>
                    <span className="font-bold text-gray-300">
                      {heatMapData.summary.average_inherent_score.toFixed(1)}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">Avg Residual</span>
                    <span className="font-bold text-emerald-400">
                      {heatMapData.summary.average_residual_score.toFixed(1)}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">Risk Reduction</span>
                    <span className="font-bold text-emerald-400">
                      {(
                        ((heatMapData.summary.average_inherent_score -
                          heatMapData.summary.average_residual_score) /
                          heatMapData.summary.average_inherent_score) *
                        100
                      ).toFixed(0)}
                      %
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Bow-Tie View */}
      {view === 'bowtie' && (
        <div className="bg-slate-800 rounded-xl border border-slate-700 p-6">
          <h2 className="text-xl font-bold mb-6 text-white">Bow-Tie Analysis</h2>

          {selectedRisk ? (
            <div className="relative">
              {/* Bow-Tie Diagram */}
              <div className="flex items-center justify-center gap-4">
                {/* Causes (Left Side) */}
                <div className="w-1/4">
                  <h3 className="text-center font-semibold text-red-400 mb-4">CAUSES</h3>
                  <div className="space-y-2">
                    {['Equipment failure', 'Human error', 'Process breakdown'].map((cause, i) => (
                      <div
                        key={i}
                        className="bg-red-500/20 border border-red-500/50 rounded-lg p-3 text-center text-sm text-red-300"
                      >
                        {cause}
                      </div>
                    ))}
                  </div>
                </div>

                {/* Prevention Barriers */}
                <div className="w-16 flex flex-col items-center justify-center">
                  <div className="h-full w-1 bg-gradient-to-b from-red-500 to-yellow-500"></div>
                  <div className="my-2 text-xs text-gray-400 text-center" style={{ writingMode: 'vertical-rl' }}>
                    Prevention
                  </div>
                </div>

                {/* Central Risk Event */}
                <div className="w-1/5">
                  <div
                    className="rounded-full p-8 text-center border-4"
                    style={{ borderColor: selectedRisk.risk_color, backgroundColor: `${selectedRisk.risk_color}20` }}
                  >
                    <AlertTriangle className="w-8 h-8 mx-auto mb-2" style={{ color: selectedRisk.risk_color }} />
                    <span className="font-bold text-white text-sm">{selectedRisk.title.substring(0, 50)}...</span>
                    <div className="mt-2">
                      <span
                        className="px-2 py-1 rounded-full text-xs font-bold"
                        style={{ backgroundColor: selectedRisk.risk_color }}
                      >
                        Score: {selectedRisk.residual_score}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Mitigation Barriers */}
                <div className="w-16 flex flex-col items-center justify-center">
                  <div className="h-full w-1 bg-gradient-to-b from-yellow-500 to-blue-500"></div>
                  <div className="my-2 text-xs text-gray-400 text-center" style={{ writingMode: 'vertical-rl' }}>
                    Mitigation
                  </div>
                </div>

                {/* Consequences (Right Side) */}
                <div className="w-1/4">
                  <h3 className="text-center font-semibold text-blue-400 mb-4">CONSEQUENCES</h3>
                  <div className="space-y-2">
                    {['Financial loss', 'Reputational damage', 'Regulatory penalty'].map((consequence, i) => (
                      <div
                        key={i}
                        className="bg-blue-500/20 border border-blue-500/50 rounded-lg p-3 text-center text-sm text-blue-300"
                      >
                        {consequence}
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Controls/Barriers */}
              <div className="mt-8 grid grid-cols-2 gap-6">
                <div className="bg-slate-700 rounded-lg p-4">
                  <h4 className="font-semibold text-emerald-400 mb-3 flex items-center gap-2">
                    <Shield className="w-4 h-4" />
                    Prevention Controls
                  </h4>
                  <div className="space-y-2">
                    <div className="flex items-center gap-2 p-2 bg-slate-600 rounded">
                      <div className="w-2 h-2 bg-emerald-500 rounded-full"></div>
                      <span className="text-sm text-gray-300">Preventive maintenance program</span>
                    </div>
                    <div className="flex items-center gap-2 p-2 bg-slate-600 rounded">
                      <div className="w-2 h-2 bg-emerald-500 rounded-full"></div>
                      <span className="text-sm text-gray-300">Training and competency assessments</span>
                    </div>
                    <div className="flex items-center gap-2 p-2 bg-slate-600 rounded">
                      <div className="w-2 h-2 bg-yellow-500 rounded-full"></div>
                      <span className="text-sm text-gray-300">Procedure documentation</span>
                    </div>
                  </div>
                </div>

                <div className="bg-slate-700 rounded-lg p-4">
                  <h4 className="font-semibold text-blue-400 mb-3 flex items-center gap-2">
                    <Zap className="w-4 h-4" />
                    Mitigation Controls
                  </h4>
                  <div className="space-y-2">
                    <div className="flex items-center gap-2 p-2 bg-slate-600 rounded">
                      <div className="w-2 h-2 bg-emerald-500 rounded-full"></div>
                      <span className="text-sm text-gray-300">Emergency response plan</span>
                    </div>
                    <div className="flex items-center gap-2 p-2 bg-slate-600 rounded">
                      <div className="w-2 h-2 bg-emerald-500 rounded-full"></div>
                      <span className="text-sm text-gray-300">Insurance coverage</span>
                    </div>
                    <div className="flex items-center gap-2 p-2 bg-slate-600 rounded">
                      <div className="w-2 h-2 bg-yellow-500 rounded-full"></div>
                      <span className="text-sm text-gray-300">Communication protocols</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="text-center py-12 text-gray-400">
              <GitBranch className="w-16 h-16 mx-auto mb-4 opacity-50" />
              <p>Select a risk from the register to view its Bow-Tie analysis</p>
              <button
                onClick={() => setView('register')}
                className="mt-4 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 rounded-lg text-white transition-colors"
              >
                Go to Risk Register
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
