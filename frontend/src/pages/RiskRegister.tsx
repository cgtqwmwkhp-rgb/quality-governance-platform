import { useState, useEffect, useCallback, useMemo } from 'react'
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
  X,
  Loader2,
  Trash2,
  ChevronDown,
  ChevronUp,
} from 'lucide-react'
import { Button } from '../components/ui/Button'
import { Card, CardContent } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { riskRegisterApi } from '../api/client'
import { ToastContainer, useToast } from '../components/ui/Toast'
import { TableSkeleton } from '../components/ui/SkeletonLoader'

interface Risk {
  id: number
  reference: string
  title: string
  description?: string
  category: string
  department: string
  inherent_score: number
  inherent_likelihood?: number
  inherent_impact?: number
  residual_score: number
  residual_likelihood?: number
  residual_impact?: number
  risk_level: string
  risk_color: string
  treatment_strategy: string
  treatment_plan?: string
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

interface BowTieData {
  risk: { id: number; reference: string; title: string; description: string; category: string; inherent_score: number; residual_score: number }
  causes: { id: number; title: string; description: string }[]
  prevention_barriers: { id: number; title: string; barrier_type: string; effectiveness: string; linked_control_id: number | null }[]
  consequences: { id: number; title: string; description: string }[]
  mitigation_barriers: { id: number; title: string; barrier_type: string; effectiveness: string; linked_control_id: number | null }[]
  escalation_factors: { id: number; title: string; description: string }[]
  controls: { id: number; reference: string; name: string; control_type: string; effectiveness: string }[]
}

const CATEGORIES = [
  { id: 'strategic', label: 'Strategic' },
  { id: 'operational', label: 'Operational' },
  { id: 'financial', label: 'Financial' },
  { id: 'compliance', label: 'Compliance' },
  { id: 'reputational', label: 'Reputational' },
  { id: 'health_safety', label: 'Health & Safety' },
  { id: 'environmental', label: 'Environmental' },
  { id: 'technological', label: 'Technological' },
  { id: 'legal', label: 'Legal' },
  { id: 'project', label: 'Project' },
]

const TREATMENT_STRATEGIES = [
  { id: 'treat', label: 'Treat' },
  { id: 'tolerate', label: 'Tolerate' },
  { id: 'transfer', label: 'Transfer' },
  { id: 'terminate', label: 'Terminate' },
]

const EMPTY_FORM = {
  title: '',
  description: '',
  category: 'operational',
  department: '',
  inherent_likelihood: 3,
  inherent_impact: 3,
  residual_likelihood: 2,
  residual_impact: 2,
  treatment_strategy: 'treat',
  treatment_plan: '',
  risk_owner_name: '',
  review_frequency_days: 90,
}

export default function RiskRegister() {
  const [view, setView] = useState<'register' | 'heatmap' | 'bowtie'>('register')
  const [risks, setRisks] = useState<Risk[]>([])
  const [heatMapData, setHeatMapData] = useState<HeatMapData | null>(null)
  const [selectedRisk, setSelectedRisk] = useState<Risk | null>(null)
  const [bowTieData, setBowTieData] = useState<BowTieData | null>(null)
  const [bowTieLoading, setBowTieLoading] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showFilters, setShowFilters] = useState(false)
  const [filterCategory, setFilterCategory] = useState('')
  const [filterStatus, setFilterStatus] = useState('')
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [showDetailModal, setShowDetailModal] = useState(false)
  const [showEditModal, setShowEditModal] = useState(false)
  const [detailRisk, setDetailRisk] = useState<Record<string, unknown> | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [createForm, setCreateForm] = useState({ ...EMPTY_FORM })
  const [editForm, setEditForm] = useState({ ...EMPTY_FORM })
  const [saving, setSaving] = useState(false)
  const { toasts, show: showToast, dismiss: dismissToast } = useToast()

  const [summary, setSummary] = useState({
    total_risks: 0,
    by_level: { critical: 0, high: 0, medium: 0, low: 0 },
    outside_appetite: 0,
    overdue_review: 0,
    escalated: 0,
  })

  const scoreToLevel = (score: number) => {
    if (score > 16) return 'critical'
    if (score > 9) return 'high'
    if (score > 4) return 'medium'
    return 'low'
  }

  const levelToColor = (level: string) => {
    const map: Record<string, string> = {
      critical: 'hsl(var(--destructive))',
      high: 'hsl(var(--warning))',
      medium: 'hsl(var(--info))',
      low: 'hsl(var(--success))',
    }
    return map[level] || map.low
  }

  const loadRisks = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const params: Record<string, string | number> = { skip: 0, limit: 100 }
      if (filterCategory) params.category = filterCategory
      if (filterStatus) params.status = filterStatus

      const res = await riskRegisterApi.list(params)
      const data = res.data as unknown as Record<string, unknown>
      const rawItems = (data?.risks ?? data?.items ?? []) as Record<string, unknown>[]
      const mapped: Risk[] = rawItems.map((r) => {
        const resScore = Number(r.residual_score || 0)
        const inhScore = Number(r.inherent_score || 0)
        const level = String(r.risk_level || scoreToLevel(resScore || inhScore))
        return {
          id: Number(r.id),
          reference: String(r.reference || `RISK-${String(r.id).padStart(4, '0')}`),
          title: String(r.title || ''),
          description: String(r.description || ''),
          category: String(r.category || 'operational'),
          department: String(r.department || ''),
          inherent_score: inhScore,
          inherent_likelihood: Number(r.inherent_likelihood || 0),
          inherent_impact: Number(r.inherent_impact || 0),
          residual_score: resScore,
          residual_likelihood: Number(r.residual_likelihood || 0),
          residual_impact: Number(r.residual_impact || 0),
          risk_level: level,
          risk_color: String(r.risk_color || levelToColor(level)),
          treatment_strategy: String(r.treatment_strategy || 'treat'),
          treatment_plan: String(r.treatment_plan || ''),
          status: String(r.status || 'monitoring'),
          is_within_appetite: r.is_within_appetite !== false,
          risk_owner_name: String(r.risk_owner_name || ''),
          next_review_date: r.next_review_date ? String(r.next_review_date) : null,
        }
      })
      setRisks(mapped)

