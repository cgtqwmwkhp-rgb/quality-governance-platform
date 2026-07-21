/**
 * Pure helpers for the CES / Safety Asset Register board.
 * OK SSOT mirrors Training (`compliant` | `due_soon`): active + not overdue.
 */
import type { SafetyAsset } from '../../api/safetyAssetsClient'

export type AssetBoardView = 'assets' | 'engineer' | 'vehicle' | 'type' | 'upload'

export type AssetHeroBand =
  | 'all'
  | 'overdue'
  | 'due_30'
  | 'due_60'
  | 'due_90'
  | 'in_date'
  | 'quarantined'
  | 'decommissioned'

export type AssetHorizon = 'overdue' | 'due_30' | 'due_60' | 'due_90' | 'in_date' | 'none'

export type SortDirection = 'asc' | 'desc'

const DAY_MS = 24 * 60 * 60 * 1000

export const HERO_BANDS: { id: AssetHeroBand; label: string }[] = [
  { id: 'all', label: 'All' },
  { id: 'overdue', label: 'Overdue' },
  { id: 'due_30', label: 'Due 30d' },
  { id: 'due_60', label: 'Due 60d' },
  { id: 'due_90', label: 'Due 90d' },
  { id: 'in_date', label: 'In date' },
  { id: 'quarantined', label: 'Fail / quarantine' },
  { id: 'decommissioned', label: 'Removed' },
]

export const BOARD_VIEWS: { id: AssetBoardView; label: string }[] = [
  { id: 'assets', label: 'Assets' },
  { id: 'engineer', label: 'By engineer' },
  { id: 'vehicle', label: 'By vehicle' },
  { id: 'type', label: 'By type' },
  { id: 'upload', label: 'CES upload' },
]

function startOfDay(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate())
}

export function parseExpiryDate(value?: string | null): Date | null {
  if (!value) return null
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value)
  if (match) {
    const [, y, m, d] = match
    return new Date(Number(y), Number(m) - 1, Number(d))
  }
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return null
  return startOfDay(parsed)
}

export function horizonForAsset(asset: SafetyAsset, today: Date = new Date()): AssetHorizon {
  const due = parseExpiryDate(asset.expiry_date)
  if (!due) return 'none'
  const daysAway = Math.round((due.getTime() - startOfDay(today).getTime()) / DAY_MS)
  if (daysAway < 0) return 'overdue'
  if (daysAway <= 30) return 'due_30'
  if (daysAway <= 60) return 'due_60'
  if (daysAway <= 90) return 'due_90'
  return 'in_date'
}

/** Training-style OK: in service and not past expiry (due-soon bands count as OK). */
export function isOkAsset(asset: SafetyAsset, today: Date = new Date()): boolean {
  if ((asset.status || '').toLowerCase() !== 'active') return false
  const horizon = horizonForAsset(asset, today)
  return horizon === 'in_date' || horizon === 'due_30' || horizon === 'due_60' || horizon === 'due_90'
}

export function isOverdueAsset(asset: SafetyAsset, today: Date = new Date()): boolean {
  return horizonForAsset(asset, today) === 'overdue'
}

export type AssetHeroCounts = Record<AssetHeroBand, number>

export function computeHeroCounts(assets: SafetyAsset[], today: Date = new Date()): AssetHeroCounts {
  const counts: AssetHeroCounts = {
    all: assets.length,
    overdue: 0,
    due_30: 0,
    due_60: 0,
    due_90: 0,
    in_date: 0,
    quarantined: 0,
    decommissioned: 0,
  }
  for (const asset of assets) {
    const status = (asset.status || '').toLowerCase()
    if (status === 'quarantined') counts.quarantined += 1
    if (status === 'decommissioned') counts.decommissioned += 1
    const horizon = horizonForAsset(asset, today)
    if (horizon === 'overdue') counts.overdue += 1
    else if (horizon === 'due_30') counts.due_30 += 1
    else if (horizon === 'due_60') counts.due_60 += 1
    else if (horizon === 'due_90') counts.due_90 += 1
    else if (horizon === 'in_date') counts.in_date += 1
  }
  return counts
}

export function assetMatchesHeroBand(
  asset: SafetyAsset,
  band: AssetHeroBand,
  today: Date = new Date(),
): boolean {
  if (band === 'all') return true
  if (band === 'quarantined') return (asset.status || '').toLowerCase() === 'quarantined'
  if (band === 'decommissioned') return (asset.status || '').toLowerCase() === 'decommissioned'
  return horizonForAsset(asset, today) === band
}

export type AssetEntityRollup = {
  key: string
  label: string
  total: number
  ok: number
  overdue: number
  quarantined: number
  pct: number
  assets: SafetyAsset[]
}

