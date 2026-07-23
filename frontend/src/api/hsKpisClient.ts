import type { AxiosInstance } from 'axios'

export interface HsKpiYear {
  reporting_year: number
  period_start: string
  period_end: string
  average_fte: number
  hours_per_fte_year?: number
  manual_hours?: number | null
  hours: number
  hours_source?: 'manual' | 'calculated'
  injuries: number
  near_misses: number
  rtas: number
  complaints: number
  ltis: number
  riddor: number
  ltifr: number
  afr: number
  rate_unit: string
}

export interface HsKpiSummary {
  rate_unit: string
  by_year: HsKpiYear[]
}

export interface HsReportingPeriodRow {
  id: number
  reporting_year: number
  period_start: string
  period_end: string
  average_fte: number
  hours_per_fte_year: number
  manual_hours: number | null
  hours: number
  hours_source: 'manual' | 'calculated'
}

export interface HsReportingPeriodInput {
  reporting_year: number
  period_start: string
  period_end: string
  average_fte: number
  hours_per_fte_year: number
  manual_hours: number | null
}

export interface HsExcelImportDryRun {
  counts: Record<string, number>
  warnings: string[]
  rows: Array<Record<string, unknown>>
  total_rows: number
}

export interface HsExcelImportCommit {
  created: Record<string, number>
  warnings: string[]
}

export function createHsKpisApi(api: AxiosInstance) {
  return {
    getSummary: () => api.get<HsKpiSummary>('/api/v1/hs-kpis/summary'),
    listPeriods: () => api.get<{ items: HsReportingPeriodRow[]; total: number }>('/api/v1/hs-kpis/periods'),
    putPeriod: (reportingYear: number, payload: HsReportingPeriodInput) =>
      api.put<HsReportingPeriodRow>(`/api/v1/hs-kpis/periods/${reportingYear}`, payload),
    dryRunExcelImport: (file: File) => {
      const form = new FormData()
      form.append('file', file)
      return api.post<HsExcelImportDryRun>('/api/v1/hs-imports/excel/dry-run', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
    },
    commitExcelImport: (file: File) => {
      const form = new FormData()
      form.append('file', file)
      return api.post<HsExcelImportCommit>('/api/v1/hs-imports/excel/commit', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
    },
  }
}
