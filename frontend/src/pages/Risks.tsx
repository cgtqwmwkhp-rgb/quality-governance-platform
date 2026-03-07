import { useEffect, useState, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { trackError } from '../utils/errorTracker'
import { Plus, Shield, Search } from 'lucide-react'
import { risksApi, Risk, RiskCreate } from '../api/client'
import { Button } from '../components/ui/Button'
import { EmptyState } from '../components/ui/EmptyState'
import { Input } from '../components/ui/Input'
import { CardSkeleton } from '../components/ui/SkeletonLoader'
import { Textarea } from '../components/ui/Textarea'
import { Card } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import {
  Dialog,
  DialogContent,
  DialogDescription,
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
  const { t } = useTranslation()
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

  const loadRisks = useCallback(async (search?: string) => {
    setError(null)
    try {
      const response = await risksApi.list(1, 50, search || undefined)
      setRisks(response.data.items ?? [])
    } catch (err) {
      trackError(err, { component: 'Risks', action: 'loadRisks' })
      setError(t('risks.error.load_failed'))
    } finally {
      setLoading(false)
    }
  }, [t])

  useEffect(() => { loadRisks() }, [loadRisks])
  useEffect(() => {
    if (!searchTerm) return
    const timer = setTimeout(() => loadRisks(searchTerm), 300)
    return () => clearTimeout(timer)
  }, [searchTerm, loadRisks])

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    setCreating(true)
    setError(null)
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
      trackError(err, { component: 'Risks', action: 'createRisk' })
      setError(t('risks.error.load_failed'))
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

  const riskStats = {
    critical: risks.filter(r => r.risk_score >= 20).length,
    high: risks.filter(r => r.risk_score >= 12 && r.risk_score < 20).length,
    medium: risks.filter(r => r.risk_score >= 6 && r.risk_score < 12).length,
    low: risks.filter(r => r.risk_score < 6).length,
  }

  if (loading) {
    return (
      <div className="space-y-6 animate-fade-in">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-foreground">{t('risks.title')}</h1>
            <p className="text-muted-foreground mt-1">{t('risks.subtitle')}</p>
          </div>
        </div>
        <CardSkeleton count={6} />
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {error && (
        <div className="mx-4 mt-4 p-4 bg-destructive/10 border border-destructive/20 rounded-lg flex items-center justify-between">
          <p className="text-sm text-destructive">{error}</p>
          <button onClick={() => { setError(null); loadRisks(); }} className="text-sm font-medium text-destructive hover:underline">
            {t('risks.error.try_again')}
          </button>
        </div>
      )}

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground">{t('risks.title')}</h1>
          <p className="text-muted-foreground mt-1">{t('risks.subtitle')}</p>
        </div>
        <Button onClick={() => setShowModal(true)}>
          <Plus size={20} />
          {t('risks.new')}
        </Button>
      </div>

      {/* Search */}
      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
        <Input
          type="text"
          placeholder={t('risks.search_placeholder')}
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="pl-10"
        />
      </div>

      {/* Risk Heat Map Summary */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: t('risks.stats.critical_risks'), count: riskStats.critical, variant: 'destructive' as const },
          { label: t('risks.stats.high_risks'), count: riskStats.high, variant: 'warning' as const },
          { label: t('risks.stats.medium_risks'), count: riskStats.medium, variant: 'warning' as const },
          { label: t('risks.stats.low_risks'), count: riskStats.low, variant: 'success' as const },
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
            <p className="text-sm font-medium text-muted-foreground">{stat.label}</p>
          </Card>
        ))}
      </div>

      {/* Risks Table */}
      <Card className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-border">
                <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">{t('risks.table.reference')}</th>
                <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">{t('risks.table.risk')}</th>
                <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">{t('risks.table.category')}</th>
                <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">{t('risks.table.score')}</th>
                <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">{t('risks.table.status')}</th>
                <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">{t('risks.table.treatment')}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {risks.length === 0 ? (
                <tr>
                  <td colSpan={6}>
                    <EmptyState
                      icon={<Shield className="w-6 h-6 text-muted-foreground" />}
                      title={t('risks.empty.title', 'No risks found')}
                      description={t('risks.empty.subtitle', 'Create your first risk to get started.')}
                      action={
                        <Button variant="outline" size="sm" onClick={() => setShowModal(true)}>
                          <Plus size={16} /> {t('risks.new', 'New Risk')}
                        </Button>
                      }
                    />
                  </td>
                </tr>
              ) : (
                risks.map((risk) => (
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
            <DialogTitle>{t('risks.dialog.title')}</DialogTitle>
            <DialogDescription>{t('risks.subtitle')}</DialogDescription>
          </DialogHeader>
          <form onSubmit={handleCreate} className="space-y-5">
            <div>
              <label htmlFor="risks-field-0" className="block text-sm font-medium text-foreground mb-2">{t('risks.form.title')}</label>
              <Input id="risks-field-0"
                type="text"
                required
                value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                placeholder={t('risks.form.title_placeholder')}
              />
            </div>

            <div>
              <label htmlFor="risks-field-1" className="block text-sm font-medium text-foreground mb-2">{t('risks.form.description')}</label>
              <Textarea id="risks-field-1"
                required
                rows={3}
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                placeholder={t('risks.form.description_placeholder')}
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label htmlFor="risks-field-2" className="block text-sm font-medium text-foreground mb-2">{t('risks.form.category')}</label>
                <Select
                  value={formData.category}
                  onValueChange={(value) => setFormData({ ...formData, category: value })}
                >
                  <SelectTrigger id="risks-field-2">
                    <SelectValue placeholder={t('risks.form.select_category')} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="strategic">{t('risks.category.strategic')}</SelectItem>
                    <SelectItem value="operational">{t('risks.category.operational')}</SelectItem>
                    <SelectItem value="financial">{t('risks.category.financial')}</SelectItem>
                    <SelectItem value="compliance">{t('risks.category.compliance')}</SelectItem>
                    <SelectItem value="reputational">{t('risks.category.reputational')}</SelectItem>
                    <SelectItem value="technology">{t('risks.category.technology')}</SelectItem>
                    <SelectItem value="environmental">{t('risks.category.environmental')}</SelectItem>
                    <SelectItem value="health_safety">{t('risks.category.health_safety')}</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <label htmlFor="risks-field-3" className="block text-sm font-medium text-foreground mb-2">{t('risks.form.treatment')}</label>
                <Select
                  value={formData.treatment_strategy}
                  onValueChange={(value) => setFormData({ ...formData, treatment_strategy: value })}
                >
                  <SelectTrigger id="risks-field-3">
                    <SelectValue placeholder={t('risks.form.select_treatment')} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="accept">{t('risks.treatment.accept')}</SelectItem>
                    <SelectItem value="mitigate">{t('risks.treatment.mitigate')}</SelectItem>
                    <SelectItem value="transfer">{t('risks.treatment.transfer')}</SelectItem>
                    <SelectItem value="avoid">{t('risks.treatment.avoid')}</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label htmlFor="risks-field-4" className="block text-sm font-medium text-foreground mb-2">
                  {t('risks.form.likelihood')}
                </label>
                <input id="risks-field-4"
                  type="range"
                  min="1"
                  max="5"
                  value={formData.likelihood}
                  onChange={(e) => setFormData({ ...formData, likelihood: parseInt(e.target.value) })}
                  className="w-full h-2 bg-surface rounded-lg appearance-none cursor-pointer accent-primary"
                  aria-label="Likelihood"
                />
                <div className="flex justify-between text-xs text-muted-foreground mt-1">
                  <span>{t('risks.form.likelihood_rare')}</span>
                  <span className="text-primary font-medium">{formData.likelihood}</span>
                  <span>{t('risks.form.likelihood_certain')}</span>
                </div>
              </div>

              <div>
                <label htmlFor="risks-field-5" className="block text-sm font-medium text-foreground mb-2">
                  {t('risks.form.impact')}
                </label>
                <input id="risks-field-5"
                  type="range"
                  min="1"
                  max="5"
                  value={formData.impact}
                  onChange={(e) => setFormData({ ...formData, impact: parseInt(e.target.value) })}
                  className="w-full h-2 bg-surface rounded-lg appearance-none cursor-pointer accent-primary"
                  aria-label="Impact"
                />
                <div className="flex justify-between text-xs text-muted-foreground mt-1">
                  <span>{t('risks.form.impact_negligible')}</span>
                  <span className="text-primary font-medium">{formData.impact}</span>
                  <span>{t('risks.form.impact_catastrophic')}</span>
                </div>
              </div>
            </div>

            <Card className="p-4">
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">{t('risks.form.calculated_score')}</span>
                <Badge variant={getRiskLevelVariant('', formData.likelihood * formData.impact) as any} className="text-lg px-4 py-2">
                  {formData.likelihood * formData.impact}
                </Badge>
              </div>
            </Card>

            <DialogFooter className="gap-3 pt-4">
              <Button type="button" variant="outline" onClick={() => setShowModal(false)}>
                {t('cancel')}
              </Button>
              <Button type="submit" disabled={creating}>
                {creating ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    {t('risks.creating')}
                  </>
                ) : (
                  t('risks.create')
                )}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}
