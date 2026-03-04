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
import { Button } from '../components/ui/Button'
import { Card, CardContent } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'

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
  { id: 'strategic', label: 'Strategic', color: 'bg-primary' },
  { id: 'operational', label: 'Operational', color: 'bg-info' },
  { id: 'financial', label: 'Financial', color: 'bg-success' },
  { id: 'compliance', label: 'Compliance', color: 'bg-warning' },
  { id: 'reputational', label: 'Reputational', color: 'bg-destructive' },
  { id: 'health_safety', label: 'Health & Safety', color: 'bg-destructive' },
  { id: 'environmental', label: 'Environmental', color: 'bg-success' },
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
  const [showFilters, setShowFilters] = useState(false)
  const [summary, setSummary] = useState({
    total_risks: 0,
    by_level: { critical: 0, high: 0, medium: 0, low: 0 },
    outside_appetite: 0,
    overdue_review: 0,
    escalated: 0,
  })

  useEffect(() => {
    setTimeout(() => {
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
          risk_color: 'hsl(var(--warning))',
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
          risk_color: 'hsl(var(--warning))',
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
          risk_color: 'hsl(var(--info))',
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
          risk_color: 'hsl(var(--info))',
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
          risk_color: 'hsl(var(--info))',
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

      for (let likelihood = 5; likelihood >= 1; likelihood--) {
        const row: MatrixCell[] = []
        for (let impact = 1; impact <= 5; impact++) {
          const score = likelihood * impact
          let level = 'low'
          let color = 'hsl(var(--success))'
          if (score > 16) {
            level = 'critical'
            color = 'hsl(var(--destructive))'
          } else if (score > 9) {
            level = 'high'
            color = 'hsl(var(--warning))'
          } else if (score > 4) {
            level = 'medium'
            color = 'hsl(var(--info))'
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

  const getRiskLevelBadge = (level: string) => {
    const variants: Record<string, 'destructive' | 'warning' | 'info' | 'resolved'> = {
      critical: 'destructive',
      high: 'warning',
      medium: 'info',
      low: 'resolved',
    }
    return (
      <Badge variant={variants[level] || 'default'} className="uppercase">
        {level}
      </Badge>
    )
  }

  const getTreatmentBadge = (strategy: string) => {
    const s = TREATMENT_STRATEGIES.find((t) => t.id === strategy)
    return (
      <span className="px-2 py-1 bg-muted rounded-full text-xs">
        {s?.icon} {s?.label}
      </span>
    )
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-foreground mb-2">Enterprise Risk Register</h1>
          <p className="text-muted-foreground">ISO 31000 Compliant Risk Management</p>
        </div>
        <div className="flex gap-3">
          <Button variant="secondary" onClick={() => setShowFilters(!showFilters)}>
            <Filter className="w-4 h-4" />
            Filters
          </Button>
          <Button variant="secondary">
            <Download className="w-4 h-4" />
            Export
          </Button>
          <Button>
            <Plus className="w-4 h-4" />
            Add Risk
          </Button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3 mb-2">
              <div className="p-2 bg-info/20 rounded-lg">
                <Layers className="w-5 h-5 text-info" />
              </div>
              <span className="text-2xl font-bold text-foreground">{summary.total_risks}</span>
            </div>
            <p className="text-sm text-muted-foreground">Total Risks</p>
          </CardContent>
        </Card>

        <Card className="border-destructive/30">
          <CardContent className="p-4">
            <div className="flex items-center gap-3 mb-2">
              <div className="p-2 bg-destructive/20 rounded-lg">
                <AlertTriangle className="w-5 h-5 text-destructive" />
              </div>
              <span className="text-2xl font-bold text-destructive">{summary.by_level.critical}</span>
            </div>
            <p className="text-sm text-muted-foreground">Critical</p>
          </CardContent>
        </Card>

        <Card className="border-warning/30">
          <CardContent className="p-4">
            <div className="flex items-center gap-3 mb-2">
              <div className="p-2 bg-warning/20 rounded-lg">
                <AlertCircle className="w-5 h-5 text-warning" />
              </div>
              <span className="text-2xl font-bold text-warning">{summary.by_level.high}</span>
            </div>
            <p className="text-sm text-muted-foreground">High</p>
          </CardContent>
        </Card>

        <Card className="border-info/30">
          <CardContent className="p-4">
            <div className="flex items-center gap-3 mb-2">
              <div className="p-2 bg-info/20 rounded-lg">
                <Activity className="w-5 h-5 text-info" />
              </div>
              <span className="text-2xl font-bold text-info">{summary.by_level.medium}</span>
            </div>
            <p className="text-sm text-muted-foreground">Medium</p>
          </CardContent>
        </Card>

        <Card className="border-primary/30">
          <CardContent className="p-4">
            <div className="flex items-center gap-3 mb-2">
              <div className="p-2 bg-primary/20 rounded-lg">
                <Target className="w-5 h-5 text-primary" />
              </div>
              <span className="text-2xl font-bold text-primary">{summary.outside_appetite}</span>
            </div>
            <p className="text-sm text-muted-foreground">Outside Appetite</p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3 mb-2">
              <div className="p-2 bg-muted rounded-lg">
                <Clock className="w-5 h-5 text-muted-foreground" />
              </div>
              <span className="text-2xl font-bold text-foreground">{summary.overdue_review}</span>
            </div>
            <p className="text-sm text-muted-foreground">Overdue Review</p>
          </CardContent>
        </Card>
      </div>

      {/* View Toggle */}
      <div className="flex gap-2">
        <Button
          variant={view === 'register' ? 'default' : 'secondary'}
          onClick={() => setView('register')}
        >
          <Layers className="w-4 h-4" />
          Risk Register
        </Button>
        <Button
          variant={view === 'heatmap' ? 'default' : 'secondary'}
          onClick={() => setView('heatmap')}
        >
          <BarChart3 className="w-4 h-4" />
          Heat Map
        </Button>
        <Button
          variant={view === 'bowtie' ? 'default' : 'secondary'}
          onClick={() => setView('bowtie')}
        >
          <GitBranch className="w-4 h-4" />
          Bow-Tie Analysis
        </Button>
      </div>

      {/* Register View */}
      {view === 'register' && (
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-muted/50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase">
                    Reference
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase">
                    Risk Title
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase">
                    Category
                  </th>
                  <th className="px-4 py-3 text-center text-xs font-semibold text-muted-foreground uppercase">
                    Inherent
                  </th>
                  <th className="px-4 py-3 text-center text-xs font-semibold text-muted-foreground uppercase">
                    Residual
                  </th>
                  <th className="px-4 py-3 text-center text-xs font-semibold text-muted-foreground uppercase">
                    Level
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase">
                    Treatment
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase">
                    Owner
                  </th>
                  <th className="px-4 py-3 text-center text-xs font-semibold text-muted-foreground uppercase">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {risks.map((risk) => (
                  <tr
                    key={risk.id}
                    className="hover:bg-muted/30 transition-colors cursor-pointer"
                    onClick={() => setSelectedRisk(risk)}
                  >
                    <td className="px-4 py-4">
                      <span className="font-mono text-primary">{risk.reference}</span>
                    </td>
                    <td className="px-4 py-4">
                      <div className="flex items-center gap-2">
                        {!risk.is_within_appetite && (
                          <span className="w-2 h-2 bg-destructive rounded-full animate-pulse" title="Outside Risk Appetite"></span>
                        )}
                        <span className="text-foreground">{risk.title}</span>
                      </div>
                    </td>
                    <td className="px-4 py-4">
                      <Badge variant="default">
                        {CATEGORIES.find((c) => c.id === risk.category)?.label || risk.category}
                      </Badge>
                    </td>
                    <td className="px-4 py-4 text-center">
                      <span className="text-xl font-bold text-muted-foreground">{risk.inherent_score}</span>
                    </td>
                    <td className="px-4 py-4 text-center">
                      <span className="text-xl font-bold text-primary">
                        {risk.residual_score}
                      </span>
                    </td>
                    <td className="px-4 py-4 text-center">
                      {getRiskLevelBadge(risk.risk_level)}
                    </td>
                    <td className="px-4 py-4">{getTreatmentBadge(risk.treatment_strategy)}</td>
                    <td className="px-4 py-4">
                      <div className="flex items-center gap-2">
                        <User className="w-4 h-4 text-muted-foreground" />
                        <span className="text-sm text-foreground">{risk.risk_owner_name}</span>
                      </div>
                    </td>
                    <td className="px-4 py-4 text-center">
                      <div className="flex items-center justify-center gap-2">
                        <Button variant="ghost" size="sm">
                          <Eye className="w-4 h-4" />
                        </Button>
                        <Button variant="ghost" size="sm">
                          <Edit2 className="w-4 h-4" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* Heat Map View */}
      {view === 'heatmap' && heatMapData && (
        <Card>
          <CardContent className="p-6">
            <h2 className="text-xl font-bold mb-6 text-foreground">5×5 Risk Heat Map (Residual Risk)</h2>

            <div className="flex gap-8">
              {/* Matrix */}
              <div className="flex-grow">
                <div className="flex">
                  {/* Y-axis label */}
                  <div className="flex flex-col items-center justify-center pr-4">
                    <span
                      className="text-muted-foreground text-sm font-medium"
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
                          className="w-20 text-center text-xs text-muted-foreground mb-2"
                        >
                          {heatMapData.impact_labels[impact]}
                        </div>
                      ))}
                    </div>

                    {/* Matrix Grid */}
                    {heatMapData.matrix.map((row, rowIndex) => (
                      <div key={rowIndex} className="flex items-center">
                        {/* Row label */}
                        <div className="w-24 text-right pr-4 text-xs text-muted-foreground">
                          {heatMapData.likelihood_labels[5 - rowIndex]}
                        </div>

                        {/* Cells */}
                        {row.map((cell, cellIndex) => (
                          <div
                            key={cellIndex}
                            className="w-20 h-16 m-0.5 rounded-lg flex flex-col items-center justify-center cursor-pointer hover:ring-2 hover:ring-ring transition-all"
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
                    <div className="text-center mt-4 text-muted-foreground text-sm font-medium">
                      IMPACT →
                    </div>
                  </div>
                </div>
              </div>

              {/* Legend & Stats */}
              <div className="w-64 space-y-4">
                <Card>
                  <CardContent className="p-4">
                    <h3 className="font-semibold text-foreground mb-3">Risk Levels</h3>
                    <div className="space-y-2">
                      <div className="flex items-center gap-2">
                        <div className="w-4 h-4 rounded bg-destructive"></div>
                        <span className="text-sm text-foreground">Critical (17-25)</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="w-4 h-4 rounded bg-warning"></div>
                        <span className="text-sm text-foreground">High (10-16)</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="w-4 h-4 rounded bg-info"></div>
                        <span className="text-sm text-foreground">Medium (5-9)</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="w-4 h-4 rounded bg-success"></div>
                        <span className="text-sm text-foreground">Low (1-4)</span>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardContent className="p-4">
                    <h3 className="font-semibold text-foreground mb-3">Summary</h3>
                    <div className="space-y-3">
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Total Risks</span>
                        <span className="font-bold text-foreground">{heatMapData.summary.total_risks}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Avg Inherent</span>
                        <span className="font-bold text-muted-foreground">
                          {(heatMapData.summary?.average_inherent_score ?? 0).toFixed(1)}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Avg Residual</span>
                        <span className="font-bold text-success">
                          {(heatMapData.summary?.average_residual_score ?? 0).toFixed(1)}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Risk Reduction</span>
                        <span className="font-bold text-success">
                          {(
                            heatMapData.summary?.average_inherent_score
                              ? ((heatMapData.summary.average_inherent_score -
                                  (heatMapData.summary.average_residual_score ?? 0)) /
                                  heatMapData.summary.average_inherent_score) *
                                100
                              : 0
                          ).toFixed(0)}
                          %
                        </span>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Bow-Tie View */}
      {view === 'bowtie' && (
        <Card>
          <CardContent className="p-6">
            <h2 className="text-xl font-bold mb-6 text-foreground">Bow-Tie Analysis</h2>

            {selectedRisk ? (
              <div className="relative">
                {/* Bow-Tie Diagram */}
                <div className="flex items-center justify-center gap-4">
                  {/* Causes (Left Side) */}
                  <div className="w-1/4">
                    <h3 className="text-center font-semibold text-destructive mb-4">CAUSES</h3>
                    <div className="space-y-2">
                      {['Equipment failure', 'Human error', 'Process breakdown'].map((cause, i) => (
                        <div
                          key={i}
                          className="bg-destructive/20 border border-destructive/50 rounded-lg p-3 text-center text-sm text-destructive"
                        >
                          {cause}
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Prevention Barriers */}
                  <div className="w-16 flex flex-col items-center justify-center">
                    <div className="h-full w-1 bg-gradient-to-b from-destructive to-warning"></div>
                    <div className="my-2 text-xs text-muted-foreground text-center" style={{ writingMode: 'vertical-rl' }}>
                      Prevention
                    </div>
                  </div>

                  {/* Central Risk Event */}
                  <div className="w-1/5">
                    <div className="rounded-full p-8 text-center border-4 border-warning bg-warning/20">
                      <AlertTriangle className="w-8 h-8 mx-auto mb-2 text-warning" />
                      <span className="font-bold text-foreground text-sm">{selectedRisk.title.substring(0, 50)}...</span>
                      <div className="mt-2">
                        <Badge variant="warning">
                          Score: {selectedRisk.residual_score}
                        </Badge>
                      </div>
                    </div>
                  </div>

                  {/* Mitigation Barriers */}
                  <div className="w-16 flex flex-col items-center justify-center">
                    <div className="h-full w-1 bg-gradient-to-b from-warning to-info"></div>
                    <div className="my-2 text-xs text-muted-foreground text-center" style={{ writingMode: 'vertical-rl' }}>
                      Mitigation
                    </div>
                  </div>

                  {/* Consequences (Right Side) */}
                  <div className="w-1/4">
                    <h3 className="text-center font-semibold text-info mb-4">CONSEQUENCES</h3>
                    <div className="space-y-2">
                      {['Financial loss', 'Reputational damage', 'Regulatory penalty'].map((consequence, i) => (
                        <div
                          key={i}
                          className="bg-info/20 border border-info/50 rounded-lg p-3 text-center text-sm text-info"
                        >
                          {consequence}
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Controls/Barriers */}
                <div className="mt-8 grid grid-cols-2 gap-6">
                  <Card>
                    <CardContent className="p-4">
                      <h4 className="font-semibold text-success mb-3 flex items-center gap-2">
                        <Shield className="w-4 h-4" />
                        Prevention Controls
                      </h4>
                      <div className="space-y-2">
                        <div className="flex items-center gap-2 p-2 bg-muted rounded">
                          <div className="w-2 h-2 bg-success rounded-full"></div>
                          <span className="text-sm text-foreground">Preventive maintenance program</span>
                        </div>
                        <div className="flex items-center gap-2 p-2 bg-muted rounded">
                          <div className="w-2 h-2 bg-success rounded-full"></div>
                          <span className="text-sm text-foreground">Training and competency assessments</span>
                        </div>
                        <div className="flex items-center gap-2 p-2 bg-muted rounded">
                          <div className="w-2 h-2 bg-warning rounded-full"></div>
                          <span className="text-sm text-foreground">Procedure documentation</span>
                        </div>
                      </div>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardContent className="p-4">
                      <h4 className="font-semibold text-info mb-3 flex items-center gap-2">
                        <Zap className="w-4 h-4" />
                        Mitigation Controls
                      </h4>
                      <div className="space-y-2">
                        <div className="flex items-center gap-2 p-2 bg-muted rounded">
                          <div className="w-2 h-2 bg-success rounded-full"></div>
                          <span className="text-sm text-foreground">Emergency response plan</span>
                        </div>
                        <div className="flex items-center gap-2 p-2 bg-muted rounded">
                          <div className="w-2 h-2 bg-success rounded-full"></div>
                          <span className="text-sm text-foreground">Insurance coverage</span>
                        </div>
                        <div className="flex items-center gap-2 p-2 bg-muted rounded">
                          <div className="w-2 h-2 bg-warning rounded-full"></div>
                          <span className="text-sm text-foreground">Communication protocols</span>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </div>
              </div>
            ) : (
              <div className="text-center py-12 text-muted-foreground">
                <GitBranch className="w-16 h-16 mx-auto mb-4 opacity-50" />
                <p>Select a risk from the register to view its Bow-Tie analysis</p>
                <Button onClick={() => setView('register')} className="mt-4">
                  Go to Risk Register
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  )
}
