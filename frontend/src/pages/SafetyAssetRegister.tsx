import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  Loader2,
  Package,
  RefreshCw,
  Trash2,
} from 'lucide-react'
import {
  safetyAssetsApi,
  type CesAssetImportReport,
  type CesLookupConfirmation,
  type CesLookupProposal,
  type SafetyAsset,
  type SafetyAssetType,
  type SafetyLocation,
} from '../api/safetyAssetsClient'
import { getApiErrorMessage, workforceApi } from '../api/client'
import { toast } from '../contexts/ToastContext'
import { Badge, type BadgeVariant } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { Card, CardContent } from '../components/ui/Card'
import { Input } from '../components/ui/Input'
import {
  Sheet,
  SheetBody,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '../components/ui/Sheet'
import { TableSkeleton } from '../components/ui/SkeletonLoader'
import {
  BOARD_VIEWS,
  EMPTY_ASSET_ROW_FILTERS,
  EMPTY_ENTITY_ROLLUP_FILTERS,
  HERO_BANDS,
  applyHideRemoved,
  assetMatchesHeroBand,
  bandLabel,
  buildEngineerRollups,
  buildTypeRollups,
  buildVehicleRollups,
  computeHeroCounts,
  filterAssetRows,
  filterEntityRollups,
  isActiveFailAsset,
  isOkAsset,
  isRemovedAsset,
  ownerLabel,
  siteLabel,
  sortAssetRows,
  sortEntityRollups,
  type AssetBoardView,
  type AssetEntityRollup,
  type AssetHeroBand,
  type AssetRowColumnFilters,
  type AssetRowSortKey,
  type EntityRollupColumnFilters,
  type EntityRollupSortKey,
  type SortDirection,
} from './safetyAssets/safetyAssetBoardHelpers'

function statusVariant(status: string): BadgeVariant {
  switch (status) {
    case 'active':
      return 'success'
    case 'quarantined':
      return 'critical'
    case 'vor':
    case 'maintenance':
      return 'warning'
    case 'decommissioned':
      return 'secondary'
    default:
      return 'outline'
  }
}

function formatDate(value?: string | null): string {
  if (!value) return '—'
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? '—' : parsed.toLocaleDateString()
}

function heroIcon(band: AssetHeroBand) {
  switch (band) {
    case 'overdue':
    case 'quarantined':
      return AlertTriangle
    case 'decommissioned':
      return Trash2
    case 'in_date':
      return CheckCircle2
    case 'due_30':
    case 'due_60':
    case 'due_90':
      return Clock
    default:
      return Package
  }
}

export default function SafetyAssetRegister() {
  const { t } = useTranslation()

  const [boardAssets, setBoardAssets] = useState<SafetyAsset[]>([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [assetTypes, setAssetTypes] = useState<SafetyAssetType[]>([])
  const [locations, setLocations] = useState<SafetyLocation[]>([])
  const [ownerNames, setOwnerNames] = useState<Map<number, string>>(new Map())

  const [view, setView] = useState<AssetBoardView>('assets')
  const [heroBand, setHeroBand] = useState<AssetHeroBand>('all')
  const [search, setSearch] = useState('')
  const [hideRemoved, setHideRemoved] = useState(() => {
    try {
      return window.localStorage.getItem('qgp.safetyAssets.hideRemoved') !== 'false'
    } catch {
      return true
    }
  })

  const [assetSortKey, setAssetSortKey] = useState<AssetRowSortKey>('expiry')
  const [assetSortDir, setAssetSortDir] = useState<SortDirection>('asc')
  const [assetFilters, setAssetFilters] = useState<AssetRowColumnFilters>(EMPTY_ASSET_ROW_FILTERS)
  const [entitySortKey, setEntitySortKey] = useState<EntityRollupSortKey>('overdue')
  const [entitySortDir, setEntitySortDir] = useState<SortDirection>('desc')
  const [entityFilters, setEntityFilters] =
    useState<EntityRollupColumnFilters>(EMPTY_ENTITY_ROLLUP_FILTERS)

  const [drilldown, setDrilldown] = useState<AssetEntityRollup | null>(null)

  const [cesFile, setCesFile] = useState<File | null>(null)
  const [cesReport, setCesReport] = useState<CesAssetImportReport | null>(null)
  const [cesBusy, setCesBusy] = useState(false)
  const [cesError, setCesError] = useState<string | null>(null)
  /** key = `${kind}:${name}` → confirmation choice for similar lookups */
  const [cesConfirmations, setCesConfirmations] = useState<Record<string, CesLookupConfirmation>>({})

  const typeNameById = useMemo(() => {
    const map = new Map<number, string>()
    assetTypes.forEach((at) => map.set(at.id, at.name))
    return map
  }, [assetTypes])

  const locationNameById = useMemo(() => {
    const map = new Map<number, string>()
    locations.forEach((loc) => map.set(loc.id, loc.name))
    return map
  }, [locations])

  const loadBoard = useCallback(async () => {
    setLoading(true)
    setLoadError(null)
    try {
      const [assetsRes, typesRes, locsRes, engineersRes] = await Promise.allSettled([
        safetyAssetsApi.listAllAssetsForBoard(),
        // Include inactive/pending provisional lookups so CES-imported assets show names.
        safetyAssetsApi.listAssetTypes({ page: 1, page_size: 200 }),
        safetyAssetsApi.listLocations({ page: 1, page_size: 200 }),
        workforceApi.listEngineers({ page: 1, page_size: 500, is_active: true }),
      ])
      if (assetsRes.status === 'rejected') {
        throw assetsRes.reason
      }
      setBoardAssets(assetsRes.value)
      if (typesRes.status === 'fulfilled') {
        setAssetTypes(typesRes.value.data.items ?? [])
      }
      if (locsRes.status === 'fulfilled') {
        setLocations(locsRes.value.data.items ?? [])
      }
      if (engineersRes.status === 'fulfilled') {
        const names = new Map<number, string>()
        for (const eng of engineersRes.value.data?.items ?? []) {
          if (eng.user_id != null && eng.display_name) {
            names.set(eng.user_id, eng.display_name)
          }
        }
        setOwnerNames(names)
      }
    } catch (err) {
      const message = getApiErrorMessage(err, 'Could not load safety assets.')
      setLoadError(message)
      setBoardAssets([])
      toast.error(message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadBoard()
  }, [loadBoard])

  useEffect(() => {
    try {
      window.localStorage.setItem('qgp.safetyAssets.hideRemoved', String(hideRemoved))
    } catch {
      // Storage may be unavailable in private browsing contexts.
    }
  }, [hideRemoved])

  const scopeAssets = useMemo(
    () => applyHideRemoved(boardAssets, hideRemoved),
    [boardAssets, hideRemoved],
  )
  const heroCounts = useMemo(
    () => ({
      ...computeHeroCounts(scopeAssets),
      decommissioned: boardAssets.filter(isRemovedAsset).length,
    }),
    [scopeAssets, boardAssets],
  )
  const metricsReady = !loading && loadError == null
  const kpisUnavailable = !loading && loadError != null

  const bandFiltered = useMemo(
    () => scopeAssets.filter((asset) => assetMatchesHeroBand(asset, heroBand)),
    [scopeAssets, heroBand],
  )

  const searchFiltered = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return bandFiltered
    return bandFiltered.filter((asset) => {
      const type = typeNameById.get(asset.asset_type_id) || ''
      const owner = ownerLabel(asset, ownerNames)
      const haystack = [
        asset.serial_number,
        asset.asset_number,
        asset.name,
        type,
        owner,
        asset.vehicle_reg,
        siteLabel(asset, locationNameById),
        asset.status,
      ]
        .filter(Boolean)
        .join(' ')
        .toLowerCase()
      return haystack.includes(q)
    })
  }, [bandFiltered, search, typeNameById, ownerNames, locationNameById])

  const assetRows = useMemo(() => {
    const filtered = filterAssetRows(
      searchFiltered,
      assetFilters,
      typeNameById,
      ownerNames,
      locationNameById,
    )
    return sortAssetRows(
      filtered,
      assetSortKey,
      assetSortDir,
      typeNameById,
      ownerNames,
      locationNameById,
    )
  }, [
    searchFiltered,
    assetFilters,
    assetSortKey,
    assetSortDir,
    typeNameById,
    ownerNames,
    locationNameById,
  ])

  const engineerRollups = useMemo(
    () => buildEngineerRollups(searchFiltered, ownerNames),
    [searchFiltered, ownerNames],
  )
  const vehicleRollups = useMemo(() => buildVehicleRollups(searchFiltered), [searchFiltered])
  const typeRollups = useMemo(
    () => buildTypeRollups(searchFiltered, typeNameById),
    [searchFiltered, typeNameById],
  )

  const activeEntityRollups = useMemo(() => {
    const source =
      view === 'engineer' ? engineerRollups : view === 'vehicle' ? vehicleRollups : typeRollups
    return sortEntityRollups(filterEntityRollups(source, entityFilters), entitySortKey, entitySortDir)
  }, [
    view,
    engineerRollups,
    vehicleRollups,
    typeRollups,
    entityFilters,
    entitySortKey,
    entitySortDir,
  ])

  const toggleAssetSort = (key: AssetRowSortKey) => {
    if (assetSortKey === key) {
      setAssetSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setAssetSortKey(key)
      setAssetSortDir(key === 'expiry' || key === 'name' ? 'asc' : 'desc')
    }
  }

  const toggleEntitySort = (key: EntityRollupSortKey) => {
    if (entitySortKey === key) {
      setEntitySortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setEntitySortKey(key)
      setEntitySortDir(key === 'label' ? 'asc' : 'desc')
    }
  }

  const similarProposals = useMemo(
    () => (cesReport?.lookup_proposals || []).filter((p) => p.needs_confirmation),
    [cesReport],
  )
  const newProposals = useMemo(
    () => (cesReport?.lookup_proposals || []).filter((p) => p.intent === 'new'),
    [cesReport],
  )
  const allSimilarConfirmed = similarProposals.every(
    (p) => Boolean(cesConfirmations[`${p.kind}:${p.name}`]),
  )
  // Dry-run sets can_commit=false while similar lookups need UI confirmation;
  // after every similar proposal is confirmed, allow Commit (server re-checks).
  // Legacy mocks without can_commit still work when allSimilarConfirmed.
  const serverAllowsCesCommit =
    cesReport?.can_commit === true ||
    Boolean(cesReport?.requires_confirmation) ||
    typeof cesReport?.can_commit !== 'boolean'
  const canCommitCes = Boolean(
    cesReport &&
      !cesBusy &&
      allSimilarConfirmed &&
      cesReport.valid_rows > 0 &&
      serverAllowsCesCommit,
  )

  const dryRunCesImport = async () => {
    if (!cesFile) return
    setCesBusy(true)
    setCesError(null)
    setCesConfirmations({})
    try {
      const response = await safetyAssetsApi.cesImportDryRun(cesFile)
      setCesReport(response.data)
    } catch (err) {
      setCesError(getApiErrorMessage(err, 'Could not validate CES workbook.'))
      setCesReport(null)
    } finally {
      setCesBusy(false)
    }
  }

  const setProposalConfirmation = (
    proposal: CesLookupProposal,
    action: 'reuse' | 'create',
    reuseId?: number | null,
  ) => {
    const key = `${proposal.kind}:${proposal.name}`
    setCesConfirmations((prev) => ({
      ...prev,
      [key]: {
        kind: proposal.kind,
        name: proposal.name,
        action,
        reuse_id: action === 'reuse' ? reuseId ?? proposal.similar_matches[0]?.id : null,
      },
    }))
  }

  const commitCesImport = async () => {
    if (!cesFile || !canCommitCes) return
    setCesBusy(true)
    setCesError(null)
    try {
      const response = await safetyAssetsApi.cesImportCommit(
        cesFile,
        Object.values(cesConfirmations),
      )
      setCesReport(response.data.report)
      const pendingTypes = response.data.provisional_type_ids?.length || 0
      const pendingLocs = response.data.provisional_location_ids?.length || 0
      const skipped = response.data.report?.skipped_error_rows || response.data.report?.error_rows || 0
      toast.success(
        `CES import complete: ${response.data.created_count} created, ${response.data.updated_count} updated.` +
          (skipped ? ` ${skipped} error row(s) skipped.` : '') +
          (pendingTypes + pendingLocs
            ? ` ${pendingTypes + pendingLocs} Safety lookup(s) awaiting approval in Admin → Lookups.`
            : ''),
      )
      void loadBoard()
    } catch (err) {
      setCesError(getApiErrorMessage(err, 'Could not commit CES workbook.'))
    } finally {
      setCesBusy(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-3xl font-bold text-foreground">
            {t('safetyAssets.title', 'Safety Asset Register')}
          </h1>
          <p className="mt-1 text-muted-foreground">
            {t(
              'safetyAssets.subtitle',
              'CES-fed register — click hero bands, roll up by engineer/vehicle/type, drill into kits.',
            )}
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => void loadBoard()}>
          <RefreshCw className="mr-2 h-4 w-4" />
          {t('safetyAssets.refresh', 'Refresh')}
        </Button>
      </div>

      {kpisUnavailable ? (
        <div
          className="rounded-lg border border-warning/40 bg-warning/10 px-4 py-3 text-sm"
          role="status"
          data-testid="safety-assets-kpi-unavailable"
        >
          <p className="font-medium text-warning-foreground">
            {t(
              'safetyAssets.kpi.unavailable',
              'KPI metrics unavailable — not shown as fake zeros.',
            )}
          </p>
        </div>
      ) : null}

      <div
        className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-8"
        data-testid="safety-assets-kpi-row"
        role="tablist"
        aria-label="Asset hero bands"
      >
        {HERO_BANDS.map((band) => {
          const Icon = heroIcon(band.id)
          const active = heroBand === band.id
          const value = heroCounts[band.id]
          const tone =
            band.id === 'overdue' || band.id === 'quarantined'
              ? 'text-destructive'
              : band.id === 'in_date'
                ? 'text-success'
                : band.id.startsWith('due_')
                  ? 'text-warning'
                  : 'text-foreground'
          return (
            <button
              key={band.id}
              type="button"
              role="tab"
              aria-selected={active}
              data-testid={`safety-assets-kpi-${band.id === 'all' ? 'total' : band.id}`}
              className={`rounded-lg border p-4 text-left transition-colors ${
                active
                  ? 'border-primary bg-primary/10 ring-1 ring-primary'
                  : band.id === 'quarantined'
                    ? 'border-destructive/50 bg-destructive/10 hover:border-destructive'
                    : 'border-border bg-card hover:border-primary/50'
              }`}
              onClick={() => setHeroBand(band.id)}
            >
              <div className="flex items-center gap-2 text-muted-foreground">
                <Icon className="h-4 w-4" />
                <span className="text-xs font-medium">{band.label}</span>
              </div>
              <p className={`mt-2 text-2xl font-bold ${tone}`}>
                {metricsReady ? value : '—'}
              </p>
            </button>
          )
        })}
      </div>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap gap-1" role="tablist" aria-label="Board view">
          {BOARD_VIEWS.map((item) => (
            <button
              key={item.id}
              type="button"
              role="tab"
              aria-selected={view === item.id}
              data-testid={`safety-assets-view-${item.id}`}
              className={`rounded-full border px-3 py-1.5 text-sm ${
                view === item.id
                  ? 'border-primary bg-primary text-primary-foreground'
                  : 'border-border text-muted-foreground hover:text-foreground'
              }`}
              onClick={() => setView(item.id)}
            >
              {item.label}
            </button>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <label className="inline-flex items-center gap-2 text-sm text-muted-foreground">
            <input
              type="checkbox"
              checked={hideRemoved}
              onChange={(event) => setHideRemoved(event.target.checked)}
              data-testid="safety-assets-hide-removed"
            />
            Hide removed
          </label>
          {view !== 'upload' ? (
            <Input
              className="max-w-sm"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={t('safetyAssets.search', 'Search serial, owner, vehicle…')}
              aria-label="Search assets"
              data-testid="safety-assets-search"
            />
          ) : null}
        </div>
      </div>

      {loadError ? (
        <div
          className="rounded-lg border border-destructive/30 bg-destructive/5 p-4"
          role="alert"
          data-testid="safety-assets-list-error"
        >
          <div className="flex items-center gap-2 text-destructive">
            <AlertTriangle className="h-4 w-4" />
            <p className="text-sm font-medium">{loadError}</p>
          </div>
        </div>
      ) : null}

      {view === 'upload' ? (
        <Card data-testid="ces-import-panel">
          <CardContent className="space-y-3 p-4">
            <div>
              <h2 className="font-semibold text-foreground">CES Calibrations import</h2>
              <p className="text-sm text-muted-foreground">
                Admin-only XLSX import. Dry-run validates serial upserts before any assets are changed.
              </p>
            </div>
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
              <Input
                type="file"
                accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                aria-label="CES workbook"
                onChange={(event) => {
                  setCesFile(event.target.files?.[0] ?? null)
                  setCesReport(null)
                  setCesError(null)
                  setCesConfirmations({})
                }}
              />
              <Button size="sm" disabled={!cesFile || cesBusy} onClick={() => void dryRunCesImport()}>
                {cesBusy ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Working…
                  </>
                ) : (
                  'Dry run'
                )}
              </Button>
              <Button
                size="sm"
                disabled={!canCommitCes}
                data-testid="ces-import-commit"
                onClick={() => void commitCesImport()}
              >
                Commit import
              </Button>
            </div>
            {cesError ? (
              <p className="text-sm text-destructive" role="alert">
                {cesError}
              </p>
            ) : null}
            {cesReport ? (
              <div className="space-y-3 rounded-md bg-muted/50 p-3 text-sm" data-testid="ces-import-summary">
                <p>
                  {cesReport.valid_rows} valid, {cesReport.error_rows} error rows, {cesReport.creates}{' '}
                  creates, {cesReport.updates} updates
                  {newProposals.length
                    ? `, ${newProposals.length} new lookups will be queued for approval on commit`
                    : ''}
                  {similarProposals.length
                    ? `, ${similarProposals.length} similar lookups need confirmation`
                    : ''}
                  .
                </p>
                {cesReport.error_rows > 0 && canCommitCes ? (
                  <p className="text-xs text-warning-foreground" data-testid="ces-import-skip-errors">
                    Commit will import {cesReport.valid_rows} valid row(s) and skip{' '}
                    {cesReport.error_rows} error row(s). Fix skipped rows and re-import later if needed.
                  </p>
                ) : null}
                {cesReport.error_rows > 0 && !canCommitCes && !similarProposals.length ? (
                  <p className="text-xs text-destructive" data-testid="ces-import-blocked">
                    Commit is blocked until there is at least one valid row (or similar lookups are
                    confirmed).
                  </p>
                ) : null}
                {newProposals.length ? (
                  <div data-testid="ces-import-new-lookups">
                    <p className="font-medium">Will create pending Safety lookups on commit</p>
                    <ul className="mt-1 list-disc pl-5 text-muted-foreground">
                      {newProposals.slice(0, 12).map((p) => (
                        <li key={`${p.kind}:${p.name}`}>
                          {p.kind === 'asset_type' ? 'Type' : 'Location'}: {p.name} ({p.row_count} rows)
                        </li>
                      ))}
                      {newProposals.length > 12 ? (
                        <li>…and {newProposals.length - 12} more</li>
                      ) : null}
                    </ul>
                    <p className="mt-1 text-xs text-muted-foreground">
                      New equipment types and site locations appear under{' '}
                      <Link className="underline" to="/admin/lookups?pending=safety">
                        Admin → Lookups → Safety Asset Types &amp; Site Locations
                      </Link>{' '}
                      (not the form Tools/Locations cards below).
                    </p>
                  </div>
                ) : null}
                {similarProposals.length ? (
                  <div className="space-y-2" data-testid="ces-import-similar-lookups">
                    <p className="font-medium text-warning-foreground">
                      Confirm similar lookups (required before commit)
                    </p>
                    {similarProposals.map((proposal) => {
                      const key = `${proposal.kind}:${proposal.name}`
                      const chosen = cesConfirmations[key]
                      const top = proposal.similar_matches[0]
                      return (
                        <div
                          key={key}
                          className="rounded border border-border bg-card p-2"
                          data-testid={`ces-similar-${proposal.kind}-${proposal.name}`}
                        >
                          <p>
                            Proposed {proposal.kind === 'asset_type' ? 'type' : 'location'}{' '}
                            <strong>{proposal.name}</strong> looks like{' '}
                            <strong>{top?.name}</strong>
                            {top ? ` (${Math.round(top.score * 100)}% match)` : ''}.
                          </p>
                          <div className="mt-2 flex flex-wrap gap-3">
                            <label className="inline-flex items-center gap-1.5">
                              <input
                                type="radio"
                                name={key}
                                checked={chosen?.action === 'reuse'}
                                onChange={() => setProposalConfirmation(proposal, 'reuse', top?.id)}
                              />
                              Use existing “{top?.name}”
                            </label>
                            <label className="inline-flex items-center gap-1.5">
                              <input
                                type="radio"
                                name={key}
                                checked={chosen?.action === 'create'}
                                onChange={() => setProposalConfirmation(proposal, 'create')}
                              />
                              Create new “{proposal.name}” anyway
                            </label>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                ) : null}
                {(cesReport.errors?.length ?? 0) > 0 ? (
                  <div className="space-y-1 text-destructive" data-testid="ces-import-errors">
                    <p className="font-medium">
                      {cesReport.error_rows} error row(s)
                      {canCommitCes ? ' (will be skipped on commit)' : ''}:
                    </p>
                    <ul className="list-disc pl-5 text-xs">
                      {cesReport.errors.slice(0, 25).map((issue, idx) => (
                        <li key={`${issue.row}-${issue.code}-${idx}`}>
                          {issue.row > 0 ? `Row ${issue.row}: ${issue.code}` : issue.message}
                          {issue.message && issue.row > 0 ? ` — ${issue.message}` : ''}
                        </li>
                      ))}
                      {cesReport.errors.length > 25 ? (
                        <li>…and {cesReport.errors.length - 25} more</li>
                      ) : null}
                    </ul>
                  </div>
                ) : null}
              </div>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      {view !== 'upload' && loading ? <TableSkeleton rows={8} /> : null}

      {view === 'assets' && !loading ? (
        <Card>
          <CardContent className="p-0">
            <div className="flex items-center justify-between border-b border-border px-4 py-3">
              <span className="text-sm text-muted-foreground" data-testid="safety-assets-list-total">
                {t('safetyAssets.list.count', '{{count}} assets', { count: assetRows.length })}
              </span>
              <span className="text-xs text-muted-foreground">
                % OK = active and not overdue (Training-style SSOT)
              </span>
            </div>
            {assetRows.length === 0 ? (
              <div className="p-12 text-center" data-testid="safety-assets-empty">
                <Package className="mx-auto mb-3 h-12 w-12 text-muted-foreground" />
                <h3 className="text-lg font-semibold text-foreground">
                  {t('safetyAssets.empty.title', 'No safety assets found')}
                </h3>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm" data-testid="safety-assets-table">
                  <thead>
                    <tr className="border-b border-border bg-muted/50">
                      {(
                        [
                          ['serial', 'Serial'],
                          ['name', 'Name'],
                          ['type', 'Type'],
                          ['owner', 'Owner'],
                          ['vehicle', 'Vehicle'],
                          ['site', 'Site'],
                          ['expiry', 'Next'],
                          ['status', 'Status'],
                        ] as const
                      ).map(([key, label]) => (
                        <th key={key} className="p-3 text-left font-medium text-muted-foreground">
                          <button
                            type="button"
                            className="hover:text-foreground"
                            onClick={() => toggleAssetSort(key)}
                          >
                            {label}
                            {assetSortKey === key ? (assetSortDir === 'asc' ? ' ↑' : ' ↓') : ''}
                          </button>
                        </th>
                      ))}
                      <th className="p-3 text-left font-medium text-muted-foreground">Band</th>
                    </tr>
                    <tr className="border-b border-border bg-muted/30">
                      {(
                        [
                          'serial',
                          'name',
                          'type',
                          'owner',
                          'vehicle',
                          'site',
                          'expiry',
                          'status',
                        ] as const
                      ).map((key) => (
                        <th key={key} className="p-2">
                          <Input
                            className="h-8"
                            value={assetFilters[key]}
                            onChange={(e) =>
                              setAssetFilters((prev) => ({ ...prev, [key]: e.target.value }))
                            }
                            aria-label={`Filter ${key}`}
                          />
                        </th>
                      ))}
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {assetRows.map((asset) => (
                      <tr
                        key={asset.id}
                        className={`border-b border-border ${
                          isActiveFailAsset(asset)
                            ? 'bg-destructive/10 hover:bg-destructive/20'
                            : 'hover:bg-muted/30'
                        }`}
                        data-testid={`safety-asset-row-${asset.id}`}
                      >
                        <td className="p-3 font-medium">
                          <Link
                            to={`/safety-assets/${asset.id}`}
                            className="text-primary hover:underline"
                          >
                            {asset.serial_number || asset.asset_number}
                          </Link>
                        </td>
                        <td className="p-3">{asset.name}</td>
                        <td className="p-3">{typeNameById.get(asset.asset_type_id) || '—'}</td>
                        <td className="p-3">{ownerLabel(asset, ownerNames)}</td>
                        <td className="p-3">{asset.vehicle_reg || '—'}</td>
                        <td className="p-3">{siteLabel(asset, locationNameById) || '—'}</td>
                        <td className="p-3">{formatDate(asset.expiry_date)}</td>
                        <td className="p-3">
                          <Badge variant={statusVariant(asset.status)}>{asset.status}</Badge>
                        </td>
                        <td className="p-3">
                          <Badge variant={isOkAsset(asset) ? 'success' : 'warning'}>
                            {bandLabel(asset)}
                          </Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      ) : null}

      {(view === 'engineer' || view === 'vehicle' || view === 'type') && !loading ? (
        <Card>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm" data-testid={`safety-assets-${view}-table`}>
                <thead>
                  <tr className="border-b border-border bg-muted/50">
                    {(
                      [
                        ['label', view === 'engineer' ? 'Engineer' : view === 'vehicle' ? 'Vehicle' : 'Type'],
                        ['total', 'Assets'],
                        ['ok', 'OK'],
                        ['overdue', 'Overdue'],
                        ['quarantined', 'Fail'],
                        ['pct', '% OK'],
                      ] as const
                    ).map(([key, label]) => (
                      <th key={key} className="p-3 text-left font-medium text-muted-foreground">
                        <button
                          type="button"
                          className="hover:text-foreground"
                          onClick={() => toggleEntitySort(key)}
                        >
                          {label}
                          {entitySortKey === key ? (entitySortDir === 'asc' ? ' ↑' : ' ↓') : ''}
                        </button>
                      </th>
                    ))}
                  </tr>
                  <tr className="border-b border-border bg-muted/30">
                    {(
                      ['label', 'total', 'ok', 'overdue', 'quarantined', 'pct'] as const
                    ).map((key) => (
                      <th key={key} className="p-2">
                        <Input
                          className="h-8"
                          value={entityFilters[key]}
                          onChange={(e) =>
                            setEntityFilters((prev) => ({ ...prev, [key]: e.target.value }))
                          }
                          aria-label={`Filter ${key}`}
                        />
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {activeEntityRollups.map((row) => (
                    <tr
                      key={row.key}
                      className="cursor-pointer border-b border-border hover:bg-muted/30"
                      data-testid={`safety-assets-rollup-${row.key}`}
                      onClick={() => setDrilldown(row)}
                    >
                      <td className="p-3 font-medium text-primary">{row.label}</td>
                      <td className="p-3">{row.total}</td>
                      <td className="p-3">{row.ok}</td>
                      <td className="p-3">{row.overdue}</td>
                      <td className="p-3">{row.quarantined}</td>
                      <td className="p-3 font-semibold">{row.pct}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      ) : null}

      <Sheet open={drilldown != null} onOpenChange={(open) => !open && setDrilldown(null)}>
        <SheetContent side="right" className="max-w-lg" data-testid="safety-assets-drilldown-sheet">
          <SheetHeader>
            <SheetTitle>{drilldown?.label || 'Kit'}</SheetTitle>
            <SheetDescription>
              {drilldown
                ? `${drilldown.ok}/${drilldown.total} OK · ${drilldown.overdue} overdue · ${drilldown.pct}%`
                : ''}
            </SheetDescription>
          </SheetHeader>
          <SheetBody className="space-y-3">
            {(drilldown?.assets || []).map((asset) => (
              <div
                key={asset.id}
                className="rounded-md border border-border p-3 text-sm"
                data-testid={`safety-assets-sheet-row-${asset.id}`}
              >
                <div className="flex items-center justify-between gap-2">
                  <Link
                    to={`/safety-assets/${asset.id}`}
                    className="font-medium text-primary hover:underline"
                  >
                    {asset.serial_number || asset.asset_number}
                  </Link>
                  <Badge variant={isOkAsset(asset) ? 'success' : 'warning'}>{bandLabel(asset)}</Badge>
                </div>
                <p className="mt-1 text-muted-foreground">{asset.name}</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {typeNameById.get(asset.asset_type_id) || '—'} · Next {formatDate(asset.expiry_date)}
                </p>
              </div>
            ))}
          </SheetBody>
        </SheetContent>
      </Sheet>
    </div>
  )
}
