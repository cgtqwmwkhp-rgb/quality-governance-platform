import { describe, expect, it } from 'vitest'
import {
  PLANET_MARK_SECTION_IDS,
  buildCategoryDeltas,
  buildHistoricalRowsWithDeltas,
  buildHotspotInitiatives,
  buildPlanetMarkExportPack,
  buildPlanetMarkExportUrl,
  buildPlanetMarkTrendsViewModel,
  buildPlanetMarkYearsViewModel,
  buildScopeDeltas,
  buildTrendRowsFromDashboard,
  computePercentChange,
  findPriorReportingYear,
  formatDeltaPercent,
  formatEmissions,
  hasRecordedCarbonValue,
  hasTrendData,
  initiativeToCreateActionPayload,
  parsePlanetMarkSection,
  resolveSelectedYearId,
  sortReportingYearsDesc,
} from '../planetMarkHelpers'

const baseYear = {
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
}

describe('planetMarkHelpers', () => {
  it('defaults invalid section params to years', () => {
    expect(parsePlanetMarkSection(null)).toBe('years')
    expect(parsePlanetMarkSection('unknown')).toBe('years')
    expect(parsePlanetMarkSection('trends')).toBe('trends')
  })

  it('sorts reporting years descending by year_number', () => {
    const sorted = sortReportingYearsDesc([
      baseYear,
      {
        ...baseYear,
        id: 2,
        year_label: 'YE2026',
        year_number: 2026,
        total_emissions: 8,
        emissions_per_fte: 8,
      },
    ])
    expect(sorted.map((y) => y.year_number)).toEqual([2026, 2024])
  })

  it('resolves selected year from param or first sorted year', () => {
    const years = sortReportingYearsDesc([
      { ...baseYear, id: 10, year_label: 'YE2025', year_number: 2025 },
      { ...baseYear, id: 11, year_label: 'YE2026', year_number: 2026 },
    ])
    expect(resolveSelectedYearId(years, null)).toBe(11)
    expect(resolveSelectedYearId(years, '10')).toBe(10)
    expect(resolveSelectedYearId(years, '999')).toBe(11)
    expect(resolveSelectedYearId([], '1')).toBeNull()
  })

  it('builds export URL for a reporting year', () => {
    expect(buildPlanetMarkExportUrl(42)).toBe('/api/v1/planet-mark/years/42/export')
  })

  it('maps dashboard historical years without inventing totals', () => {
    const rows = buildTrendRowsFromDashboard([
      { label: 'YE2025', total: 20, per_fte: 1.2 },
      { label: 'YE2026', total: null, per_fte: null },
    ])
    expect(rows).toEqual([
      { label: 'YE2025', total: 20, perFte: 1.2 },
      { label: 'YE2026', total: null, perFte: null },
    ])
    expect(hasTrendData(rows)).toBe(true)
    expect(hasTrendData([])).toBe(false)
  })

  it('computes YoY deltas only when both sides are recorded', () => {
    expect(computePercentChange(18, 20)).toBeCloseTo(-10)
    expect(computePercentChange(null, 20)).toBeNull()
    expect(formatDeltaPercent(-10)).toBe('-10.0%')
    expect(formatEmissions(null)).toBe('—')
    expect(hasRecordedCarbonValue(0)).toBe(true)
  })

  it('builds historical rows with adjacent YoY deltas', () => {
    const rows = buildHistoricalRowsWithDeltas([
      { label: 'YE2026', total: 18, perFte: 1.0 },
      { label: 'YE2025', total: 20, perFte: 1.2 },
    ])
    expect(rows[0]?.yoyTotalPercent).toBeCloseTo(-10)
    expect(rows[1]?.yoyTotalPercent).toBeNull()
  })

  it('finds the prior reporting year for scope comparisons', () => {
    const years = sortReportingYearsDesc([
      { ...baseYear, id: 1, year_number: 2026 },
      { ...baseYear, id: 2, year_number: 2025, scope_1: 5 },
    ])
    expect(findPriorReportingYear(years, 1)?.id).toBe(2)
    expect(buildScopeDeltas(years[0]!, years[1]!)[0]?.deltaPercent).toBeCloseTo(-80)
  })

  it('builds category deltas from measured scope 3 categories only', () => {
    const deltas = buildCategoryDeltas(
      {
        year_id: 1,
        measured_count: 1,
        total_co2e: 3,
        categories: [
          {
            number: 1,
            name: 'Purchased goods',
            is_measured: true,
            total_co2e: 3,
            percentage: 100,
          },
          {
            number: 2,
            name: 'Capital goods',
            is_measured: false,
            total_co2e: 0,
            percentage: 0,
          },
        ],
      },
      {
        year_id: 2,
        measured_count: 1,
        total_co2e: 2,
        categories: [
          {
            number: 1,
            name: 'Purchased goods',
            is_measured: true,
            total_co2e: 2,
            percentage: 100,
          },
        ],
      },
    )
    expect(deltas).toHaveLength(1)
    expect(deltas[0]?.deltaPercent).toBeCloseTo(50)
  })

  it('builds an honest trends view model with thin prior years when totals are missing', () => {
    const vm = buildPlanetMarkTrendsViewModel({
      dashboard: {
        current_year: {
          id: 1,
          label: 'YE2026',
          total_emissions: 0,
          emissions_per_fte: 0,
          fte: 1,
          yoy_change_percent: null,
          on_track: false,
        },
        emissions_breakdown: {
          scope_1: { value: 0, label: 'Direct' },
          scope_2: { value: 0, label: 'Indirect' },
          scope_3: { value: 0, label: 'Value Chain' },
        },
        data_quality: { scope_1_2: 0, scope_3: 0, target: 12 },
        certification: { status: 'draft', expiry_date: null },
        actions: { total: 0, completed: 0, overdue: 0 },
        targets: { reduction_percent: null, target_per_fte: null },
        historical_years: [],
      },
      years: [
        {
          ...baseYear,
          id: 1,
          year_label: 'YE2026',
          year_number: 2026,
          total_emissions: 0,
          scope_1: 0,
          scope_2_market: 0,
          scope_3: 0,
        },
        {
          ...baseYear,
          id: 2,
          year_label: 'YE2025',
          year_number: 2025,
          total_emissions: 0,
          scope_1: 0,
          scope_2_market: 0,
          scope_3: 0,
        },
      ],
      selectedYearId: 1,
      scope3Current: null,
      scope3Prior: null,
    })

    expect(vm.showHistoricalTable).toBe(false)
    expect(vm.showComparativePanels).toBe(false)
    expect(vm.showThinPriorYear).toBe(true)
    expect(vm.isEmpty).toBe(false)
    expect(vm.thinPriorYears).toHaveLength(1)
  })

  it('exposes five shell section ids', () => {
    expect(PLANET_MARK_SECTION_IDS).toEqual(['years', 'trends', 'monthly', 'improve', 'export'])
  })

  it('builds years view model with MS XLSX ingest panel when selected year lacks carbon', () => {
    const vm = buildPlanetMarkYearsViewModel({
      years: [
        {
          ...baseYear,
          id: 1,
          year_label: 'YE2026',
          year_number: 2026,
          total_emissions: 0,
          emissions_per_fte: 0,
        },
        {
          ...baseYear,
          id: 2,
          year_label: 'YE2025',
          year_number: 2025,
          total_emissions: 0,
          emissions_per_fte: 0,
        },
      ],
      selectedYearId: 1,
    })

    expect(vm.showMsXlsxIngestPanel).toBe(true)
    expect(vm.showMsXlsxIngestPlaceholder).toBe(true)
    expect(vm.selectedHasIngestedCarbon).toBe(false)
    expect(vm.priorYearsWithoutIngest).toHaveLength(1)
    expect(vm.allYearRows.every((row) => !row.hasIngestedCarbon)).toBe(true)
  })

  it('keeps MS XLSX ingest panel when selected year already has recorded carbon totals', () => {
    const vm = buildPlanetMarkYearsViewModel({
      years: [{ ...baseYear, id: 1, year_label: 'YE2026', year_number: 2026 }],
      selectedYearId: 1,
    })

    expect(vm.showMsXlsxIngestPanel).toBe(true)
    expect(vm.selectedHasIngestedCarbon).toBe(true)
    expect(vm.allYearRows[0]?.total).toBe(10)
  })
})

