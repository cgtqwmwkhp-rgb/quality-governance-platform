import { useEffect, useState, useDeferredValue } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Plus, AlertTriangle, Search, Loader2 } from 'lucide-react'
import { incidentsApi, Incident, IncidentCreate, getApiErrorMessage } from '../api/client'
import { trackError } from '../utils/errorTracker'
import { Button } from '../components/ui/Button'
import { EmptyState } from '../components/ui/EmptyState'
import { Input } from '../components/ui/Input'
import { TableSkeleton } from '../components/ui/SkeletonLoader'
import { Textarea } from '../components/ui/Textarea'
import { Card, CardContent } from '../components/ui/Card'
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

export default function Incidents() {
  const navigate = useNavigate()
  const { t } = useTranslation()
  const [incidents, setIncidents] = useState<Incident[]>([])
  const [loading, setLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [formData, setFormData] = useState<IncidentCreate>({
    title: '',
    description: '',
    incident_type: 'other',
    severity: 'medium',
    incident_date: new Date().toISOString().slice(0, 16),
    reported_date: new Date().toISOString().slice(0, 16),
  })

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      try {
        const response = await incidentsApi.list(1, 50)
        if (!cancelled) setIncidents(response.data.items ?? [])
      } catch (err) {
        if (!cancelled) {
          trackError(err, { component: 'Incidents', action: 'load' })
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
      const response = await incidentsApi.create({
        ...formData,
        incident_date: new Date(formData.incident_date).toISOString(),
        reported_date: new Date(formData.reported_date).toISOString(),
      })
      if (response.data) {
        setIncidents(prev => [response.data, ...prev])
      }
      setShowModal(false)
      setFormData({
        title: '',
        description: '',
        incident_type: 'other',
        severity: 'medium',
        incident_date: new Date().toISOString().slice(0, 16),
        reported_date: new Date().toISOString().slice(0, 16),
      })
    } catch (err) {
      trackError(err, { component: 'Incidents', action: 'create' })
      setCreateError(getApiErrorMessage(err))
    } finally {
      setCreating(false)
    }
  }

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'injury': return '🩹'
      case 'near_miss': return '⚠️'
      case 'hazard': return '☢️'
      case 'quality': return '✓'
      case 'security': return '🔒'
      case 'environmental': return '🌿'
      default: return '📋'
    }
  }

  const getSeverityVariant = (severity: string) => {
    switch (severity) {
      case 'critical': return 'critical'
      case 'high': return 'high'
      case 'medium': return 'medium'
      case 'low': return 'low'
      default: return 'secondary'
    }
  }

  const getStatusVariant = (status: string) => {
    switch (status) {
      case 'closed': return 'resolved'
      case 'reported': return 'submitted'
      case 'under_investigation': return 'in-progress'
      case 'pending_actions': return 'acknowledged'
      default: return 'secondary'
    }
  }

  const deferredSearch = useDeferredValue(searchTerm)
  const filteredIncidents = incidents.filter(
    i => i.title.toLowerCase().includes(deferredSearch.toLowerCase()) ||
         i.reference_number.toLowerCase().includes(deferredSearch.toLowerCase())
  )

  if (loading) {
    return (
      <div className="space-y-6 animate-fade-in">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-foreground">{t('incidents.title')}</h1>
            <p className="text-muted-foreground mt-1">{t('incidents.subtitle')}</p>
          </div>
        </div>
        <Card><CardContent className="p-6"><TableSkeleton rows={6} columns={6} /></CardContent></Card>
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {loadError && (
        <div className="bg-destructive/10 text-destructive p-4 rounded-lg">{loadError}</div>
      )}
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground">{t('incidents.title')}</h1>
          <p className="text-muted-foreground mt-1">{t('incidents.subtitle')}</p>
        </div>
        <Button onClick={() => setShowModal(true)}>
          <Plus size={20} />
          {t('incidents.new')}
        </Button>
      </div>

      {/* Search & Filter */}
      <div className="flex gap-4">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
          <Input
            type="text"
            placeholder={t('incidents.search_placeholder')}
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-10"
          />
        </div>
      </div>

      {/* Incidents Table */}
      <Card>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border">
                  <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">{t('incidents.table.reference')}</th>
                  <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">{t('incidents.table.title')}</th>
                  <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">{t('incidents.table.type')}</th>
                  <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">{t('incidents.table.severity')}</th>
                  <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">{t('incidents.table.status')}</th>
                  <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">{t('incidents.table.date')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {filteredIncidents.length === 0 ? (
                  <tr>
                    <td colSpan={6}>
                      <EmptyState
                        icon={<AlertTriangle className="w-6 h-6 text-muted-foreground" />}
                        title={t('incidents.empty.title', 'No incidents found')}
                        description={t('incidents.empty.subtitle', 'Create your first incident report to get started.')}
                        action={
                          <Button variant="outline" size="sm" onClick={() => setShowModal(true)}>
                            <Plus size={16} /> {t('incidents.new', 'Report Incident')}
                          </Button>
                        }
                      />
                    </td>
                  </tr>
                ) : (
                  filteredIncidents.map((incident, index) => (
                    <tr
                      key={incident.id}
                      data-testid="incident-row-link"
                      className="hover:bg-surface transition-colors cursor-pointer"
                      style={{ animationDelay: `${index * 30}ms` }}
                      onClick={() => navigate(`/incidents/${incident.id}`)}
                      role="button"
                      tabIndex={0}
                      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); navigate(`/incidents/${incident.id}`); } }}
                    >
                      <td className="px-6 py-4">
                        <span className="font-mono text-sm text-primary">{incident.reference_number}</span>
                      </td>
                      <td className="px-6 py-4">
                        <p className="text-sm font-medium text-foreground truncate max-w-xs">{incident.title}</p>
                      </td>
                      <td className="px-6 py-4">
                        <span className="inline-flex items-center gap-1.5 text-sm text-foreground">
                          <span>{getTypeIcon(incident.incident_type)}</span>
                          {incident.incident_type.replace('_', ' ')}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        <Badge variant={getSeverityVariant(incident.severity) as any}>
                          {incident.severity}
                        </Badge>
                      </td>
                      <td className="px-6 py-4">
                        <Badge variant={getStatusVariant(incident.status) as any}>
                          {incident.status.replace('_', ' ')}
                        </Badge>
                      </td>
                      <td className="px-6 py-4 text-sm text-muted-foreground">
                        {new Date(incident.incident_date).toLocaleDateString()}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Create Modal */}
      <Dialog open={showModal} onOpenChange={setShowModal}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('incidents.dialog.title')}</DialogTitle>
            <DialogDescription>{t('incidents.subtitle')}</DialogDescription>
          </DialogHeader>
          <form onSubmit={handleCreate} className="space-y-5">
            {createError && (
              <div className="bg-destructive/10 text-destructive text-sm p-3 rounded-lg">{createError}</div>
            )}
            <div>
              <label htmlFor="incidents-field-0" className="block text-sm font-medium text-foreground mb-2">{t('incidents.form.title')} <span className="text-destructive">*</span></label>
              <Input id="incidents-field-0"
                type="text"
                required
                value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                placeholder={t('incidents.form.title_placeholder')}
                aria-required="true"
              />
            </div>

            <div>
              <label htmlFor="incidents-field-1" className="block text-sm font-medium text-foreground mb-2">{t('incidents.form.description')} <span className="text-destructive">*</span></label>
              <Textarea id="incidents-field-1"
                required
                rows={3}
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                placeholder={t('incidents.form.description_placeholder')}
                aria-required="true"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label htmlFor="incidents-field-2" className="block text-sm font-medium text-foreground mb-2">{t('incidents.form.type')}</label>
                <Select
                  value={formData.incident_type}
                  onValueChange={(value) => setFormData({ ...formData, incident_type: value })}
                >
                  <SelectTrigger id="incidents-field-2">
                    <SelectValue placeholder={t('incidents.form.select_type')} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="injury">{t('incidents.type.injury')}</SelectItem>
                    <SelectItem value="near_miss">{t('incidents.type.near_miss')}</SelectItem>
                    <SelectItem value="hazard">{t('incidents.type.hazard')}</SelectItem>
                    <SelectItem value="property_damage">{t('incidents.type.property_damage')}</SelectItem>
                    <SelectItem value="environmental">{t('incidents.type.environmental')}</SelectItem>
                    <SelectItem value="security">{t('incidents.type.security')}</SelectItem>
                    <SelectItem value="quality">{t('incidents.type.quality')}</SelectItem>
                    <SelectItem value="other">{t('incidents.type.other')}</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <label htmlFor="incidents-field-3" className="block text-sm font-medium text-foreground mb-2">{t('incidents.form.severity')}</label>
                <Select
                  value={formData.severity}
                  onValueChange={(value) => setFormData({ ...formData, severity: value })}
                >
                  <SelectTrigger id="incidents-field-3">
                    <SelectValue placeholder={t('incidents.form.select_severity')} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="critical">{t('severity.critical')}</SelectItem>
                    <SelectItem value="high">{t('severity.high')}</SelectItem>
                    <SelectItem value="medium">{t('severity.medium')}</SelectItem>
                    <SelectItem value="low">{t('severity.low')}</SelectItem>
                    <SelectItem value="negligible">{t('severity.negligible')}</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div>
              <label htmlFor="incidents-field-4" className="block text-sm font-medium text-foreground mb-2">{t('incidents.form.incident_date')} <span className="text-destructive">*</span></label>
              <Input id="incidents-field-4"
                type="datetime-local"
                required
                aria-required="true"
                value={formData.incident_date}
                onChange={(e) => setFormData({ ...formData, incident_date: e.target.value })}
              />
            </div>

            <DialogFooter className="gap-3 pt-4">
              <Button
                type="button"
                variant="outline"
                onClick={() => setShowModal(false)}
              >
                {t('cancel')}
              </Button>
              <Button
                type="submit"
                disabled={creating}
              >
                {creating ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    {t('incidents.creating')}
                  </>
                ) : (
                  t('incidents.create')
                )}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}
