import { useCallback, useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { ClipboardList, Loader2, Plus, Settings2, Trash2 } from 'lucide-react'
import { getApiErrorMessage, lookupsApi, type LookupOption } from '../../api/client'
import {
  safetyAssetsApi,
  type SafetyLookupPendingItem,
} from '../../api/safetyAssetsClient'
import { Card, CardContent, CardHeader } from '../../components/ui/Card'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/Dialog'
import { toast } from '../../contexts/ToastContext'
import { cn } from '../../helpers/utils'
import {
  CUSTOMERS_LOOKUP_CATEGORY,
  CUSTOMER_CODE_HINTS,
  customerHintCodes,
} from './customersCatalog'
import {
  WORKFORCE_ROLES_LOOKUP_CATEGORY,
  WORKFORCE_ROLE_CODE_HINTS,
  workforceRoleHintCodes,
} from './workforceRolesCatalog'

const LOOKUP_CATEGORIES = [
  { key: 'incident_types', label: 'Incident Types' },
  { key: 'complaint_types', label: 'Complaint Types' },
  { key: 'severity_levels', label: 'Severity Levels' },
  { key: CUSTOMERS_LOOKUP_CATEGORY, label: 'Customers' },
  { key: WORKFORCE_ROLES_LOOKUP_CATEGORY, label: 'Workforce Roles' },
  { key: 'medical_assistance', label: 'Medical Assistance' },
  { key: 'assets', label: 'Assets', kind: 'asset_types' },
] as const

type CategoryKey = (typeof LOOKUP_CATEGORIES)[number]['key']

type CategoryState = {
  total: number | null
  loading: boolean
  error: boolean
}

/** Stable machine key from a human name (max 50 chars to match API). */
export function generateLookupCode(name: string): string {
  const slug = name
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .slice(0, 50)
  return slug || 'option'
}

function uniqueLookupCode(base: string, existing: LookupOption[]): string {
  const taken = new Set(existing.map((o) => o.code.toLowerCase()))
  if (!taken.has(base.toLowerCase())) return base
  for (let i = 2; i < 100; i++) {
    const suffix = `_${i}`
    const candidate = `${base.slice(0, Math.max(1, 50 - suffix.length))}${suffix}`
    if (!taken.has(candidate.toLowerCase())) return candidate
  }
  return `${base.slice(0, 43)}_${Date.now().toString(36)}`.slice(0, 50)
}

export default function LookupTables() {
  const { t } = useTranslation()
  const [searchParams] = useSearchParams()
  const [counts, setCounts] = useState<Record<string, CategoryState>>(() =>
    Object.fromEntries(
      LOOKUP_CATEGORIES.map((c) => [c.key, { total: null, loading: true, error: false }]),
    ),
  )
  const [hubFilter, setHubFilter] = useState<string>(() => {
    const category = searchParams.get('category')
    return LOOKUP_CATEGORIES.some((item) => item.key === category) ? category! : 'all'
  })
  const [editorCategory, setEditorCategory] = useState<(typeof LOOKUP_CATEGORIES)[number] | null>(
    null,
  )
  const [options, setOptions] = useState<LookupOption[]>([])
  const [editorLoading, setEditorLoading] = useState(false)
  const [editorError, setEditorError] = useState<string | null>(null)
  const [newLabel, setNewLabel] = useState('')
  const [newCode, setNewCode] = useState('')
  const [codeManual, setCodeManual] = useState(false)
  const [showAdvancedCode, setShowAdvancedCode] = useState(false)
  const [saving, setSaving] = useState(false)
  const [pendingSafety, setPendingSafety] = useState<SafetyLookupPendingItem[]>([])
  const [pendingLoading, setPendingLoading] = useState(true)
  const [pendingBusyId, setPendingBusyId] = useState<string | null>(null)
  const [safetyCreateKind, setSafetyCreateKind] = useState<'asset_type' | 'location' | null>(null)
  const [safetyCreateName, setSafetyCreateName] = useState('')
  const [safetyCreatePreview, setSafetyCreatePreview] = useState<{
    intent: string
    similar_matches: { id: number; name: string; score: number }[]
    blocked_exact_duplicate: boolean
  } | null>(null)
  const [safetyCreateBusy, setSafetyCreateBusy] = useState(false)
  const highlightPending = searchParams.get('pending') === 'safety'

  const visibleCategories =
    hubFilter === 'all'
      ? LOOKUP_CATEGORIES
      : LOOKUP_CATEGORIES.filter((c) => c.key === hubFilter)

  const refreshCounts = useCallback(async () => {
    await Promise.all(
      LOOKUP_CATEGORIES.map(async (cat) => {
        try {
          if (cat.key === 'assets') {
            const assetTotal = (
              await safetyAssetsApi.listAssetTypes({ page: 1, page_size: 1 })
            ).data.total
            setCounts((prev) => ({
              ...prev,
              [cat.key]: { total: assetTotal, loading: false, error: false },
            }))
            return
          }
          const lookupData = await lookupsApi.list(cat.key, false)
          setCounts((prev) => ({
            ...prev,
            [cat.key]: {
              total: lookupData?.total ?? lookupData?.items?.length ?? 0,
              loading: false,
              error: false,
            },
          }))
        } catch {
          setCounts((prev) => ({
            ...prev,
            [cat.key]: { total: null, loading: false, error: true },
          }))
        }
      }),
    )
  }, [])

  useEffect(() => {
    void refreshCounts()
  }, [refreshCounts])

  const refreshPendingSafety = useCallback(async () => {
    setPendingLoading(true)
    try {
      const res = await safetyAssetsApi.listPendingSafetyLookups()
      setPendingSafety(res.data.items ?? [])
    } catch (err) {
      setPendingSafety([])
      toast.error(getApiErrorMessage(err, 'Could not load pending Safety lookups'))
    } finally {
      setPendingLoading(false)
    }
  }, [])

  useEffect(() => {
    void refreshPendingSafety()
  }, [refreshPendingSafety])

  const resetCreateForm = () => {
    setNewLabel('')
    setNewCode('')
    setCodeManual(false)
    setShowAdvancedCode(false)
  }

  const openEditor = async (cat: (typeof LOOKUP_CATEGORIES)[number]) => {
    setEditorCategory(cat)
    setEditorLoading(true)
    setEditorError(null)
    setOptions([])
    resetCreateForm()
    try {
      const assetData =
        cat.key === 'assets' ? await safetyAssetsApi.listAllAssetTypes() : null
      const lookupData = cat.key === 'assets' ? null : await lookupsApi.list(cat.key, false)
      const items = assetData
        ? assetData.items.map((assetType) => ({
            id: assetType.id,
            category: 'assets',
            code: assetType.name,
            label: assetType.name,
            description: assetType.description ?? undefined,
            is_active: assetType.is_active,
            display_order: assetType.id,
          }))
        : (lookupData?.items ?? [])
      setOptions(items)
      setCounts((prev) => ({
        ...prev,
        [cat.key]: {
          total: assetData?.total ?? lookupData?.total ?? items.length,
          loading: false,
          error: false,
        },
      }))
    } catch {
      setEditorError(
        t(
          'admin.lookups.load_failed',
          'Could not load lookup options. Counts are not shown as zero.',
        ),
      )
    } finally {
      setEditorLoading(false)
    }
  }

  const handleNameChange = (name: string) => {
    setNewLabel(name)
    if (!codeManual) {
      setNewCode(generateLookupCode(name))
    }
  }

  const resolvedCode = codeManual
    ? newCode.trim()
    : uniqueLookupCode(generateLookupCode(newLabel), options)

  const handleCreate = async () => {
    if (!editorCategory || !newLabel.trim() || !resolvedCode) return
    setSaving(true)
    try {
      const createdOption =
        editorCategory.key === 'assets'
          ? (() => undefined)()
          : await lookupsApi.create(editorCategory.key, {
              category: editorCategory.key,
              code: resolvedCode,
              label: newLabel.trim(),
              is_active: true,
              display_order: options.length,
            })
      const assetCreated =
        editorCategory.key === 'assets'
          ? await safetyAssetsApi.createAssetType({
              category: 'safety',
              name: newLabel.trim(),
              force: false,
            })
          : null
      const option =
        assetCreated
          ? {
              id: assetCreated.data.id,
              category: 'assets',
              code: assetCreated.data.name,
              label: assetCreated.data.name,
              description: assetCreated.data.description ?? undefined,
              is_active: assetCreated.data.is_active,
              display_order: assetCreated.data.id,
            }
          : createdOption!
      setOptions((prev) => [...prev, option])
      resetCreateForm()
      setCounts((prev) => ({
        ...prev,
        [editorCategory.key]: {
          total: (prev[editorCategory.key]?.total ?? options.length) + 1,
          loading: false,
          error: false,
        },
      }))
      toast.success(t('admin.lookups.option_added', 'Lookup option added'))
    } catch (err) {
      toast.error(
        getApiErrorMessage(err, t('admin.lookups.save_failed', 'Failed to add lookup option')),
      )
    } finally {
      setSaving(false)
    }
  }

  const handleRemove = async (option: LookupOption) => {
    if (!editorCategory) return
    if (editorCategory.key === 'assets') return
    const confirmed = window.confirm(
      t('admin.lookups.remove_confirm', 'Remove “{{label}}” from this lookup?', {
        label: option.label,
      }),
    )
    if (!confirmed) return
    setSaving(true)
    try {
      await lookupsApi.delete(editorCategory.key, option.id)
      setOptions((prev) => prev.filter((o) => o.id !== option.id))
      setCounts((prev) => ({
        ...prev,
        [editorCategory.key]: {
          total: Math.max(0, (prev[editorCategory.key]?.total ?? options.length) - 1),
          loading: false,
          error: false,
        },
      }))
      toast.success(t('admin.lookups.option_removed', 'Lookup option removed'))
    } catch (err) {
      toast.error(
        getApiErrorMessage(err, t('admin.lookups.remove_failed', 'Failed to remove lookup option')),
      )
    } finally {
      setSaving(false)
    }
  }

  const handleApprovePending = async (item: SafetyLookupPendingItem) => {
    const key = `${item.kind}:${item.id}`
    setPendingBusyId(key)
    try {
      await safetyAssetsApi.approveSafetyLookup(item.kind, item.id)
      toast.success(`Approved “${item.name}”`)
      await refreshPendingSafety()
    } catch (err) {
      toast.error(getApiErrorMessage(err, 'Could not approve lookup'))
    } finally {
      setPendingBusyId(null)
    }
  }

  const handleMergePending = async (item: SafetyLookupPendingItem, targetId: number) => {
    const key = `${item.kind}:${item.id}`
    setPendingBusyId(key)
    try {
      await safetyAssetsApi.mergeSafetyLookup(item.kind, item.id, targetId)
      toast.success(`Merged “${item.name}” into existing lookup`)
      await refreshPendingSafety()
    } catch (err) {
      toast.error(getApiErrorMessage(err, 'Could not merge lookup'))
    } finally {
      setPendingBusyId(null)
    }
  }

  const runSafetyCreatePreview = async (name: string) => {
    setSafetyCreateName(name)
    if (!safetyCreateKind || name.trim().length < 2) {
      setSafetyCreatePreview(null)
      return
    }
    try {
      const res = await safetyAssetsApi.previewSafetyLookup(safetyCreateKind, name.trim())
      setSafetyCreatePreview({
        intent: res.data.intent,
        similar_matches: res.data.similar_matches || [],
        blocked_exact_duplicate: res.data.blocked_exact_duplicate,
      })
    } catch {
      setSafetyCreatePreview(null)
    }
  }

  const handleSafetyCreate = async (force: boolean) => {
    if (!safetyCreateKind || !safetyCreateName.trim()) return
    setSafetyCreateBusy(true)
    try {
      if (safetyCreateKind === 'asset_type') {
        await safetyAssetsApi.createAssetType({
          category: 'safety',
          name: safetyCreateName.trim(),
          force,
        })
      } else {
        await safetyAssetsApi.createLocation({
          name: safetyCreateName.trim(),
          kind: 'site',
          force,
        })
      }
      toast.success('Safety lookup created')
      setSafetyCreateKind(null)
      setSafetyCreateName('')
      setSafetyCreatePreview(null)
      await refreshPendingSafety()
    } catch (err) {
      toast.error(getApiErrorMessage(err, 'Could not create safety lookup'))
    } finally {
      setSafetyCreateBusy(false)
    }
  }

  return (
    <div className="space-y-6" data-testid="admin-lookup-tables">
      <div>
        <h1 className="text-2xl font-bold">{t('admin.lookups.title', 'Lookup Tables')}</h1>
        <p className="text-muted-foreground mt-1">
          {t('admin.lookups.subtitle', 'Manage dropdown options and reference data')}
        </p>
      </div>

      <Card
        className={cn(highlightPending && 'ring-2 ring-primary')}
        data-testid="safety-lookup-pending-panel"
      >
        <CardHeader className="pb-2">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h2 className="text-lg font-semibold">Safety Asset Types &amp; Site Locations</h2>
              <p className="text-sm text-muted-foreground">
                CES import provisional lookups awaiting approval. Exact duplicates are blocked;
                near-matches must be confirmed.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={() => {
                  setSafetyCreateKind('asset_type')
                  setSafetyCreateName('')
                  setSafetyCreatePreview(null)
                }}
              >
                Add asset type
              </Button>
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={() => {
                  setSafetyCreateKind('location')
                  setSafetyCreateName('')
                  setSafetyCreatePreview(null)
                }}
              >
                Add location
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          {pendingLoading ? (
            <p className="text-sm text-muted-foreground">Loading pending approvals…</p>
          ) : pendingSafety.length === 0 ? (
            <p className="text-sm text-muted-foreground" data-testid="safety-lookup-pending-empty">
              No pending Safety lookups.
            </p>
          ) : (
            <div className="space-y-2">
              <p className="text-sm font-medium">
                Pending approval ({pendingSafety.length})
              </p>
              {pendingSafety.map((item) => {
                const busyKey = `${item.kind}:${item.id}`
                const top = item.similar_matches[0]
                return (
                  <div
                    key={busyKey}
                    className="flex flex-col gap-2 rounded-md border border-border p-3 sm:flex-row sm:items-center sm:justify-between"
                    data-testid={`safety-pending-${item.kind}-${item.id}`}
                  >
                    <div className="text-sm">
                      <p className="font-medium">
                        {item.kind === 'asset_type' ? 'Asset type' : 'Location'}: {item.name}
                      </p>
                      <p className="text-muted-foreground">
                        Source: {item.source || 'manual'}
                        {top
                          ? ` · similar to “${top.name}” (${Math.round(top.score * 100)}%)`
                          : ''}
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Button
                        type="button"
                        size="sm"
                        disabled={pendingBusyId === busyKey}
                        data-testid={`safety-pending-approve-${item.kind}-${item.id}`}
                        onClick={() => void handleApprovePending(item)}
                      >
                        Approve
                      </Button>
                      {top ? (
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          disabled={pendingBusyId === busyKey}
                          data-testid={`safety-pending-merge-${item.kind}-${item.id}`}
                          onClick={() => void handleMergePending(item, top.id)}
                        >
                          Use “{top.name}”
                        </Button>
                      ) : null}
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog
        open={safetyCreateKind !== null}
        onOpenChange={(open) => {
          if (!open) {
            setSafetyCreateKind(null)
            setSafetyCreatePreview(null)
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              Add Safety {safetyCreateKind === 'location' ? 'location' : 'asset type'}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <Input
              value={safetyCreateName}
              onChange={(e) => void runSafetyCreatePreview(e.target.value)}
              placeholder="Name"
              aria-label="Safety lookup name"
            />
            {safetyCreatePreview?.blocked_exact_duplicate ? (
              <p className="text-sm text-destructive">
                An exact match already exists — create is blocked to prevent duplicates.
              </p>
            ) : null}
            {safetyCreatePreview?.intent === 'similar' ? (
              <div className="rounded-md border border-border p-2 text-sm">
                <p className="font-medium">Are you sure? Similar entries already exist:</p>
                <ul className="mt-1 list-disc pl-5 text-muted-foreground">
                  {safetyCreatePreview.similar_matches.map((m) => (
                    <li key={m.id}>
                      {m.name} ({Math.round(m.score * 100)}%)
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setSafetyCreateKind(null)}
              disabled={safetyCreateBusy}
            >
              Cancel
            </Button>
            <Button
              type="button"
              disabled={
                safetyCreateBusy ||
                !safetyCreateName.trim() ||
                Boolean(safetyCreatePreview?.blocked_exact_duplicate)
              }
              onClick={() =>
                void handleSafetyCreate(safetyCreatePreview?.intent === 'similar')
              }
            >
              {safetyCreatePreview?.intent === 'similar' ? 'Create anyway' : 'Create'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center">
        <label htmlFor="lookup-hub-filter" className="text-sm font-medium text-muted-foreground">
          {t('admin.lookups.category_filter', 'Category')}
        </label>
        <select
          id="lookup-hub-filter"
          value={hubFilter}
          onChange={(e) => setHubFilter(e.target.value)}
          aria-label={t('admin.lookups.category_filter', 'Category')}
          data-testid="lookup-hub-category-filter"
          className="w-full sm:w-64 rounded-lg border border-border bg-card px-3 py-2 text-sm text-foreground"
        >
          <option value="all">{t('admin.lookups.all_categories', 'All categories')}</option>
          {LOOKUP_CATEGORIES.map((cat) => (
            <option key={cat.key} value={cat.key}>
              {cat.label}
            </option>
          ))}
        </select>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {visibleCategories.map((cat) => {
          const state = counts[cat.key]
          const notConfigured = !state?.error && !state?.loading && state?.total === 0
          const countLabel = state?.loading
            ? t('admin.lookups.loading', 'Loading…')
            : state?.error
              ? t('admin.lookups.unavailable', 'Count unavailable')
              : notConfigured
                ? t('admin.lookups.not_configured', 'Not configured')
                : t('admin.lookups.item_count', '{{count}} items', { count: state?.total ?? 0 })

          return (
            <Card
              key={cat.key}
              className={cn(
                'hover:shadow-md transition-shadow',
                notConfigured && 'border-amber-300/80',
              )}
              data-testid={`lookup-card-${cat.key}`}
            >
              <CardHeader className="flex flex-row items-center gap-3 pb-2">
                <div className="w-10 h-10 rounded-lg bg-orange-100 flex items-center justify-center">
                  <ClipboardList className="w-5 h-5 text-orange-600" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="font-medium">{cat.label}</p>
                  <p
                    className={cn(
                      'text-sm',
                      notConfigured ? 'text-amber-700 font-medium' : 'text-muted-foreground',
                    )}
                    data-testid={`lookup-count-${cat.key}`}
                  >
                    {countLabel}
                  </p>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                <p className="text-sm text-muted-foreground">
                  {cat.key === WORKFORCE_ROLES_LOOKUP_CATEGORY
                    ? t(
                        'admin.lookups.workforce_roles_desc',
                        'Configure role codes for employees (job_title / competency role matching). Nothing is pre-seeded.',
                      )
                    : cat.key === CUSTOMERS_LOOKUP_CATEGORY
                      ? t(
                          'admin.lookups.customers_desc',
                          'Configure customer names for forms and dropdowns across the platform. Nothing is pre-seeded.',
                        )
                      : cat.key === 'assets'
                        ? t(
                            'admin.lookups.assets_desc',
                            'Asset types used by the Safety Asset Register (tools, extinguishers, gauges, etc.)',
                          )
                        : t(
                            `admin.lookups.${cat.key}_desc`,
                            `Configure ${cat.label.toLowerCase()} for your organisation`,
                          )}
                </p>
                {cat.key === WORKFORCE_ROLES_LOOKUP_CATEGORY ? (
                  <p
                    className="text-xs text-muted-foreground font-mono"
                    data-testid="lookup-workforce-roles-hints"
                  >
                    {t('admin.lookups.workforce_roles_hint', 'Suggested codes')}:{' '}
                    <span className="font-mono">{workforceRoleHintCodes()}</span>
                  </p>
                ) : null}
                {cat.key === CUSTOMERS_LOOKUP_CATEGORY ? (
                  <p
                    className="text-xs text-muted-foreground font-mono"
                    data-testid="lookup-customers-hints"
                  >
                    {t('admin.lookups.customers_hint', 'Suggested codes')}:{' '}
                    <span className="font-mono">{customerHintCodes()}</span>
                  </p>
                ) : null}
                {notConfigured ? (
                  <p className="text-xs text-amber-800" data-testid={`lookup-empty-${cat.key}`}>
                    {t(
                      'admin.lookups.empty_honesty',
                      'No options yet — forms using this category will show an empty dropdown until you configure it.',
                    )}
                  </p>
                ) : null}
                <Button
                  type="button"
                  className="w-full"
                  variant={notConfigured ? 'default' : 'outline'}
                  data-testid={`lookup-configure-${cat.key}`}
                  onClick={() => void openEditor(cat)}
                >
                  <Settings2 className="w-4 h-4" />
                  {t('admin.lookups.configure', 'Configure')}
                </Button>
              </CardContent>
            </Card>
          )
        })}
      </div>

      <Dialog open={editorCategory != null} onOpenChange={(open) => !open && setEditorCategory(null)}>
        <DialogContent className="max-w-lg" data-testid="lookup-editor-dialog">
          <DialogHeader>
            <DialogTitle>
              {t('admin.lookups.editor_title', 'Configure {{label}}', {
                label: editorCategory?.label ?? '',
              })}
            </DialogTitle>
          </DialogHeader>

          {editorLoading ? (
            <div className="flex items-center gap-2 py-8 text-sm text-muted-foreground justify-center">
              <Loader2 className="w-4 h-4 animate-spin" />
              {t('admin.lookups.loading', 'Loading…')}
            </div>
          ) : editorError ? (
            <p className="text-sm text-destructive py-4" data-testid="lookup-editor-error">
              {editorError}
            </p>
          ) : (
            <div className="space-y-4">
              {options.length === 0 ? (
                <div className="space-y-2">
                  <p className="text-sm text-muted-foreground" data-testid="lookup-editor-empty">
                    {t(
                      'admin.lookups.editor_empty',
                      'Not configured — add the first option below. Nothing is fabricated.',
                    )}
                  </p>
                  {editorCategory?.key === WORKFORCE_ROLES_LOOKUP_CATEGORY ? (
                    <ul
                      className="text-xs text-muted-foreground space-y-1"
                      data-testid="lookup-editor-workforce-role-hints"
                    >
                      {WORKFORCE_ROLE_CODE_HINTS.map((hint) => (
                        <li key={hint.code} className="font-mono">
                          {hint.code}
                          <span className="font-sans text-muted-foreground/80"> — {hint.label}</span>
                        </li>
                      ))}
                    </ul>
                  ) : null}
                  {editorCategory?.key === CUSTOMERS_LOOKUP_CATEGORY ? (
                    <ul
                      className="text-xs text-muted-foreground space-y-1"
                      data-testid="lookup-editor-customer-hints"
                    >
                      {CUSTOMER_CODE_HINTS.map((hint) => (
                        <li key={hint.code} className="font-mono">
                          {hint.code}
                          <span className="font-sans text-muted-foreground/80"> — {hint.label}</span>
                        </li>
                      ))}
                    </ul>
                  ) : null}
                </div>
              ) : (
                <ul className="space-y-2 max-h-56 overflow-y-auto" data-testid="lookup-editor-list">
                  {options.map((opt) => (
                    <li
                      key={opt.id}
                      className="flex items-center justify-between gap-2 rounded-md border border-border px-3 py-2 text-sm"
                    >
                      <span>
                        <span className="font-mono text-xs text-muted-foreground mr-2">
                          {opt.code}
                        </span>
                        {opt.label}
                        {!opt.is_active ? (
                          <span className="ml-2 text-xs text-muted-foreground">inactive</span>
                        ) : null}
                      </span>
                      {editorCategory?.key !== 'assets' ? (
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="shrink-0 text-destructive hover:text-destructive"
                        disabled={saving}
                        onClick={() => void handleRemove(opt)}
                        data-testid={`lookup-remove-${opt.code}`}
                        aria-label={t('admin.lookups.remove_option', 'Remove {{label}}', {
                          label: opt.label,
                        })}
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                      ) : null}
                    </li>
                  ))}
                </ul>
              )}

              <div className="space-y-2">
                <Input
                  placeholder={t('admin.lookups.name_placeholder', 'Name')}
                  value={newLabel}
                  onChange={(e) => handleNameChange(e.target.value)}
                  aria-label={t('admin.lookups.name_placeholder', 'Name')}
                  data-testid="lookup-new-label"
                />
                <p className="text-xs text-muted-foreground" data-testid="lookup-code-preview">
                  {t('admin.lookups.code_auto_hint', 'System code')}:{' '}
                  <span className="font-mono">{resolvedCode || '—'}</span>
                </p>
                <button
                  type="button"
                  className="text-xs text-primary hover:underline"
                  onClick={() => setShowAdvancedCode((prev) => !prev)}
                  data-testid="lookup-advanced-code-toggle"
                  aria-expanded={showAdvancedCode}
                >
                  {showAdvancedCode
                    ? t('admin.lookups.hide_advanced_code', 'Hide advanced code')
                    : t('admin.lookups.show_advanced_code', 'Advanced: edit code')}
                </button>
                {showAdvancedCode ? (
                  <Input
                    placeholder={t('admin.lookups.code_placeholder', 'Code')}
                    value={codeManual ? newCode : resolvedCode}
                    onChange={(e) => {
                      setCodeManual(true)
                      setNewCode(e.target.value)
                    }}
                    aria-label={t('admin.lookups.code_placeholder', 'Code')}
                    data-testid="lookup-new-code"
                  />
                ) : null}
              </div>
            </div>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setEditorCategory(null)}>
              {t('common.close', 'Close')}
            </Button>
            <Button
              type="button"
              disabled={saving || !newLabel.trim() || !resolvedCode || !!editorError}
              onClick={() => void handleCreate()}
              data-testid="lookup-add-option"
            >
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
              {t('admin.lookups.add_option', 'Add option')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

export type { CategoryKey }