function metricRollup(label: string, key: string, assets: SafetyAsset[], today: Date): AssetEntityRollup {
  const total = assets.length
  const ok = assets.filter((a) => isOkAsset(a, today)).length
  const overdue = assets.filter((a) => isOverdueAsset(a, today)).length
  const quarantined = assets.filter((a) => (a.status || '').toLowerCase() === 'quarantined').length
  return {
    key,
    label,
    total,
    ok,
    overdue,
    quarantined,
    pct: total ? Math.round((100 * ok) / total) : 0,
    assets,
  }
}

export function buildEngineerRollups(
  assets: SafetyAsset[],
  ownerNames: Map<number, string>,
  today: Date = new Date(),
): AssetEntityRollup[] {
  const groups = new Map<string, SafetyAsset[]>()
  for (const asset of assets) {
    const ownerId = asset.owner_user_id
    const key = ownerId == null ? 'unassigned' : `user:${ownerId}`
    const bucket = groups.get(key)
    if (bucket) bucket.push(asset)
    else groups.set(key, [asset])
  }
  return [...groups.entries()]
    .map(([key, rows]) => {
      const ownerId = key.startsWith('user:') ? Number(key.slice(5)) : null
      const label =
        ownerId == null
          ? 'Unassigned'
          : ownerNames.get(ownerId) || `User #${ownerId}`
      return metricRollup(label, key, rows, today)
    })
    .sort((a, b) => b.overdue - a.overdue || a.label.localeCompare(b.label))
}

export function buildVehicleRollups(
  assets: SafetyAsset[],
  today: Date = new Date(),
): AssetEntityRollup[] {
  const groups = new Map<string, SafetyAsset[]>()
  for (const asset of assets) {
    const reg = (asset.vehicle_reg || '').trim().toUpperCase()
    const key = reg || 'no-vehicle'
    const bucket = groups.get(key)
    if (bucket) bucket.push(asset)
    else groups.set(key, [asset])
  }
  return [...groups.entries()]
    .map(([key, rows]) =>
      metricRollup(key === 'no-vehicle' ? 'No vehicle' : key, key, rows, today),
    )
    .sort((a, b) => b.overdue - a.overdue || a.label.localeCompare(b.label))
}

export function buildTypeRollups(
  assets: SafetyAsset[],
  typeNames: Map<number, string>,
  today: Date = new Date(),
): AssetEntityRollup[] {
  const groups = new Map<string, SafetyAsset[]>()
  for (const asset of assets) {
    const key = `type:${asset.asset_type_id}`
    const bucket = groups.get(key)
    if (bucket) bucket.push(asset)
    else groups.set(key, [asset])
  }
  return [...groups.entries()]
    .map(([key, rows]) => {
      const typeId = Number(key.slice(5))
      return metricRollup(typeNames.get(typeId) || `Type #${typeId}`, key, rows, today)
    })
    .sort((a, b) => b.overdue - a.overdue || a.label.localeCompare(b.label))
}

export type EntityRollupSortKey = 'label' | 'total' | 'ok' | 'overdue' | 'quarantined' | 'pct'

export type EntityRollupColumnFilters = {
  label: string
  total: string
  ok: string
  overdue: string
  quarantined: string
  pct: string
}

export const EMPTY_ENTITY_ROLLUP_FILTERS: EntityRollupColumnFilters = {
  label: '',
  total: '',
  ok: '',
  overdue: '',
  quarantined: '',
  pct: '',
}

function matchesTextFilter(value: string | null | undefined, filter: string): boolean {
  const q = filter.trim().toLowerCase()
  if (!q) return true
  return (value || '').toLowerCase().includes(q)
}

function matchesExactNumberFilter(value: number, filter: string): boolean {
  const q = filter.trim()
  if (!q) return true
  const n = Number(q)
  if (!Number.isFinite(n)) return String(value).includes(q)
  return value === n
}

export function filterEntityRollups(
  rollups: AssetEntityRollup[],
  filters: EntityRollupColumnFilters,
): AssetEntityRollup[] {
  return rollups.filter(
    (row) =>
      matchesTextFilter(row.label, filters.label) &&
      matchesExactNumberFilter(row.total, filters.total) &&
      matchesExactNumberFilter(row.ok, filters.ok) &&
      matchesExactNumberFilter(row.overdue, filters.overdue) &&
      matchesExactNumberFilter(row.quarantined, filters.quarantined) &&
      matchesExactNumberFilter(row.pct, filters.pct),
  )
}

