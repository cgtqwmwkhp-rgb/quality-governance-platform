import type { LucideIcon } from 'lucide-react'
import { BarChart3, CalendarDays, Download, LineChart, Target } from 'lucide-react'
import type { PlanetMarkReportingYearRecord } from '../api/planetMarkClient'

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

export function buildTrendRowsFromDashboard(
  historicalYears: Array<{ label: string; total: number; per_fte: number }> | undefined,
): PlanetMarkTrendRow[] {
  if (!historicalYears?.length) return []
  return historicalYears.map((row) => ({
    label: row.label,
    total: row.total,
    perFte: row.per_fte,
  }))
}

export function hasTrendData(rows: PlanetMarkTrendRow[]): boolean {
  return rows.some((row) => row.total != null || row.perFte != null)
}