      // Load summary from API
      try {
        const summaryRes = await riskRegisterApi.getSummary()
        const sd = summaryRes.data as unknown as Record<string, unknown>
        const defaultByLevel = {
          critical: mapped.filter(r => r.risk_level === 'critical').length,
          high: mapped.filter(r => r.risk_level === 'high').length,
          medium: mapped.filter(r => r.risk_level === 'medium').length,
          low: mapped.filter(r => r.risk_level === 'low').length,
        }
        const byLevel = sd?.by_level as { critical: number; high: number; medium: number; low: number } | undefined
        setSummary({
          total_risks: Number(sd?.total_risks || mapped.length),
          by_level: byLevel || defaultByLevel,
          outside_appetite: Number(sd?.outside_appetite || 0),
          overdue_review: Number(sd?.overdue_review || 0),
          escalated: Number(sd?.escalated || 0),
        })
      } catch {
        const critical = mapped.filter(r => r.risk_level === 'critical').length
        const high = mapped.filter(r => r.risk_level === 'high').length
        const medium = mapped.filter(r => r.risk_level === 'medium').length
        const low = mapped.filter(r => r.risk_level === 'low').length
        setSummary({
          total_risks: mapped.length,
          by_level: { critical, high, medium, low },
          outside_appetite: mapped.filter(r => !r.is_within_appetite).length,
          overdue_review: mapped.filter(r => r.next_review_date && new Date(r.next_review_date) < new Date()).length,
          escalated: 0,
        })
      }

