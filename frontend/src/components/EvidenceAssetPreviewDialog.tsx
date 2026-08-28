import { useEffect, useState } from 'react'
import { Download, FileText } from 'lucide-react'
import { evidenceAssetsApi, type EvidenceAsset } from '../api/client'
import { canPreviewInApp, DocumentPreview } from './DocumentPreview'
import { Button } from './ui/Button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from './ui/Dialog'

type Props = {
  asset: EvidenceAsset | null
  open: boolean
  onOpenChange: (open: boolean) => void
  /** Optional override when the host already holds an inline URL. */
  previewUrl?: string | null
}

function assetLabel(asset: EvidenceAsset): string {
  return asset.title || asset.original_filename || `Evidence #${asset.id}`
}

/**
 * Host-facing lightbox for a single evidence asset.
 * Tier 1/2 types preview in-app via DocumentPreview, from bytes fetched through the
 * API and wrapped in an object URL rather than a blob SAS URL. Download remains a
 * secondary CTA and still redirects to storage with attachment disposition.
 */
export function EvidenceAssetPreviewDialog({
  asset,
  open,
  onOpenChange,
  previewUrl: previewUrlOverride,
}: Props) {
  const [fetchedUrl, setFetchedUrl] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [loadFailed, setLoadFailed] = useState(false)
  const [downloadError, setDownloadError] = useState<string | null>(null)

  const previewable =
    asset != null && canPreviewInApp(asset.content_type, asset.original_filename || asset.title)

  useEffect(() => {
    if (!open || !asset || !previewable) {
      setFetchedUrl(null)
      setLoading(false)
      setLoadFailed(false)
      setDownloadError(null)
      return
    }

    if (previewUrlOverride) {
      setFetchedUrl(previewUrlOverride)
      setLoading(false)
      setLoadFailed(false)
      return
    }

    let cancelled = false
    let objectUrl: string | null = null
    setLoading(true)
    setLoadFailed(false)
    setFetchedUrl(null)
    setDownloadError(null)

    void (async () => {
      try {
        const response = await evidenceAssetsApi.getContent(asset.id, 'inline')
        if (!cancelled) {
          objectUrl = URL.createObjectURL(response.data)
          setFetchedUrl(objectUrl)
        }
      } catch {
        if (!cancelled) setLoadFailed(true)
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()

    // The URL is created only after the cancellation check, so a dialog closed
    // mid-fetch never leaves one behind; this releases the one that was rendered.
    return () => {
      cancelled = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [asset, open, previewUrlOverride, previewable])

  const downloadAsset = async () => {
    if (!asset) return
    setDownloadError(null)
    try {
      const response = await evidenceAssetsApi.getSignedUrl(asset.id, undefined, 'attachment')
      window.open(response.data.signed_url, '_blank', 'noopener,noreferrer')
    } catch {
      setDownloadError('The download link could not be created. Please try again.')
    }
  }

  return (
    <Dialog open={open && asset !== null} onOpenChange={onOpenChange}>
      {asset ? (
        <DialogContent className="max-w-4xl" data-testid="evidence-asset-preview-dialog">
          <DialogHeader>
            <DialogTitle>{assetLabel(asset)}</DialogTitle>
            <DialogDescription>{asset.content_type}</DialogDescription>
          </DialogHeader>
          <div className="relative flex min-h-64 items-center justify-center overflow-hidden rounded-lg bg-muted">
            {previewable ? (
              <DocumentPreview
                url={fetchedUrl}
                contentType={asset.content_type}
                fileName={asset.original_filename || asset.title}
                alt={assetLabel(asset)}
                loading={loading && !fetchedUrl && !loadFailed}
                loadFailed={loadFailed}
                className="w-full"
              />
            ) : (
              <div
                className="p-8 text-center text-sm text-muted-foreground"
                data-testid="evidence-asset-preview-unsupported"
              >
                <FileText className="mx-auto mb-2 h-10 w-10" aria-hidden="true" />
                This file cannot be previewed here. Download it to view.
              </div>
            )}
          </div>
          {downloadError ? <p className="text-sm text-destructive">{downloadError}</p> : null}
          <div className="flex justify-end">
            <Button
              type="button"
              variant="outline"
              onClick={() => void downloadAsset()}
              data-testid="evidence-asset-preview-download"
            >
              <Download className="h-4 w-4" />
              Download
            </Button>
          </div>
        </DialogContent>
      ) : null}
    </Dialog>
  )
}
