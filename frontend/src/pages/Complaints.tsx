import { useEffect, useState, useDeferredValue } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { trackError } from '../utils/errorTracker'
import { Plus, MessageSquare, Search, Loader2, MailWarning, Paperclip } from 'lucide-react'
import {
  complaintsApi,
  Complaint,
  ComplaintCreate,
  Contract,
  contractsApi,
  evidenceAssetsApi,
  getApiErrorMessage,
  lookupsApi,
  notificationsApi,
  UserSearchResult,
} from '../api/client'
import { queueForSync } from '../lib/syncService'
import { toast } from '../contexts/ToastContext'
import { Button } from '../components/ui/Button'
import { EmptyState } from '../components/ui/EmptyState'
import { Input } from '../components/ui/Input'
import { TableSkeleton } from '../components/ui/SkeletonLoader'
import { Textarea } from '../components/ui/Textarea'
import { Card, CardContent } from '../components/ui/Card'
import { Badge, type BadgeVariant } from '../components/ui/Badge'
import { EngineerPeoplePicker } from '../components/EngineerPeoplePicker'
import FuzzySearchDropdown from '../components/FuzzySearchDropdown'
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
import {
  CUSTOMERS_LOOKUP_CATEGORY,
  toCustomerSelectOptions,
} from './admin/customersCatalog'
import { mergeLookupSelectOptions } from './admin/lookupSelectOptions'

const COMPLAINT_TYPE_VALUES = [
  'product',
  'service',
  'delivery',
  'communication',
  'billing',
  'staff',
  'environmental',
  'safety',
  'other',
] as const

const CHANNEL_OPTIONS = [
  { value: 'phone', label: 'Phone' },
  { value: 'email', label: 'Email' },
  { value: 'in_person', label: 'In person' },
  { value: 'portal', label: 'Portal' },
  { value: 'api', label: 'API' },
  { value: 'manual', label: 'Manual / other' },
] as const

const EMPTY_FORM: ComplaintCreate = {
  title: '',
  description: '',
  complaint_type: 'other',
  priority: 'medium',
  received_date: new Date().toISOString().slice(0, 16),
  complainant_name: '',
  complainant_email: '',
  complainant_phone: '',
  complainant_company: '',
  source_type: 'manual',
  contract_id: null,
  subject_user_id: null,
  subject_name: '',
  alleged_event_at: null,
}

function freshComplaintForm(): ComplaintCreate {
  return { ...EMPTY_FORM, received_date: new Date().toISOString().slice(0, 16) }
}

function isComplaintCreateDirty(
  form: ComplaintCreate,
  extras: { subjectEmail: string; pendingFiles: File[]; selectedCustomerCode: string },
): boolean {
  if (extras.pendingFiles.length > 0) return true
  if (extras.subjectEmail.trim()) return true
  if (extras.selectedCustomerCode.trim()) return true
  if (form.title.trim() || form.description.trim()) return true
  if (
    form.complainant_name.trim() ||
    form.complainant_email?.trim() ||
    form.complainant_phone?.trim()
  ) {
    return true
  }
  if (form.complainant_company?.trim() || form.subject_name?.trim()) return true
  if (form.contract_id != null) return true
  if (form.complaint_type !== 'other' || form.priority !== 'medium') return true
  if (form.alleged_event_at) return true
  return false
}

type OwnerFilter = 'all' | 'unassigned'

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

