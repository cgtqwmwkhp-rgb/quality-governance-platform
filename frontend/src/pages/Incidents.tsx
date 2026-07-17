import { useEffect, useState, useDeferredValue } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Plus, AlertTriangle, Search, Loader2, MailWarning } from 'lucide-react'
import {
  incidentsApi,
  Incident,
  IncidentCreate,
  getApiErrorMessage,
  notificationsApi,
  UserSearchResult,
} from '../api/client'
import { trackError } from '../utils/errorTracker'
import { queueForSync } from '../lib/syncService'
import { toast } from '../contexts/ToastContext'
import { Button } from '../components/ui/Button'
import { EmptyState } from '../components/ui/EmptyState'
import { Input } from '../components/ui/Input'
import { TableSkeleton } from '../components/ui/SkeletonLoader'
import { Textarea } from '../components/ui/Textarea'
import { Card, CardContent } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { UserEmailSearch } from '../components/UserEmailSearch'
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

type OwnerFilter = 'all' | 'unassigned'

const ALL_FILTER = 'all'
const PAGE_SIZE = 50

/** Display helper — never throw on null/undefined API fields (ErrorBoundary killers). */
function humanizeToken(value: unknown): string {
  if (value == null || value === '') return '—'
  return String(value).replace(/_/g, ' ')
}

function formatIncidentDate(value: unknown): string {
  if (value == null || value === '') return '—'
  const d = new Date(String(value))
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString()
}

/** Coerce list payloads so a shape mismatch cannot crash `.filter` / `.map`. */
function normalizeIncidentItems(payload: unknown): Incident[] {
  if (!payload || typeof payload !== 'object') return []
  const items = (payload as { items?: unknown }).items
  if (!Array.isArray(items)) return []
  return items.filter(
    (row): row is Incident =>
      !!row && typeof row === 'object' && typeof (row as Incident).id === 'number',
  )
}

function parseListPage(raw: string | null): number {
  const n = parseInt(raw || '1', 10)
  return Number.isFinite(n) && n >= 1 ? n : 1
}

function parseListFilter(raw: string | null): string {
  const value = raw?.trim()
  return value && value !== ALL_FILTER ? value : ALL_FILTER
}

function buildIncidentsListSearch(params: {
  q: string
  status: string
  severity: string
  page: number
  owner: OwnerFilter
}): string {
  const next = new URLSearchParams()
  const q = params.q.trim()
  if (q) next.set('q', q)
  if (params.status !== ALL_FILTER) next.set('status', params.status)
  if (params.severity !== ALL_FILTER) next.set('severity', params.severity)
  if (params.page > 1) next.set('page', String(params.page))
  if (params.owner === 'unassigned') next.set('owner', 'unassigned')
  return next.toString()
}

