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
  ShieldAlert,
} from 'lucide-react'
import {
  EMPTY_SAFETY_ASSET_KPIS,
  safetyAssetsApi,
  type ExpiryBand,
  type MetricValue,
  type SafetyAsset,
  type SafetyAssetKpis,
  type SafetyAssetType,
  type SafetyLocation,
} from '../api/safetyAssetsClient'
import { getApiErrorMessage } from '../api/client'
import { toast } from '../contexts/ToastContext'
import { Badge, type BadgeVariant } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { Card, CardContent } from '../components/ui/Card'
import { Input } from '../components/ui/Input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/Select'
import { TableSkeleton } from '../components/ui/SkeletonLoader'

function formatMetric(value: MetricValue): string {
  return value == null ? '—' : String(value)
}

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

const EXPIRY_BANDS: { value: ExpiryBand | 'all'; labelKey: string }[] = [
  { value: 'all', labelKey: 'safetyAssets.filter.expiry_all' },
  { value: 'overdue', labelKey: 'safetyAssets.filter.expiry_overdue' },
  { value: 'due_30', labelKey: 'safetyAssets.filter.expiry_due_30' },
  { value: 'due_60', labelKey: 'safetyAssets.filter.expiry_due_60' },
  { value: 'due_90', labelKey: 'safetyAssets.filter.expiry_due_90' },
]

