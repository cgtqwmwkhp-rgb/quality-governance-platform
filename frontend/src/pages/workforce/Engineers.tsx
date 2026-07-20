import { useState, useEffect, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import {
  Search,
  Users,
  MapPin,
  Building2,
  ChevronRight,
  RefreshCw,
  Plus,
  LayoutGrid,
  List,
  Rows3,
} from 'lucide-react'
import { CardSkeleton } from '../../components/ui/SkeletonLoader'
import { useNavigate } from 'react-router-dom'
import {
  workforceApi,
  type EngineerProfile,
} from '../../api/client'
import type { EngineerCreatePayload } from '../../api/workforceClient'
import { getApiErrorMessage } from '../../api/client'
import { Input } from '../../components/ui/Input'
import { Label } from '../../components/ui/Label'
import { Card, CardContent } from '../../components/ui/Card'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/Dialog'
import { UserEmailSearch } from '../../components/UserEmailSearch'
import type { UserSearchResult } from '../../api/client'
import { cn } from '../../helpers/utils'
import { isWorkforceManager } from '../../utils/workforceAccess'

type ActiveFilter = '' | 'true' | 'false'
type ViewMode = 'cards' | 'list' | 'compact'

type EmployeeFormState = {
  display_name: string
  user_id: string
  employee_number: string
  job_title: string
  department: string
  site: string
}

const emptyEmployeeForm = (): EmployeeFormState => ({
  display_name: '',
  user_id: '',
  employee_number: '',
  job_title: '',
  department: '',
  site: '',
})

function engineerLabel(eng: EngineerProfile): string {
  return (
    eng.display_name?.trim() ||
    eng.employee_number?.trim() ||
    eng.job_title?.trim() ||
    `Employee #${eng.id}`
  )
}

function formToCreatePayload(form: EmployeeFormState): EngineerCreatePayload {
  const userRaw = form.user_id.trim()
  const user_id = userRaw === '' ? undefined : Number(userRaw)
  return {
    display_name: form.display_name.trim() || undefined,
    user_id: Number.isFinite(user_id) ? user_id : undefined,
    employee_number: form.employee_number.trim() || undefined,
    job_title: form.job_title.trim() || undefined,
    department: form.department.trim() || undefined,
    site: form.site.trim() || undefined,
  }
}

export default function Engineers() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [engineers, setEngineers] = useState<EngineerProfile[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  // Best-in-class default: active engineers only (roster for assignment / reporting).
  const [activeFilter, setActiveFilter] = useState<ActiveFilter>('true')
  const [viewMode, setViewMode] = useState<ViewMode>('cards')
  const [syncing, setSyncing] = useState(false)
  const [syncMessage, setSyncMessage] = useState<string | null>(null)

  const [createDialogOpen, setCreateDialogOpen] = useState(false)
  const [createForm, setCreateForm] = useState<EmployeeFormState>(emptyEmployeeForm)
  const [createSaving, setCreateSaving] = useState(false)
  const [createFormError, setCreateFormError] = useState<string | null>(null)
  const [createLinkEmail, setCreateLinkEmail] = useState('')
  const [createLinkUser, setCreateLinkUser] = useState<UserSearchResult | undefined>()
  const [selectedEngineerIds, setSelectedEngineerIds] = useState<number[]>([])
  const [bulkLinkOpen, setBulkLinkOpen] = useState(false)
  const [bulkLinkUsers, setBulkLinkUsers] = useState<Record<number, UserSearchResult | undefined>>({})
  const [bulkLinkEmails, setBulkLinkEmails] = useState<Record<number, string>>({})
  const [bulkLinkSaving, setBulkLinkSaving] = useState(false)
  const [bulkLinkError, setBulkLinkError] = useState<string | null>(null)

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(searchTerm), 300)
    return () => clearTimeout(timer)
  }, [searchTerm])

  const loadEngineers = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const params: Record<string, string> = { page: '1', page_size: '50' }
      if (debouncedSearch) params.search = debouncedSearch
      if (activeFilter) params.is_active = activeFilter
      const res = await workforceApi.listEngineers(params)
      setEngineers(res.data.items || [])
    } catch (err) {
      setEngineers([])
      setError(getApiErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }, [debouncedSearch, activeFilter])

  useEffect(() => {
    void loadEngineers()
  }, [loadEngineers])

  const handleSyncFromPams = async () => {
    setSyncing(true)
    setSyncMessage(null)
    setError(null)
    try {
      const res = await workforceApi.syncFromPams()
      setSyncMessage(
        t('workforce.engineers.sync_from_pams_success', {
          created: res.data.created,
          updated: res.data.updated,
          deactivated: res.data.deactivated,
        }),
      )
      await loadEngineers()
    } catch (err) {
      setError(getApiErrorMessage(err) || t('workforce.engineers.sync_from_pams_error'))
    } finally {
      setSyncing(false)
    }
  }

  const openCreateDialog = () => {
    setCreateForm(emptyEmployeeForm())
    setCreateFormError(null)
    setCreateLinkEmail('')
    setCreateLinkUser(undefined)
    setCreateDialogOpen(true)
  }

  const closeCreateDialog = () => {
    if (createSaving) return
    setCreateDialogOpen(false)
    setCreateFormError(null)
    setCreateLinkEmail('')
    setCreateLinkUser(undefined)
  }

  const handleCreateEmployee = async () => {
    const payload = formToCreatePayload({
      ...createForm,
      user_id: createLinkUser?.id != null ? String(createLinkUser.id) : createForm.user_id,
      display_name:
        createForm.display_name.trim() ||
        createLinkUser?.full_name ||
        createLinkUser?.email ||
        '',
    })
    if (!payload.display_name && payload.user_id == null) {
      setCreateFormError(t('workforce.engineers.form_required'))
      return
    }

    setCreateSaving(true)
    setCreateFormError(null)
    setError(null)
    try {
      const res = await workforceApi.createEngineer(payload)
      setCreateDialogOpen(false)
      setSyncMessage(t('workforce.engineers.create_success'))
      await loadEngineers()
      navigate(`/workforce/engineers/${res.data.id}`)
    } catch (err) {
      setCreateFormError(getApiErrorMessage(err))
    } finally {
      setCreateSaving(false)
    }
  }

  const canManageRoster = isWorkforceManager()
  const selectedUnlinkedEngineers = engineers.filter(
    (engineer) => selectedEngineerIds.includes(engineer.id) && engineer.user_id == null,
  )

  const toggleEngineerSelection = (engineerId: number) => {
    setSelectedEngineerIds((selected) =>
      selected.includes(engineerId)
        ? selected.filter((id) => id !== engineerId)
        : [...selected, engineerId],
    )
  }

  const openBulkLinkDialog = () => {
    setBulkLinkError(null)
    setBulkLinkUsers({})
    setBulkLinkEmails({})
    setBulkLinkOpen(true)
  }

  const closeBulkLinkDialog = () => {
    if (bulkLinkSaving) return
    setBulkLinkOpen(false)
    setBulkLinkError(null)
  }

  const handleBulkLink = async () => {
    if (selectedUnlinkedEngineers.some((engineer) => !bulkLinkUsers[engineer.id])) {
      setBulkLinkError('Choose a QGP user for every selected employee.')
      return
    }
    setBulkLinkSaving(true)
    setBulkLinkError(null)
    try {
      // Keep the existing server-side dual gate authoritative. Each link is
      // deliberately sent through the dedicated endpoint, never PATCH user_id.
      for (const engineer of selectedUnlinkedEngineers) {
        await workforceApi.linkEngineerUser(engineer.id, bulkLinkUsers[engineer.id]!.id)
      }
      setSelectedEngineerIds([])
      setBulkLinkOpen(false)
      setSyncMessage(`Linked ${selectedUnlinkedEngineers.length} employee login(s).`)
      await loadEngineers()
    } catch (err) {
      setBulkLinkError(getApiErrorMessage(err))
    } finally {
      setBulkLinkSaving(false)
    }
  }

  const rosterEmpty =
    !loading && engineers.length === 0 && !debouncedSearch && activeFilter === 'true'

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">{t('workforce.engineers.title')}</h1>
          <p className="text-muted-foreground mt-1">{t('workforce.engineers.subtitle')}</p>
        </div>
        <div className="flex flex-wrap gap-2 shrink-0">
          {canManageRoster ? (
            <>
              {selectedUnlinkedEngineers.length > 0 && (
                <Button type="button" variant="outline" onClick={openBulkLinkDialog} disabled={loading}>
                  Link selected ({selectedUnlinkedEngineers.length})
                </Button>
              )}
              <Button type="button" onClick={openCreateDialog} disabled={loading}>
                <Plus className="w-4 h-4 mr-2" />
                {t('workforce.engineers.add')}
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={() => void handleSyncFromPams()}
                disabled={syncing || loading}
              >
                <RefreshCw className={cn('w-4 h-4 mr-2', syncing && 'animate-spin')} />
                {syncing ? t('workforce.engineers.syncing') : t('workforce.engineers.sync_from_pams')}
              </Button>
            </>
          ) : (
            <Button type="button" disabled title={t('workforce.engineers.manager_gate_honesty')}>
              <Plus className="w-4 h-4 mr-2" />
              {t('workforce.engineers.add')}
            </Button>
          )}
        </div>
      </div>

      {!canManageRoster && (
        <div
          className="rounded-lg border border-warning/40 bg-warning/10 p-4 text-sm text-foreground"
          data-testid="engineers-manager-gate-honesty"
        >
          {t('workforce.engineers.manager_gate_honesty')}
        </div>
      )}

      <Card>
        <CardContent className="pt-6">
          {error && (
            <div className="mb-4 p-3 rounded-lg bg-destructive/10 text-destructive text-sm">
              {error}
            </div>
          )}
          {syncMessage && (
            <div className="mb-4 p-3 rounded-lg bg-primary/10 text-primary text-sm">
              {syncMessage}
            </div>
          )}
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center">
            <div className="relative flex-1 max-w-md">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                placeholder={t('workforce.engineers.search_placeholder')}
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-9"
              />
            </div>
            <select
              value={activeFilter}
              onChange={(e) => setActiveFilter(e.target.value as ActiveFilter)}
              className="h-9 rounded-md border border-border bg-card px-3 text-sm text-foreground"
              aria-label={t('workforce.engineers.filter_status')}
            >
              <option value="">{t('workforce.engineers.filter_all')}</option>
              <option value="true">{t('common.active')}</option>
              <option value="false">{t('common.inactive')}</option>
            </select>
            <div
              className="inline-flex rounded-md border border-border p-0.5"
              role="group"
              aria-label={t('workforce.engineers.view_mode', 'View mode')}
            >
              {(
                [
                  { id: 'cards' as const, icon: LayoutGrid, label: 'Cards' },
                  { id: 'list' as const, icon: List, label: 'List' },
                  { id: 'compact' as const, icon: Rows3, label: 'Compact' },
                ] as const
              ).map(({ id, icon: Icon, label }) => (
                <button
                  key={id}
                  type="button"
                  className={cn(
                    'inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs rounded-sm',
                    viewMode === id
                      ? 'bg-primary text-primary-foreground'
                      : 'text-muted-foreground hover:text-foreground',
                  )}
                  aria-pressed={viewMode === id}
                  onClick={() => setViewMode(id)}
                  data-testid={`employees-view-${id}`}
                >
                  <Icon className="w-3.5 h-3.5" />
                  {label}
                </button>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>

      {loading ? (
        <CardSkeleton count={6} />
      ) : engineers.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground space-y-4">
            <p>{rosterEmpty ? t('workforce.engineers.empty') : t('common.no_results')}</p>
            {rosterEmpty && canManageRoster && (
              <Button
                type="button"
                variant="outline"
                onClick={() => void handleSyncFromPams()}
                disabled={syncing}
              >
                <RefreshCw className={cn('w-4 h-4 mr-2', syncing && 'animate-spin')} />
                {syncing ? t('workforce.engineers.syncing') : t('workforce.engineers.sync_from_pams')}
              </Button>
            )}
          </CardContent>
        </Card>
      ) : viewMode === 'cards' ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3" data-testid="employees-view-cards-grid">
          {engineers.map((eng) => (
            <Card
              key={eng.id}
              hoverable
              className={cn('cursor-pointer transition-all', 'hover:shadow-md hover:border-border-strong')}
              onClick={() => navigate(`/workforce/engineers/${eng.id}`)}
            >
              <CardContent className="p-6">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      {canManageRoster && eng.user_id == null && (
                        <input
                          type="checkbox"
                          aria-label={`Select ${engineerLabel(eng)} for user linking`}
                          checked={selectedEngineerIds.includes(eng.id)}
                          onClick={(event) => event.stopPropagation()}
                          onChange={() => toggleEngineerSelection(eng.id)}
                        />
                      )}
                      <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center">
                        <Users className="w-5 h-5 text-primary" />
                      </div>
                      <div>
                        <h3 className="font-semibold text-foreground truncate">{engineerLabel(eng)}</h3>
                        <p className="text-sm text-muted-foreground truncate">
                          {eng.job_title ?? eng.department ?? eng.site ?? '—'}
                        </p>
                      </div>
                    </div>
                    <div className="mt-4 space-y-1.5 text-sm">
                      {eng.department && (
                        <div className="flex items-center gap-2 text-muted-foreground">
                          <Building2 className="w-3.5 h-3.5 shrink-0" />
                          <span className="truncate">{eng.department}</span>
                        </div>
                      )}
                      {eng.site && (
                        <div className="flex items-center gap-2 text-muted-foreground">
                          <MapPin className="w-3.5 h-3.5 shrink-0" />
                          <span className="truncate">{eng.site}</span>
                        </div>
                      )}
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2">
                      <Badge variant={eng.is_active ? 'success' : 'secondary'}>
                        {eng.is_active ? t('common.active') : t('common.inactive')}
                      </Badge>
                      {eng.user_id != null ? (
                        <Badge variant="outline" data-testid={`engineer-user-linked-${eng.id}`}>
                          {t('workforce.engineers.user_link.roster_linked', { id: eng.user_id })}
                        </Badge>
                      ) : (
                        <Badge variant="secondary" data-testid={`engineer-user-unlinked-${eng.id}`}>
                          {t('workforce.engineers.user_link.roster_unlinked')}
                        </Badge>
                      )}
                    </div>
                  </div>
                  <ChevronRight className="w-5 h-5 text-muted-foreground shrink-0" />
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : viewMode === 'list' ? (
        <Card data-testid="employees-view-list">
          <CardContent className="p-0 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-muted-foreground">
                  <th className="px-4 py-3 font-medium">Name</th>
                  <th className="px-4 py-3 font-medium">Role</th>
                  <th className="px-4 py-3 font-medium">Site</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                  <th className="px-4 py-3 font-medium">Login</th>
                  <th className="px-4 py-3 font-medium w-10" />
                </tr>
              </thead>
              <tbody>
                {engineers.map((eng) => (
                  <tr
                    key={eng.id}
                    className="border-b border-border last:border-0 hover:bg-muted/40 cursor-pointer"
                    onClick={() => navigate(`/workforce/engineers/${eng.id}`)}
                  >
                    <td className="px-4 py-3 font-medium text-foreground">{engineerLabel(eng)}</td>
                    <td className="px-4 py-3 text-muted-foreground">{eng.job_title || '—'}</td>
                    <td className="px-4 py-3 text-muted-foreground">{eng.site || '—'}</td>
                    <td className="px-4 py-3">
                      <Badge variant={eng.is_active ? 'success' : 'secondary'}>
                        {eng.is_active ? t('common.active') : t('common.inactive')}
                      </Badge>
                    </td>
                    <td className="px-4 py-3">
                      {eng.user_id != null ? (
                        <Badge variant="outline">
                          {t('workforce.engineers.user_link.roster_linked', { id: eng.user_id })}
                        </Badge>
                      ) : (
                        <Badge variant="secondary">
                          {t('workforce.engineers.user_link.roster_unlinked')}
                        </Badge>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <ChevronRight className="w-4 h-4 text-muted-foreground" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      ) : (
        <div
          className="rounded-lg border border-border divide-y divide-border bg-card"
          data-testid="employees-view-compact"
        >
          {engineers.map((eng) => (
            <button
              key={eng.id}
              type="button"
              className="w-full flex items-center gap-3 px-3 py-2 text-left hover:bg-muted/40"
              onClick={() => navigate(`/workforce/engineers/${eng.id}`)}
            >
              <Users className="w-4 h-4 text-primary shrink-0" />
              <span className="flex-1 min-w-0 truncate text-sm font-medium text-foreground">
                {engineerLabel(eng)}
              </span>
              <span className="hidden sm:inline text-xs text-muted-foreground truncate max-w-[10rem]">
                {eng.job_title || eng.site || '—'}
              </span>
              <Badge variant={eng.is_active ? 'success' : 'secondary'} className="shrink-0">
                {eng.is_active ? t('common.active') : t('common.inactive')}
              </Badge>
              {eng.user_id == null ? (
                <Badge variant="secondary" className="shrink-0 hidden md:inline-flex">
                  {t('workforce.engineers.user_link.roster_unlinked')}
                </Badge>
              ) : null}
              <ChevronRight className="w-4 h-4 text-muted-foreground shrink-0" />
            </button>
          ))}
        </div>
      )}

      <Dialog
        open={createDialogOpen}
        onOpenChange={(open) => {
          if (!open) closeCreateDialog()
          else setCreateDialogOpen(true)
        }}
      >
        <DialogContent className="sm:max-w-lg" data-testid="employee-create-dialog">
          <DialogHeader>
            <DialogTitle>{t('workforce.engineers.create_title')}</DialogTitle>
            <DialogDescription>{t('workforce.engineers.create_description')}</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            {createFormError && (
              <div className="p-3 rounded-lg bg-destructive/10 text-destructive text-sm">
                {createFormError}
              </div>
            )}
            <div className="space-y-2">
              <Label htmlFor="employee-display-name">{t('workforce.engineers.display_name')}</Label>
              <Input
                id="employee-display-name"
                value={createForm.display_name}
                onChange={(e) =>
                  setCreateForm((prev) => ({ ...prev, display_name: e.target.value }))
                }
                placeholder={t('workforce.engineers.display_name_placeholder')}
              />
            </div>
            <div className="space-y-2">
              <Label>{t('workforce.engineers.user_link.label', 'QGP user link')}</Label>
              <UserEmailSearch
                value={createLinkEmail}
                onChange={(email, user) => {
                  setCreateLinkEmail(email)
                  setCreateLinkUser(user)
                  if (user && !createForm.display_name.trim()) {
                    setCreateForm((prev) => ({
                      ...prev,
                      display_name: user.full_name || user.email,
                    }))
                  }
                }}
                placeholder={t(
                  'workforce.engineers.user_link.search_placeholder',
                  'Optional — search QGP user to link…',
                )}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="employee-number">{t('workforce.engineers.employee_no')}</Label>
              <Input
                id="employee-number"
                value={createForm.employee_number}
                onChange={(e) =>
                  setCreateForm((prev) => ({ ...prev, employee_number: e.target.value }))
                }
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="employee-job-title">{t('workforce.engineers.job_title')}</Label>
              <Input
                id="employee-job-title"
                value={createForm.job_title}
                onChange={(e) =>
                  setCreateForm((prev) => ({ ...prev, job_title: e.target.value }))
                }
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="employee-department">{t('workforce.common.department')}</Label>
              <Input
                id="employee-department"
                value={createForm.department}
                onChange={(e) =>
                  setCreateForm((prev) => ({ ...prev, department: e.target.value }))
                }
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="employee-site">{t('workforce.engineers.site')}</Label>
              <Input
                id="employee-site"
                value={createForm.site}
                onChange={(e) => setCreateForm((prev) => ({ ...prev, site: e.target.value }))}
              />
            </div>
          </div>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button type="button" variant="secondary" onClick={closeCreateDialog} disabled={createSaving}>
              {t('common.cancel')}
            </Button>
            <Button type="button" onClick={() => void handleCreateEmployee()} disabled={createSaving}>
              {createSaving ? t('workforce.common.creating') : t('workforce.engineers.add')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={bulkLinkOpen}
        onOpenChange={(open) => {
          if (!open) closeBulkLinkDialog()
          else setBulkLinkOpen(true)
        }}
      >
        <DialogContent className="sm:max-w-lg" data-testid="employee-bulk-link-dialog">
          <DialogHeader>
            <DialogTitle>Link selected employees to QGP users</DialogTitle>
            <DialogDescription>
              Each employee needs a distinct active QGP user. Existing employee data is unchanged.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            {bulkLinkError && (
              <div className="p-3 rounded-lg bg-destructive/10 text-destructive text-sm">{bulkLinkError}</div>
            )}
            {selectedUnlinkedEngineers.map((engineer) => (
              <div key={engineer.id} className="space-y-2">
                <Label>{engineerLabel(engineer)}</Label>
                <UserEmailSearch
                  value={bulkLinkEmails[engineer.id] ?? ''}
                  onChange={(email, selectedUser) => {
                    setBulkLinkEmails((current) => ({ ...current, [engineer.id]: email }))
                    setBulkLinkUsers((current) => ({ ...current, [engineer.id]: selectedUser }))
                  }}
                  placeholder="Search active QGP user…"
                />
              </div>
            ))}
          </div>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button type="button" variant="secondary" onClick={closeBulkLinkDialog} disabled={bulkLinkSaving}>
              {t('common.cancel')}
            </Button>
            <Button type="button" onClick={() => void handleBulkLink()} disabled={bulkLinkSaving}>
              {bulkLinkSaving ? 'Linking…' : `Link ${selectedUnlinkedEngineers.length} employee(s)`}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
