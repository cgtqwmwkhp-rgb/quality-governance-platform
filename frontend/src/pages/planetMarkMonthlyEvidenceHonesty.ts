/** PM-E4 — Monthly evidence upload + forecast follow-on honesty helpers. */

export const PM_E4_MONTHLY_CAPABILITIES = [
  'year_evidence_api',
  'monthly_emission_ingest',
  'forecast_vs_target',
] as const

export type PmE4MonthlyCapability = (typeof PM_E4_MONTHLY_CAPABILITIES)[number]

export type PmE4CapabilityStatus = 'live_api' | 'shell_only' | 'follow_on'

export interface PmE4MonthlyCapabilityRow {
  id: PmE4MonthlyCapability
  status: PmE4CapabilityStatus
}

export interface PmE4MonthlyEvidenceViewModel {
  hasSelectedYear: boolean
  capabilities: PmE4MonthlyCapabilityRow[]
  /** Year-level evidence upload exists on the API; monthly series UI is shell-only. */
  yearEvidenceUploadAvailable: boolean
  /** Forecast vs 5% S1&2 commitment is not wired on Monthly. */
  forecastFollowOn: boolean
  showSelectYearPrompt: boolean
}

export function buildMonthlyEvidenceHonestyViewModel(opts: {
  hasSelectedYear: boolean
}): PmE4MonthlyEvidenceViewModel {
  const { hasSelectedYear } = opts
  return {
    hasSelectedYear,
    showSelectYearPrompt: !hasSelectedYear,
    yearEvidenceUploadAvailable: hasSelectedYear,
    forecastFollowOn: true,
    capabilities: [
      { id: 'year_evidence_api', status: hasSelectedYear ? 'live_api' : 'shell_only' },
      { id: 'monthly_emission_ingest', status: 'shell_only' },
      { id: 'forecast_vs_target', status: 'follow_on' },
    ],
  }
}