export function sortEntityRollups(
  rollups: AssetEntityRollup[],
  sortKey: EntityRollupSortKey,
  sortDir: SortDirection,
): AssetEntityRollup[] {
  const dir = sortDir === 'asc' ? 1 : -1
  return [...rollups].sort((a, b) => {
    let cmp = 0
    switch (sortKey) {
      case 'label':
        cmp = a.label.localeCompare(b.label, undefined, { sensitivity: 'base' })
        break
      case 'total':
        cmp = a.total - b.total
        break
      case 'ok':
        cmp = a.ok - b.ok
        break
      case 'overdue':
        cmp = a.overdue - b.overdue
        break
      case 'quarantined':
        cmp = a.quarantined - b.quarantined
        break
      case 'pct':
        cmp = a.pct - b.pct
        break
      default:
        cmp = 0
    }
    if (cmp !== 0) return cmp * dir
    return a.label.localeCompare(b.label)
  })
}

export type AssetRowSortKey =
  | 'serial'
  | 'name'
  | 'type'
  | 'owner'
  | 'vehicle'
  | 'site'
  | 'expiry'
  | 'status'

export type AssetRowColumnFilters = {
  serial: string
  name: string
  type: string
  owner: string
  vehicle: string
  site: string
  expiry: string
  status: string
}

export const EMPTY_ASSET_ROW_FILTERS: AssetRowColumnFilters = {
  serial: '',
  name: '',
  type: '',
  owner: '',
  vehicle: '',
  site: '',
  expiry: '',
  status: '',
}

export function ownerLabel(
  asset: SafetyAsset,
  ownerNames: Map<number, string>,
): string {
  if (asset.owner_user_id == null) return '—'
  return ownerNames.get(asset.owner_user_id) || `User #${asset.owner_user_id}`
}

export function filterAssetRows(
  assets: SafetyAsset[],
  filters: AssetRowColumnFilters,
  typeNames: Map<number, string>,
  ownerNames: Map<number, string>,
): SafetyAsset[] {
  return assets.filter((asset) => {
    const type = typeNames.get(asset.asset_type_id) || ''
    const owner = ownerLabel(asset, ownerNames)
    const site = asset.site || ''
    const expiry = asset.expiry_date || ''
    return (
      matchesTextFilter(asset.serial_number || asset.asset_number, filters.serial) &&
      matchesTextFilter(asset.name, filters.name) &&
      matchesTextFilter(type, filters.type) &&
      matchesTextFilter(owner, filters.owner) &&
      matchesTextFilter(asset.vehicle_reg, filters.vehicle) &&
      matchesTextFilter(site, filters.site) &&
      matchesTextFilter(expiry, filters.expiry) &&
      matchesTextFilter(asset.status, filters.status)
    )
  })
}

export function sortAssetRows(
  assets: SafetyAsset[],
  sortKey: AssetRowSortKey,
  sortDir: SortDirection,
  typeNames: Map<number, string>,
  ownerNames: Map<number, string>,
): SafetyAsset[] {
  const dir = sortDir === 'asc' ? 1 : -1
  return [...assets].sort((a, b) => {
    let cmp = 0
    switch (sortKey) {
      case 'serial':
        cmp = (a.serial_number || a.asset_number || '').localeCompare(
          b.serial_number || b.asset_number || '',
          undefined,
          { sensitivity: 'base' },
        )
        break
      case 'name':
        cmp = (a.name || '').localeCompare(b.name || '', undefined, { sensitivity: 'base' })
        break
      case 'type':
        cmp = (typeNames.get(a.asset_type_id) || '').localeCompare(
          typeNames.get(b.asset_type_id) || '',
          undefined,
          { sensitivity: 'base' },
        )
        break
      case 'owner':
        cmp = ownerLabel(a, ownerNames).localeCompare(ownerLabel(b, ownerNames), undefined, {
          sensitivity: 'base',
        })
        break
      case 'vehicle':
        cmp = (a.vehicle_reg || '').localeCompare(b.vehicle_reg || '', undefined, {
          sensitivity: 'base',
        })
        break
      case 'site':
        cmp = (a.site || '').localeCompare(b.site || '', undefined, { sensitivity: 'base' })
        break
      case 'expiry':
        cmp = (a.expiry_date || '').localeCompare(b.expiry_date || '')
        break
      case 'status':
        cmp = (a.status || '').localeCompare(b.status || '', undefined, { sensitivity: 'base' })
        break
      default:
        cmp = 0
    }
    if (cmp !== 0) return cmp * dir
    return a.id - b.id
  })
}

export function bandLabel(asset: SafetyAsset, today: Date = new Date()): string {
  const status = (asset.status || '').toLowerCase()
  if (status === 'quarantined') return 'Fail'
  if (status === 'decommissioned') return 'Removed'
  const horizon = horizonForAsset(asset, today)
  switch (horizon) {
    case 'overdue':
      return 'Overdue'
    case 'due_30':
      return 'Due 30d'
    case 'due_60':
      return 'Due 60d'
    case 'due_90':
      return 'Due 90d'
    case 'in_date':
      return 'In date'
    default:
      return '—'
  }
}