      // Load heatmap from API
      try {
        const hmRes = await riskRegisterApi.getHeatmap()
        setHeatMapData(hmRes.data as unknown as HeatMapData)
      } catch {
        setHeatMapData(null)
      }
    } catch {
      setError('Failed to load risks. Please try again.')
    } finally {
      setLoading(false)
    }
  }, [filterCategory, filterStatus])

  useEffect(() => {
    loadRisks()
  }, [loadRisks])

  const loadBowTie = useCallback(async (riskId: number) => {
    try {
      setBowTieLoading(true)
      const res = await riskRegisterApi.getBowtie(riskId)
      setBowTieData(res.data as unknown as BowTieData)
    } catch {
      setBowTieData(null)
      showToast('Bow-tie data not available for this risk', 'info')
    } finally {
      setBowTieLoading(false)
    }
  }, [showToast])

  const handleViewRisk = async (risk: Risk) => {
    try {
      setDetailLoading(true)
      setShowDetailModal(true)
      const res = await riskRegisterApi.get(risk.id)
      setDetailRisk(res.data as unknown as Record<string, unknown>)
    } catch {
      showToast('Failed to load risk details', 'error')
      setShowDetailModal(false)
    } finally {
      setDetailLoading(false)
    }
  }

  const handleEditRisk = async (risk: Risk) => {
    try {
      const res = await riskRegisterApi.get(risk.id)
      const d = res.data as unknown as Record<string, unknown>
      setEditForm({
        title: String(d.title || ''),
        description: String(d.description || ''),
        category: String(d.category || 'operational'),
        department: String(d.department || ''),
        inherent_likelihood: Number(d.inherent_likelihood) || 3,
        inherent_impact: Number(d.inherent_impact) || 3,
        residual_likelihood: Number(d.residual_likelihood) || 2,
        residual_impact: Number(d.residual_impact) || 2,
        treatment_strategy: String(d.treatment_strategy || 'treat'),
        treatment_plan: String(d.treatment_plan || ''),
        risk_owner_name: String(d.risk_owner_name || ''),
        review_frequency_days: Number(d.review_frequency_days) || 90,
      })
      setSelectedRisk(risk)
      setShowEditModal(true)
    } catch {
      showToast('Failed to load risk for editing', 'error')
    }
  }

  const handleCreateRisk = async () => {
    if (!createForm.title || createForm.title.length < 5) {
      showToast('Risk title must be at least 5 characters', 'warning')
      return
    }
    if (!createForm.description || createForm.description.length < 10) {
      showToast('Risk description must be at least 10 characters', 'warning')
      return
    }
    try {
      setSaving(true)
      await riskRegisterApi.create(createForm)
      showToast('Risk created successfully', 'success')
      setShowCreateModal(false)
      setCreateForm({ ...EMPTY_FORM })
      await loadRisks()
    } catch {
      showToast('Failed to create risk', 'error')
    } finally {
      setSaving(false)
    }
  }

  const handleUpdateRisk = async () => {
    if (!selectedRisk) return
    try {
      setSaving(true)
      await riskRegisterApi.update(selectedRisk.id, {
        title: editForm.title,
        description: editForm.description,
        category: editForm.category,
        department: editForm.department,
        treatment_strategy: editForm.treatment_strategy,
        treatment_plan: editForm.treatment_plan,
      })
      await riskRegisterApi.assess(selectedRisk.id, {
        likelihood: editForm.residual_likelihood,
        impact: editForm.residual_impact,
      })
      showToast('Risk updated successfully', 'success')
      setShowEditModal(false)
      await loadRisks()
    } catch {
      showToast('Failed to update risk', 'error')
    } finally {
      setSaving(false)
    }
  }

  const handleDeleteRisk = async (risk: Risk) => {
    if (!window.confirm(`Archive risk "${risk.reference}: ${risk.title}"? This will set its status to closed.`)) return
    try {
      await riskRegisterApi.delete(risk.id)
      showToast('Risk archived successfully', 'success')
      await loadRisks()
    } catch {
      showToast('Failed to archive risk', 'error')
    }
  }

  const handleExport = () => {
    if (risks.length === 0) {
      showToast('No risks to export', 'info')
      return
    }
    const headers = ['Reference', 'Title', 'Category', 'Inherent Score', 'Residual Score', 'Level', 'Treatment', 'Owner', 'Status']
    const csvRows = [
      headers.join(','),
      ...risks.map(r =>
        [r.reference, `"${r.title}"`, r.category, r.inherent_score, r.residual_score, r.risk_level, r.treatment_strategy, `"${r.risk_owner_name}"`, r.status].join(',')
      ),
    ]
    const blob = new Blob([csvRows.join('\n')], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `risk-register-${new Date().toISOString().slice(0, 10)}.csv`
    a.click()
    URL.revokeObjectURL(url)
    showToast('Risk register exported', 'success')
  }

  const getRiskLevelBadge = (level: string) => {
    const variants: Record<string, 'destructive' | 'warning' | 'info' | 'resolved'> = {
      critical: 'destructive',
      high: 'warning',
      medium: 'info',
      low: 'resolved',
    }
    return <Badge variant={variants[level] || 'default'} className="uppercase">{level}</Badge>
  }

  const getTreatmentBadge = (strategy: string) => {
    const s = TREATMENT_STRATEGIES.find(t => t.id === strategy)
    return <span className="px-2 py-1 bg-muted rounded-full text-xs text-foreground">{s?.label || strategy}</span>
  }

  const effectivenessColor = (eff: string | null | undefined) => {
    if (!eff) return 'bg-muted'
    if (eff === 'effective') return 'bg-success'
    if (eff === 'partially') return 'bg-warning'
    return 'bg-destructive'
  }

  const riskReduction = useMemo(() => {
    if (!heatMapData) return 0
    const inh = heatMapData.summary.average_inherent_score
    const res = heatMapData.summary.average_residual_score
    if (!inh || inh === 0) return 0
    return ((inh - res) / inh) * 100
  }, [heatMapData])

  // ── Render ──

  if (loading) {
    return (
      <div className="p-6"><TableSkeleton rows={5} columns={4} /></div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-screen gap-4">
        <AlertCircle className="h-16 w-16 text-destructive" />
        <p className="text-lg text-foreground">{error}</p>
        <Button onClick={loadRisks}>Retry</Button>
      </div>
    )
  }

  const RiskFormFields = ({ form, onChange }: { form: typeof EMPTY_FORM; onChange: (f: typeof EMPTY_FORM) => void }) => (
    <div className="space-y-4 max-h-[70vh] overflow-y-auto pr-2">
      <div>
        <label className="block text-sm font-medium text-foreground mb-1">Title *</label>
        <input
          className="w-full border border-border rounded-lg px-3 py-2 bg-card text-foreground focus:ring-2 focus:ring-primary focus:border-primary"
          value={form.title}
          onChange={e => onChange({ ...form, title: e.target.value })}
          placeholder="Risk title (min 5 chars)"
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-foreground mb-1">Description *</label>
        <textarea
          rows={3}
          className="w-full border border-border rounded-lg px-3 py-2 bg-card text-foreground focus:ring-2 focus:ring-primary focus:border-primary resize-none"
          value={form.description}
          onChange={e => onChange({ ...form, description: e.target.value })}
          placeholder="Detailed risk description (min 10 chars)"
        />
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-foreground mb-1">Category</label>
          <select
            className="w-full border border-border rounded-lg px-3 py-2 bg-card text-foreground"
            value={form.category}
            onChange={e => onChange({ ...form, category: e.target.value })}
          >
            {CATEGORIES.map(c => (
              <option key={c.id} value={c.id}>{c.label}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-foreground mb-1">Department</label>
          <input
            className="w-full border border-border rounded-lg px-3 py-2 bg-card text-foreground"
            value={form.department}
            onChange={e => onChange({ ...form, department: e.target.value })}
            placeholder="e.g. Operations"
          />
        </div>
      </div>
      <div>
        <label className="block text-sm font-medium text-foreground mb-1">Risk Owner</label>
        <input
          className="w-full border border-border rounded-lg px-3 py-2 bg-card text-foreground"
          value={form.risk_owner_name}
          onChange={e => onChange({ ...form, risk_owner_name: e.target.value })}
          placeholder="Person responsible"
        />
      </div>
      <div className="border-t border-border pt-4">
        <h4 className="text-sm font-semibold text-foreground mb-3">Inherent Risk (before controls)</h4>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs text-muted-foreground mb-1">Likelihood (1-5)</label>
            <input
              type="range" min={1} max={5} step={1}
              className="w-full accent-primary"
              value={form.inherent_likelihood}
              onChange={e => onChange({ ...form, inherent_likelihood: Number(e.target.value) })}
            />
            <div className="flex justify-between text-xs text-muted-foreground">
              <span>Rare</span><span className="font-bold text-foreground">{form.inherent_likelihood}</span><span>Certain</span>
            </div>
          </div>
          <div>
            <label className="block text-xs text-muted-foreground mb-1">Impact (1-5)</label>
            <input
              type="range" min={1} max={5} step={1}
              className="w-full accent-primary"
              value={form.inherent_impact}
              onChange={e => onChange({ ...form, inherent_impact: Number(e.target.value) })}
            />
            <div className="flex justify-between text-xs text-muted-foreground">
              <span>Minor</span><span className="font-bold text-foreground">{form.inherent_impact}</span><span>Critical</span>
            </div>
          </div>
        </div>
        <div className="mt-2 text-center">
          <span className="text-sm text-muted-foreground">Inherent Score: </span>
          <span className="font-bold text-lg" style={{ color: levelToColor(scoreToLevel(form.inherent_likelihood * form.inherent_impact)) }}>
            {form.inherent_likelihood * form.inherent_impact}
          </span>
        </div>
      </div>
      <div className="border-t border-border pt-4">
        <h4 className="text-sm font-semibold text-foreground mb-3">Residual Risk (after controls)</h4>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs text-muted-foreground mb-1">Likelihood (1-5)</label>
            <input
              type="range" min={1} max={5} step={1}
              className="w-full accent-primary"
              value={form.residual_likelihood}
              onChange={e => onChange({ ...form, residual_likelihood: Number(e.target.value) })}
            />
            <div className="flex justify-between text-xs text-muted-foreground">
              <span>Rare</span><span className="font-bold text-foreground">{form.residual_likelihood}</span><span>Certain</span>
            </div>
          </div>
          <div>
            <label className="block text-xs text-muted-foreground mb-1">Impact (1-5)</label>
            <input
              type="range" min={1} max={5} step={1}
              className="w-full accent-primary"
              value={form.residual_impact}
              onChange={e => onChange({ ...form, residual_impact: Number(e.target.value) })}
            />
            <div className="flex justify-between text-xs text-muted-foreground">
              <span>Minor</span><span className="font-bold text-foreground">{form.residual_impact}</span><span>Critical</span>
            </div>
          </div>
        </div>
        <div className="mt-2 text-center">
          <span className="text-sm text-muted-foreground">Residual Score: </span>
          <span className="font-bold text-lg" style={{ color: levelToColor(scoreToLevel(form.residual_likelihood * form.residual_impact)) }}>
            {form.residual_likelihood * form.residual_impact}
          </span>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-4 border-t border-border pt-4">
        <div>
          <label className="block text-sm font-medium text-foreground mb-1">Treatment Strategy</label>
          <select
            className="w-full border border-border rounded-lg px-3 py-2 bg-card text-foreground"
            value={form.treatment_strategy}
            onChange={e => onChange({ ...form, treatment_strategy: e.target.value })}
          >
            {TREATMENT_STRATEGIES.map(s => (
              <option key={s.id} value={s.id}>{s.label}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-foreground mb-1">Review Frequency (days)</label>
          <input
            type="number" min={7} max={365}
            className="w-full border border-border rounded-lg px-3 py-2 bg-card text-foreground"
            value={form.review_frequency_days}
            onChange={e => onChange({ ...form, review_frequency_days: Number(e.target.value) })}
          />
        </div>
      </div>
      <div>
        <label className="block text-sm font-medium text-foreground mb-1">Treatment Plan</label>
        <textarea
          rows={2}
          className="w-full border border-border rounded-lg px-3 py-2 bg-card text-foreground resize-none"
          value={form.treatment_plan}
          onChange={e => onChange({ ...form, treatment_plan: e.target.value })}
          placeholder="Actions to treat this risk"
        />
      </div>
    </div>
  )

  return (
    <div className="space-y-6">
      <ToastContainer toasts={toasts} onDismiss={dismissToast} />

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
            {showFilters ? <ChevronUp className="w-3 h-3 ml-1" /> : <ChevronDown className="w-3 h-3 ml-1" />}
          </Button>
          <Button variant="secondary" onClick={handleExport}>
            <Download className="w-4 h-4" />
            Export
          </Button>
          <Button onClick={() => { setCreateForm({ ...EMPTY_FORM }); setShowCreateModal(true) }}>
            <Plus className="w-4 h-4" />
            Add Risk
          </Button>
        </div>
      </div>

      {/* Filter Panel */}
      {showFilters && (
        <Card>
          <CardContent className="p-4">
            <div className="flex flex-wrap items-end gap-4">
              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-1">Category</label>
                <select
                  className="border border-border rounded-lg px-3 py-2 bg-card text-foreground text-sm"
                  value={filterCategory}
                  onChange={e => setFilterCategory(e.target.value)}
                >
                  <option value="">All Categories</option>
                  {CATEGORIES.map(c => (
                    <option key={c.id} value={c.id}>{c.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-1">Status</label>
                <select
                  className="border border-border rounded-lg px-3 py-2 bg-card text-foreground text-sm"
                  value={filterStatus}
                  onChange={e => setFilterStatus(e.target.value)}
                >
                  <option value="">All Statuses</option>
                  <option value="identified">Identified</option>
                  <option value="assessing">Assessing</option>
                  <option value="treating">Treating</option>
                  <option value="monitoring">Monitoring</option>
                </select>
              </div>
              <Button variant="secondary" size="sm" onClick={() => { setFilterCategory(''); setFilterStatus('') }}>
                Clear Filters
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3 mb-2">
              <div className="p-2 bg-info/20 rounded-lg"><Layers className="w-5 h-5 text-info" /></div>
              <span className="text-2xl font-bold text-foreground">{summary.total_risks}</span>
            </div>
            <p className="text-sm text-muted-foreground">Total Risks</p>
          </CardContent>
        </Card>
        <Card className="border-destructive/30">
          <CardContent className="p-4">
            <div className="flex items-center gap-3 mb-2">
              <div className="p-2 bg-destructive/20 rounded-lg"><AlertTriangle className="w-5 h-5 text-destructive" /></div>
              <span className="text-2xl font-bold text-destructive">{summary.by_level.critical}</span>
            </div>
            <p className="text-sm text-muted-foreground">Critical</p>
          </CardContent>
        </Card>
        <Card className="border-warning/30">
          <CardContent className="p-4">
            <div className="flex items-center gap-3 mb-2">
              <div className="p-2 bg-warning/20 rounded-lg"><AlertCircle className="w-5 h-5 text-warning" /></div>
              <span className="text-2xl font-bold text-warning">{summary.by_level.high}</span>
            </div>
            <p className="text-sm text-muted-foreground">High</p>
          </CardContent>
        </Card>
        <Card className="border-info/30">
          <CardContent className="p-4">
            <div className="flex items-center gap-3 mb-2">
              <div className="p-2 bg-info/20 rounded-lg"><Activity className="w-5 h-5 text-info" /></div>
              <span className="text-2xl font-bold text-info">{summary.by_level.medium}</span>
            </div>
            <p className="text-sm text-muted-foreground">Medium</p>
          </CardContent>
        </Card>
        <Card className="border-primary/30">
          <CardContent className="p-4">
            <div className="flex items-center gap-3 mb-2">
              <div className="p-2 bg-primary/20 rounded-lg"><Target className="w-5 h-5 text-primary" /></div>
              <span className="text-2xl font-bold text-primary">{summary.outside_appetite}</span>
            </div>
            <p className="text-sm text-muted-foreground">Outside Appetite</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3 mb-2">
              <div className="p-2 bg-muted rounded-lg"><Clock className="w-5 h-5 text-muted-foreground" /></div>
              <span className="text-2xl font-bold text-foreground">{summary.overdue_review}</span>
            </div>
            <p className="text-sm text-muted-foreground">Overdue Review</p>
          </CardContent>
        </Card>
      </div>

      {/* View Toggle */}
      <div className="flex gap-2">
        <Button variant={view === 'register' ? 'default' : 'secondary'} onClick={() => setView('register')}>
          <Layers className="w-4 h-4" /> Risk Register
        </Button>
        <Button variant={view === 'heatmap' ? 'default' : 'secondary'} onClick={() => setView('heatmap')}>
          <BarChart3 className="w-4 h-4" /> Heat Map
        </Button>
        <Button
          variant={view === 'bowtie' ? 'default' : 'secondary'}
          onClick={() => {
            setView('bowtie')
            if (selectedRisk && !bowTieData) loadBowTie(selectedRisk.id)
          }}
        >
          <GitBranch className="w-4 h-4" /> Bow-Tie Analysis
        </Button>
      </div>

      {/* Register View */}
      {view === 'register' && (
        <Card>
          {risks.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
              <Shield className="w-16 h-16 mb-4 opacity-40" />
              <p className="text-lg font-medium mb-2">No risks registered</p>
              <p className="text-sm mb-4">Get started by adding your first risk to the register.</p>
              <Button onClick={() => { setCreateForm({ ...EMPTY_FORM }); setShowCreateModal(true) }}>
                <Plus className="w-4 h-4" /> Add First Risk
              </Button>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-muted/50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase">Reference</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase">Risk Title</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase">Category</th>
                    <th className="px-4 py-3 text-center text-xs font-semibold text-muted-foreground uppercase">Inherent</th>
                    <th className="px-4 py-3 text-center text-xs font-semibold text-muted-foreground uppercase">Residual</th>
                    <th className="px-4 py-3 text-center text-xs font-semibold text-muted-foreground uppercase">Level</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase">Treatment</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase">Owner</th>
                    <th className="px-4 py-3 text-center text-xs font-semibold text-muted-foreground uppercase">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {risks.map(risk => (
                    <tr
                      key={risk.id}
                      className={`hover:bg-muted/30 transition-colors cursor-pointer ${selectedRisk?.id === risk.id ? 'bg-primary/5' : ''}`}
                      onClick={() => setSelectedRisk(risk)}
                    >
                      <td className="px-4 py-4">
                        <span className="font-mono text-primary">{risk.reference}</span>
                      </td>
                      <td className="px-4 py-4">
                        <div className="flex items-center gap-2">
                          {!risk.is_within_appetite && (
                            <span className="w-2 h-2 bg-destructive rounded-full animate-pulse flex-shrink-0" title="Outside Risk Appetite" />
                          )}
                          <span className="text-foreground">{risk.title}</span>
                        </div>
                      </td>
                      <td className="px-4 py-4">
                        <Badge variant="default">{CATEGORIES.find(c => c.id === risk.category)?.label || risk.category}</Badge>
                      </td>
                      <td className="px-4 py-4 text-center">
                        <span className="text-xl font-bold text-muted-foreground">{risk.inherent_score}</span>
                      </td>
                      <td className="px-4 py-4 text-center">
                        <span className="text-xl font-bold" style={{ color: risk.risk_color }}>{risk.residual_score}</span>
                      </td>
                      <td className="px-4 py-4 text-center">{getRiskLevelBadge(risk.risk_level)}</td>
                      <td className="px-4 py-4">{getTreatmentBadge(risk.treatment_strategy)}</td>
                      <td className="px-4 py-4">
                        <div className="flex items-center gap-2">
                          <User className="w-4 h-4 text-muted-foreground" />
                          <span className="text-sm text-foreground">{risk.risk_owner_name || '—'}</span>
                        </div>
                      </td>
                      <td className="px-4 py-4 text-center">
                        <div className="flex items-center justify-center gap-1" onClick={e => e.stopPropagation()}>
                          <Button variant="ghost" size="sm" onClick={() => handleViewRisk(risk)} aria-label="View risk details">
                            <Eye className="w-4 h-4" />
                          </Button>
                          <Button variant="ghost" size="sm" onClick={() => handleEditRisk(risk)} aria-label="Edit risk">
                            <Edit2 className="w-4 h-4" />
                          </Button>
                          <Button variant="ghost" size="sm" onClick={() => handleDeleteRisk(risk)} aria-label="Archive risk">
                            <Trash2 className="w-4 h-4 text-destructive" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}

      {/* Heat Map View */}
      {view === 'heatmap' && heatMapData && (
        <Card>
          <CardContent className="p-6">
            <h2 className="text-xl font-bold mb-6 text-foreground">5x5 Risk Heat Map (Residual Risk)</h2>
            <div className="flex gap-8">
              <div className="flex-grow">
                <div className="flex">
                  <div className="flex flex-col items-center justify-center pr-4">
                    <span className="text-muted-foreground text-sm font-medium" style={{ writingMode: 'vertical-rl', transform: 'rotate(180deg)' }}>
                      LIKELIHOOD &rarr;
                    </span>
                  </div>
                  <div>
                    <div className="flex">
                      <div className="w-24" />
                      {[1, 2, 3, 4, 5].map(impact => (
                        <div key={impact} className="w-20 text-center text-xs text-muted-foreground mb-2">
                          {heatMapData.impact_labels[impact]}
                        </div>
                      ))}
                    </div>
                    {heatMapData.matrix.map((row, rowIndex) => (
                      <div key={rowIndex} className="flex items-center">
                        <div className="w-24 text-right pr-4 text-xs text-muted-foreground">
                          {heatMapData.likelihood_labels[5 - rowIndex]}
                        </div>
                        {row.map((cell, cellIndex) => (
                          <div
                            key={cellIndex}
                            className="w-20 h-16 m-0.5 rounded-lg flex flex-col items-center justify-center cursor-pointer hover:ring-2 hover:ring-ring transition-all relative group"
                            style={{ backgroundColor: cell.color }}
                            title={cell.risk_titles?.join(', ') || `Score ${cell.score}`}
                          >
                            <span className="text-white font-bold text-lg">{cell.score}</span>
                            {cell.risk_count > 0 && (
                              <span className="text-white/80 text-xs">({cell.risk_count} risk{cell.risk_count > 1 ? 's' : ''})</span>
                            )}
                          </div>
                        ))}
                      </div>
                    ))}
                    <div className="text-center mt-4 text-muted-foreground text-sm font-medium">IMPACT &rarr;</div>
                  </div>
                </div>
              </div>
              <div className="w-64 space-y-4">
                <Card>
                  <CardContent className="p-4">
                    <h3 className="font-semibold text-foreground mb-3">Risk Levels</h3>
                    <div className="space-y-2">
                      {[
                        { level: 'Critical (17-25)', cls: 'bg-destructive' },
                        { level: 'High (10-16)', cls: 'bg-warning' },
                        { level: 'Medium (5-9)', cls: 'bg-info' },
                        { level: 'Low (1-4)', cls: 'bg-success' },
                      ].map(l => (
                        <div key={l.level} className="flex items-center gap-2">
                          <div className={`w-4 h-4 rounded ${l.cls}`} />
                          <span className="text-sm text-foreground">{l.level}</span>
                        </div>
                      ))}
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
                        <span className="font-bold text-muted-foreground">{(heatMapData.summary.average_inherent_score || 0).toFixed(1)}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Avg Residual</span>
                        <span className="font-bold text-success">{(heatMapData.summary.average_residual_score || 0).toFixed(1)}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Risk Reduction</span>
                        <span className="font-bold text-success">{riskReduction.toFixed(0)}%</span>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {view === 'heatmap' && !heatMapData && (
        <Card>
          <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
            <BarChart3 className="w-16 h-16 mb-4 opacity-40" />
            <p>No heat map data available. Add risks to see the heat map.</p>
          </div>
        </Card>
      )}

      {/* Bow-Tie View */}
      {view === 'bowtie' && (
        <Card>
          <CardContent className="p-6">
            <h2 className="text-xl font-bold mb-6 text-foreground">Bow-Tie Analysis</h2>

            {!selectedRisk ? (
              <div className="text-center py-12 text-muted-foreground">
                <GitBranch className="w-16 h-16 mx-auto mb-4 opacity-50" />
                <p className="mb-4">Select a risk from the register to view its Bow-Tie analysis</p>
                <Button onClick={() => setView('register')}>Go to Risk Register</Button>
              </div>
            ) : bowTieLoading ? (
              <div className="flex items-center justify-center py-16">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
              </div>
            ) : bowTieData ? (
              <div>
                <div className="flex items-center justify-center gap-4">
                  {/* Causes */}
                  <div className="w-1/4">
                    <h3 className="text-center font-semibold text-destructive mb-4">CAUSES</h3>
                    <div className="space-y-2">
                      {bowTieData.causes.length > 0 ? bowTieData.causes.map(cause => (
                        <div key={cause.id} className="bg-destructive/10 border border-destructive/30 rounded-lg p-3 text-center text-sm text-foreground">
                          {cause.title}
                        </div>
                      )) : (
                        <p className="text-xs text-center text-muted-foreground italic">No causes defined</p>
                      )}
                    </div>
                  </div>

                  {/* Prevention Barriers */}
                  <div className="w-16 flex flex-col items-center justify-center">
                    <div className="h-full w-1 bg-gradient-to-b from-destructive to-warning" />
                    <div className="my-2 text-xs text-muted-foreground text-center" style={{ writingMode: 'vertical-rl' }}>
                      Prevention ({bowTieData.prevention_barriers.length})
                    </div>
                  </div>

                  {/* Central Risk */}
                  <div className="w-1/5">
                    <div className="rounded-2xl p-6 text-center border-4 border-warning bg-warning/10">
                      <AlertTriangle className="w-8 h-8 mx-auto mb-2 text-warning" />
                      <span className="font-bold text-foreground text-sm block">
                        {bowTieData.risk.title.length > 50 ? bowTieData.risk.title.substring(0, 50) + '...' : bowTieData.risk.title}
                      </span>
                      <div className="mt-2">
                        <Badge variant="warning">Score: {bowTieData.risk.residual_score}</Badge>
                      </div>
                    </div>
                  </div>

                  {/* Mitigation Barriers */}
                  <div className="w-16 flex flex-col items-center justify-center">
                    <div className="h-full w-1 bg-gradient-to-b from-warning to-info" />
                    <div className="my-2 text-xs text-muted-foreground text-center" style={{ writingMode: 'vertical-rl' }}>
                      Mitigation ({bowTieData.mitigation_barriers.length})
                    </div>
                  </div>

                  {/* Consequences */}
                  <div className="w-1/4">
                    <h3 className="text-center font-semibold text-info mb-4">CONSEQUENCES</h3>
                    <div className="space-y-2">
                      {bowTieData.consequences.length > 0 ? bowTieData.consequences.map(cons => (
                        <div key={cons.id} className="bg-info/10 border border-info/30 rounded-lg p-3 text-center text-sm text-foreground">
                          {cons.title}
                        </div>
                      )) : (
                        <p className="text-xs text-center text-muted-foreground italic">No consequences defined</p>
                      )}
                    </div>
                  </div>
                </div>

                {/* Controls/Barriers Detail */}
                <div className="mt-8 grid grid-cols-2 gap-6">
                  <Card>
                    <CardContent className="p-4">
                      <h4 className="font-semibold text-success mb-3 flex items-center gap-2">
                        <Shield className="w-4 h-4" /> Prevention Controls
                      </h4>
                      <div className="space-y-2">
                        {bowTieData.prevention_barriers.length > 0 ? bowTieData.prevention_barriers.map(b => (
                          <div key={b.id} className="flex items-center gap-2 p-2 bg-muted rounded">
                            <div className={`w-2 h-2 rounded-full ${effectivenessColor(b.effectiveness)}`} />
                            <span className="text-sm text-foreground flex-1">{b.title}</span>
                            {b.effectiveness && <span className="text-xs text-muted-foreground">{b.effectiveness}</span>}
                          </div>
                        )) : (
                          <p className="text-sm text-muted-foreground italic">No prevention controls defined yet</p>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                  <Card>
                    <CardContent className="p-4">
                      <h4 className="font-semibold text-info mb-3 flex items-center gap-2">
                        <Zap className="w-4 h-4" /> Mitigation Controls
                      </h4>
                      <div className="space-y-2">
                        {bowTieData.mitigation_barriers.length > 0 ? bowTieData.mitigation_barriers.map(b => (
                          <div key={b.id} className="flex items-center gap-2 p-2 bg-muted rounded">
                            <div className={`w-2 h-2 rounded-full ${effectivenessColor(b.effectiveness)}`} />
                            <span className="text-sm text-foreground flex-1">{b.title}</span>
                            {b.effectiveness && <span className="text-xs text-muted-foreground">{b.effectiveness}</span>}
                          </div>
                        )) : (
                          <p className="text-sm text-muted-foreground italic">No mitigation controls defined yet</p>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                </div>
              </div>
            ) : (
              <div className="text-center py-12 text-muted-foreground">
                <GitBranch className="w-16 h-16 mx-auto mb-4 opacity-50" />
                <p className="mb-2">No bow-tie data for {selectedRisk.reference}</p>
                <p className="text-sm mb-4">Add causes, consequences, and barriers to build the bow-tie diagram.</p>
                <Button onClick={() => setView('register')}>Back to Register</Button>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* ══════════════ Modals ══════════════ */}

      {/* Create Risk Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm" onClick={() => setShowCreateModal(false)}>
          <div className="bg-card border border-border rounded-2xl shadow-2xl w-full max-w-2xl mx-4 p-6" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-bold text-foreground">Add New Risk</h2>
              <button onClick={() => setShowCreateModal(false)} className="p-1 rounded-lg hover:bg-muted transition-colors">
                <X className="w-5 h-5 text-muted-foreground" />
              </button>
            </div>
            <RiskFormFields form={createForm} onChange={setCreateForm} />
            <div className="flex justify-end gap-3 mt-6 pt-4 border-t border-border">
              <Button variant="secondary" onClick={() => setShowCreateModal(false)}>Cancel</Button>
              <Button onClick={handleCreateRisk} disabled={saving}>
                {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
                Create Risk
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Edit Risk Modal */}
      {showEditModal && selectedRisk && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm" onClick={() => setShowEditModal(false)}>
          <div className="bg-card border border-border rounded-2xl shadow-2xl w-full max-w-2xl mx-4 p-6" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-bold text-foreground">Edit Risk — {selectedRisk.reference}</h2>
              <button onClick={() => setShowEditModal(false)} className="p-1 rounded-lg hover:bg-muted transition-colors">
                <X className="w-5 h-5 text-muted-foreground" />
              </button>
            </div>
            <RiskFormFields form={editForm} onChange={setEditForm} />
            <div className="flex justify-end gap-3 mt-6 pt-4 border-t border-border">
              <Button variant="secondary" onClick={() => setShowEditModal(false)}>Cancel</Button>
              <Button onClick={handleUpdateRisk} disabled={saving}>
                {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Edit2 className="w-4 h-4" />}
                Save Changes
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* View Risk Detail Modal */}
      {showDetailModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm" onClick={() => setShowDetailModal(false)}>
          <div className="bg-card border border-border rounded-2xl shadow-2xl w-full max-w-3xl mx-4 p-6 max-h-[85vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-bold text-foreground">
                {detailRisk ? `${String(detailRisk.reference)} — ${String(detailRisk.title)}` : 'Risk Details'}
              </h2>
              <button onClick={() => setShowDetailModal(false)} className="p-1 rounded-lg hover:bg-muted transition-colors">
                <X className="w-5 h-5 text-muted-foreground" />
              </button>
            </div>

            {detailLoading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
              </div>
            ) : detailRisk ? (
              <div className="space-y-6">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <span className="text-xs text-muted-foreground uppercase">Category</span>
                    <p className="text-sm font-medium text-foreground">{CATEGORIES.find(c => c.id === detailRisk.category)?.label || String(detailRisk.category)}</p>
                  </div>
                  <div>
                    <span className="text-xs text-muted-foreground uppercase">Status</span>
                    <p className="text-sm font-medium text-foreground capitalize">{String(detailRisk.status)}</p>
                  </div>
                  <div>
                    <span className="text-xs text-muted-foreground uppercase">Department</span>
                    <p className="text-sm text-foreground">{detailRisk.department ? String(detailRisk.department) : '—'}</p>
                  </div>
                  <div>
                    <span className="text-xs text-muted-foreground uppercase">Owner</span>
                    <p className="text-sm text-foreground">{detailRisk.risk_owner_name ? String(detailRisk.risk_owner_name) : '—'}</p>
                  </div>
                </div>

                <div>
                  <span className="text-xs text-muted-foreground uppercase">Description</span>
                  <p className="text-sm text-foreground mt-1">{String(detailRisk.description ?? '')}</p>
                </div>

                <div className="grid grid-cols-3 gap-4 bg-muted/50 rounded-xl p-4">
                  <div className="text-center">
                    <span className="text-xs text-muted-foreground">Inherent</span>
                    <p className="text-2xl font-bold text-muted-foreground">{String(detailRisk.inherent_score)}</p>
                    <p className="text-xs text-muted-foreground">{String(detailRisk.inherent_likelihood)} x {String(detailRisk.inherent_impact)}</p>
                  </div>
                  <div className="text-center">
                    <span className="text-xs text-muted-foreground">Residual</span>
                    <p className="text-2xl font-bold" style={{ color: levelToColor(scoreToLevel(Number(detailRisk.residual_score))) }}>{String(detailRisk.residual_score)}</p>
                    <p className="text-xs text-muted-foreground">{String(detailRisk.residual_likelihood)} x {String(detailRisk.residual_impact)}</p>
                  </div>
                  <div className="text-center">
                    <span className="text-xs text-muted-foreground">Target</span>
                    <p className="text-2xl font-bold text-success">{detailRisk.target_score ? String(detailRisk.target_score) : '—'}</p>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <span className="text-xs text-muted-foreground uppercase">Treatment Strategy</span>
                    <p className="text-sm text-foreground capitalize">{String(detailRisk.treatment_strategy)}</p>
                  </div>
                  <div>
                    <span className="text-xs text-muted-foreground uppercase">Within Appetite</span>
                    <p className="text-sm">
                      {detailRisk.is_within_appetite
                        ? <Badge variant="resolved">Yes</Badge>
                        : <Badge variant="destructive">No — outside threshold ({String(detailRisk.appetite_threshold)})</Badge>
                      }
                    </p>
                  </div>
                </div>

                {detailRisk.treatment_plan ? (
                  <div>
                    <span className="text-xs text-muted-foreground uppercase">Treatment Plan</span>
                    <p className="text-sm text-foreground mt-1">{String(detailRisk.treatment_plan)}</p>
                  </div>
                ) : null}

                {/* Controls */}
                {Array.isArray(detailRisk.controls) && detailRisk.controls.length > 0 && (
                  <div>
                    <span className="text-xs text-muted-foreground uppercase">Linked Controls ({detailRisk.controls.length})</span>
                    <div className="mt-2 space-y-2">
                      {(detailRisk.controls as Array<Record<string, unknown>>).map((c) => (
                        <div key={String(c.id)} className="flex items-center gap-3 p-2 bg-muted rounded-lg">
                          <Shield className="w-4 h-4 text-success" />
                          <div className="flex-1">
                            <span className="text-sm font-medium text-foreground">{String(c.name)}</span>
                            <span className="text-xs text-muted-foreground ml-2">{String(c.reference)}</span>
                          </div>
                          <Badge variant="default">{String(c.effectiveness)}</Badge>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* KRIs */}
                {Array.isArray(detailRisk.kris) && detailRisk.kris.length > 0 && (
                  <div>
                    <span className="text-xs text-muted-foreground uppercase">Key Risk Indicators ({detailRisk.kris.length})</span>
                    <div className="mt-2 space-y-2">
                      {(detailRisk.kris as Array<Record<string, unknown>>).map((k) => (
                        <div key={String(k.id)} className="flex items-center justify-between p-2 bg-muted rounded-lg">
                          <span className="text-sm text-foreground">{String(k.name)}</span>
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-bold">{k.current_value != null ? String(k.current_value) : '—'}</span>
                            <div className={`w-3 h-3 rounded-full ${k.current_status === 'red' ? 'bg-destructive' : k.current_status === 'amber' ? 'bg-warning' : 'bg-success'}`} />
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Assessment History */}
                {Array.isArray(detailRisk.assessment_history) && detailRisk.assessment_history.length > 0 && (
                  <div>
                    <span className="text-xs text-muted-foreground uppercase">Assessment History</span>
                    <div className="mt-2 space-y-1">
                      {(detailRisk.assessment_history as Array<Record<string, unknown>>).map((h, i) => (
                        <div key={i} className="flex items-center justify-between p-2 bg-muted/50 rounded text-sm">
                          <span className="text-muted-foreground">{h.date ? new Date(String(h.date)).toLocaleDateString('en-GB') : '—'}</span>
                          <div className="flex items-center gap-4">
                            <span className="text-muted-foreground">Inherent: {String(h.inherent_score)}</span>
                            <span style={{ color: levelToColor(scoreToLevel(Number(h.residual_score))) }}>Residual: {String(h.residual_score)}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="text-xs text-muted-foreground uppercase">Last Review</span>
                    <p className="text-foreground">{detailRisk.last_review_date ? new Date(String(detailRisk.last_review_date)).toLocaleDateString('en-GB') : 'Never'}</p>
                  </div>
                  <div>
                    <span className="text-xs text-muted-foreground uppercase">Next Review</span>
                    <p className="text-foreground">{detailRisk.next_review_date ? new Date(String(detailRisk.next_review_date)).toLocaleDateString('en-GB') : '—'}</p>
                  </div>
                </div>
              </div>
            ) : null}

            <div className="flex justify-end mt-6 pt-4 border-t border-border">
              <Button variant="secondary" onClick={() => setShowDetailModal(false)}>Close</Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