function buildComplaintsListSearch(params: {
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

export default function Complaints() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const { t } = useTranslation()
  const [complaints, setComplaints] = useState<Complaint[]>([])
  const [loading, setLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [creating, setCreating] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [listUnavailable, setListUnavailable] = useState(false)
  const [emailConfigured, setEmailConfigured] = useState<boolean | null>(null)
  const [searchTerm, setSearchTerm] = useState(() => searchParams.get('q') || '')
  const [statusFilter, setStatusFilter] = useState(() => parseListFilter(searchParams.get('status')))
  const [severityFilter, setSeverityFilter] = useState(() =>
    parseListFilter(searchParams.get('severity')),
  )
  const [page, setPage] = useState(() => parseListPage(searchParams.get('page')))
  const [ownerFilter, setOwnerFilter] = useState<OwnerFilter>(
    searchParams.get('owner') === 'unassigned' ? 'unassigned' : 'all',
  )
  const [assigningId, setAssigningId] = useState<number | null>(null)
  const [assigneeById, setAssigneeById] = useState<
    Record<number, { email: string; user?: UserSearchResult }>
  >({})
  const [formData, setFormData] = useState<ComplaintCreate>(freshComplaintForm)
  const [contracts, setContracts] = useState<Contract[]>([])
  const [customerOptions, setCustomerOptions] = useState<{ value: string; label: string }[]>([])
  const [selectedCustomerCode, setSelectedCustomerCode] = useState('')
  const [customersLoaded, setCustomersLoaded] = useState(false)
  const [topicOptions, setTopicOptions] = useState<{ value: string; label: string }[]>([])
  const [subjectEmail, setSubjectEmail] = useState('')
  const [pendingFiles, setPendingFiles] = useState<File[]>([])

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

  // Load Customers lookup (SSOT) + contracts (optional FK) + topic labels when create opens.
  useEffect(() => {
    if (!showModal) {
      setCustomersLoaded(false)
      return
    }
    let cancelled = false
    setCustomersLoaded(false)
    ;(async () => {
      try {
        const [customerRes, contractRes, lookupRes] = await Promise.all([
          lookupsApi.list(CUSTOMERS_LOOKUP_CATEGORY, true).catch(() => ({ items: [], total: 0 })),
          contractsApi.list(true).catch(() => ({ items: [] as Contract[] })),
          lookupsApi.list('complaint_types', true).catch(() => ({ items: [], total: 0 })),
        ])
        if (cancelled) return
        const fromLookup = toCustomerSelectOptions(customerRes.items || [])
        const fromContracts = (contractRes.items || []).map((c) => ({
          value: `contract:${c.id}`,
          label: c.client_name ? `${c.client_name} (${c.code})` : `${c.name} (${c.code})`,
        }))
        // Prefer Admin → Lookups → Customers; fall back to Contracts only if lookup empty.
        setCustomerOptions(fromLookup.length > 0 ? fromLookup : fromContracts)
        setContracts(contractRes.items || [])
        setCustomersLoaded(true)
        setTopicOptions(
          mergeLookupSelectOptions(
            COMPLAINT_TYPE_VALUES.map((code) => ({
              value: code,
              label: t(`complaints.type.${code}`, code),
            })),
            lookupRes.items,
          ),
        )
      } catch (err) {
        if (!cancelled) {
          setCustomersLoaded(true)
          trackError(err, { component: 'Complaints', action: 'loadCreateLookups' })
          setTopicOptions(
            COMPLAINT_TYPE_VALUES.map((code) => ({
              value: code,
              label: t(`complaints.type.${code}`, code),
            })),
          )
        }
      }
    })()
    return () => {
      cancelled = true
    }
  }, [showModal, t])

  const customersUnavailable = customersLoaded && customerOptions.length === 0

  const applyCustomerSelection = (value: string) => {
    setSelectedCustomerCode(value)
    if (!value) {
      setFormData((prev) => ({
        ...prev,
        contract_id: null,
        complainant_company: '',
      }))
      return
    }
    if (value.startsWith('contract:')) {
      const id = Number(value.slice('contract:'.length))
      const contract = contracts.find((c) => c.id === id)
      setFormData((prev) => ({
        ...prev,
        contract_id: Number.isFinite(id) ? id : null,
        complainant_company: contract?.client_name || contract?.name || '',
      }))
      return
    }
    const option = customerOptions.find((o) => o.value === value)
    const label = option?.label || value
    const matched = contracts.find(
      (c) =>
        c.code?.toLowerCase() === value.toLowerCase() ||
        c.client_name?.toLowerCase() === label.toLowerCase() ||
        c.name?.toLowerCase() === label.toLowerCase(),
    )
    setFormData((prev) => ({
      ...prev,
      contract_id: matched?.id ?? null,
      complainant_company: label,
    }))
  }

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
    const desired = buildComplaintsListSearch({
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
        const response = await complaintsApi.list(
          page,
          PAGE_SIZE,
          ownerFilter === 'unassigned' ? { owner: 'unassigned' } : undefined,
        )
        if (!cancelled) {
          setComplaints(response.data.items ?? [])
          setListUnavailable(false)
          setLoadError(null)
        }
      } catch (err) {
        if (!cancelled) {
          trackError(err, { component: 'Complaints', action: 'load' })
          const message = getApiErrorMessage(err)
          // Do not clear to [] and imply "no complaints" — that is compliance theatre.
          setListUnavailable(true)
          setLoadError(message)
          toast.error(`Complaints list unavailable: ${message}`)
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

  const handleAssignOwner = async (complaintId: number) => {
    const picked = assigneeById[complaintId]
    if (!picked?.user?.id) {
      toast.error(t('complaints.triage.select_owner', 'Select a case owner from search results'))
      return
    }
    setAssigningId(complaintId)
    try {
      await complaintsApi.update(complaintId, { owner_id: picked.user.id })
      toast.success(
        emailConfigured === false
          ? t('complaints.triage.assigned_in_app', 'Assigned in-app (email alerts unavailable)')
          : t('complaints.triage.assigned', 'Case owner assigned'),
      )
      setComplaints((prev) => prev.filter((c) => c.id !== complaintId))
      setAssigneeById((prev) => {
        const next = { ...prev }
        delete next[complaintId]
        return next
      })
    } catch (err) {
      trackError(err, { component: 'Complaints', action: 'assign_owner' })
      toast.error(getApiErrorMessage(err))
    } finally {
      setAssigningId(null)
    }
  }

  const resetCreateForm = () => {
    setPendingFiles([])
    setSubjectEmail('')
    setFormError(null)
    setSelectedCustomerCode('')
    setFormData(freshComplaintForm())
  }

  const requestCloseCreateModal = (): boolean => {
    if (
      isComplaintCreateDirty(formData, { subjectEmail, pendingFiles, selectedCustomerCode }) &&
      !window.confirm(
        t(
          'complaints.dialog.discard_confirm',
          'Discard unsaved complaint details?',
        ),
      )
    ) {
      return false
    }
    resetCreateForm()
    setShowModal(false)
    return true
  }

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!formData.title.trim() || !formData.description.trim() || !formData.complainant_name.trim()) {
      setFormError(t('complaints.form.required_error'))
      return
    }
    if (!selectedCustomerCode) {
      setFormError(t('complaints.form.customer_required', 'Select which customer this complaint is from.'))
      return
    }
    if (customersUnavailable) {
      setFormError(
        t(
          'complaints.form.customer_unavailable',
          'No customers are available — add customers in Admin → Lookups before creating a complaint.',
        ),
      )
      return
    }
    setFormError(null)
    setCreating(true)

    const selectedCustomerLabel =
      customerOptions.find((o) => o.value === selectedCustomerCode)?.label?.trim() ||
      selectedCustomerCode
    const complainantCompany =
      formData.complainant_company?.trim() || selectedCustomerLabel || undefined

    const payload: ComplaintCreate = {
      ...formData,
      received_date: new Date(formData.received_date).toISOString(),
      alleged_event_at: formData.alleged_event_at
        ? new Date(formData.alleged_event_at).toISOString()
        : null,
      subject_name: formData.subject_name?.trim() || null,
      complainant_company: complainantCompany,
      source_type: formData.source_type || 'manual',
    }

    if (!navigator.onLine) {
      await queueForSync('/api/v1/complaints', 'POST', payload)
      toast.success(t('complaints.saved_offline', 'Saved for sync when back online'))
      resetCreateForm()
      setShowModal(false)
      setCreating(false)
      return
    }

    try {
      const response = await complaintsApi.create(payload)
      if (response.data) {
        const created = response.data
        if (pendingFiles.length > 0) {
          const uploadResults = await Promise.allSettled(
            pendingFiles.map((file) =>
              evidenceAssetsApi.upload(file, {
                source_module: 'complaint',
                source_id: created.id,
                title: file.name,
              }),
            ),
          )
          const failed = uploadResults.filter((r) => r.status === 'rejected').length
          if (failed > 0) {
            toast.error(
              t(
                'complaints.attachments_partial',
                {
                  count: failed,
                  defaultValue:
                    '{{count}} attachment(s) failed to upload — open the complaint to retry.',
                },
              ),
            )
          }
        }
        setComplaints((prev) => [created, ...prev])
        setShowModal(false)
        resetCreateForm()
        toast.success(`Complaint ${created.reference_number} recorded`)
        navigate(`/complaints/${created.id}`)
      }
    } catch (err) {
      trackError(err, { component: 'Complaints', action: 'create' })
      setFormError(getApiErrorMessage(err))
    } finally {
      setCreating(false)
    }
  }

  const getPriorityVariant = (priority: string): BadgeVariant => {
    switch (priority) {
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

  const getStatusVariant = (status: string): BadgeVariant => {
    switch (status) {
      case 'closed':
      case 'resolved':
        return 'resolved'
      case 'received':
        return 'submitted'
      case 'acknowledged':
        return 'acknowledged'
      case 'under_investigation':
        return 'in-progress'
      case 'pending_response':
        return 'awaiting-user'
      case 'awaiting_customer':
        return 'awaiting-user'
      case 'escalated':
        return 'critical'
      default:
        return 'secondary'
    }
  }

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'product':
        return '📦'
      case 'service':
        return '🛠️'
      case 'delivery':
        return '🚚'
      case 'communication':
        return '📞'
      case 'billing':
        return '💳'
      case 'staff':
        return '👤'
      case 'environmental':
        return '🌿'
      case 'safety':
        return '⚠️'
      default:
        return '📋'
    }
  }

  const deferredSearch = useDeferredValue(searchTerm)
  const needle = deferredSearch.trim().toLowerCase()
  // Null-safe client filter — never throw on missing complainant/title fields from API.
  const filteredComplaints = complaints.filter((c) => {
    if (statusFilter !== ALL_FILTER && c.status !== statusFilter) return false
    if (severityFilter !== ALL_FILTER && c.priority !== severityFilter) return false
    if (!needle) return true
    const haystack = [c.title, c.reference_number, c.complainant_name]
      .filter((v): v is string => typeof v === 'string' && v.length > 0)
      .join(' ')
      .toLowerCase()
    return haystack.includes(needle)
  })
  const isLive = !loading && !listUnavailable && !loadError

  if (loading) {
    return (
      <div className="space-y-6 animate-fade-in">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-foreground">{t('complaints.title')}</h1>
            <p className="text-muted-foreground mt-1">{t('complaints.subtitle')}</p>
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
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-2xl font-bold text-foreground">{t('complaints.title')}</h1>
            {isLive && (
              <Badge variant="resolved" data-testid="complaints-live-badge">
                Live data
              </Badge>
            )}
            {listUnavailable && (
              <Badge variant="critical" data-testid="complaints-unavailable-badge">
                Unavailable
              </Badge>
            )}
          </div>
          <p className="text-muted-foreground mt-1">{t('complaints.subtitle')}</p>
        </div>
        <Button onClick={() => setShowModal(true)} data-testid="complaints-new">
          <Plus size={20} />
          {t('complaints.new')}
        </Button>
      </div>

      {emailConfigured === false ? (
        <div
          className="rounded-xl border border-amber-300 bg-amber-50 p-4 text-amber-950 dark:border-amber-700 dark:bg-amber-950/30 dark:text-amber-100"
          role="status"
          data-testid="complaints-email-unavailable"
        >
          <div className="flex items-start gap-3">
            <MailWarning className="mt-0.5 h-5 w-5 shrink-0" aria-hidden="true" />
            <div>
              <p className="font-semibold">Email alerts unavailable</p>
              <p className="mt-1 text-sm">
                Complaints and follow-up actions are saved, but outbound email is not configured — do
                not expect complainant or assignee alerts to send.
              </p>
            </div>
          </div>
        </div>
      ) : null}

      {loadError && (
        <div
          className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 mb-4"
          data-testid="complaints-load-error"
          role="alert"
        >
          <p className="text-sm text-destructive">{loadError}</p>
        </div>
      )}

      <div className="flex gap-2" role="group" aria-label={t('complaints.triage.tabs', 'Triage filters')}>
        <Button
          type="button"
          variant={ownerFilter === 'all' ? 'default' : 'outline'}
          size="sm"
          data-testid="complaints-filter-all"
          onClick={() => setFilter('all')}
        >
          {t('complaints.triage.all', 'All')}
        </Button>
        <Button
          type="button"
          variant={ownerFilter === 'unassigned' ? 'default' : 'outline'}
          size="sm"
          data-testid="complaints-filter-unassigned"
          onClick={() => setFilter('unassigned')}
        >
          {t('complaints.triage.unassigned', 'Unassigned')}
        </Button>
      </div>
      {ownerFilter === 'unassigned' ? (
        <p className="text-sm text-muted-foreground" data-testid="complaints-server-filter-label">
          {t(
            'complaints.triage.server_filter_label',
            'Server filter: owner=unassigned (portal intakes without a case owner)',
          )}
        </p>
      ) : null}

      {/* Search */}
      <div className="flex gap-4">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
          <Input
            type="text"
            placeholder={t('complaints.search_placeholder')}
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-10"
            data-testid="complaints-search"
            disabled={listUnavailable}
          />
        </div>
      </div>

      {/* Complaints Table */}
      <Card>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border">
                  <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    {t('complaints.table.reference')}
                  </th>
                  <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    {t('complaints.table.title')}
                  </th>
                  <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    {t('complaints.table.type')}
                  </th>
                  <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    {t('complaints.table.complainant')}
                  </th>
                  <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    {t('complaints.table.priority')}
                  </th>
                  <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    {t('complaints.table.status')}
                  </th>
                  <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    {t('complaints.table.received')}
                  </th>
                  {ownerFilter === 'unassigned' ? (
                    <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                      {t('complaints.triage.assign_owner', 'Assign owner')}
                    </th>
                  ) : null}
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {listUnavailable ? (
                  <tr>
                    <td colSpan={7}>
                      <div data-testid="complaints-list-unavailable">
                        <EmptyState
                          icon={<MessageSquare className="w-6 h-6 text-muted-foreground" />}
                          title="Complaints unavailable"
                          description="The complaints list could not be loaded. This is not an empty register — retry when the service recovers."
                        />
                      </div>
                    </td>
                  </tr>
                ) : filteredComplaints.length === 0 ? (
                  <tr>
                    <td colSpan={ownerFilter === 'unassigned' ? 8 : 7}>
                      <EmptyState
                        icon={<MessageSquare className="w-6 h-6 text-muted-foreground" />}
                        title={
                          needle
                            ? 'No matching complaints'
                            : t('complaints.empty.title', 'No complaints found')
                        }
                        description={
                          needle
                            ? 'Try a different search term. Tenant-scoped results only — other tenants are never shown.'
                            : t(
                                'complaints.empty.subtitle',
                                'Create your first complaint to get started.',
                              )
                        }
                        action={
                          !needle ? (
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => setShowModal(true)}
                              data-testid="complaints-empty-create"
                            >
                              <Plus size={16} /> {t('complaints.new', 'New Complaint')}
                            </Button>
                          ) : undefined
                        }
                      />
                    </td>
                  </tr>
                ) : (
                  filteredComplaints.map((complaint, index) => (
                    <tr
                      key={complaint.id}
                      className="hover:bg-surface transition-colors"
                      style={{ animationDelay: `${index * 30}ms` }}
                      onClick={() => navigate(`/complaints/${complaint.id}`)}
                      role="button"
                      tabIndex={0}
                      data-testid="complaint-row-link"
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault()
                          navigate(`/complaints/${complaint.id}`)
                        }
                      }}
                    >
                      <td
                        className="px-6 py-4 cursor-pointer"
                        onClick={() => navigate(`/complaints/${complaint.id}`)}
                      >
                        <span className="font-mono text-sm text-primary">
                          {complaint.reference_number}
                        </span>
                      </td>
                      <td
                        className="px-6 py-4 cursor-pointer"
                        onClick={() => navigate(`/complaints/${complaint.id}`)}
                      >
                        <p className="text-sm font-medium text-foreground truncate max-w-xs">
                          {complaint.title}
                        </p>
                      </td>
                      <td className="px-6 py-4">
                        <span className="inline-flex items-center gap-1.5 text-sm text-foreground">
                          <span>{getTypeIcon(complaint.complaint_type)}</span>
                          {complaint.complaint_type}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        <p className="text-sm text-foreground">
                          {complaint.complainant_name || '—'}
                        </p>
                      </td>
                      <td className="px-6 py-4">
                        <Badge variant={getPriorityVariant(complaint.priority)}>
                          {complaint.priority}
                        </Badge>
                      </td>
                      <td className="px-6 py-4">
                        <Badge variant={getStatusVariant(complaint.status)}>
                          {complaint.status.replace('_', ' ')}
                        </Badge>
                      </td>
                      <td className="px-6 py-4 text-sm text-muted-foreground">
                        {new Date(complaint.received_date).toLocaleDateString()}
                      </td>
                      {ownerFilter === 'unassigned' ? (
                        <td
                          className="px-6 py-4"
                          onClick={(e) => e.stopPropagation()}
                          data-testid={`complaint-assign-${complaint.id}`}
                        >
                          <div className="flex flex-col gap-2 min-w-[220px]">
                            <EngineerPeoplePicker
                              valueLabel={assigneeById[complaint.id]?.email || ''}
                              requireLogin
                              onChange={(selection) =>
                                setAssigneeById((prev) => ({
                                  ...prev,
                                  [complaint.id]: selection?.user
                                    ? {
                                        email: selection.user.email || selection.label,
                                        user: selection.user,
                                      }
                                    : { email: '' },
                                }))
                              }
                              placeholder={t(
                                'complaints.triage.search_owner',
                                'Search active employees…',
                              )}
                              testId={`complaint-owner-picker-${complaint.id}`}
                            />
                            <Button
                              type="button"
                              size="sm"
                              disabled={assigningId === complaint.id}
                              onClick={() => handleAssignOwner(complaint.id)}
                            >
                              {assigningId === complaint.id ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                              ) : (
                                t('complaints.triage.assign', 'Assign')
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

      {/* Create Modal — Wave 1 intake (customer, parties, channel, topic, times, attachments) */}
      <Dialog
        open={showModal}
        onOpenChange={(open) => {
          if (open) {
            setShowModal(true)
            return
          }
          requestCloseCreateModal()
        }}
      >
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-xl">
          <DialogHeader>
            <DialogTitle>{t('complaints.dialog.title')}</DialogTitle>
            <DialogDescription>
              {t(
                'complaints.dialog.intake_hint',
                'Capture who, which customer, channel, topic, and when — then attach evidence.',
              )}
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleCreate} className="space-y-5" data-testid="complaints-create-form">
            <div className="space-y-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                {t('complaints.form.group_customer', 'Customer')}
              </p>
              <FuzzySearchDropdown
                label={`${t('complaints.form.customer', 'Which customer')} *`}
                required
                options={customerOptions}
                value={selectedCustomerCode}
                onChange={applyCustomerSelection}
                placeholder={t('complaints.form.customer_search', 'Search customer…')}
              />
              {customersUnavailable ? (
                <div
                  className="rounded-lg border border-warning/40 bg-warning/10 px-3 py-3 text-sm text-foreground"
                  data-testid="complaints-customer-unavailable"
                >
                  <p className="font-medium">
                    {t(
                      'complaints.form.customer_empty_title',
                      'No customers are configured',
                    )}
                  </p>
                  <p className="text-muted-foreground mt-1">
                    {t(
                      'complaints.form.customer_empty_body',
                      'Complaint intake needs at least one customer in Admin → Lookups → Customers. This is a setup gap — not an empty search result.',
                    )}
                  </p>
                  <Link
                    to="/admin/lookups"
                    className="inline-flex mt-2 text-sm font-medium text-primary hover:underline"
                    data-testid="complaints-customer-admin-link"
                  >
                    {t('complaints.form.customer_admin_cta', 'Open Admin → Lookups → Customers')}
                  </Link>
                </div>
              ) : null}
            </div>

            <div className="space-y-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                {t('complaints.form.group_parties', 'Parties')}
              </p>
              <div>
                <label
                  htmlFor="complaints-field-4"
                  className="block text-sm font-medium text-foreground mb-2"
                >
                  {t('complaints.form.complainant_name')} <span className="text-destructive">*</span>
                </label>
                <Input
                  id="complaints-field-4"
                  type="text"
                  required
                  value={formData.complainant_name}
                  onChange={(e) => setFormData({ ...formData, complainant_name: e.target.value })}
                  placeholder={t('complaints.form.name_placeholder')}
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label
                    htmlFor="complaints-field-5"
                    className="block text-sm font-medium text-foreground mb-2"
                  >
                    {t('complaints.form.email')}
                  </label>
                  <Input
                    id="complaints-field-5"
                    type="email"
                    value={formData.complainant_email || ''}
                    onChange={(e) => setFormData({ ...formData, complainant_email: e.target.value })}
                    placeholder={t('complaints.form.email_placeholder')}
                  />
                </div>
                <div>
                  <label
                    htmlFor="complaints-field-6"
                    className="block text-sm font-medium text-foreground mb-2"
                  >
                    {t('complaints.form.phone')}
                  </label>
                  <Input
                    id="complaints-field-6"
                    type="tel"
                    value={formData.complainant_phone || ''}
                    onChange={(e) => setFormData({ ...formData, complainant_phone: e.target.value })}
                    placeholder={t('complaints.form.phone_placeholder')}
                  />
                </div>
              </div>
              <div>
                <label
                  htmlFor="complaints-company"
                  className="block text-sm font-medium text-foreground mb-2"
                >
                  {t('complaints.form.company', 'Complainant company')}
                </label>
                <Input
                  id="complaints-company"
                  type="text"
                  value={formData.complainant_company || ''}
                  onChange={(e) =>
                    setFormData({ ...formData, complainant_company: e.target.value })
                  }
                  placeholder={t('complaints.form.company_placeholder', 'Organisation (optional)')}
                />
              </div>
              <div className="space-y-2">
                <label className="block text-sm font-medium text-foreground">
                  {t('complaints.form.about_staff', 'Who is the complaint about (staff)')}
                </label>
                <EngineerPeoplePicker
                  valueLabel={subjectEmail}
                  requireLogin={false}
                  onChange={(selection) => {
                    setSubjectEmail(selection?.label || '')
                    setFormData({
                      ...formData,
                      subject_user_id: selection?.user?.id ?? null,
                      subject_name:
                        selection?.label ||
                        selection?.user?.full_name ||
                        formData.subject_name ||
                        '',
                    })
                  }}
                  placeholder={t(
                    'complaints.form.about_staff_placeholder',
                    'Search employees (login optional)…',
                  )}
                  testId="complaint-subject-picker"
                />
              </div>
              <div>
                <label
                  htmlFor="complaints-subject-name"
                  className="block text-sm font-medium text-foreground mb-2"
                >
                  {t('complaints.form.about_name', 'About (name if not a staff user)')}
                </label>
                <Input
                  id="complaints-subject-name"
                  type="text"
                  value={formData.subject_name || ''}
                  onChange={(e) => setFormData({ ...formData, subject_name: e.target.value })}
                  placeholder={t(
                    'complaints.form.about_name_placeholder',
                    'Person or team the complaint concerns',
                  )}
                />
              </div>
            </div>

            <div className="space-y-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                {t('complaints.form.group_channel_topic', 'Channel & topic')}
              </p>
              <div>
                <label
                  htmlFor="complaints-channel"
                  className="block text-sm font-medium text-foreground mb-2"
                >
                  {t('complaints.form.channel', 'How did it come in')}{' '}
                  <span className="text-destructive">*</span>
                </label>
                <Select
                  value={formData.source_type || 'manual'}
                  onValueChange={(value) =>
                    setFormData({
                      ...formData,
                      source_type: value as ComplaintCreate['source_type'],
                    })
                  }
                >
                  <SelectTrigger id="complaints-channel">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {CHANNEL_OPTIONS.map((opt) => (
                      <SelectItem key={opt.value} value={opt.value}>
                        {opt.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <FuzzySearchDropdown
                label={t('complaints.form.type')}
                options={topicOptions}
                value={formData.complaint_type}
                onChange={(value) => setFormData({ ...formData, complaint_type: value })}
                placeholder={t('complaints.form.topic_search', 'Search topic / reason…')}
              />
              <div>
                <label
                  htmlFor="complaints-field-3"
                  className="block text-sm font-medium text-foreground mb-2"
                >
                  {t('complaints.form.priority')}
                </label>
                <Select
                  value={formData.priority}
                  onValueChange={(value) => setFormData({ ...formData, priority: value })}
                >
                  <SelectTrigger id="complaints-field-3">
                    <SelectValue placeholder={t('complaints.form.select_priority')} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="critical">{t('priority.critical')}</SelectItem>
                    <SelectItem value="high">{t('priority.high')}</SelectItem>
                    <SelectItem value="medium">{t('priority.medium')}</SelectItem>
                    <SelectItem value="low">{t('priority.low')}</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="space-y-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                {t('complaints.form.group_when', 'When')}
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label
                    htmlFor="complaints-field-7"
                    className="block text-sm font-medium text-foreground mb-2"
                  >
                    {t('complaints.form.received_date')} <span className="text-destructive">*</span>
                  </label>
                  <Input
                    id="complaints-field-7"
                    type="datetime-local"
                    required
                    value={formData.received_date}
                    onChange={(e) => setFormData({ ...formData, received_date: e.target.value })}
                  />
                </div>
                <div>
                  <label
                    htmlFor="complaints-alleged"
                    className="block text-sm font-medium text-foreground mb-2"
                  >
                    {t('complaints.form.alleged_event', 'Alleged event date/time')}
                  </label>
                  <Input
                    id="complaints-alleged"
                    type="datetime-local"
                    value={formData.alleged_event_at || ''}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        alleged_event_at: e.target.value || null,
                      })
                    }
                  />
                </div>
              </div>
            </div>

            <div className="space-y-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                {t('complaints.form.group_narrative', 'What happened')}
              </p>
              <div>
                <label
                  htmlFor="complaints-field-0"
                  className="block text-sm font-medium text-foreground mb-2"
                >
                  {t('complaints.form.title')} <span className="text-destructive">*</span>
                </label>
                <Input
                  id="complaints-field-0"
                  type="text"
                  required
                  value={formData.title}
                  onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                  placeholder={t('complaints.form.title_placeholder')}
                />
              </div>
              <div>
                <label
                  htmlFor="complaints-field-1"
                  className="block text-sm font-medium text-foreground mb-2"
                >
                  {t('complaints.form.description')} <span className="text-destructive">*</span>
                </label>
                <Textarea
                  id="complaints-field-1"
                  required
                  rows={3}
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  placeholder={t('complaints.form.description_placeholder')}
                />
              </div>
            </div>

            <div className="space-y-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                {t('complaints.form.group_attachments', 'Documents')}
              </p>
              <label className="inline-flex">
                <Button type="button" variant="outline" size="sm" asChild>
                  <span>
                    <Paperclip className="w-4 h-4 mr-1.5" />
                    {t('complaints.form.attach', 'Attach files')}
                  </span>
                </Button>
                <input
                  type="file"
                  className="sr-only"
                  multiple
                  data-testid="complaints-attach-input"
                  onChange={(e) => {
                    const files = Array.from(e.target.files || [])
                    if (files.length) setPendingFiles((prev) => [...prev, ...files])
                    e.target.value = ''
                  }}
                />
              </label>
              {pendingFiles.length > 0 ? (
                <ul className="text-xs text-muted-foreground space-y-1" data-testid="complaints-attach-list">
                  {pendingFiles.map((file, idx) => (
                    <li key={`${file.name}-${idx}`} className="flex items-center justify-between gap-2">
                      <span className="truncate">{file.name}</span>
                      <button
                        type="button"
                        className="text-destructive hover:underline shrink-0"
                        onClick={() =>
                          setPendingFiles((prev) => prev.filter((_, i) => i !== idx))
                        }
                      >
                        {t('common.remove', 'Remove')}
                      </button>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-xs text-muted-foreground">
                  {t(
                    'complaints.form.attach_hint',
                    'Optional — uploaded to the shared evidence store after create.',
                  )}
                </p>
              )}
            </div>

            <DialogFooter className="gap-3 pt-4">
              {formError && <p className="text-sm text-destructive">{formError}</p>}
              <Button type="button" variant="outline" onClick={() => requestCloseCreateModal()}>
                {t('cancel')}
              </Button>
              <Button type="submit" disabled={creating || customersUnavailable}>
                {creating ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    {t('complaints.creating')}
                  </>
                ) : (
                  t('complaints.create')
                )}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}
