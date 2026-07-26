import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { trackError } from '../utils/errorTracker'
import { Plus, Car, Search, AlertCircle, RefreshCw } from 'lucide-react'
import { TableSkeleton } from '../components/ui/SkeletonLoader'
import { EmptyState } from '../components/ui/EmptyState'
import api, {
  rtasApi,
  RTA,
  RTACreate,
  ThirdParty,
  getApiErrorMessage,
  type PaginatedResponse,
} from '../api/client'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Textarea } from '../components/ui/Textarea'
import { Card, CardContent } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { Switch } from '../components/ui/Switch'
import { CaseRegisterTable } from '../components/register/CaseRegisterTable'
import { useCaseRegisterLabels } from '../components/register/useCaseRegisterLabels'
import { formatDisplayDate, formatReference } from '../helpers/formatters'
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
import {
  FormField,
  FormNotice,
  SubmitButton,
  UnsavedChangesDialog,
  useFormController,
  useUnsavedChangesGuard,
  type FieldSpecs,
} from '../components/ui/form'

type RtaFormField =
  | 'title'
  | 'description'
  | 'location'
  | 'severity'
  | 'company_vehicle_registration'
  | 'driver_name'
  | 'collision_date'

/** Stable control ids — also used by the "scroll to first invalid field" behaviour. */
const RTA_CONTROL_IDS: Record<RtaFormField, string> = {
  title: 'rtas-field-0',
  description: 'rtas-field-1',
  location: 'rtas-field-2',
  severity: 'rtas-field-3',
  company_vehicle_registration: 'rtas-field-4',
  driver_name: 'rtas-field-5',
  collision_date: 'rtas-field-6',
}

function buildInitialRtaForm(): RTACreate {
  const now = new Date().toISOString().slice(0, 16)
  return {
    title: '',
    description: '',
    severity: 'damage_only',
    collision_date: now,
    reported_date: now,
    location: '',
    driver_name: '',
    company_vehicle_registration: '',
    police_attended: false,
    driver_injured: false,
  }
}

function buildRtasListSearch(params: { ids: string }): string {
  const next = new URLSearchParams()
  const ids = params.ids.trim()
  if (ids) next.set('ids', ids)
  return next.toString()
}

