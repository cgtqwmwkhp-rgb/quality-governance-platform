import type { LucideIcon } from 'lucide-react'
import { BarChart3, CalendarDays, Download, LineChart, Target } from 'lucide-react'
import type {
  PlanetMarkDashboardResponse,
  PlanetMarkReportingYearRecord,
  PlanetMarkScope3Response,
} from '../api/planetMarkClient'

export type PlanetMarkSectionId = 'years' | 'trends' | 'monthly' | 'improve' | 'export'

export const PLANET_MARK_SECTION_IDS: PlanetMarkSectionId[] = [
  'years',
  'trends',
  'monthly',
  'improve',
  'export',
]

export interface PlanetMarkSectionDef {
  id: PlanetMarkSectionId
  labelKey: string
  icon: LucideIcon
}

export const PLANET_MARK_SECTIONS: PlanetMarkSectionDef[] = [
  { id: 'years', labelKey: 'planet_mark.shell.section.years', icon: CalendarDays },
  { id: 'trends', labelKey: 'planet_mark.shell.section.trends', icon: LineChart },
  { id: 'monthly', labelKey: 'planet_mark.shell.section.monthly', icon: BarChart3 },
  { id: 'improve', labelKey: 'planet_mark.shell.section.improve', icon: Target },
  { id: 'export', labelKey: 'planet_mark.shell.section.export', icon: Download },
]

export function parsePlanetMarkSection(
  value: string | null,
): PlanetMarkSectionId {
  if (value && PLANET_MARK_SECTION_IDS.includes(value as PlanetMarkSectionId)) {
    return value as PlanetMarkSectionId
  }
  return 'years'
}

export function sortReportingYearsDesc(
  years: PlanetMarkReportingYearRecord[],
): PlanetMarkReportingYearRecord[] {
  return [...years].sort((a, b) => b.year_number - a.year_number)
}

export function resolveSelectedYearId(
  years: PlanetMarkReportingYearRecord[],
  yearParam: string | null,
): number | null {
  if (years.length === 0) return null
  if (yearParam) {
    const parsed = Number.parseInt(yearParam, 10)
    if (Number.isFinite(parsed) && years.some((y) => y.id === parsed)) {
      return parsed
    }
  }
  return years[0]?.id ?? null
}

export function buildPlanetMarkExportUrl(yearId: number): string {
  return `/api/v1/planet-mark/years/${yearId}/export`
}

export interface PlanetMarkTrendRow {
  label: string
  total: number | null
  perFte: number | null
}

export interface PlanetMarkTrendRowWithDelta extends PlanetMarkTrendRow {
  yoyTotalPercent: number | null
  yoyPerFtePercent: number | null
}

export interface PlanetMarkScopeDelta {
  scopeKey: 'scope_1' | 'scope_2_market' | 'scope_3'
  labelKey: string
  current: number | null
  prior: number | null
  deltaPercent: number | null
}

export interface PlanetMarkCategoryDelta {
  number: number
  name: string
  current: number | null
  prior: number | null
  deltaPercent: number | null
}

export interface PlanetMarkThinPriorYear {
  label: string
  total: number | null
  perFte: number | null
}

export interface PlanetMarkTrendsViewModel {
  historicalRows: PlanetMarkTrendRowWithDelta[]
  yoyPerFtePercent: number | null
  scopeDeltas: PlanetMarkScopeDelta[]
  categoryDeltas: PlanetMarkCategoryDelta[]
  thinPriorYears: PlanetMarkThinPriorYear[]
  showHistoricalTable: boolean
  showComparativePanels: boolean
  showThinPriorYear: boolean
  isEmpty: boolean
}

export function hasRecordedCarbonValue(value: number | null | undefined): value is number {
  return value != null && Number.isFinite(value)
}

export function hasPositiveCarbonTotal(value: number | null | undefined): value is number {
  return hasRecordedCarbonValue(value) && value > 0
}

