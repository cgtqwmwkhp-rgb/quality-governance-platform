import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { trackError } from '../utils/errorTracker'
import { Plus, FileText, Search, Loader2 } from 'lucide-react'
import { TableSkeleton } from '../components/ui/SkeletonLoader'
import { policiesApi, Policy, PolicyCreate, getApiErrorMessage } from '../api/client'
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

export default function Policies() {
  const { t } = useTranslation()
  const [policies, setPolicies] = useState<Policy[]>([])
  const [loading, setLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [creating, setCreating] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [createError, setCreateError] = useState<string | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [formData, setFormData] = useState<PolicyCreate>({
    title: '',
    description: '',
    document_type: 'policy',
    category: '',
    department: '',
    review_frequency_months: 12,
  })

  const loadPolicies = async () => {
    try {
      const response = await policiesApi.list(1, 50)
      setPolicies(response.data.items ?? [])
    } catch (err) {
      trackError(err, { component: 'Policies', action: 'load' })
      setLoadError(getApiErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      try {
        const response = await policiesApi.list(1, 50)
        if (!cancelled) setPolicies(response.data.items ?? [])
      } catch (err) {
        if (!cancelled) {
          trackError(err, { component: 'Policies', action: 'load' })
          setLoadError(getApiErrorMessage(err))
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => { cancelled = true }
  }, [])

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    setCreating(true)
    setCreateError(null)
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
      trackError(err, { component: 'Policies', action: 'create' })
      setCreateError(getApiErrorMessage(err))
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

  const getStatusVariant = (status: string) => {
    switch (status) {
      case 'published': return 'resolved'
      case 'approved': return 'success'
      case 'under_review': return 'in-progress'
      case 'draft': return 'submitted'
      case 'superseded': return 'closed'
      case 'retired': return 'destructive'
      default: return 'secondary'
    }
  }

  const filteredPolicies = policies.filter(
    p => p.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
         p.reference_number.toLowerCase().includes(searchTerm.toLowerCase()) ||
         (p.category || '').toLowerCase().includes(searchTerm.toLowerCase())
  )

  if (loading) {
    return <TableSkeleton rows={8} columns={4} />
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {loadError && (
        <div className="bg-destructive/10 text-destructive p-4 rounded-lg">{loadError}</div>
      )}
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground">{t('policies.title')}</h1>
          <p className="text-muted-foreground mt-1">{t('policies.subtitle')}</p>
        </div>
        <Button onClick={() => setShowModal(true)}>
          <Plus size={20} />
          {t('policies.new')}
        </Button>
      </div>

      {/* Search */}
      <div className="flex gap-4">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
          <Input
            type="text"
            placeholder={t('policies.search_placeholder')}
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-10"
          />
        </div>
      </div>

      {/* Policies Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filteredPolicies.length === 0 ? (
          <div className="col-span-full">
            <Card className="p-12 text-center">
              <FileText className="w-12 h-12 mx-auto mb-4 text-muted-foreground/50" />
              <p className="text-muted-foreground">{t('policies.empty.title')}</p>
              <p className="text-sm text-muted-foreground mt-1">{t('policies.empty.subtitle')}</p>
            </Card>
          </div>
        ) : (
          filteredPolicies.map((policy) => (
            <Card
              key={policy.id}
              hoverable
              className="p-5 cursor-pointer"
            >
              <div className="flex items-start gap-4">
                <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center text-2xl">
                  {getTypeIcon(policy.document_type)}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-mono text-xs text-primary mb-1">{policy.reference_number}</p>
                  <h3 className="font-semibold text-foreground truncate">{policy.title}</h3>
                  {policy.description && (
                    <p className="text-sm text-muted-foreground mt-1 line-clamp-2">{policy.description}</p>
                  )}
                </div>
              </div>
              <div className="mt-4 flex items-center justify-between">
                <Badge variant={getStatusVariant(policy.status) as any}>
                  {policy.status.replace('_', ' ')}
                </Badge>
                <span className="text-xs text-muted-foreground">
                  {policy.document_type.replace('_', ' ')}
                </span>
              </div>
              {policy.next_review_date && (
                <div className="mt-3 pt-3 border-t border-border">
                  <p className="text-xs text-muted-foreground">
                    {t('policies.review_due')} {new Date(policy.next_review_date).toLocaleDateString()}
                  </p>
                </div>
              )}
            </Card>
          ))
        )}
      </div>

      {/* Create Modal */}
      <Dialog open={showModal} onOpenChange={setShowModal}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('policies.dialog.title')}</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleCreate} className="space-y-5">
            {createError && (
              <div className="bg-destructive/10 text-destructive text-sm p-3 rounded-lg">{createError}</div>
            )}
            <div>
              <label htmlFor="policies-field-0" className="block text-sm font-medium text-foreground mb-2">{t('policies.form.title')}</label>
              <Input id="policies-field-0"
                type="text"
                required
                value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                placeholder={t('policies.form.title_placeholder')}
              />
            </div>

            <div>
              <label htmlFor="policies-field-1" className="block text-sm font-medium text-foreground mb-2">{t('policies.form.description')}</label>
              <Textarea id="policies-field-1"
                rows={3}
                value={formData.description || ''}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                placeholder={t('policies.form.description_placeholder')}
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label htmlFor="policies-field-2" className="block text-sm font-medium text-foreground mb-2">{t('policies.form.type')}</label>
                <Select
                  value={formData.document_type}
                  onValueChange={(value) => setFormData({ ...formData, document_type: value })}
                >
                  <SelectTrigger id="policies-field-2">
                    <SelectValue placeholder={t('policies.form.select_type')} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="policy">{t('policies.type.policy')}</SelectItem>
                    <SelectItem value="procedure">{t('policies.type.procedure')}</SelectItem>
                    <SelectItem value="work_instruction">{t('policies.type.work_instruction')}</SelectItem>
                    <SelectItem value="sop">{t('policies.type.sop')}</SelectItem>
                    <SelectItem value="form">{t('policies.type.form')}</SelectItem>
                    <SelectItem value="template">{t('policies.type.template')}</SelectItem>
                    <SelectItem value="guideline">{t('policies.type.guideline')}</SelectItem>
                    <SelectItem value="manual">{t('policies.type.manual')}</SelectItem>
                    <SelectItem value="record">{t('policies.type.record')}</SelectItem>
                    <SelectItem value="other">{t('policies.type.other')}</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <label htmlFor="policies-field-3" className="block text-sm font-medium text-foreground mb-2">{t('policies.form.review_frequency')}</label>
                <Select
                  value={String(formData.review_frequency_months)}
                  onValueChange={(value) => setFormData({ ...formData, review_frequency_months: parseInt(value) })}
                >
                  <SelectTrigger id="policies-field-3">
                    <SelectValue placeholder={t('policies.form.select_frequency')} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="6">{t('policies.frequency.6_months')}</SelectItem>
                    <SelectItem value="12">{t('policies.frequency.12_months')}</SelectItem>
                    <SelectItem value="24">{t('policies.frequency.24_months')}</SelectItem>
                    <SelectItem value="36">{t('policies.frequency.36_months')}</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label htmlFor="policies-field-4" className="block text-sm font-medium text-foreground mb-2">{t('policies.form.category')}</label>
                <Input id="policies-field-4"
                  type="text"
                  value={formData.category || ''}
                  onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                  placeholder={t('policies.form.category_placeholder')}
                />
              </div>
              <div>
                <label htmlFor="policies-field-5" className="block text-sm font-medium text-foreground mb-2">{t('policies.form.department')}</label>
                <Input id="policies-field-5"
                  type="text"
                  value={formData.department || ''}
                  onChange={(e) => setFormData({ ...formData, department: e.target.value })}
                  placeholder={t('policies.form.department_placeholder')}
                />
              </div>
            </div>

            <DialogFooter className="gap-3 pt-4">
              <Button type="button" variant="outline" onClick={() => setShowModal(false)}>
                {t('cancel')}
              </Button>
              <Button type="submit" disabled={creating}>
                {creating ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    {t('policies.creating')}
                  </>
                ) : (
                  t('policies.create')
                )}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}
