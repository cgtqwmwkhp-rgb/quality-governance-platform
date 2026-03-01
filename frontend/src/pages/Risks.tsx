import { useEffect, useState } from 'react'
import { Plus, Shield, Search, Loader2 } from 'lucide-react'
import { risksApi, Risk, RiskCreate } from '../api/client'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Textarea } from '../components/ui/Textarea'
import { Card } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '../components/ui/Dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/Select'
import { cn } from "../helpers/utils"

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
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadRisks()
  }, [])

  const loadRisks = async () => {
    setError(null)
    try {
      const response = await risksApi.list(1, 50)
      setRisks(response.data.items ?? [])
    } catch (err) {
      console.error('Failed to load risks:', err)
      setError('Failed to load data. Please try again.')
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

  const getRiskLevelVariant = (level: string, score: number) => {
    if (score >= 20 || level === 'critical') return 'critical'
    if (score >= 12 || level === 'high') return 'high'
    if (score >= 6 || level === 'medium') return 'medium'
    return 'low'
  }

  const getStatusVariant = (status: string) => {
    switch (status) {
      case 'closed': return 'resolved'
      case 'identified': return 'submitted'
      case 'assessing': return 'acknowledged'
      case 'treating': return 'in-progress'
      case 'monitoring': return 'info'
      default: return 'secondary'
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

  const riskStats = {
    critical: risks.filter(r => r.risk_score >= 20).length,
    high: risks.filter(r => r.risk_score >= 12 && r.risk_score < 20).length,
    medium: risks.filter(r => r.risk_score >= 6 && r.risk_score < 12).length,
    low: risks.filter(r => r.risk_score < 6).length,
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 text-primary animate-spin" />
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {error && (
        <div className="mx-4 mt-4 p-4 bg-destructive/10 border border-destructive/20 rounded-lg flex items-center justify-between">
          <p className="text-sm text-destructive">{error}</p>
          <button onClick={() => { setError(null); loadRisks(); }} className="text-sm font-medium text-destructive hover:underline">
            Try Again
          </button>
        </div>
      )}

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Risk Register</h1>
          <p className="text-muted-foreground mt-1">Identify, assess, and manage organizational risks</p>
        </div>
        <Button onClick={() => setShowModal(true)}>
          <Plus size={20} />
          New Risk
        </Button>
      </div>

      {/* Search */}
      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
        <Input
          type="text"
          placeholder="Search risks..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="pl-10"
        />
      </div>

      {/* Risk Heat Map Summary */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: 'Critical', count: riskStats.critical, variant: 'destructive' as const },
          { label: 'High', count: riskStats.high, variant: 'warning' as const },
          { label: 'Medium', count: riskStats.medium, variant: 'warning' as const },
          { label: 'Low', count: riskStats.low, variant: 'success' as const },
        ].map((stat) => (
          <Card key={stat.label} className="p-4">
            <div className={cn(
              "w-10 h-10 rounded-lg flex items-center justify-center mb-3",
              stat.variant === 'destructive' && "bg-destructive/10 text-destructive",
              stat.variant === 'warning' && "bg-warning/10 text-warning",
              stat.variant === 'success' && "bg-success/10 text-success",
            )}>
              <span className="font-bold">{stat.count}</span>
            </div>
            <p className="text-sm font-medium text-muted-foreground">{stat.label} Risks</p>
          </Card>
        ))}
      </div>

      {/* Risks Table */}
      <Card className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-border">
                <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">Reference</th>
                <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">Risk</th>
                <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">Category</th>
                <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">Score</th>
                <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">Status</th>
                <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">Treatment</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {filteredRisks.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-6 py-12 text-center text-muted-foreground">
                    <Shield className="w-12 h-12 mx-auto mb-4 text-muted-foreground/50" />
                    <p>No risks found</p>
                    <p className="text-sm mt-1">Add a risk to your register to get started</p>
                  </td>
                </tr>
              ) : (
                filteredRisks.map((risk) => (
                  <tr
                    key={risk.id}
                    className="hover:bg-surface transition-colors cursor-pointer"
                  >
                    <td className="px-6 py-4">
                      <span className="font-mono text-sm text-primary">{risk.reference_number}</span>
                    </td>
                    <td className="px-6 py-4">
                      <p className="text-sm font-medium text-foreground truncate max-w-xs">{risk.title}</p>
                    </td>
                    <td className="px-6 py-4">
                      <span className="inline-flex items-center gap-1.5 text-sm text-foreground">
                        <span>{getCategoryIcon(risk.category)}</span>
                        {risk.category.replace('_', ' ')}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2">
                        <Badge variant={getRiskLevelVariant(risk.risk_level, risk.risk_score) as any}>
                          {risk.risk_score}
                        </Badge>
                        <span className="text-xs text-muted-foreground">
                          ({risk.likelihood}×{risk.impact})
                        </span>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <Badge variant={getStatusVariant(risk.status) as any}>
                        {risk.status.replace('_', ' ')}
                      </Badge>
                    </td>
                    <td className="px-6 py-4">
                      <span className="text-sm text-muted-foreground capitalize">
                        {risk.treatment_strategy}
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Create Modal */}
      <Dialog open={showModal} onOpenChange={setShowModal}>
        <DialogContent className="max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>New Risk</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleCreate} className="space-y-5">
            <div>
              <label className="block text-sm font-medium text-foreground mb-2">Title</label>
              <Input
                type="text"
                required
                value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                placeholder="Brief risk title..."
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-foreground mb-2">Description</label>
              <Textarea
                required
                rows={3}
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                placeholder="Detailed description of the risk..."
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-foreground mb-2">Category</label>
                <Select
                  value={formData.category}
                  onValueChange={(value) => setFormData({ ...formData, category: value })}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select category" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="strategic">Strategic</SelectItem>
                    <SelectItem value="operational">Operational</SelectItem>
                    <SelectItem value="financial">Financial</SelectItem>
                    <SelectItem value="compliance">Compliance</SelectItem>
                    <SelectItem value="reputational">Reputational</SelectItem>
                    <SelectItem value="technology">Technology</SelectItem>
                    <SelectItem value="environmental">Environmental</SelectItem>
                    <SelectItem value="health_safety">Health & Safety</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <label className="block text-sm font-medium text-foreground mb-2">Treatment</label>
                <Select
                  value={formData.treatment_strategy}
                  onValueChange={(value) => setFormData({ ...formData, treatment_strategy: value })}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select treatment" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="accept">Accept</SelectItem>
                    <SelectItem value="mitigate">Mitigate</SelectItem>
                    <SelectItem value="transfer">Transfer</SelectItem>
                    <SelectItem value="avoid">Avoid</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-foreground mb-2">
                  Likelihood (1-5)
                </label>
                <input
                  type="range"
                  min="1"
                  max="5"
                  value={formData.likelihood}
                  onChange={(e) => setFormData({ ...formData, likelihood: parseInt(e.target.value) })}
                  className="w-full h-2 bg-surface rounded-lg appearance-none cursor-pointer accent-primary"
                  aria-label="Likelihood"
                />
                <div className="flex justify-between text-xs text-muted-foreground mt-1">
                  <span>Rare</span>
                  <span className="text-primary font-medium">{formData.likelihood}</span>
                  <span>Almost Certain</span>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-foreground mb-2">
                  Impact (1-5)
                </label>
                <input
                  type="range"
                  min="1"
                  max="5"
                  value={formData.impact}
                  onChange={(e) => setFormData({ ...formData, impact: parseInt(e.target.value) })}
                  className="w-full h-2 bg-surface rounded-lg appearance-none cursor-pointer accent-primary"
                  aria-label="Impact"
                />
                <div className="flex justify-between text-xs text-muted-foreground mt-1">
                  <span>Negligible</span>
                  <span className="text-primary font-medium">{formData.impact}</span>
                  <span>Catastrophic</span>
                </div>
              </div>
            </div>

            <Card className="p-4">
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Calculated Risk Score:</span>
                <Badge variant={getRiskLevelVariant('', formData.likelihood * formData.impact) as any} className="text-lg px-4 py-2">
                  {formData.likelihood * formData.impact}
                </Badge>
              </div>
            </Card>

            <DialogFooter className="gap-3 pt-4">
              <Button type="button" variant="outline" onClick={() => setShowModal(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={creating}>
                {creating ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Creating...
                  </>
                ) : (
                  'Create Risk'
                )}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}