export function computePercentChange(
  current: number | null | undefined,
  prior: number | null | undefined,
): number | null {
  if (!hasRecordedCarbonValue(current) || !hasRecordedCarbonValue(prior)) {
    return null
  }
  if (prior === 0) {
    return current === 0 ? 0 : null
  }
  return ((current - prior) / prior) * 100
}

export function formatDeltaPercent(value: number | null): string {
  if (value == null || !Number.isFinite(value)) return '—'
  const sign = value > 0 ? '+' : ''
  return `${sign}${value.toFixed(1)}%`
}

export function formatEmissions(value: number | null, fractionDigits = 1): string {
  if (!hasRecordedCarbonValue(value)) return '—'
  return value.toFixed(fractionDigits)
}

export function findPriorReportingYear(
  years: PlanetMarkReportingYearRecord[],
  selectedYearId: number,
): PlanetMarkReportingYearRecord | null {
  const sorted = sortReportingYearsDesc(years)
  const index = sorted.findIndex((year) => year.id === selectedYearId)
  if (index < 0 || index >= sorted.length - 1) return null
  return sorted[index + 1] ?? null
}

export function buildTrendRowsFromDashboard(
  historicalYears: Array<{ label: string; total?: number | null; per_fte?: number | null }> | undefined,
): PlanetMarkTrendRow[] {
  if (!historicalYears?.length) return []
  return historicalYears.map((row) => ({
    label: row.label,
    total: hasPositiveCarbonTotal(row.total) ? row.total : null,
    perFte: hasPositiveCarbonTotal(row.per_fte) ? row.per_fte : null,
  }))
}

export function buildHistoricalRowsWithDeltas(
  rows: PlanetMarkTrendRow[],
): PlanetMarkTrendRowWithDelta[] {
  return rows.map((row, index) => {
    const prior = rows[index + 1]
    return {
      ...row,
      yoyTotalPercent: prior ? computePercentChange(row.total, prior.total) : null,
      yoyPerFtePercent: prior ? computePercentChange(row.perFte, prior.perFte) : null,
    }
  })
}

export function buildScopeDeltas(
  current: PlanetMarkReportingYearRecord,
  prior: PlanetMarkReportingYearRecord | null,
): PlanetMarkScopeDelta[] {
  const scopes: Array<{
    scopeKey: PlanetMarkScopeDelta['scopeKey']
    labelKey: string
    current: number | null | undefined
    prior: number | null | undefined
  }> = [
    {
      scopeKey: 'scope_1',
      labelKey: 'planet_mark.shell.trends.scope_1',
      current: current.scope_1,
      prior: prior?.scope_1,
    },
    {
      scopeKey: 'scope_2_market',
      labelKey: 'planet_mark.shell.trends.scope_2',
      current: current.scope_2_market,
      prior: prior?.scope_2_market,
    },
    {
      scopeKey: 'scope_3',
      labelKey: 'planet_mark.shell.trends.scope_3',
      current: current.scope_3,
      prior: prior?.scope_3,
    },
  ]

  return scopes.map(({ scopeKey, labelKey, current: currentValue, prior: priorValue }) => ({
    scopeKey,
    labelKey,
    current: hasPositiveCarbonTotal(currentValue) ? currentValue : null,
    prior: hasPositiveCarbonTotal(priorValue) ? priorValue : null,
    deltaPercent: computePercentChange(
      hasPositiveCarbonTotal(currentValue) ? currentValue : null,
      hasPositiveCarbonTotal(priorValue) ? priorValue : null,
    ),
  }))
}

export function buildCategoryDeltas(
  current: PlanetMarkScope3Response | null,
  prior: PlanetMarkScope3Response | null,
): PlanetMarkCategoryDelta[] {
  if (!current?.categories?.length) return []

  const priorByNumber = new Map(
    (prior?.categories ?? []).map((category) => [category.number, category]),
  )

  return current.categories
    .filter((category) => category.is_measured)
    .map((category) => {
      const priorCategory = priorByNumber.get(category.number)
      const currentValue = hasPositiveCarbonTotal(category.total_co2e) ? category.total_co2e : null
      const priorValue =
        priorCategory && hasPositiveCarbonTotal(priorCategory.total_co2e)
          ? priorCategory.total_co2e
          : null

      return {
        number: category.number,
        name: category.name,
        current: currentValue,
        prior: priorValue,
        deltaPercent: computePercentChange(currentValue, priorValue),
      }
    })
    .filter((row) => row.current != null || row.prior != null)
}

