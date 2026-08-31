import { API_BASE_URL } from '../config/apiBase'
import { getPlatformToken } from './auth'

export type ExportModuleId =
  | 'incidents'
  | 'rtas'
  | 'complaints'
  | 'risks'
  | 'audits'
  | 'actions'
  | 'documents'
  | 'compliance_schedule'

export type ExportFormat = 'csv' | 'xlsx' | 'pdf'

export interface ModuleExportRequest {
  module: ExportModuleId
  format?: ExportFormat
  /** PEL register reference to tag the filename with. Does not narrow the rows. */
  register?: string
}

export interface ModuleExportResult {
  filename: string
  truncated: boolean
}

/**
 * Download one Export Center module synchronously (POST /api/v1/exports).
 *
 * Shared by the Export Center page and the Register of Registers caption
 * overlay so there is one sync download path. Callers own their own toasts.
 */
export async function downloadModuleExport({
  module,
  format = 'csv',
  register,
}: ModuleExportRequest): Promise<ModuleExportResult> {
  const token = getPlatformToken()
  const response = await fetch(`${API_BASE_URL}/api/v1/exports`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(register ? { module, format, register } : { module, format }),
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error((body as { detail?: string }).detail || `Export failed (${response.status})`)
  }
  const blob = await response.blob()
  const disposition = response.headers.get('Content-Disposition') || ''
  const match = /filename="?([^"]+)"?/i.exec(disposition)
  const filename = match?.[1] || `${module}_export.${format}`
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
  return { filename, truncated: response.headers.get('X-Export-Truncated') === 'true' }
}
