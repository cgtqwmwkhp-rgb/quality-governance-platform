import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Plus, AlertTriangle, Search, Loader2 } from 'lucide-react'
import { incidentsApi, Incident, IncidentCreate } from '../api/client'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Textarea } from '../components/ui/Textarea'
import { Card, CardContent } from '../components/ui/Card'
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

export default function Incidents() {
  const navigate = useNavigate()
  const { t } = useTranslation()
  const [incidents, setIncidents] = useState<Incident[]>([])
  const [loading, setLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [creating, setCreating] = useState(false)
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
    loadIncidents()
  }, [])

  const loadIncidents = async () => {
    try {
      const response = await incidentsApi.list(1, 50)
      setIncidents(response.data.items ?? [])
    } catch (err) {
      console.error('Failed to load incidents:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    setCreating(true)
    try {
      await incidentsApi.create({
        ...formData,
        incident_date: new Date(formData.incident_date).toISOString(),
        reported_date: new Date(formData.reported_date).toISOString(),
      })
      setShowModal(false)
      setFormData({
        title: '',
        description: '',
        incident_type: 'other',
        severity: 'medium',
        incident_date: new Date().toISOString().slice(0, 16),
        reported_date: new Date().toISOString().slice(0, 16),
      })
      loadIncidents()
    } catch (err) {
      console.error('Failed to create incident:', err)
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

  const filteredIncidents = incidents.filter(
    i => i.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
         i.reference_number.toLowerCase().includes(searchTerm.toLowerCase())
  )

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 text-primary animate-spin" />
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-fade-in">
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
                    <td colSpan={6} className="px-6 py-12 text-center text-muted-foreground">
                      <AlertTriangle className="w-12 h-12 mx-auto mb-4 text-muted-foreground/50" />
                      <p>{t('incidents.empty.title')}</p>
                      <p className="text-sm mt-1">{t('incidents.empty.subtitle')}</p>
                    </td>
                  </tr>
                ) : (
                  filteredIncidents.map((incident, index) => (
                    <tr
                      key={incident.id}
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
          </DialogHeader>
          <form onSubmit={handleCreate} className="space-y-5">
            <div>
              <label htmlFor="incidents-field-0" className="block text-sm font-medium text-foreground mb-2">{t('incidents.form.title')}</label>
              <Input id="incidents-field-0"
                type="text"
                required
                value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                placeholder={t('incidents.form.title_placeholder')}
              />
            </div>

            <div>
              <label htmlFor="incidents-field-1" className="block text-sm font-medium text-foreground mb-2">{t('incidents.form.description')}</label>
              <Textarea id="incidents-field-1"
                required
                rows={3}
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                placeholder={t('incidents.form.description_placeholder')}
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
              <label htmlFor="incidents-field-4" className="block text-sm font-medium text-foreground mb-2">{t('incidents.form.incident_date')}</label>
              <Input id="incidents-field-4"
                type="datetime-local"
                required
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