describe('planetMarkHelpers PM-W3 export + initiatives', () => {
  it('ranks hotspot initiatives by footprint share', () => {
    const initiatives = buildHotspotInitiatives({
      year_id: 1,
      measured_count: 2,
      total_co2e: 100,
      categories: [
        {
          number: 3,
          name: 'Fuel',
          is_measured: true,
          total_co2e: 60,
          percentage: 60,
        },
        {
          number: 1,
          name: 'Purchased goods',
          is_measured: true,
          total_co2e: 15,
          percentage: 15,
        },
        {
          number: 2,
          name: 'Empty',
          is_measured: true,
          total_co2e: 0,
          percentage: 0,
        },
      ],
    })
    expect(initiatives).toHaveLength(2)
    expect(initiatives[0]?.categoryName).toBe('Fuel')
    expect(initiatives[0]?.suggestedReductionPercent).toBe(10)
    expect(initiatives[1]?.suggestedReductionPercent).toBe(5)
  })

  it('builds JSON export pack with honesty notes', () => {
    const pack = buildPlanetMarkExportPack({
      year: {
        ...{
          id: 1,
          year_label: 'YE2026',
          year_number: 2026,
          period: '2026',
          average_fte: 10,
          total_emissions: 22,
          emissions_per_fte: 2.2,
          scope_1: 10,
          scope_2_market: 5,
          scope_3: 7,
          data_quality: 12,
          certification_status: 'in_progress',
          is_baseline: false,
        },
      },
      scope3: null,
      actions: [],
      initiatives: [],
    })
    expect(pack.filename).toContain('planet-mark-export-YE2026')
    const body = JSON.parse(pack.body)
    expect(body.export_kind).toBe('json_pack')
    expect(body.pdf_note).toMatch(/PDF/)
    expect(body.xlsx_note).toMatch(/xlsx/i)
  })

  it('maps initiative to createAction payload', () => {
    const payload = initiativeToCreateActionPayload({
      id: 'cat-3',
      title: 'Reduce Fuel',
      categoryNumber: 3,
      categoryName: 'Fuel',
      footprintPercent: 60,
      currentCo2e: 60,
      suggestedReductionPercent: 10,
      expectedReductionCo2e: 6,
      specific: 'specific',
      measurable: 'measurable',
    })
    expect(payload.action_title).toBe('Reduce Fuel')
    expect(payload.expected_reduction_pct).toBe(10)
    expect(payload.achievable_owner).toBe('Unassigned')
  })

  it('keeps legacy export URL helper for reference', () => {
    expect(buildPlanetMarkExportUrl(42)).toBe('/api/v1/planet-mark/years/42/export')
  })
})
