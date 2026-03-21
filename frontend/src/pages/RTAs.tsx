import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { trackError } from '../utils/errorTracker'
import { Plus, Car, Search, Loader2, AlertCircle, RefreshCw } from 'lucide-react'
import { TableSkeleton } from '../components/ui/SkeletonLoader'
import { EmptyState } from '../components/ui/EmptyState'
import { rtasApi, RTA, RTACreate, ThirdParty, getApiErrorMessage } from '../api/client'
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
  const [error, setError] = useState<{ message: string; code?: string; requestId?: string } | null>(
    null,
  )
  const [showModal, setShowModal] = useState(false)
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const emptyThirdParty: ThirdParty = {
    name: '',
    vehicle_reg: '',
    vehicle_make_model: '',
    phone: '',
    insurer: '',
    insurer_policy_number: '',
    injured: false,
    damage: '',
  }
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
  const [thirdParties, setThirdParties] = useState<ThirdParty[]>([{ ...emptyThirdParty }])

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
      trackError(err, { component: 'RTAs', action: 'load' })

      // Extract error details for display
      const isTimeout =
        err.code === 'ECONNABORTED' || err.message?.includes('timeout') || err.name === 'AbortError'
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
          message:
            err.response?.data?.message ||
            err.response?.data?.detail?.message ||
            t('rtas.error.generic'),
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
    setCreateError(null)
    try {
      const nonEmptyParties = thirdParties.filter(
        (p) => p.name || p.vehicle_reg || p.phone,
      )
      await rtasApi.create({
        ...formData,
        collision_date: new Date(formData.collision_date).toISOString(),
        reported_date: new Date(formData.reported_date).toISOString(),
        third_parties:
          nonEmptyParties.length > 0 ? { parties: nonEmptyParties } : undefined,
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
      setThirdParties([{ ...emptyThirdParty }])
      loadRtas()
    } catch (err) {
      trackError(err, { component: 'RTAs', action: 'create' })
      setCreateError(getApiErrorMessage(err))
    } finally {
      setCreating(false)
    }
  }

  const getSeverityVariant = (severity: string) => {
    switch (severity) {
      case 'fatal':
        return 'critical'
      case 'serious_injury':
        return 'critical'
      case 'minor_injury':
        return 'high'
      case 'damage_only':
        return 'medium'
      case 'near_miss':
        return 'low'
      default:
        return 'secondary'
    }
  }

  const getStatusVariant = (status: string) => {
    switch (status) {
      case 'closed':
        return 'resolved'
      case 'reported':
        return 'submitted'
      case 'under_investigation':
        return 'in-progress'
      case 'pending_insurance':
        return 'acknowledged'
      case 'pending_actions':
        return 'awaiting-user'
      default:
        return 'secondary'
    }
  }

  const filteredRtas = rtas.filter(
    (r) =>
      r.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
      r.reference_number.toLowerCase().includes(searchTerm.toLowerCase()) ||
      r.location.toLowerCase().includes(searchTerm.toLowerCase()),
  )

  if (loading) {
    return <TableSkeleton rows={8} columns={5} />
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
            <h2 className="text-lg font-semibold text-foreground mb-1">
              {t('rtas.error.load_failed')}
            </h2>
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
        <>
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
                aria-label="Search RTAs"
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
                      <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                        {t('rtas.table.reference')}
                      </th>
                      <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                        {t('rtas.table.title')}
                      </th>
                      <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                        {t('rtas.table.location')}
                      </th>
                      <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                        {t('rtas.table.severity')}
                      </th>
                      <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                        {t('rtas.table.status')}
                      </th>
                      <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                        {t('rtas.table.date')}
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {filteredRtas.length === 0 ? (
                      <tr>
                        <td colSpan={6}>
                          <EmptyState
                            icon={<Car className="w-8 h-8 text-muted-foreground" />}
                            title={t('rtas.empty.title')}
                            description={t('rtas.empty.subtitle')}
                          />
                        </td>
                      </tr>
                    ) : (
                      filteredRtas.map((rta, index) => (
                        <tr
                          key={rta.id}
                          className="hover:bg-surface transition-colors cursor-pointer"
                          style={{ animationDelay: `${index * 30}ms` }}
                          onClick={() => navigate(`/rtas/${rta.id}`)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter' || e.key === ' ') navigate(`/rtas/${rta.id}`)
                          }}
                          role="button"
                          tabIndex={0}
                          aria-label={`View RTA: ${rta.title}`}
                        >
                          <td className="px-6 py-4">
                            <span className="font-mono text-sm text-primary">
                              {rta.reference_number}
                            </span>
                          </td>
                          <td className="px-6 py-4">
                            <p className="text-sm font-medium text-foreground truncate max-w-xs">
                              {rta.title}
                            </p>
                          </td>
                          <td className="px-6 py-4">
                            <p className="text-sm text-foreground truncate max-w-xs">
                              {rta.location}
                            </p>
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
        </>
      )}

      {/* Create Modal */}
      <Dialog open={showModal} onOpenChange={setShowModal}>
        <DialogContent className="max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{t('rtas.dialog.title')}</DialogTitle>
            <DialogDescription>{t('rtas.dialog.description')}</DialogDescription>
          </DialogHeader>
          <form onSubmit={handleCreate} className="space-y-5">
            {createError && (
              <div className="bg-destructive/10 text-destructive text-sm p-3 rounded-lg">
                {createError}
              </div>
            )}
            <div>
              <label
                htmlFor="rtas-field-0"
                className="block text-sm font-medium text-foreground mb-2"
              >
                {t('common.title')}
              </label>
              <Input
                id="rtas-field-0"
                type="text"
                required
                value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                placeholder={t('rtas.form.placeholder.title')}
              />
            </div>

            <div>
              <label
                htmlFor="rtas-field-1"
                className="block text-sm font-medium text-foreground mb-2"
              >
                {t('common.description')}
              </label>
              <Textarea
                id="rtas-field-1"
                required
                rows={3}
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                placeholder={t('rtas.form.placeholder.description')}
              />
            </div>

            <div>
              <label
                htmlFor="rtas-field-2"
                className="block text-sm font-medium text-foreground mb-2"
              >
                {t('rtas.table.location')}
              </label>
              <Input
                id="rtas-field-2"
                type="text"
                required
                value={formData.location}
                onChange={(e) => setFormData({ ...formData, location: e.target.value })}
                placeholder={t('rtas.form.placeholder.location')}
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label
                  htmlFor="rtas-field-3"
                  className="block text-sm font-medium text-foreground mb-2"
                >
                  {t('rtas.table.severity')}
                </label>
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
                    <SelectItem value="serious_injury">
                      {t('rtas.severity.serious_injury')}
                    </SelectItem>
                    <SelectItem value="fatal">{t('rtas.severity.fatal')}</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <label
                  htmlFor="rtas-field-4"
                  className="block text-sm font-medium text-foreground mb-2"
                >
                  {t('rtas.form.vehicle_reg')}
                </label>
                <Input
                  id="rtas-field-4"
                  type="text"
                  value={formData.company_vehicle_registration || ''}
                  onChange={(e) =>
                    setFormData({ ...formData, company_vehicle_registration: e.target.value })
                  }
                  placeholder={t('rtas.form.placeholder.vehicle_reg')}
                />
              </div>
            </div>

            <div>
              <label
                htmlFor="rtas-field-5"
                className="block text-sm font-medium text-foreground mb-2"
              >
                {t('rtas.form.driver_name')}
              </label>
              <Input
                id="rtas-field-5"
                type="text"
                value={formData.driver_name || ''}
                onChange={(e) => setFormData({ ...formData, driver_name: e.target.value })}
                placeholder={t('rtas.form.placeholder.driver_name')}
              />
            </div>

            <div>
              <label
                htmlFor="rtas-field-6"
                className="block text-sm font-medium text-foreground mb-2"
              >
                {t('rtas.form.collision_date')}
              </label>
              <Input
                id="rtas-field-6"
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
                  onCheckedChange={(checked) =>
                    setFormData({ ...formData, police_attended: checked })
                  }
                />
                <span className="text-sm text-foreground">{t('rtas.form.police_attended')}</span>
              </div>
              <div className="flex items-center gap-2">
                <Switch
                  checked={formData.driver_injured || false}
                  onCheckedChange={(checked) =>
                    setFormData({ ...formData, driver_injured: checked })
                  }
                />
                <span className="text-sm text-foreground">{t('rtas.form.driver_injured')}</span>
              </div>
            </div>

            {/* Other Vehicle / Third Party Section */}
            <div className="border-t pt-4">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold text-foreground">
                  Other Vehicle &amp; Driver Details
                </h3>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() =>
                    setThirdParties([...thirdParties, { ...emptyThirdParty }])
                  }
                >
                  <Plus className="w-3 h-3 mr-1" />
                  Add Party
                </Button>
              </div>

              {thirdParties.map((party, idx) => (
                <div
                  key={idx}
                  className="border rounded-lg p-4 mb-3 space-y-3 bg-muted/30"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                      Third Party {idx + 1}
                    </span>
                    {thirdParties.length > 1 && (
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="text-destructive h-6 px-2 text-xs"
                        onClick={() =>
                          setThirdParties(thirdParties.filter((_, i) => i !== idx))
                        }
                      >
                        Remove
                      </Button>
                    )}
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-medium text-muted-foreground mb-1">
                        Driver / Contact Name
                      </label>
                      <Input
                        type="text"
                        value={party.name || ''}
                        onChange={(e) => {
                          const updated = [...thirdParties]
                          updated[idx] = { ...updated[idx], name: e.target.value }
                          setThirdParties(updated)
                        }}
                        placeholder="Full name"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-muted-foreground mb-1">
                        Phone Number
                      </label>
                      <Input
                        type="tel"
                        value={party.phone || ''}
                        onChange={(e) => {
                          const updated = [...thirdParties]
                          updated[idx] = { ...updated[idx], phone: e.target.value }
                          setThirdParties(updated)
                        }}
                        placeholder="07xxx xxxxxx"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-medium text-muted-foreground mb-1">
                        Vehicle Registration
                      </label>
                      <Input
                        type="text"
                        value={party.vehicle_reg || ''}
                        onChange={(e) => {
                          const updated = [...thirdParties]
                          updated[idx] = { ...updated[idx], vehicle_reg: e.target.value }
                          setThirdParties(updated)
                        }}
                        placeholder="AB12 CDE"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-muted-foreground mb-1">
                        Vehicle Make / Model
                      </label>
                      <Input
                        type="text"
                        value={party.vehicle_make_model || ''}
                        onChange={(e) => {
                          const updated = [...thirdParties]
                          updated[idx] = {
                            ...updated[idx],
                            vehicle_make_model: e.target.value,
                          }
                          setThirdParties(updated)
                        }}
                        placeholder="e.g. Ford Transit"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-muted-foreground mb-1">
                      Damage Description
                    </label>
                    <Input
                      type="text"
                      value={party.damage || ''}
                      onChange={(e) => {
                        const updated = [...thirdParties]
                        updated[idx] = { ...updated[idx], damage: e.target.value }
                        setThirdParties(updated)
                      }}
                      placeholder="Describe damage to other vehicle"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-medium text-muted-foreground mb-1">
                        Insurer
                      </label>
                      <Input
                        type="text"
                        value={party.insurer || ''}
                        onChange={(e) => {
                          const updated = [...thirdParties]
                          updated[idx] = { ...updated[idx], insurer: e.target.value }
                          setThirdParties(updated)
                        }}
                        placeholder="Insurance company"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-muted-foreground mb-1">
                        Policy Number
                      </label>
                      <Input
                        type="text"
                        value={party.insurer_policy_number || ''}
                        onChange={(e) => {
                          const updated = [...thirdParties]
                          updated[idx] = {
                            ...updated[idx],
                            insurer_policy_number: e.target.value,
                          }
                          setThirdParties(updated)
                        }}
                        placeholder="Policy number"
                      />
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <Switch
                      checked={party.injured || false}
                      onCheckedChange={(checked) => {
                        const updated = [...thirdParties]
                        updated[idx] = { ...updated[idx], injured: checked }
                        setThirdParties(updated)
                      }}
                    />
                    <span className="text-sm text-foreground">
                      Third party injured
                    </span>
                  </div>
                </div>
              ))}
            </div>

            <DialogFooter className="gap-3 pt-4">
              <Button type="button" variant="outline" onClick={() => setShowModal(false)}>
                {t('cancel')}
              </Button>
              <Button type="submit" disabled={creating}>
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