export function buildThinPriorYears(
  years: PlanetMarkReportingYearRecord[],
  selectedYearId: number | null,
): PlanetMarkThinPriorYear[] {
  if (!selectedYearId) {
    return sortReportingYearsDesc(years).slice(1).map((year) => ({
      label: year.year_label,
      total: hasPositiveCarbonTotal(year.total_emissions) ? year.total_emissions : null,
      perFte: hasPositiveCarbonTotal(year.emissions_per_fte) ? year.emissions_per_fte : null,
    }))
  }

  return sortReportingYearsDesc(years)
    .filter((year) => year.id !== selectedYearId)
    .map((year) => ({
      label: year.year_label,
      total: hasPositiveCarbonTotal(year.total_emissions) ? year.total_emissions : null,
      perFte: hasPositiveCarbonTotal(year.emissions_per_fte) ? year.emissions_per_fte : null,
    }))
}

export function buildPlanetMarkTrendsViewModel(input: {
  dashboard: PlanetMarkDashboardResponse | null
  years: PlanetMarkReportingYearRecord[]
  selectedYearId: number | null
  scope3Current: PlanetMarkScope3Response | null
  scope3Prior: PlanetMarkScope3Response | null
}): PlanetMarkTrendsViewModel {
  const { dashboard, years, selectedYearId, scope3Current, scope3Prior } = input
  const historicalRows = buildHistoricalRowsWithDeltas(
    buildTrendRowsFromDashboard(dashboard?.historical_years),
  )

  const selectedYear = years.find((year) => year.id === selectedYearId) ?? null
  const priorYear = selectedYearId != null ? findPriorReportingYear(years, selectedYearId) : null

  const yoyPerFtePercent =
    dashboard?.current_year?.id === selectedYearId
      ? (dashboard.current_year.yoy_change_percent ?? null)
      : selectedYear && priorYear
        ? computePercentChange(selectedYear.emissions_per_fte, priorYear.emissions_per_fte)
        : null

  const scopeDeltas = selectedYear ? buildScopeDeltas(selectedYear, priorYear) : []
  const categoryDeltas = buildCategoryDeltas(scope3Current, scope3Prior)

  const showHistoricalTable = historicalRows.some(
    (row) => hasPositiveCarbonTotal(row.total) || hasPositiveCarbonTotal(row.perFte),
  )

  const showComparativePanels =
    (yoyPerFtePercent != null && Number.isFinite(yoyPerFtePercent)) ||
    scopeDeltas.some(
      (delta) =>
        hasPositiveCarbonTotal(delta.current) && hasPositiveCarbonTotal(delta.prior),
    ) ||
    categoryDeltas.some(
      (delta) =>
        hasPositiveCarbonTotal(delta.current) && hasPositiveCarbonTotal(delta.prior),
    )

  const thinPriorYears = buildThinPriorYears(years, selectedYearId)
  const showThinPriorYear =
    years.length > 1 && !showHistoricalTable && !showComparativePanels && thinPriorYears.length > 0

  return {
    historicalRows,
    yoyPerFtePercent,
    scopeDeltas,
    categoryDeltas,
    thinPriorYears,
    showHistoricalTable,
    showComparativePanels,
    showThinPriorYear,
    isEmpty: !showHistoricalTable && !showComparativePanels && !showThinPriorYear,
  }
}

export function hasTrendData(rows: PlanetMarkTrendRow[]): boolean {
  return rows.some(
    (row) => hasPositiveCarbonTotal(row.total) || hasPositiveCarbonTotal(row.perFte),
  )
}
