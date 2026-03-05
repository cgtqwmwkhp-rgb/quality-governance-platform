import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { Plus, Car, Search, Loader2, AlertCircle, RefreshCw } from 'lucide-react'
import { rtasApi, RTA, RTACreate } from '../api/client'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Textarea } from '../components/ui/Textarea'
import { Card, CardContent } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { Switch } from '../components/ui/Switch'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from '../components/ui/Dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/Select'

export default function RTAs() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [rtas, setRtas] = useState<RTA[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<{ message: string; code?: string; requestId?: string } | null>(null)
  const [showModal, setShowModal] = useState(false)
  const [creating, setCreating] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')
  const [formData, setFormData] = useState<RTACreate>({
    title: '',
    description: '',
    severity: 'damage_only',
    collision_date: new Date().toISOString().slice(0, 16),
    reported_date: new Date().toISOString().slice(0, 16),
    location: '',
    driver_name: '',
    company_vehicle_registration: '',
    police_attended: false,
    driver_injured: false,
  })

  useEffect(() => {
    loadRtas()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const loadRtas = async () => {
    setLoading(true)
    setError(null)

    // Create abort controller for timeout
    const controller = new AbortController()
    const timeoutId = setTimeout(() => {
      controller.abort()
    }, 15000) // 15 second timeout

    try {
      const response = await rtasApi.list(1, 50)
      setRtas(response.data.items ?? [])
      setError(null)
    } catch (err: any) {
      console.error('Failed to load RTAs:', err)
      
      // Extract error details for display
      const isTimeout = err.code === 'ECONNABORTED' || err.message?.includes('timeout') || err.name === 'AbortError'
      const status = err.response?.status
      const requestId = err.response?.data?.request_id || err.response?.headers?.['x-request-id']
      
      if (isTimeout) {
        setError({
          message: t('rtas.error.timeout'),
          code: 'TIMEOUT',
          requestId,
        })
      } else if (!err.response) {
        setError({
          message: t('rtas.error.network'),
          code: 'NETWORK_ERROR',
          requestId,
        })
      } else {
        setError({
          message: err.response?.data?.message || err.response?.data?.detail?.message || t('rtas.error.generic'),
          code: status ? `HTTP_${status}` : 'UNKNOWN',
          requestId,
        })
      }
      setRtas([])
    } finally {
      clearTimeout(timeoutId)
      setLoading(false)
    }
  }

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    setCreating(true)
    try {
      await rtasApi.create({
        ...formData,
        collision_date: new Date(formData.collision_date).toISOString(),
        reported_date: new Date(formData.reported_date).toISOString(),
      })
      setShowModal(false)
      setFormData({
        title: '',
        description: '',
        severity: 'damage_only',
        collision_date: new Date().toISOString().slice(0, 16),
        reported_date: new Date().toISOString().slice(0, 16),
        location: '',
        driver_name: '',
        company_vehicle_registration: '',
        police_attended: false,
        driver_injured: false,
      })
      loadRtas()
    } catch (err) {
      console.error('Failed to create RTA:', err)
    } finally {
      setCreating(false)
    }
  }

  const getSeverityVariant = (severity: string) => {
    switch (severity) {
      case 'fatal': return 'critical'
      case 'serious_injury': return 'critical'
      case 'minor_injury': return 'high'
      case 'damage_only': return 'medium'
      case 'near_miss': return 'low'
      default: return 'secondary'
    }
  }

  const getStatusVariant = (status: string) => {
    switch (status) {
      case 'closed': return 'resolved'
      case 'reported': return 'submitted'
      case 'under_investigation': return 'in-progress'
      case 'pending_insurance': return 'acknowledged'
      case 'pending_actions': return 'awaiting-user'
      default: return 'secondary'
    }
  }

  const filteredRtas = rtas.filter(
    r => r.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
         r.reference_number.toLowerCase().includes(searchTerm.toLowerCase()) ||
         r.location.toLowerCase().includes(searchTerm.toLowerCase())
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
      {/* Header — always visible so users can create RTAs even if list fails */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground">{t('rtas.title')}</h1>
          <p className="text-muted-foreground mt-1">{t('rtas.subtitle')}</p>
        </div>
        <Button data-testid="create-rta-btn" onClick={() => setShowModal(true)}>
          <Plus size={20} />
          {t('rtas.report')}
        </Button>
      </div>

      {error && (
        <div className="flex flex-col items-center justify-center h-64 gap-4">
          <div className="w-16 h-16 rounded-full bg-destructive/10 flex items-center justify-center">
            <AlertCircle className="w-8 h-8 text-destructive" />
          </div>
          <div className="text-center">
            <h2 className="text-lg font-semibold text-foreground mb-1">{t('rtas.error.load_failed')}</h2>
            <p className="text-muted-foreground max-w-md">{error.message}</p>
            {error.code && (
              <p className="text-xs text-muted-foreground mt-1">
                {t('rtas.error.code_label')}: {error.code}
                {error.requestId && ` | ${t('rtas.error.request_id_label')}: ${error.requestId}`}
              </p>
            )}
          </div>
          <Button onClick={loadRtas} variant="outline">
            <RefreshCw className="w-4 h-4 mr-2" />
            {t('retry')}
          </Button>
        </div>
      )}

      {!error && (

      {/* Search */}
      <div className="flex gap-4">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
          <Input
            type="text"
            placeholder={t('rtas.search_placeholder')}
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-10"
          />
        </div>
      </div>

      {/* RTAs Table */}
      <Card>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border">
                  <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">{t('rtas.table.reference')}</th>
                  <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">{t('rtas.table.title')}</th>
                  <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">{t('rtas.table.location')}</th>
                  <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">{t('rtas.table.severity')}</th>
                  <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">{t('rtas.table.status')}</th>
                  <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">{t('rtas.table.date')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {filteredRtas.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-6 py-12 text-center text-muted-foreground">
                      <Car className="w-12 h-12 mx-auto mb-4 text-muted-foreground/50" />
                      <p>{t('rtas.empty.title')}</p>
                      <p className="text-sm mt-1">{t('rtas.empty.subtitle')}</p>
                    </td>
                  </tr>
                ) : (
                  filteredRtas.map((rta, index) => (
                    <tr
                      key={rta.id}
                      className="hover:bg-surface transition-colors cursor-pointer"
                      style={{ animationDelay: `${index * 30}ms` }}
                      onClick={() => navigate(`/rtas/${rta.id}`)}
                    >
                      <td className="px-6 py-4">
                        <span className="font-mono text-sm text-primary">{rta.reference_number}</span>
                      </td>
                      <td className="px-6 py-4">
                        <p className="text-sm font-medium text-foreground truncate max-w-xs">{rta.title}</p>
                      </td>
                      <td className="px-6 py-4">
                        <p className="text-sm text-foreground truncate max-w-xs">{rta.location}</p>
                      </td>
                      <td className="px-6 py-4">
                        <Badge variant={getSeverityVariant(rta.severity) as any}>
                          {rta.severity.replace('_', ' ')}
                        </Badge>
                      </td>
                      <td className="px-6 py-4">
                        <Badge variant={getStatusVariant(rta.status) as any}>
                          {rta.status.replace('_', ' ')}
                        </Badge>
                      </td>
                      <td className="px-6 py-4 text-sm text-muted-foreground">
                        {new Date(rta.collision_date).toLocaleDateString()}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
      )}

      {/* Create Modal */}
      <Dialog open={showModal} onOpenChange={setShowModal}>
        <DialogContent className="max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{t('rtas.dialog.title')}</DialogTitle>
            <DialogDescription>
              {t('rtas.dialog.description')}
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleCreate} className="space-y-5">
            <div>
              <label htmlFor="rtas-field-0" className="block text-sm font-medium text-foreground mb-2">{t('common.title')}</label>
              <Input id="rtas-field-0"
                type="text"
                required
                value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                placeholder={t('rtas.form.placeholder.title')}
              />
            </div>

            <div>
              <label htmlFor="rtas-field-1" className="block text-sm font-medium text-foreground mb-2">{t('common.description')}</label>
              <Textarea id="rtas-field-1"
                required
                rows={3}
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                placeholder={t('rtas.form.placeholder.description')}
              />
            </div>

            <div>
              <label htmlFor="rtas-field-2" className="block text-sm font-medium text-foreground mb-2">{t('rtas.table.location')}</label>
              <Input id="rtas-field-2"
                type="text"
                required
                value={formData.location}
                onChange={(e) => setFormData({ ...formData, location: e.target.value })}
                placeholder={t('rtas.form.placeholder.location')}
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label htmlFor="rtas-field-3" className="block text-sm font-medium text-foreground mb-2">{t('rtas.table.severity')}</label>
                <Select
                  value={formData.severity}
                  onValueChange={(value) => setFormData({ ...formData, severity: value })}
                >
                  <SelectTrigger id="rtas-field-3">
                    <SelectValue placeholder={t('rtas.form.placeholder.severity')} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="near_miss">{t('rtas.severity.near_miss')}</SelectItem>
                    <SelectItem value="damage_only">{t('rtas.severity.damage_only')}</SelectItem>
                    <SelectItem value="minor_injury">{t('rtas.severity.minor_injury')}</SelectItem>
                    <SelectItem value="serious_injury">{t('rtas.severity.serious_injury')}</SelectItem>
                    <SelectItem value="fatal">{t('rtas.severity.fatal')}</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <label htmlFor="rtas-field-4" className="block text-sm font-medium text-foreground mb-2">{t('rtas.form.vehicle_reg')}</label>
                <Input id="rtas-field-4"
                  type="text"
                  value={formData.company_vehicle_registration || ''}
                  onChange={(e) => setFormData({ ...formData, company_vehicle_registration: e.target.value })}
                  placeholder={t('rtas.form.placeholder.vehicle_reg')}
                />
              </div>
            </div>

            <div>
              <label htmlFor="rtas-field-5" className="block text-sm font-medium text-foreground mb-2">{t('rtas.form.driver_name')}</label>
              <Input id="rtas-field-5"
                type="text"
                value={formData.driver_name || ''}
                onChange={(e) => setFormData({ ...formData, driver_name: e.target.value })}
                placeholder={t('rtas.form.placeholder.driver_name')}
              />
            </div>

            <div>
              <label htmlFor="rtas-field-6" className="block text-sm font-medium text-foreground mb-2">{t('rtas.form.collision_date')}</label>
              <Input id="rtas-field-6"
                type="datetime-local"
                required
                value={formData.collision_date}
                onChange={(e) => setFormData({ ...formData, collision_date: e.target.value })}
              />
            </div>

            <div className="flex gap-6">
              <div className="flex items-center gap-2">
                <Switch
                  checked={formData.police_attended || false}
                  onCheckedChange={(checked) => setFormData({ ...formData, police_attended: checked })}
                />
                <span className="text-sm text-foreground">{t('rtas.form.police_attended')}</span>
              </div>
              <div className="flex items-center gap-2">
                <Switch
                  checked={formData.driver_injured || false}
                  onCheckedChange={(checked) => setFormData({ ...formData, driver_injured: checked })}
                />
                <span className="text-sm text-foreground">{t('rtas.form.driver_injured')}</span>
              </div>
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
                    {t('rtas.reporting')}
                  </>
                ) : (
                  t('rtas.report')
                )}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}