export default function RTAs() {
  const { t } = useTranslation()
  const registerLabels = useCaseRegisterLabels()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const [rtas, setRtas] = useState<RTA[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<{ message: string; code?: string; requestId?: string } | null>(
    null,
  )
  const [showModal, setShowModal] = useState(false)
  const [formDirty, setFormDirty] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')
  const [idsFilter, setIdsFilter] = useState(() => searchParams.get('ids') || '')
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
  const [formData, setFormData] = useState<RTACreate>(buildInitialRtaForm)
  const [thirdParties, setThirdParties] = useState<ThirdParty[]>([{ ...emptyThirdParty }])

  // Hydrate ids deep-link from shareable URL (back/forward + Safety Insights).
  useEffect(() => {
    const nextIds = searchParams.get('ids') || ''
    setIdsFilter((prev) => (prev === nextIds ? prev : nextIds))
  }, [searchParams])

  // Keep ids in the URL; replace history entry.
  useEffect(() => {
    const desired = buildRtasListSearch({ ids: idsFilter })
    if (desired !== searchParams.toString()) {
      setSearchParams(desired ? new URLSearchParams(desired) : new URLSearchParams(), {
        replace: true,
      })
    }
  }, [idsFilter, searchParams, setSearchParams])

  useEffect(() => {
    loadRtas()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [idsFilter])

  const loadRtas = async () => {
    setLoading(true)
    setError(null)

    // Create abort controller for timeout
    const controller = new AbortController()
    const timeoutId = setTimeout(() => {
      controller.abort()
    }, 15000) // 15 second timeout

    try {
      const ids = idsFilter.trim()
      // Deep-links from Safety Insights may cite more than one page of cases.
      const idCount = ids ? ids.split(',').filter((part) => part.trim()).length : 0
      const pageSize = ids ? Math.min(Math.max(idCount, 50), 100) : 50
      const params = new URLSearchParams({ page: '1', page_size: String(pageSize) })
      if (ids) params.set('ids', ids)
      const response = ids
        ? await api.get<PaginatedResponse<RTA>>(`/api/v1/rtas/?${params.toString()}`)
        : await rtasApi.list(1, pageSize)
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

  /** Any edit marks the form dirty so closing it cannot silently bin typed work. */
  const updateForm = (patch: Partial<RTACreate>) => {
    setFormDirty(true)
    setFormData((prev) => ({ ...prev, ...patch }))
  }

  const updateThirdParties = (next: ThirdParty[]) => {
    setFormDirty(true)
    setThirdParties(next)
  }

  const closeCreateModal = () => {
    setShowModal(false)
    setFormDirty(false)
    setFormData(buildInitialRtaForm())
    setThirdParties([{ ...emptyThirdParty }])
  }

  const rtaFields: FieldSpecs<RtaFormField> = {
    title: { label: t('common.title'), required: true },
    description: { label: t('common.description'), required: true },
    location: { label: t('rtas.table.location'), required: true },
    severity: { label: t('rtas.table.severity') },
    company_vehicle_registration: { label: t('rtas.form.vehicle_reg') },
    driver_name: { label: t('rtas.form.driver_name') },
    collision_date: { label: t('rtas.form.collision_date'), required: true },
  }

  const createForm = useFormController<RtaFormField>({
    fields: rtaFields,
    values: formData as unknown as Record<string, unknown>,
    controlId: (name) => RTA_CONTROL_IDS[name],
    toErrorMessage: (err) => {
      trackError(err, { component: 'RTAs', action: 'create' })
      return getApiErrorMessage(err)
    },
    onSubmit: async () => {
      const nonEmptyParties = thirdParties.filter((p) => p.name || p.vehicle_reg || p.phone)
      await rtasApi.create({
        ...formData,
        collision_date: new Date(formData.collision_date).toISOString(),
        reported_date: new Date(formData.reported_date).toISOString(),
        third_parties: nonEmptyParties.length > 0 ? { parties: nonEmptyParties } : undefined,
      })
      closeCreateModal()
      loadRtas()
    },
  })

  const createGuard = useUnsavedChangesGuard({ dirty: formDirty, onDiscard: closeCreateModal })

  const openCreateModal = () => {
    createForm.resetFeedback()
    setShowModal(true)
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
        <Button data-testid="create-rta-btn" onClick={openCreateModal}>
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
              <CaseRegisterTable
                label={t('rtas.title')}
                rows={filteredRtas}
                rowKey={(rta) => rta.id}
                onOpenRow={(rta) => navigate(`/rtas/${rta.id}`)}
                rowLabel={(rta) =>
                  t('rtas.row.open', 'View road traffic accident: {{reference}}', {
                    reference: formatReference(rta.reference_number),
                  })
                }
                empty={
                  <EmptyState
                    icon={<Car className="w-8 h-8 text-muted-foreground" />}
                    title={t('rtas.empty.title')}
                    description={t('rtas.empty.subtitle')}
                  />
                }
                columns={[
                  {
                    key: 'reference',
                    header: registerLabels.reference,
                    width: 'reference',
                    render: (rta) => (
                      <span className="font-mono text-sm text-primary">
                        {formatReference(rta.reference_number)}
                      </span>
                    ),
                  },
                  {
                    key: 'title',
                    header: registerLabels.title,
                    render: (rta) => (
                      <span className="text-sm font-medium text-foreground">{rta.title}</span>
                    ),
                  },
                  {
                    key: 'location',
                    header: registerLabels.location,
                    render: (rta) => <span className="text-sm text-foreground">{rta.location}</span>,
                  },
                  {
                    key: 'severity',
                    header: registerLabels.severity,
                    width: 'badge',
                    render: (rta) => (
                      <Badge variant={getSeverityVariant(rta.severity) as any}>
                        {rta.severity.replace('_', ' ')}
                      </Badge>
                    ),
                  },
                  {
                    key: 'status',
                    header: registerLabels.status,
                    width: 'badge',
                    render: (rta) => (
                      <Badge variant={getStatusVariant(rta.status) as any}>
                        {rta.status.replace('_', ' ')}
                      </Badge>
                    ),
                  },
                  {
                    key: 'occurred',
                    header: registerLabels.occurred,
                    width: 'date',
                    render: (rta) => (
                      <span className="text-sm text-muted-foreground">
                        {formatDisplayDate(rta.collision_date)}
                      </span>
                    ),
                  },
                ]}
              />
            </CardContent>
          </Card>
        </>
      )}

      {/* Create Modal */}
      <Dialog open={showModal} onOpenChange={createGuard.handleOpenChange}>
        <DialogContent className="max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{t('rtas.dialog.title')}</DialogTitle>
            <DialogDescription>{t('rtas.dialog.description')}</DialogDescription>
          </DialogHeader>
          <form {...createForm.formProps} className="space-y-5">
            {createForm.submitError ? (
              <FormNotice tone="error" data-testid="rta-create-error">
                {createForm.submitError}
              </FormNotice>
            ) : null}

            <FormField {...createForm.fieldProps('title')}>
              {(control) => (
                <Input
                  {...control}
                  type="text"
                  value={formData.title}
                  onChange={(e) => updateForm({ title: e.target.value })}
                  placeholder={t('rtas.form.placeholder.title')}
                  error={Boolean(createForm.errors.title)}
                />
              )}
            </FormField>

            <FormField {...createForm.fieldProps('description')}>
              {(control) => (
                <Textarea
                  {...control}
                  rows={3}
                  value={formData.description}
                  onChange={(e) => updateForm({ description: e.target.value })}
                  placeholder={t('rtas.form.placeholder.description')}
                />
              )}
            </FormField>

            <FormField {...createForm.fieldProps('location')}>
              {(control) => (
                <Input
                  {...control}
                  type="text"
                  value={formData.location}
                  onChange={(e) => updateForm({ location: e.target.value })}
                  placeholder={t('rtas.form.placeholder.location')}
                  error={Boolean(createForm.errors.location)}
                />
              )}
            </FormField>

            <div className="grid grid-cols-2 gap-4">
              <FormField {...createForm.fieldProps('severity')} nativeControl={false}>
                {(control) => (
                  <Select
                    value={formData.severity}
                    onValueChange={(value) => updateForm({ severity: value })}
                  >
                    <SelectTrigger {...control}>
                      <SelectValue placeholder={t('rtas.form.placeholder.severity')} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="near_miss">{t('rtas.severity.near_miss')}</SelectItem>
                      <SelectItem value="damage_only">{t('rtas.severity.damage_only')}</SelectItem>
                      <SelectItem value="minor_injury">
                        {t('rtas.severity.minor_injury')}
                      </SelectItem>
                      <SelectItem value="serious_injury">
                        {t('rtas.severity.serious_injury')}
                      </SelectItem>
                      <SelectItem value="fatal">{t('rtas.severity.fatal')}</SelectItem>
                    </SelectContent>
                  </Select>
                )}
              </FormField>

              <FormField {...createForm.fieldProps('company_vehicle_registration')}>
                {(control) => (
                  <Input
                    {...control}
                    type="text"
                    value={formData.company_vehicle_registration || ''}
                    onChange={(e) => updateForm({ company_vehicle_registration: e.target.value })}
                    placeholder={t('rtas.form.placeholder.vehicle_reg')}
                  />
                )}
              </FormField>
            </div>

            <FormField {...createForm.fieldProps('driver_name')}>
              {(control) => (
                <Input
                  {...control}
                  type="text"
                  value={formData.driver_name || ''}
                  onChange={(e) => updateForm({ driver_name: e.target.value })}
                  placeholder={t('rtas.form.placeholder.driver_name')}
                />
              )}
            </FormField>

            <FormField {...createForm.fieldProps('collision_date')}>
              {(control) => (
                <Input
                  {...control}
                  type="datetime-local"
                  value={formData.collision_date}
                  onChange={(e) => updateForm({ collision_date: e.target.value })}
                  error={Boolean(createForm.errors.collision_date)}
                />
              )}
            </FormField>

            <div className="flex gap-6">
              <div className="flex items-center gap-2">
                <Switch
                  checked={formData.police_attended || false}
                  onCheckedChange={(checked) => updateForm({ police_attended: checked })}
                />
                <span className="text-sm text-foreground">{t('rtas.form.police_attended')}</span>
              </div>
              <div className="flex items-center gap-2">
                <Switch
                  checked={formData.driver_injured || false}
                  onCheckedChange={(checked) => updateForm({ driver_injured: checked })}
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
                    updateThirdParties([...thirdParties, { ...emptyThirdParty }])
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
                          updateThirdParties(thirdParties.filter((_, i) => i !== idx))
                        }
                      >
                        Remove
                      </Button>
                    )}
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label htmlFor={`tp-${idx}-name`} className="block text-xs font-medium text-muted-foreground mb-1">
                        Driver / Contact Name
                      </label>
                      <Input
                        id={`tp-${idx}-name`}
                        type="text"
                        value={party.name || ''}
                        onChange={(e) => {
                          const updated = [...thirdParties]
                          updated[idx] = { ...updated[idx], name: e.target.value }
                          updateThirdParties(updated)
                        }}
                        placeholder="Full name"
                      />
                    </div>
                    <div>
                      <label htmlFor={`tp-${idx}-phone`} className="block text-xs font-medium text-muted-foreground mb-1">
                        Phone Number
                      </label>
                      <Input
                        id={`tp-${idx}-phone`}
                        type="tel"
                        value={party.phone || ''}
                        onChange={(e) => {
                          const updated = [...thirdParties]
                          updated[idx] = { ...updated[idx], phone: e.target.value }
                          updateThirdParties(updated)
                        }}
                        placeholder="07xxx xxxxxx"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label htmlFor={`tp-${idx}-reg`} className="block text-xs font-medium text-muted-foreground mb-1">
                        Vehicle Registration
                      </label>
                      <Input
                        id={`tp-${idx}-reg`}
                        type="text"
                        value={party.vehicle_reg || ''}
                        onChange={(e) => {
                          const updated = [...thirdParties]
                          updated[idx] = { ...updated[idx], vehicle_reg: e.target.value }
                          updateThirdParties(updated)
                        }}
                        placeholder="AB12 CDE"
                      />
                    </div>
                    <div>
                      <label htmlFor={`tp-${idx}-make`} className="block text-xs font-medium text-muted-foreground mb-1">
                        Vehicle Make / Model
                      </label>
                      <Input
                        id={`tp-${idx}-make`}
                        type="text"
                        value={party.vehicle_make_model || ''}
                        onChange={(e) => {
                          const updated = [...thirdParties]
                          updated[idx] = {
                            ...updated[idx],
                            vehicle_make_model: e.target.value,
                          }
                          updateThirdParties(updated)
                        }}
                        placeholder="e.g. Ford Transit"
                      />
                    </div>
                  </div>

                  <div>
                    <label htmlFor={`tp-${idx}-damage`} className="block text-xs font-medium text-muted-foreground mb-1">
                      Damage Description
                    </label>
                    <Input
                      id={`tp-${idx}-damage`}
                      type="text"
                      value={party.damage || ''}
                      onChange={(e) => {
                        const updated = [...thirdParties]
                        updated[idx] = { ...updated[idx], damage: e.target.value }
                        updateThirdParties(updated)
                      }}
                      placeholder="Describe damage to other vehicle"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label htmlFor={`tp-${idx}-insurer`} className="block text-xs font-medium text-muted-foreground mb-1">
                        Insurer
                      </label>
                      <Input
                        id={`tp-${idx}-insurer`}
                        type="text"
                        value={party.insurer || ''}
                        onChange={(e) => {
                          const updated = [...thirdParties]
                          updated[idx] = { ...updated[idx], insurer: e.target.value }
                          updateThirdParties(updated)
                        }}
                        placeholder="Insurance company"
                      />
                    </div>
                    <div>
                      <label htmlFor={`tp-${idx}-policy`} className="block text-xs font-medium text-muted-foreground mb-1">
                        Policy Number
                      </label>
                      <Input
                        id={`tp-${idx}-policy`}
                        type="text"
                        value={party.insurer_policy_number || ''}
                        onChange={(e) => {
                          const updated = [...thirdParties]
                          updated[idx] = {
                            ...updated[idx],
                            insurer_policy_number: e.target.value,
                          }
                          updateThirdParties(updated)
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
                        updateThirdParties(updated)
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
              <Button type="button" variant="outline" onClick={createGuard.requestClose}>
                {t('cancel')}
              </Button>
              <SubmitButton
                submitting={createForm.submitting}
                submittingLabel={t('rtas.reporting')}
                data-testid="rta-create-submit"
              >
                {t('rtas.report')}
              </SubmitButton>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
      <UnsavedChangesDialog
        guard={createGuard}
        title={t('form.unsaved.title', 'Discard unsaved changes?')}
        description={t(
          'form.unsaved.description',
          'This form has changes that have not been saved. Closing it now will lose them.',
        )}
        keepEditingLabel={t('form.unsaved.keep_editing', 'Keep editing')}
        discardLabel={t('form.unsaved.discard', 'Discard changes')}
        data-testid="rta-unsaved-changes"
      />
    </div>
  )
}