export default function Incidents() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const { t } = useTranslation()
  const [incidents, setIncidents] = useState<Incident[]>([])
  const [loading, setLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [searchTerm, setSearchTerm] = useState(() => searchParams.get('q') || '')
  const [statusFilter, setStatusFilter] = useState(() => parseListFilter(searchParams.get('status')))
  const [severityFilter, setSeverityFilter] = useState(() =>
    parseListFilter(searchParams.get('severity')),
  )
  const [page, setPage] = useState(() => parseListPage(searchParams.get('page')))
  const [ownerFilter, setOwnerFilter] = useState<OwnerFilter>(
    searchParams.get('owner') === 'unassigned' ? 'unassigned' : 'all',
  )
  const [emailConfigured, setEmailConfigured] = useState<boolean | null>(null)
  const [assigningId, setAssigningId] = useState<number | null>(null)
  const [assigneeById, setAssigneeById] = useState<
    Record<number, { email: string; user?: UserSearchResult }>
  >({})
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
    notificationsApi
      .getDeliveryStatus()
      .then((response) => {
        if (!cancelled) setEmailConfigured(response.data.email_configured)
      })
      .catch(() => {
        // Optional honesty signal: omit the banner when readiness cannot be read.
      })
    return () => {
      cancelled = true
    }
  }, [])

  // Hydrate list filters from shareable URL (back/forward + deep links).
  useEffect(() => {
    const nextQ = searchParams.get('q') || ''
    const nextStatus = parseListFilter(searchParams.get('status'))
    const nextSeverity = parseListFilter(searchParams.get('severity'))
    const nextPage = parseListPage(searchParams.get('page'))
    const nextOwner: OwnerFilter =
      searchParams.get('owner') === 'unassigned' ? 'unassigned' : 'all'
    setSearchTerm((prev) => (prev === nextQ ? prev : nextQ))
    setStatusFilter((prev) => (prev === nextStatus ? prev : nextStatus))
    setSeverityFilter((prev) => (prev === nextSeverity ? prev : nextSeverity))
    setPage((prev) => (prev === nextPage ? prev : nextPage))
    setOwnerFilter((prev) => (prev === nextOwner ? prev : nextOwner))
  }, [searchParams])

  // Keep q/status/severity/page/owner in the URL (omit defaults); replace history entry.
  useEffect(() => {
    const desired = buildIncidentsListSearch({
      q: searchTerm,
      status: statusFilter,
      severity: severityFilter,
      page,
      owner: ownerFilter,
    })
    if (desired !== searchParams.toString()) {
      setSearchParams(desired ? new URLSearchParams(desired) : new URLSearchParams(), {
        replace: true,
      })
    }
  }, [searchTerm, statusFilter, severityFilter, page, ownerFilter, searchParams, setSearchParams])

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      setLoading(true)
      setLoadError(null)
      try {
        const response = await incidentsApi.list(
          page,
          PAGE_SIZE,
          ownerFilter === 'unassigned' ? { owner: 'unassigned' } : undefined,
        )
        if (!cancelled) {
          const rows = normalizeIncidentItems(response.data)
          setIncidents(rows)
          if (
            response.data &&
            typeof response.data === 'object' &&
            'items' in response.data &&
            !Array.isArray((response.data as { items?: unknown }).items)
          ) {
            // Static copy — avoid useEffect → t() hook-deps lint; still honest UX.
            setLoadError(
              'Incident list returned an unexpected shape. Showing an empty list.',
            )
          }
        }
      } catch (err) {
        if (!cancelled) {
          trackError(err, { component: 'Incidents', action: 'load' })
          setLoadError(getApiErrorMessage(err))
          setIncidents([])
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [ownerFilter, page])

  const setFilter = (next: OwnerFilter) => {
    setOwnerFilter(next)
    setPage(1)
  }

  const handleAssignOwner = async (incidentId: number) => {
    const picked = assigneeById[incidentId]
    if (!picked?.user?.id) {
      toast.error(t('incidents.triage.select_owner', 'Select a case owner from search results'))
      return
    }
    setAssigningId(incidentId)
    try {
      await incidentsApi.update(incidentId, { owner_id: picked.user.id })
      toast.success(
        emailConfigured === false
          ? t('incidents.triage.assigned_in_app', 'Assigned in-app (email alerts unavailable)')
          : t('incidents.triage.assigned', 'Case owner assigned'),
      )
      setIncidents((prev) => prev.filter((i) => i.id !== incidentId))
      setAssigneeById((prev) => {
        const next = { ...prev }
        delete next[incidentId]
        return next
      })
    } catch (err) {
      trackError(err, { component: 'Incidents', action: 'assign_owner' })
      toast.error(getApiErrorMessage(err))
    } finally {
      setAssigningId(null)
    }
  }

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    setCreating(true)
    setCreateError(null)

    if (!navigator.onLine) {
      const payload = {
        ...formData,
        incident_date: new Date(formData.incident_date).toISOString(),
        reported_date: new Date(formData.reported_date).toISOString(),
      }
      await queueForSync('/api/v1/incidents', 'POST', payload)
      toast.success(t('incidents.saved_offline', 'Saved for sync when back online'))
      setShowModal(false)
      setCreating(false)
      return
    }

    try {
      const response = await incidentsApi.create({
        ...formData,
        incident_date: new Date(formData.incident_date).toISOString(),
        reported_date: new Date(formData.reported_date).toISOString(),
      })
      if (response.data) {
        setIncidents((prev) => [response.data, ...prev])
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

  const getTypeIcon = (type: unknown) => {
    switch (String(type ?? '')) {
      case 'injury':
        return '🩹'
      case 'near_miss':
        return '⚠️'
      case 'hazard':
        return '☢️'
      case 'quality':
        return '✓'
      case 'security':
        return '🔒'
      case 'environmental':
        return '🌿'
      default:
        return '📋'
    }
  }

  const getSeverityVariant = (severity: unknown) => {
    switch (String(severity ?? '')) {
      case 'critical':
        return 'critical'
      case 'high':
        return 'high'
      case 'medium':
        return 'medium'
      case 'low':
        return 'low'
      default:
        return 'secondary'
    }
  }

  const getStatusVariant = (status: unknown) => {
    switch (String(status ?? '')) {
      case 'closed':
        return 'resolved'
      case 'reported':
        return 'submitted'
      case 'under_investigation':
        return 'in-progress'
      case 'pending_actions':
        return 'acknowledged'
      default:
        return 'secondary'
    }
  }

  const deferredSearch = useDeferredValue(searchTerm)
  const filteredIncidents = incidents.filter((i) => {
    if (statusFilter !== ALL_FILTER && i.status !== statusFilter) return false
    if (severityFilter !== ALL_FILTER && i.severity !== severityFilter) return false
    const needle = deferredSearch.trim().toLowerCase()
    if (!needle) return true
    return (
      i.title.toLowerCase().includes(needle) ||
      i.reference_number.toLowerCase().includes(needle)
    )
  })

  if (loading) {
    return (
      <div className="space-y-6 animate-fade-in">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-foreground">{t('incidents.title')}</h1>
            <p className="text-muted-foreground mt-1">{t('incidents.subtitle')}</p>
          </div>
        </div>
        <Card>
          <CardContent className="p-6">
            <TableSkeleton rows={6} columns={6} />
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

      {emailConfigured === false ? (
        <div
          className="rounded-xl border border-amber-300 bg-amber-50 p-4 text-amber-950 dark:border-amber-700 dark:bg-amber-950/30 dark:text-amber-100"
          role="status"
          data-testid="incidents-email-unavailable"
        >
          <div className="flex items-start gap-3">
            <MailWarning className="mt-0.5 h-5 w-5 shrink-0" aria-hidden="true" />
            <div>
              <p className="font-semibold">{t('actions.email_unavailable.title')}</p>
              <p className="mt-1 text-sm">
                {t(
                  'incidents.triage.email_unavailable_body',
                  'Case owners are notified in-app. Email alerts are unavailable while outbound email is not configured.',
                )}
              </p>
            </div>
          </div>
        </div>
      ) : null}

      <div className="flex gap-2" role="group" aria-label={t('incidents.triage.tabs', 'Triage filters')}>
        <Button
          type="button"
          variant={ownerFilter === 'all' ? 'default' : 'outline'}
          size="sm"
          data-testid="incidents-filter-all"
          onClick={() => setFilter('all')}
        >
          {t('incidents.triage.all', 'All')}
        </Button>
        <Button
          type="button"
          variant={ownerFilter === 'unassigned' ? 'default' : 'outline'}
          size="sm"
          data-testid="incidents-filter-unassigned"
          onClick={() => setFilter('unassigned')}
        >
          {t('incidents.triage.unassigned', 'Unassigned')}
        </Button>
      </div>
      {ownerFilter === 'unassigned' ? (
        <p className="text-sm text-muted-foreground" data-testid="incidents-server-filter-label">
          {t(
            'incidents.triage.server_filter_label',
            'Server filter: owner=unassigned (portal intakes without a case owner)',
          )}
        </p>
      ) : null}

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
                  <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    {t('incidents.table.reference')}
                  </th>
                  <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    {t('incidents.table.title')}
                  </th>
                  <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    {t('incidents.table.type')}
                  </th>
                  <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    {t('incidents.table.severity')}
                  </th>
                  <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    {t('incidents.table.status')}
                  </th>
                  <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    {t('incidents.table.date')}
                  </th>
                  {ownerFilter === 'unassigned' ? (
                    <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                      {t('incidents.triage.assign_owner', 'Assign owner')}
                    </th>
                  ) : null}
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {filteredIncidents.length === 0 ? (
                  <tr>
                    <td colSpan={ownerFilter === 'unassigned' ? 7 : 6}>
                      <EmptyState
                        icon={<AlertTriangle className="w-6 h-6 text-muted-foreground" />}
                        title={t('incidents.empty.title', 'No incidents found')}
                        description={t(
                          'incidents.empty.subtitle',
                          'Create your first incident report to get started.',
                        )}
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
                      className="hover:bg-surface transition-colors"
                      style={{ animationDelay: `${index * 30}ms` }}
                    >
                      <td
                        className="px-6 py-4 cursor-pointer"
                        onClick={() => navigate(`/incidents/${incident.id}`)}
                      >
                        <span className="font-mono text-sm text-primary">
                          {incident.reference_number}
                        </span>
                      </td>
                      <td
                        className="px-6 py-4 cursor-pointer"
                        onClick={() => navigate(`/incidents/${incident.id}`)}
                      >
                        <p className="text-sm font-medium text-foreground truncate max-w-xs">
                          {incident.title}
                        </p>
                      </td>
                      <td className="px-6 py-4">
                        <span className="inline-flex items-center gap-1.5 text-sm text-foreground">
                          <span>{getTypeIcon(incident.incident_type)}</span>
                          {humanizeToken(incident.incident_type)}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        <Badge variant={getSeverityVariant(incident.severity) as any}>
                          {humanizeToken(incident.severity)}
                        </Badge>
                      </td>
                      <td className="px-6 py-4">
                        <Badge variant={getStatusVariant(incident.status) as any}>
                          {humanizeToken(incident.status)}
                        </Badge>
                      </td>
                      <td className="px-6 py-4 text-sm text-muted-foreground">
                        {formatIncidentDate(incident.incident_date)}
                      </td>
                      {ownerFilter === 'unassigned' ? (
                        <td
                          className="px-6 py-4"
                          onClick={(e) => e.stopPropagation()}
                          data-testid={`incident-assign-${incident.id}`}
                        >
                          <div className="flex flex-col gap-2 min-w-[220px]">
                            <UserEmailSearch
                              value={assigneeById[incident.id]?.email || ''}
                              onChange={(email, user) =>
                                setAssigneeById((prev) => ({
                                  ...prev,
                                  [incident.id]: { email, user },
                                }))
                              }
                              placeholder={t('incidents.triage.search_owner', 'Search case owner…')}
                            />
                            <Button
                              type="button"
                              size="sm"
                              disabled={assigningId === incident.id}
                              onClick={() => handleAssignOwner(incident.id)}
                            >
                              {assigningId === incident.id ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                              ) : (
                                t('incidents.triage.assign', 'Assign')
                              )}
                            </Button>
                          </div>
                        </td>
                      ) : null}
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
              <div className="bg-destructive/10 text-destructive text-sm p-3 rounded-lg">
                {createError}
              </div>
            )}
            <div>
              <label
                htmlFor="incidents-field-0"
                className="block text-sm font-medium text-foreground mb-2"
              >
                {t('incidents.form.title')} <span className="text-destructive">*</span>
              </label>
              <Input
                id="incidents-field-0"
                type="text"
                required
                value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                placeholder={t('incidents.form.title_placeholder')}
                aria-required="true"
              />
            </div>

            <div>
              <label
                htmlFor="incidents-field-1"
                className="block text-sm font-medium text-foreground mb-2"
              >
                {t('incidents.form.description')} <span className="text-destructive">*</span>
              </label>
              <Textarea
                id="incidents-field-1"
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
                <label
                  htmlFor="incidents-field-2"
                  className="block text-sm font-medium text-foreground mb-2"
                >
                  {t('incidents.form.type')}
                </label>
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
                    <SelectItem value="property_damage">
                      {t('incidents.type.property_damage')}
                    </SelectItem>
                    <SelectItem value="environmental">
                      {t('incidents.type.environmental')}
                    </SelectItem>
                    <SelectItem value="security">{t('incidents.type.security')}</SelectItem>
                    <SelectItem value="quality">{t('incidents.type.quality')}</SelectItem>
                    <SelectItem value="other">{t('incidents.type.other')}</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <label
                  htmlFor="incidents-field-3"
                  className="block text-sm font-medium text-foreground mb-2"
                >
                  {t('incidents.form.severity')}
                </label>
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
              <label
                htmlFor="incidents-field-4"
                className="block text-sm font-medium text-foreground mb-2"
              >
                {t('incidents.form.incident_date')} <span className="text-destructive">*</span>
              </label>
              <Input
                id="incidents-field-4"
                type="datetime-local"
                required
                aria-required="true"
                value={formData.incident_date}
                onChange={(e) => setFormData({ ...formData, incident_date: e.target.value })}
              />
            </div>

            <DialogFooter className="gap-3 pt-4">
              <Button type="button" variant="outline" onClick={() => setShowModal(false)}>
                {t('cancel')}
              </Button>
              <Button type="submit" disabled={creating}>
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
