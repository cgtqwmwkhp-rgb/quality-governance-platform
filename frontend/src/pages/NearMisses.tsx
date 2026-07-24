import { useDeferredValue, useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { AlertTriangle, Loader2, Plus, Search } from 'lucide-react'
import api, {
  nearMissesApi,
  NearMiss,
  NearMissCreate,
  getApiErrorMessage,
  lookupsApi,
  type LookupOption,
  type PaginatedResponse,
} from '../api/client'
import { trackError } from '../utils/errorTracker'
import { toast } from '../contexts/ToastContext'
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
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../components/ui/Dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/Select'
import { mergeLookupSelectOptions } from './admin/lookupSelectOptions'

const ALL_FILTER = 'all'
const PAGE_SIZE = 50

function parseListPage(raw: string | null): number {
  const n = parseInt(raw || '1', 10)
  return Number.isFinite(n) && n >= 1 ? n : 1
}

function parseListFilter(raw: string | null): string {
  const value = raw?.trim()
  return value && value !== ALL_FILTER ? value : ALL_FILTER
}

function buildNearMissesListSearch(params: {
  q: string
  status: string
  severity: string
  page: number
  ids: string
}): string {
  const next = new URLSearchParams()
  const q = params.q.trim()
  if (q) next.set('q', q)
  if (params.status !== ALL_FILTER) next.set('status', params.status)
  if (params.severity !== ALL_FILTER) next.set('severity', params.severity)
  if (params.page > 1) next.set('page', String(params.page))
  const ids = params.ids.trim()
  if (ids) next.set('ids', ids)
  return next.toString()
}

export default function NearMisses() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const { t } = useTranslation()
  const [nearMisses, setNearMisses] = useState<NearMiss[]>([])
  const [loading, setLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [searchTerm, setSearchTerm] = useState(() => searchParams.get('q') || '')
  const [statusFilter, setStatusFilter] = useState(() =>
    parseListFilter(searchParams.get('status')),
  )
  const [severityFilter, setSeverityFilter] = useState(() =>
    parseListFilter(searchParams.get('severity')),
  )
  const [page, setPage] = useState(() => parseListPage(searchParams.get('page')))
  const [idsFilter, setIdsFilter] = useState(() => searchParams.get('ids') || '')
  const [formData, setFormData] = useState<NearMissCreate>({
    reporter_name: '',
    contract: '',
    location: '',
    event_date: new Date().toISOString(),
    description: '',
    potential_severity: 'medium',
    is_hipo: false,
    was_involved: true,
    witnesses_present: false,
  })
  const [customers, setCustomers] = useState<LookupOption[]>([])
  const [customersError, setCustomersError] = useState<string | null>(null)
  const defaultSeverityOptions = [
    { value: 'low', label: t('severity.low') },
    { value: 'medium', label: t('severity.medium') },
    { value: 'high', label: t('severity.high') },
    { value: 'critical', label: t('severity.critical') },
  ]
  const [severityOptions, setSeverityOptions] = useState(defaultSeverityOptions)
  const eventDateInput = formData.event_date ? formData.event_date.slice(0, 16) : ''

  useEffect(() => {
    let cancelled = false
    void lookupsApi
      .list('customers', true)
      .then((res) => {
        if (!cancelled) {
          setCustomers(res.items || [])
          setCustomersError(
            (res.items || []).length === 0
              ? 'No active customers configured. Ask an admin to add Customers in Admin → Lookups → Customers.'
              : null,
          )
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setCustomers([])
          setCustomersError(getApiErrorMessage(err, 'Could not load customers.'))
        }
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (!showModal) return
    let cancelled = false
    setSeverityOptions(defaultSeverityOptions)
    void lookupsApi
      .list('severity_levels', true)
      .then((res) => {
        if (!cancelled) {
          setSeverityOptions(mergeLookupSelectOptions(defaultSeverityOptions, res.items))
        }
      })
      .catch(() => {
        // Keep fixed API-enum defaults when Lookups are unavailable.
      })
    return () => {
      cancelled = true
    }
    // Intentional: lookup labels load only when the create dialog opens.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showModal])

  // Hydrate list filters from shareable URL (back/forward + deep links).
  useEffect(() => {
    const nextQ = searchParams.get('q') || ''
    const nextStatus = parseListFilter(searchParams.get('status'))
    const nextSeverity = parseListFilter(searchParams.get('severity'))
    const nextPage = parseListPage(searchParams.get('page'))
    const nextIds = searchParams.get('ids') || ''
    setSearchTerm((prev) => (prev === nextQ ? prev : nextQ))
    setStatusFilter((prev) => (prev === nextStatus ? prev : nextStatus))
    setSeverityFilter((prev) => (prev === nextSeverity ? prev : nextSeverity))
    setPage((prev) => (prev === nextPage ? prev : nextPage))
    setIdsFilter((prev) => (prev === nextIds ? prev : nextIds))
  }, [searchParams])

  // Keep q/status/severity/page/ids in the URL (omit defaults); replace history entry.
  useEffect(() => {
    const desired = buildNearMissesListSearch({
      q: searchTerm,
      status: statusFilter,
      severity: severityFilter,
      page,
      ids: idsFilter,
    })
    if (desired !== searchParams.toString()) {
      setSearchParams(desired ? new URLSearchParams(desired) : new URLSearchParams(), {
        replace: true,
      })
    }
  }, [searchTerm, statusFilter, severityFilter, page, idsFilter, searchParams, setSearchParams])

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      try {
        const params = new URLSearchParams({
          page: String(page),
          page_size: String(PAGE_SIZE),
        })
        const ids = idsFilter.trim()
        if (ids) params.set('ids', ids)
        const response = ids
          ? await api.get<PaginatedResponse<NearMiss>>(`/api/v1/near-misses/?${params.toString()}`)
          : await nearMissesApi.list(page, PAGE_SIZE)
        if (!cancelled) setNearMisses(response.data.items ?? [])
      } catch (err) {
        if (!cancelled) {
          trackError(err, { component: 'NearMisses', action: 'load' })
          setLoadError(getApiErrorMessage(err))
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [page, idsFilter])

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    setCreating(true)
    setCreateError(null)
    try {
      const response = await nearMissesApi.create(formData)
      setNearMisses((prev) => [response.data, ...prev])
      setShowModal(false)
      setFormData({
        reporter_name: '',
        contract: '',
        location: '',
        event_date: new Date().toISOString(),
        description: '',
        potential_severity: 'medium',
        is_hipo: false,
        was_involved: true,
        witnesses_present: false,
      })
      toast.success(t('near_misses.feedback.created', 'Near miss created'))
    } catch (err) {
      trackError(err, { component: 'NearMisses', action: 'create' })
      setCreateError(getApiErrorMessage(err))
    } finally {
      setCreating(false)
    }
  }

  const deferredSearch = useDeferredValue(searchTerm)
  const filteredNearMisses = nearMisses.filter((item) => {
    if (statusFilter !== ALL_FILTER && item.status !== statusFilter) return false
    if (severityFilter !== ALL_FILTER && (item.potential_severity || 'medium') !== severityFilter) {
      return false
    }
    const needle = deferredSearch.trim().toLowerCase()
    if (!needle) return true
    return (
      item.reference_number.toLowerCase().includes(needle) ||
      item.location.toLowerCase().includes(needle) ||
      item.contract.toLowerCase().includes(needle)
    )
  })

  if (loading) {
    return (
      <div className="space-y-6 animate-fade-in">
        <div>
          <h1 className="text-2xl font-bold text-foreground">{t('near_misses.title')}</h1>
          <p className="text-muted-foreground mt-1">{t('near_misses.subtitle')}</p>
        </div>
        <Card>
          <CardContent className="p-6">
            <TableSkeleton rows={6} columns={5} />
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {loadError && (
        <div className="bg-destructive/10 text-destructive p-4 rounded-lg">{loadError}</div>
      )}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground">{t('near_misses.title')}</h1>
          <p className="text-muted-foreground mt-1">{t('near_misses.subtitle')}</p>
        </div>
        <Button onClick={() => setShowModal(true)}>
          <Plus size={20} />
          {t('near_misses.new')}
        </Button>
      </div>

      <div className="flex gap-4">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
          <Input
            type="text"
            placeholder={t('near_misses.search_placeholder')}
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-10"
          />
        </div>
      </div>

      {filteredNearMisses.length === 0 ? (
        <EmptyState
          icon={<AlertTriangle className="w-10 h-10" />}
          title={t('near_misses.empty.title')}
          description={t('near_misses.empty.subtitle')}
          action={
            <Button onClick={() => setShowModal(true)}>
              <Plus className="w-4 h-4 mr-2" />
              {t('near_misses.create')}
            </Button>
          }
        />
      ) : (
        <Card>
          <CardContent className="p-0 overflow-x-auto">
            <table className="w-full">
              <thead className="bg-muted/50">
                <tr>
                  <th className="text-left p-4 text-sm font-medium text-muted-foreground">
                    {t('near_misses.table.reference')}
                  </th>
                  <th className="text-left p-4 text-sm font-medium text-muted-foreground">
                    {t('near_misses.table.details', 'Details')}
                  </th>
                  <th className="text-left p-4 text-sm font-medium text-muted-foreground">
                    {t('near_misses.table.date')}
                  </th>
                  <th className="text-left p-4 text-sm font-medium text-muted-foreground">
                    {t('near_misses.table.severity')}
                  </th>
                  <th className="text-left p-4 text-sm font-medium text-muted-foreground">
                    {t('near_misses.table.status')}
                  </th>
                </tr>
              </thead>
              <tbody>
                {filteredNearMisses.map((item) => (
                  <tr
                    key={item.id}
                    className="border-t border-border hover:bg-muted/30 cursor-pointer transition-colors"
                    onClick={() => navigate(`/near-misses/${item.id}`)}
                  >
                    <td className="p-4 font-medium text-foreground">{item.reference_number}</td>
                    <td className="p-4">
                      <div className="font-medium text-foreground">{item.contract}</div>
                      <div className="text-sm text-muted-foreground line-clamp-1">
                        {item.location}
                      </div>
                    </td>
                    <td className="p-4 text-sm text-muted-foreground">
                      {new Date(item.event_date).toLocaleDateString()}
                    </td>
                    <td className="p-4">
                      <div className="flex flex-wrap gap-1">
                        <Badge variant="secondary">{item.potential_severity || 'medium'}</Badge>
                        {item.is_hipo ? (
                          <Badge variant="destructive">
                            {t('near_misses.badge.hipo', 'HiPo')}
                          </Badge>
                        ) : null}
                      </div>
                    </td>
                    <td className="p-4">
                      <Badge variant="outline">{item.status}</Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}

      <Dialog open={showModal} onOpenChange={setShowModal}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>{t('near_misses.dialog.title')}</DialogTitle>
            <DialogDescription>{t('near_misses.subtitle')}</DialogDescription>
          </DialogHeader>
          <form onSubmit={handleCreate} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label
                  htmlFor="near-miss-reporter-name"
                  className="text-sm font-medium text-muted-foreground"
                >
                  {t('near_misses.form.reporter_name', 'Reporter name')}
                </label>
                <Input
                  id="near-miss-reporter-name"
                  value={formData.reporter_name}
                  onChange={(e) => setFormData({ ...formData, reporter_name: e.target.value })}
                  className="mt-1"
                  required
                />
              </div>
              <div>
                <label
                  htmlFor="near-miss-contract"
                  className="text-sm font-medium text-muted-foreground"
                >
                  {t('near_misses.form.contract', 'Customer')}
                </label>
                <Select
                  value={formData.contract || undefined}
                  onValueChange={(value) => setFormData({ ...formData, contract: value })}
                >
                  <SelectTrigger
                    id="near-miss-contract"
                    className="mt-1"
                    data-testid="near-miss-contract"
                  >
                    <SelectValue
                      placeholder={t('near_misses.form.contract_placeholder', 'Select customer')}
                    />
                  </SelectTrigger>
                  <SelectContent>
                    {customers.map((customer) => (
                      <SelectItem key={customer.id} value={customer.code}>
                        {customer.label}
                        {customer.description ? ` · ${customer.description}` : ''}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {customersError ? (
                  <p className="mt-1 text-xs text-destructive" role="alert">
                    {customersError}
                  </p>
                ) : null}
              </div>
            </div>

            <div>
              <label
                htmlFor="near-miss-location"
                className="text-sm font-medium text-muted-foreground"
              >
                {t('common.location')}
              </label>
              <Input
                id="near-miss-location"
                value={formData.location}
                onChange={(e) => setFormData({ ...formData, location: e.target.value })}
                className="mt-1"
                required
              />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label
                  htmlFor="near-miss-event-date"
                  className="text-sm font-medium text-muted-foreground"
                >
                  {t('near_misses.form.event_date', 'Event date')}
                </label>
                <Input
                  id="near-miss-event-date"
                  type="datetime-local"
                  value={eventDateInput}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      event_date: e.target.value
                        ? new Date(e.target.value).toISOString()
                        : formData.event_date,
                    })
                  }
                  className="mt-1"
                  required
                />
              </div>
              <div>
                <label
                  htmlFor="near-miss-potential-severity"
                  className="text-sm font-medium text-muted-foreground"
                >
                  {t('near_misses.form.potential_severity', 'Potential severity')}
                </label>
                <Select
                  value={formData.potential_severity}
                  onValueChange={(value) => setFormData({ ...formData, potential_severity: value })}
                >
                  <SelectTrigger id="near-miss-potential-severity" className="mt-1">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {severityOptions.map((option) => (
                      <SelectItem key={option.value} value={option.value}>
                        {option.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <label className="flex items-center gap-2 text-sm text-foreground">
              <input
                type="checkbox"
                checked={Boolean(formData.is_hipo)}
                onChange={(e) => setFormData({ ...formData, is_hipo: e.target.checked })}
              />
              {t(
                'near_misses.form.is_hipo',
                'High potential (HiPo) — serious injury or fatality potential',
              )}
            </label>

            <div>
              <label
                htmlFor="near-miss-description"
                className="text-sm font-medium text-muted-foreground"
              >
                {t('common.description')}
              </label>
              <Textarea
                id="near-miss-description"
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                rows={4}
                className="mt-1"
                required
              />
            </div>

            <div>
              <label
                htmlFor="near-miss-potential-consequences"
                className="text-sm font-medium text-muted-foreground"
              >
                {t('near_misses.form.potential_consequences', 'Potential consequences')}
              </label>
              <Textarea
                id="near-miss-potential-consequences"
                value={formData.potential_consequences || ''}
                onChange={(e) =>
                  setFormData({ ...formData, potential_consequences: e.target.value || undefined })
                }
                rows={3}
                className="mt-1"
              />
            </div>

            {createError && <div className="text-sm text-destructive">{createError}</div>}

            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setShowModal(false)}>
                {t('common.cancel')}
              </Button>
              <Button type="submit" disabled={creating}>
                {creating ? <Loader2 className="w-4 h-4 animate-spin" /> : t('near_misses.create')}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}
