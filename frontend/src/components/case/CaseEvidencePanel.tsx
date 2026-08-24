import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Camera } from 'lucide-react'
import { evidenceAssetsApi, getApiErrorMessage, type EvidenceAsset } from '../../api/client'
import { toast } from '../../contexts/ToastContext'
import { EvidenceGallery } from '../EvidenceGallery'
import { Card, CardContent, CardHeader, CardTitle } from '../ui/Card'

/** Maps 1:1 onto evidence-assets `source_module`. */
export type CaseEvidenceSourceType =
  | 'incident'
  | 'near_miss'
  | 'complaint'
  | 'road_traffic_collision'
  /** A completed or missed Compliance Schedule occurrence (`ComplianceRecord`), not the obligation itself. */
  | 'compliance_record'

export interface CaseEvidencePanelProps {
  sourceType: CaseEvidenceSourceType
  sourceId: number
  title?: string
  /** Opt-in — read-only by default so this panel is safe to drop into any case page. */
  enableUpload?: boolean
  /** Gates the delete affordance independent of upload (e.g. role/permission checks). */
  canDelete?: boolean
  emptyTitle?: string
  emptyDescription?: string
  pageSize?: number
  className?: string
  /** Optional test id prefix, e.g. "incident" → incident-evidence-panel */
  testIdPrefix?: string
  /**
   * Optional post-upload hook. Gallery already reloads via this panel; the
   * optional result lists successfully uploaded asset ids for callers that need
   * them (e.g. FRA OCR from-evidence).
   */
  onUploadComplete?: (result?: { uploadedAssetIds: number[] }) => void | Promise<void>
}

/**
 * Thin, source-agnostic wrapper around EvidenceGallery: owns fetch/upload/delete
 * against evidenceAssetsApi so case pages only need a sourceType + sourceId.
 */
export function CaseEvidencePanel({
  sourceType,
  sourceId,
  title,
  enableUpload = false,
  canDelete = true,
  emptyTitle,
  emptyDescription,
  pageSize = 50,
  className,
  testIdPrefix,
  onUploadComplete,
}: CaseEvidencePanelProps) {
  const { t } = useTranslation()
  const [assets, setAssets] = useState<EvidenceAsset[]>([])
  const [loading, setLoading] = useState(true)
  const [loadFailed, setLoadFailed] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setLoadFailed(false)
    try {
      const response = await evidenceAssetsApi.list({
        source_module: sourceType,
        source_id: sourceId,
        page_size: pageSize,
      })
      setAssets(response.data.items || [])
    } catch {
      setLoadFailed(true)
    } finally {
      setLoading(false)
    }
  }, [sourceType, sourceId, pageSize])

  useEffect(() => {
    void load()
  }, [load])

  const handleUploadComplete = useCallback(
    async (result?: { uploadedAssetIds: number[] }) => {
      await load()
      await onUploadComplete?.(result)
    },
    [load, onUploadComplete],
  )

  const handleDelete = async (assetId: number) => {
    try {
      await evidenceAssetsApi.delete(assetId)
      toast.success(t('case.evidence.delete_success', 'Evidence deleted'))
      await load()
    } catch (err) {
      toast.error(
        getApiErrorMessage(
          err,
          t('case.evidence.delete_error', 'This file could not be deleted. Please try again.'),
        ),
      )
    }
  }

  const panelId = testIdPrefix ? `${testIdPrefix}-evidence-panel` : undefined

  return (
    <Card data-testid={panelId} className={className}>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Camera className="w-5 h-5 text-primary" aria-hidden="true" />
          {title ?? t('case.evidence.title', 'Evidence')}
          <span className="text-sm font-normal text-muted-foreground">({assets.length})</span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <EvidenceGallery
          assets={assets}
          loading={loading}
          loadFailed={loadFailed}
          loadFailureDescription={t(
            'case.evidence.load_failed',
            'Evidence could not be loaded. Please try refreshing the page.',
          )}
          emptyTitle={emptyTitle ?? t('case.evidence.empty_title', 'No evidence uploaded yet')}
          emptyDescription={
            emptyDescription ??
            t(
              'case.evidence.empty_description',
              'Upload photos, videos, documents, or email files (.eml, .msg) to attach evidence to this case.',
            )
          }
          onDelete={canDelete ? handleDelete : undefined}
          enableUpload={enableUpload}
          uploadSourceModule={sourceType}
          uploadSourceId={sourceId}
          uploadLabel={t('case.evidence.upload', 'Upload evidence')}
          onUploadComplete={handleUploadComplete}
        />
      </CardContent>
    </Card>
  )
}
