import { useEffect, useState } from 'react'
import { ChevronLeft, ChevronRight, Download, FileText, ImageOff, Trash2 } from 'lucide-react'
import { evidenceAssetsApi, type EvidenceAsset } from '../api/client'
import { cn } from '../helpers/utils'
import { Button } from './ui/Button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from './ui/Dialog'

type Props = {
  assets: EvidenceAsset[]
  loading?: boolean
  loadFailed?: boolean
  emptyTitle?: string
  emptyDescription?: string
  onDelete?: (id: number) => void
  className?: string
}

type PreviewUrls = Record<number, string>

const isImage = (asset: EvidenceAsset) => asset.content_type.startsWith('image/')

const assetLabel = (asset: EvidenceAsset) =>
  asset.title || asset.original_filename || `Evidence #${asset.id}`

export function EvidenceGallery({
  assets,
  loading = false,
  loadFailed = false,
  emptyTitle = 'No evidence assets yet',
  emptyDescription = 'Files linked to this record will appear here.',
  onDelete,
  className,
}: Props) {
  const [previewUrls, setPreviewUrls] = useState<PreviewUrls>({})
  const [previewFailures, setPreviewFailures] = useState<Set<number>>(new Set())
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null)
  const [downloadError, setDownloadError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    const images = assets.filter(isImage)

    setPreviewUrls({})
    setPreviewFailures(new Set())

    void Promise.all(
      images.map(async (asset) => {
        try {
          const response = await evidenceAssetsApi.getSignedUrl(asset.id, undefined, 'inline')
          if (!cancelled) {
            setPreviewUrls((current) => ({ ...current, [asset.id]: response.data.signed_url }))
          }
        } catch {
          if (!cancelled) {
            setPreviewFailures((current) => new Set(current).add(asset.id))
          }
        }
      }),
    )

    return () => {
      cancelled = true
    }
  }, [assets])

  useEffect(() => {
    if (selectedIndex === null) return

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'ArrowLeft') {
        event.preventDefault()
        setSelectedIndex((current) => (current === null ? null : (current - 1 + assets.length) % assets.length))
      }
      if (event.key === 'ArrowRight') {
        event.preventDefault()
        setSelectedIndex((current) => (current === null ? null : (current + 1) % assets.length))
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [assets.length, selectedIndex])

  const selectedAsset = selectedIndex === null ? null : assets[selectedIndex]
  const selectedPreviewUrl = selectedAsset ? previewUrls[selectedAsset.id] : undefined

  const openAsset = (index: number) => {
    setDownloadError(null)
    setSelectedIndex(index)
  }

  const downloadAsset = async (asset: EvidenceAsset) => {
    setDownloadError(null)
    try {
      const response = await evidenceAssetsApi.getSignedUrl(asset.id, undefined, 'attachment')
      window.open(response.data.signed_url, '_blank', 'noopener,noreferrer')
    } catch {
      setDownloadError('The download link could not be created. Please try again.')
    }
  }

  if (loading) {
    return <p className={cn('text-sm text-muted-foreground', className)}>Loading evidence…</p>
  }

  if (loadFailed) {
    return (
      <p className={cn('text-sm text-muted-foreground', className)}>
        Evidence assets could not be loaded. Reporter-submission evidence is shown separately.
      </p>
    )
  }

  if (assets.length === 0) {
    return (
      <div className={cn('py-8 text-center text-muted-foreground', className)}>
        <FileText className="mx-auto mb-3 h-10 w-10 opacity-50" aria-hidden="true" />
        <p>{emptyTitle}</p>
        <p className="mt-1 text-sm">{emptyDescription}</p>
      </div>
    )
  }

  return (
    <>
      <div className={cn('grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-4', className)}>
        {assets.map((asset, index) => {
          const image = isImage(asset)
          const previewUrl = previewUrls[asset.id]
          const previewFailed = previewFailures.has(asset.id)
          const label = assetLabel(asset)

          return (
            <div
              key={asset.id}
              className="group relative overflow-hidden rounded-lg border border-border bg-muted/30"
            >
              <button
                type="button"
                className="block w-full text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                onClick={() => openAsset(index)}
                aria-label={`Preview ${label}`}
              >
                <div className="aspect-square overflow-hidden bg-muted">
                  {image && previewUrl ? (
                    <img src={previewUrl} alt={label} className="h-full w-full object-cover" />
                  ) : (
                    <div className="flex h-full flex-col items-center justify-center text-muted-foreground">
                      {image && previewFailed ? (
                        <>
                          <ImageOff className="h-8 w-8" aria-hidden="true" />
                          <span className="mt-1 text-xs">Preview unavailable</span>
                        </>
                      ) : (
                        <>
                          <FileText className="h-8 w-8" aria-hidden="true" />
                          <span className="mt-1 text-xs">
                            {image ? 'Loading preview…' : asset.content_type.split('/')[1]?.toUpperCase()}
                          </span>
                        </>
                      )}
                    </div>
                  )}
                </div>
                <div className="p-2">
                  <p className="truncate text-xs text-foreground">{label}</p>
                  <p className="text-xs text-muted-foreground">
                    {new Date(asset.created_at).toLocaleDateString()}
                  </p>
                </div>
              </button>
              {onDelete ? (
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-sm"
                  className="absolute right-1 top-1 opacity-0 group-hover:opacity-100 focus-visible:opacity-100 text-destructive"
                  onClick={() => onDelete(asset.id)}
                  aria-label={`Delete ${label}`}
                >
                  <Trash2 className="h-3 w-3" />
                </Button>
              ) : null}
            </div>
          )
        })}
      </div>

      <Dialog open={selectedAsset !== null} onOpenChange={(open) => !open && setSelectedIndex(null)}>
        {selectedAsset ? (
          <DialogContent className="max-w-4xl">
            <DialogHeader>
              <DialogTitle>{assetLabel(selectedAsset)}</DialogTitle>
              <DialogDescription>{selectedAsset.content_type}</DialogDescription>
            </DialogHeader>
            <div className="relative flex min-h-64 items-center justify-center overflow-hidden rounded-lg bg-muted">
              {isImage(selectedAsset) && selectedPreviewUrl ? (
                <img
                  src={selectedPreviewUrl}
                  alt={assetLabel(selectedAsset)}
                  className="max-h-[60vh] max-w-full object-contain"
                />
              ) : isImage(selectedAsset) ? (
                <div className="p-8 text-center text-sm text-muted-foreground">
                  <ImageOff className="mx-auto mb-2 h-10 w-10" aria-hidden="true" />
                  Preview unavailable. You can still download this file.
                </div>
              ) : (
                <div className="p-8 text-center text-sm text-muted-foreground">
                  <FileText className="mx-auto mb-2 h-10 w-10" aria-hidden="true" />
                  This file cannot be previewed here. Download it to view.
                </div>
              )}
              {assets.length > 1 ? (
                <>
                  <Button
                    type="button"
                    variant="secondary"
                    size="icon"
                    className="absolute left-3"
                    onClick={() =>
                      setSelectedIndex((current) =>
                        current === null ? null : (current - 1 + assets.length) % assets.length,
                      )
                    }
                    aria-label="Previous evidence"
                  >
                    <ChevronLeft className="h-4 w-4" />
                  </Button>
                  <Button
                    type="button"
                    variant="secondary"
                    size="icon"
                    className="absolute right-3"
                    onClick={() =>
                      setSelectedIndex((current) =>
                        current === null ? null : (current + 1) % assets.length,
                      )
                    }
                    aria-label="Next evidence"
                  >
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                </>
              ) : null}
            </div>
            {downloadError ? <p className="text-sm text-destructive">{downloadError}</p> : null}
            <div className="flex justify-end">
              <Button type="button" variant="outline" onClick={() => void downloadAsset(selectedAsset)}>
                <Download className="h-4 w-4" />
                Download
              </Button>
            </div>
          </DialogContent>
        ) : null}
      </Dialog>
    </>
  )
}
