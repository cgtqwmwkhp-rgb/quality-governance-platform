import { useCallback, useEffect, useState } from 'react'
import { Download, FileSpreadsheet, AlertCircle } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Button } from '../components/ui/Button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/Card'
import { API_BASE_URL } from '../config/apiBase'
import { getPlatformToken } from '../utils/auth'
import { toast } from '../contexts/ToastContext'

type ExportModuleId =
  | 'incidents'
  | 'rtas'
  | 'complaints'
  | 'risks'
  | 'audits'
  | 'actions'
  | 'documents'
  | 'compliance_schedule'

interface ExportModule {
  id: ExportModuleId
  name: string
  description: string
  record_count: number
  formats: string[]
  sync_available: boolean
}

interface ExportCapabilities {
  sync_csv: boolean
  job_history: boolean
  scheduled_templates: boolean
  max_sync_rows: number
}

interface ExportCatalog {
  modules: ExportModule[]
  capabilities: ExportCapabilities
}

/**
 * Export Center wired to live sync CSV APIs (PX-160).
 *
 * Sync downloads hit POST /api/v1/exports (and GET /exports/{module}/csv).
 * Job history and scheduled templates remain unavailable until Lane S lands
 * an export_jobs store — disclosed honestly, not faked.
 */
export default function ExportCenter() {
  const { t } = useTranslation()
  const [catalog, setCatalog] = useState<ExportCatalog | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [exportingId, setExportingId] = useState<string | null>(null)

  const loadCatalog = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const token = getPlatformToken()
      const response = await fetch(`${API_BASE_URL}/api/v1/exports/catalog`, {
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
      })
      if (!response.ok) {
        const body = await response.json().catch(() => ({}))
        throw new Error(
          (body as { detail?: string }).detail || `Catalog failed (${response.status})`,
        )
      }
      const data = (await response.json()) as ExportCatalog
      setCatalog(data)
    } catch (err) {
      setCatalog(null)
      setError(err instanceof Error ? err.message : 'Failed to load export catalog')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadCatalog()
  }, [loadCatalog])

  const handleExport = async (moduleId: ExportModuleId) => {
    setExportingId(moduleId)
    try {
      const token = getPlatformToken()
      const response = await fetch(`${API_BASE_URL}/api/v1/exports`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ module: moduleId, format: 'csv' }),
      })
      if (!response.ok) {
        const body = await response.json().catch(() => ({}))
        throw new Error(
          (body as { detail?: string }).detail || `Export failed (${response.status})`,
        )
      }
      const blob = await response.blob()
      const disposition = response.headers.get('Content-Disposition') || ''
      const match = /filename="?([^"]+)"?/i.exec(disposition)
      const filename = match?.[1] || `${moduleId}_export.csv`
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = filename
      anchor.click()
      URL.revokeObjectURL(url)
      const truncated = response.headers.get('X-Export-Truncated') === 'true'
      toast.success(
        truncated
          ? t(
              'exports.download_truncated',
              'CSV downloaded (row cap reached — not a full dump)',
            )
          : t('exports.download_ready', 'CSV downloaded'),
      )
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Export failed')
    } finally {
      setExportingId(null)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-foreground flex items-center gap-3">
          <div className="p-2 bg-gradient-to-br from-primary to-primary-hover rounded-xl">
            <Download className="w-8 h-8 text-primary-foreground" />
          </div>
          {t('exports.title')}
        </h1>
        <p className="text-muted-foreground mt-1">{t('exports.subtitle')}</p>
      </div>

      {catalog && !catalog.capabilities.job_history && (
        <Card data-testid="export-center-deferred-capabilities">
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-muted-foreground" aria-hidden />
              {t('exports.deferred.title', 'Async job history not available yet')}
            </CardTitle>
            <CardDescription>
              {t(
                'exports.deferred.description',
                'Sync CSV downloads are live. Job history and scheduled templates need an export job store (not in this release) and are not simulated here.',
              )}
            </CardDescription>
          </CardHeader>
        </Card>
      )}

      {loading && (
        <Card data-testid="export-center-loading">
          <CardContent className="py-8 text-muted-foreground">
            {t('exports.loading', 'Loading live export catalog…')}
          </CardContent>
        </Card>
      )}

      {!loading && error && (
        <Card data-testid="export-center-error">
          <CardHeader>
            <CardTitle className="text-base">
              {t('exports.error.title', 'Could not load export catalog')}
            </CardTitle>
            <CardDescription>{error}</CardDescription>
          </CardHeader>
          <CardContent>
            <Button type="button" variant="outline" onClick={() => void loadCatalog()}>
              {t('common.retry', 'Retry')}
            </Button>
          </CardContent>
        </Card>
      )}

      {!loading && !error && catalog && (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4" data-testid="export-center-catalog">
          {catalog.modules.map((module) => (
            <Card key={module.id} data-testid={`export-module-${module.id}`}>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <FileSpreadsheet className="w-4 h-4 text-primary" aria-hidden />
                  {module.name}
                </CardTitle>
                <CardDescription>{module.description}</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-wrap items-center justify-between gap-3">
                <p className="text-sm text-muted-foreground" data-testid={`export-count-${module.id}`}>
                  {t('exports.record_count', '{{count}} records', {
                    count: module.record_count,
                  })}
                </p>
                <Button
                  type="button"
                  data-testid={`export-${module.id}-btn`}
                  disabled={!module.sync_available || exportingId === module.id}
                  onClick={() => void handleExport(module.id)}
                >
                  {exportingId === module.id
                    ? t('exports.exporting', 'Exporting…')
                    : t('exports.download_csv', 'Download CSV')}
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