export default function SafetyAssetRegister() {
  const { t } = useTranslation()

  const [assets, setAssets] = useState<SafetyAsset[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pages, setPages] = useState(1)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)

  const [kpis, setKpis] = useState<SafetyAssetKpis>(EMPTY_SAFETY_ASSET_KPIS)
  const [kpisUnavailable, setKpisUnavailable] = useState(false)

  const [assetTypes, setAssetTypes] = useState<SafetyAssetType[]>([])
  const [locations, setLocations] = useState<SafetyLocation[]>([])
  const [filtersUnavailable, setFiltersUnavailable] = useState(false)

  const [typeFilter, setTypeFilter] = useState<string>('all')
  const [locationFilter, setLocationFilter] = useState<string>('all')
  const [vehicleFilter, setVehicleFilter] = useState('')
  const [ownerFilter, setOwnerFilter] = useState('')
  const [expiryFilter, setExpiryFilter] = useState<string>('all')

  const pageSize = 20

  const listParams = useMemo(() => {
    const params: Parameters<typeof safetyAssetsApi.listAssets>[0] = {
      page,
      page_size: pageSize,
    }
    if (typeFilter !== 'all') params.asset_type_id = Number(typeFilter)
    if (locationFilter !== 'all') params.location_id = Number(locationFilter)
    if (vehicleFilter.trim()) params.vehicle_reg = vehicleFilter.trim()
    if (ownerFilter.trim() && !Number.isNaN(Number(ownerFilter.trim()))) {
      params.owner_user_id = Number(ownerFilter.trim())
    }
    if (expiryFilter !== 'all') params.expiry_band = expiryFilter as ExpiryBand
    return params
  }, [page, typeFilter, locationFilter, vehicleFilter, ownerFilter, expiryFilter])

  const kpiBaseFilters = useMemo(() => {
    const base: Parameters<typeof safetyAssetsApi.getKpis>[0] = {}
    if (typeFilter !== 'all') base.asset_type_id = Number(typeFilter)
    if (locationFilter !== 'all') base.location_id = Number(locationFilter)
    if (vehicleFilter.trim()) base.vehicle_reg = vehicleFilter.trim()
    if (ownerFilter.trim() && !Number.isNaN(Number(ownerFilter.trim()))) {
      base.owner_user_id = Number(ownerFilter.trim())
    }
    return base
  }, [typeFilter, locationFilter, vehicleFilter, ownerFilter])

  const loadFilterOptions = useCallback(async () => {
    const [typesRes, locsRes] = await Promise.allSettled([
      safetyAssetsApi.listAssetTypes({ page: 1, page_size: 200, is_active: true }),
      safetyAssetsApi.listLocations({ page: 1, page_size: 200, is_active: true }),
    ])
    if (typesRes.status === 'fulfilled') {
      setAssetTypes(typesRes.value.data.items ?? [])
    }
    if (locsRes.status === 'fulfilled') {
      setLocations(locsRes.value.data.items ?? [])
    }
    setFiltersUnavailable(typesRes.status === 'rejected' || locsRes.status === 'rejected')
  }, [])

  const loadList = useCallback(async () => {
    setLoading(true)
    setLoadError(null)
    try {
      const res = await safetyAssetsApi.listAssets(listParams)
      setAssets(res.data.items ?? [])
      setTotal(res.data.total ?? 0)
      setPages(res.data.pages ?? 1)
    } catch (err) {
      const message = getApiErrorMessage(
        err,
        t('safetyAssets.error.load_failed', 'Could not load safety assets.'),
      )
      setLoadError(message)
      setAssets([])
      setTotal(0)
      toast.error(message)
    } finally {
      setLoading(false)
    }
  }, [listParams, t])

  const loadKpis = useCallback(async () => {
    setKpisUnavailable(false)
    try {
      const next = await safetyAssetsApi.getKpis(kpiBaseFilters)
      setKpis(next)
      const allNull = Object.values(next).every((v) => v == null)
      setKpisUnavailable(allNull)
    } catch {
      setKpis(EMPTY_SAFETY_ASSET_KPIS)
      setKpisUnavailable(true)
    }
  }, [kpiBaseFilters])

  useEffect(() => {
    void loadFilterOptions()
  }, [loadFilterOptions])

  useEffect(() => {
    void loadList()
  }, [loadList])

  useEffect(() => {
    void loadKpis()
  }, [loadKpis])

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

  const kpiCards: {
    key: keyof SafetyAssetKpis
    label: string
    icon: typeof Package
    tone?: string
  }[] = [
    {
      key: 'total',
      label: t('safetyAssets.kpi.total', 'Total'),
      icon: Package,
    },
    {
      key: 'in_date',
      label: t('safetyAssets.kpi.in_date', 'In date'),
      icon: CheckCircle2,
      tone: 'text-success',
    },
    {
      key: 'due_30',
      label: t('safetyAssets.kpi.due_30', 'Due 30d'),
      icon: Clock,
      tone: 'text-info',
    },
    {
      key: 'due_60',
      label: t('safetyAssets.kpi.due_60', 'Due 60d'),
      icon: Clock,
      tone: 'text-warning',
    },
    {
      key: 'due_90',
      label: t('safetyAssets.kpi.due_90', 'Due 90d'),
      icon: Clock,
      tone: 'text-warning',
    },
    {
      key: 'overdue',
      label: t('safetyAssets.kpi.overdue', 'Overdue'),
      icon: AlertTriangle,
      tone: 'text-destructive',
    },
    {
      key: 'quarantined',
      label: t('safetyAssets.kpi.quarantined', 'Quarantined'),
      icon: ShieldAlert,
      tone: 'text-destructive',
    },
  ]

  const clearFilters = () => {
    setTypeFilter('all')
    setLocationFilter('all')
    setVehicleFilter('')
    setOwnerFilter('')
    setExpiryFilter('all')
    setPage(1)
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
              'KPI hub for safety equipment — assignment, expiry, and quarantine status.',
            )}
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            void loadList()
            void loadKpis()
          }}
        >
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
        className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-7"
        data-testid="safety-assets-kpi-row"
      >
        {kpiCards.map((card) => {
          const Icon = card.icon
          return (
            <Card key={card.key}>
              <CardContent className="p-4">
                <div className="flex items-center gap-2 text-muted-foreground">
                  <Icon className="h-4 w-4" />
                  <span className="text-xs font-medium">{card.label}</span>
                </div>
                <p
                  className={`mt-2 text-2xl font-bold ${card.tone ?? 'text-foreground'}`}
                  data-testid={`safety-assets-kpi-${card.key}`}
                >
                  {formatMetric(kpis[card.key])}
                </p>
              </CardContent>
            </Card>
          )
        })}
      </div>

      <Card>
        <CardContent className="flex flex-col gap-3 p-4 md:flex-row md:flex-wrap md:items-end">
          <div className="min-w-[160px] space-y-1">
            <label className="text-xs font-medium text-muted-foreground">
              {t('safetyAssets.filter.type', 'Type')}
            </label>
            <Select
              value={typeFilter}
              onValueChange={(v) => {
                setTypeFilter(v)
                setPage(1)
              }}
            >
              <SelectTrigger>
                <SelectValue
                  placeholder={t('safetyAssets.filter.type_all', 'All types')}
                />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">
                  {t('safetyAssets.filter.type_all', 'All types')}
                </SelectItem>
                {assetTypes.map((at) => (
                  <SelectItem key={at.id} value={String(at.id)}>
                    {at.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="min-w-[160px] space-y-1">
            <label className="text-xs font-medium text-muted-foreground">
              {t('safetyAssets.filter.location', 'Location')}
            </label>
            <Select
              value={locationFilter}
              onValueChange={(v) => {
                setLocationFilter(v)
                setPage(1)
              }}
            >
              <SelectTrigger>
                <SelectValue
                  placeholder={t('safetyAssets.filter.location_all', 'All locations')}
                />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">
                  {t('safetyAssets.filter.location_all', 'All locations')}
                </SelectItem>
                {locations.map((loc) => (
                  <SelectItem key={loc.id} value={String(loc.id)}>
                    {loc.name} ({loc.kind})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="min-w-[140px] space-y-1">
            <label className="text-xs font-medium text-muted-foreground">
              {t('safetyAssets.filter.vehicle', 'Vehicle')}
            </label>
            <Input
              value={vehicleFilter}
              onChange={(e) => {
                setVehicleFilter(e.target.value)
                setPage(1)
              }}
              placeholder={t('safetyAssets.filter.vehicle_placeholder', 'Reg')}
            />
          </div>

          <div className="min-w-[140px] space-y-1">
            <label className="text-xs font-medium text-muted-foreground">
              {t('safetyAssets.filter.owner', 'Owner')}
            </label>
            <Input
              value={ownerFilter}
              onChange={(e) => {
                setOwnerFilter(e.target.value)
                setPage(1)
              }}
              placeholder={t('safetyAssets.filter.owner_placeholder', 'User ID')}
              inputMode="numeric"
            />
          </div>

          <div className="min-w-[160px] space-y-1">
            <label className="text-xs font-medium text-muted-foreground">
              {t('safetyAssets.filter.expiry', 'Expiry band')}
            </label>
            <Select
              value={expiryFilter}
              onValueChange={(v) => {
                setExpiryFilter(v)
                setPage(1)
              }}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {EXPIRY_BANDS.map((band) => (
                  <SelectItem key={band.value} value={band.value}>
                    {t(band.labelKey)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <Button variant="outline" size="sm" onClick={clearFilters}>
            {t('safetyAssets.filter.clear', 'Clear filters')}
          </Button>
        </CardContent>
      </Card>

      {filtersUnavailable ? (
        <p className="text-sm text-muted-foreground" role="status">
          {t(
            'safetyAssets.filter.options_unavailable',
            'Some filter options could not be loaded.',
          )}
        </p>
      ) : null}

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

      {loading ? (
        <TableSkeleton rows={8} />
      ) : (
        <Card>
          <CardContent className="p-0">
            <div className="flex items-center justify-between border-b border-border px-4 py-3">
              <span className="text-sm text-muted-foreground" data-testid="safety-assets-list-total">
                {t('safetyAssets.list.count', '{{count}} assets', { count: total })}
              </span>
            </div>
            {assets.length === 0 ? (
              <div className="p-12 text-center" data-testid="safety-assets-empty">
                <Package className="mx-auto mb-3 h-12 w-12 text-muted-foreground" />
                <h3 className="text-lg font-semibold text-foreground">
                  {t('safetyAssets.empty.title', 'No safety assets found')}
                </h3>
                <p className="mt-1 text-sm text-muted-foreground">
                  {t(
                    'safetyAssets.empty.subtitle',
                    'Adjust filters or register equipment via the assets API.',
                  )}
                </p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm" data-testid="safety-assets-table">
                  <thead>
                    <tr className="border-b border-border bg-muted/50">
                      <th className="p-3 text-left font-medium text-muted-foreground">
                        {t('safetyAssets.table.number', 'Number')}
                      </th>
                      <th className="p-3 text-left font-medium text-muted-foreground">
                        {t('safetyAssets.table.name', 'Name')}
                      </th>
                      <th className="p-3 text-left font-medium text-muted-foreground">
                        {t('safetyAssets.table.type', 'Type')}
                      </th>
                      <th className="p-3 text-left font-medium text-muted-foreground">
                        {t('safetyAssets.table.assignment', 'Assignment')}
                      </th>
                      <th className="p-3 text-left font-medium text-muted-foreground">
                        {t('safetyAssets.table.owner', 'Owner')}
                      </th>
                      <th className="p-3 text-left font-medium text-muted-foreground">
                        {t('safetyAssets.table.expiry', 'Expiry')}
                      </th>
                      <th className="p-3 text-left font-medium text-muted-foreground">
                        {t('safetyAssets.table.status', 'Status')}
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {assets.map((asset) => (
                      <tr
                        key={asset.id}
                        className="border-b border-border/50 hover:bg-muted/30"
                        data-testid={`safety-asset-row-${asset.id}`}
                      >
                        <td className="p-3">
                          <Link
                            to={`/safety-assets/${asset.id}`}
                            className="font-medium text-primary hover:underline"
                          >
                            {asset.asset_number}
                          </Link>
                        </td>
                        <td className="p-3 text-foreground">{asset.name}</td>
                        <td className="p-3 text-muted-foreground">
                          {typeNameById.get(asset.asset_type_id) ?? `#${asset.asset_type_id}`}
                        </td>
                        <td className="p-3 text-muted-foreground">
                          {asset.vehicle_reg
                            ? asset.vehicle_reg
                            : asset.location_id
                              ? (locationNameById.get(asset.location_id) ??
                                `Loc #${asset.location_id}`)
                              : (asset.site ?? '—')}
                        </td>
                        <td className="p-3 text-muted-foreground">
                          {asset.owner_user_id != null ? `#${asset.owner_user_id}` : '—'}
                        </td>
                        <td className="p-3 text-muted-foreground">
                          {formatDate(asset.expiry_date)}
                        </td>
                        <td className="p-3">
                          <Badge variant={statusVariant(asset.status)}>{asset.status}</Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {pages > 1 ? (
              <div className="flex items-center justify-end gap-2 border-t border-border px-4 py-3">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                >
                  {t('safetyAssets.pagination.prev', 'Previous')}
                </Button>
                <span className="text-sm text-muted-foreground">
                  {page} / {pages}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page >= pages}
                  onClick={() => setPage((p) => p + 1)}
                >
                  {t('safetyAssets.pagination.next', 'Next')}
                </Button>
              </div>
            ) : null}
          </CardContent>
        </Card>
      )}

      {loading ? (
        <div className="flex items-center gap-2 text-sm text-muted-foreground" aria-live="polite">
          <Loader2 className="h-4 w-4 animate-spin" />
          {t('safetyAssets.loading', 'Loading…')}
        </div>
      ) : null}
    </div>
  )
}
