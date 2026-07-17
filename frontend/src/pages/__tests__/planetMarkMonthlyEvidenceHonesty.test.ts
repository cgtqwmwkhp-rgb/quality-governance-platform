import { describe, expect, it } from 'vitest'
import {
  PM_E4_MONTHLY_CAPABILITIES,
  buildMonthlyEvidenceHonestyViewModel,
} from '../planetMarkMonthlyEvidenceHonesty'

describe('planetMarkMonthlyEvidenceHonesty PM-E4', () => {
  it('exposes year evidence, monthly ingest, and forecast capabilities', () => {
    expect(PM_E4_MONTHLY_CAPABILITIES).toEqual([
      'year_evidence_api',
      'monthly_emission_ingest',
      'forecast_vs_target',
    ])
  })

  it('marks year evidence live when a reporting year is selected', () => {
    const vm = buildMonthlyEvidenceHonestyViewModel({ hasSelectedYear: true })
    expect(vm.showSelectYearPrompt).toBe(false)
    expect(vm.yearEvidenceUploadAvailable).toBe(true)
    expect(vm.forecastFollowOn).toBe(true)
    expect(vm.capabilities).toEqual([
      { id: 'year_evidence_api', status: 'live_api' },
      { id: 'monthly_emission_ingest', status: 'shell_only' },
      { id: 'forecast_vs_target', status: 'follow_on' },
    ])
  })

  it('prompts for year selection when none is selected', () => {
    const vm = buildMonthlyEvidenceHonestyViewModel({ hasSelectedYear: false })
    expect(vm.showSelectYearPrompt).toBe(true)
    expect(vm.yearEvidenceUploadAvailable).toBe(false)
    expect(vm.capabilities[0]).toEqual({ id: 'year_evidence_api', status: 'shell_only' })
  })
})
