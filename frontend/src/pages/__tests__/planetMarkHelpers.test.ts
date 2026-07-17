import { describe, expect, it } from 'vitest'
import {
  PLANET_MARK_SECTION_IDS,
  buildPlanetMarkExportUrl,
  buildTrendRowsFromDashboard,
  hasTrendData,
  parsePlanetMarkSection,
  resolveSelectedYearId,
  sortReportingYearsDesc,
} from '../planetMarkHelpers'

describe('planetMarkHelpers', () => {
  it('defaults invalid section params to years', () => {
    expect(parsePlanetMarkSection(null)).toBe('years')
    expect(parsePlanetMarkSection('unknown')).toBe('years')
    expect(parsePlanetMarkSection('trends')).toBe('trends')
  })

  it('sorts reporting years descending by year_number', () => {
    const sorted = sortReportingYearsDesc([
      {
        id: 1,
        year_label: 'YE2024',
        year_number: 2024,
        period: '2024',
        average_fte: 1,
        total_emissions: 10,
        emissions_per_fte: 10,
        scope_1: 1,
        scope_2_market: 1,
        scope_3: 1,
        data_quality: 8,
        certification_status: 'draft',
        is_baseline: false,
      },
      {
        id: 2,
        year_label: 'YE2026',
        year_number: 2026,
        period: '2026',
        average_fte: 1,
        total_emissions: 8,
        emissions_per_fte: 8,
        scope_1: 1,
        scope_2_market: 1,
        scope_3: 1,
        data_quality: 10,
        certification_status: 'draft',
        is_baseline: false,
      },
    ])
    expect(sorted.map((y) => y.year_number)).toEqual([2026, 2024])
  })

  it('resolves selected year from param or first sorted year', () => {
    const years = sortReportingYearsDesc([
      {
        id: 10,
        year_label: 'YE2025',
        year_number: 2025,
        period: '2025',
        average_fte: 1,
        total_emissions: 0,
        emissions_per_fte: 0,
        scope_1: 0,
        scope_2_market: 0,
        scope_3: 0,
        data_quality: 0,
        certification_status: 'draft',
        is_baseline: false,
      },
      {
        id: 11,
        year_label: 'YE2026',
        year_number: 2026,
        period: '2026',
        average_fte: 1,
        total_emissions: 0,
        emissions_per_fte: 0,
        scope_1: 0,
        scope_2_market: 0,
        scope_3: 0,
        data_quality: 0,
        certification_status: 'draft',
        is_baseline: false,
      },
    ])
    expect(resolveSelectedYearId(years, null)).toBe(11)
    expect(resolveSelectedYearId(years, '10')).toBe(10)
    expect(resolveSelectedYearId(years, '999')).toBe(11)
    expect(resolveSelectedYearId([], '1')).toBeNull()
  })

  it('builds export URL for a reporting year', () => {
    expect(buildPlanetMarkExportUrl(42)).toBe('/api/v1/planet-mark/years/42/export')
  })

  it('maps dashboard historical years to trend rows', () => {
    const rows = buildTrendRowsFromDashboard([
      { label: 'YE2025', total: 20, per_fte: 1.2 },
      { label: 'YE2026', total: 18, per_fte: 1.0 },
    ])
    expect(rows).toHaveLength(2)
    expect(hasTrendData(rows)).toBe(true)
    expect(hasTrendData([])).toBe(false)
  })

  it('exposes five shell section ids', () => {
    expect(PLANET_MARK_SECTION_IDS).toEqual(['years', 'trends', 'monthly', 'improve', 'export'])
  })
})
