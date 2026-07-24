import { useCallback, useEffect, useRef, useState } from 'react'
import {
  ChevronLeft,
  ChevronRight,
  Download,
  FileText,
  ImageOff,
  Loader2,
  Trash2,
  Upload,
} from 'lucide-react'
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

/** Default upload constraints shared by every case that embeds the gallery. */
export const DEFAULT_EVIDENCE_MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024
export const DEFAULT_EVIDENCE_MIME_PREFIXES = ['image/', 'video/']
export const DEFAULT_EVIDENCE_MIME_TYPES = ['application/pdf']
export const DEFAULT_EVIDENCE_UPLOAD_ACCEPT = 'image/*,video/*,.pdf'

type Props = {
  assets: EvidenceAsset[]
  loading?: boolean
  loadFailed?: boolean
  loadFailureDescription?: string
  emptyTitle?: string
  emptyDescription?: string
  onDelete?: (id: number) => void
  /** Gates the delete affordance even when onDelete is supplied (e.g. permission checks). Defaults to true. */
  canDelete?: boolean
  className?: string
  /**
   * Opt-in upload affordance. Read-only by default so existing call sites are unaffected.
   * Requires uploadSourceModule + uploadSourceId to actually render the control.
   */
  enableUpload?: boolean
  uploadSourceModule?: string
  uploadSourceId?: number
  /** Called after every upload attempt completes (success or partial failure) so the caller can refetch. */
  onUploadComplete?: () => void | Promise<void>
  uploadLabel?: string
  uploadAccept?: string
  maxFileSizeBytes?: number
  allowedMimePrefixes?: string[]
  allowedMimeTypes?: string[]
}

type PreviewUrls = Record<number, string>

const isImage = (asset: EvidenceAsset) => asset.content_type.startsWith('image/')

const assetLabel = (asset: EvidenceAsset) =>
  asset.title || asset.original_filename || `Evidence #${asset.id}`

const isSupportedFileType = (file: File, prefixes: string[], types: string[]) =>
  prefixes.some((prefix) => file.type.startsWith(prefix)) || types.includes(file.type)

export function EvidenceGallery({
  assets,
  loading = false,
  loadFailed = false,
  loadFailureDescription = 'Evidence assets could not be loaded. Reporter-submission evidence is shown separately.',
  emptyTitle = 'No evidence assets yet',
  emptyDescription = 'Files linked to this record will appear here.',
  onDelete,
  canDelete = true,
  className,
  enableUpload = false,
  uploadSourceModule,
  uploadSourceId,
  onUploadComplete,
  uploadLabel = 'Upload evidence',
  uploadAccept = DEFAULT_EVIDENCE_UPLOAD_ACCEPT,
  maxFileSizeBytes = DEFAULT_EVIDENCE_MAX_FILE_SIZE_BYTES,
  allowedMimePrefixes = DEFAULT_EVIDENCE_MIME_PREFIXES,
  allowedMimeTypes = DEFAULT_EVIDENCE_MIME_TYPES,
}: Props) {
  const [previewUrls, setPreviewUrls] = useState<PreviewUrls>({})
  const [previewFailures, setPreviewFailures] = useState<Set<number>>(new Set())
  const [selectedAssetId, setSelectedAssetId] = useState<number | null>(null)
  const [downloadError, setDownloadError] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const selectedIndex = selectedAssetId === null ? -1 : assets.findIndex((asset) => asset.id === selectedAssetId)
  const selectedAsset = selectedIndex === -1 ? null : assets[selectedIndex]
  const uploadReady = enableUpload && !!uploadSourceModule && uploadSourceId != null
  const canShowDelete = !!onDelete && canDelete

  useEffect(() => {
    let cancelled = false
    const images = assets.filter(isImage)
    const imageIds = new Set(images.map((asset) => asset.id))

    setPreviewUrls((current) =>
      Object.fromEntries(Object.entries(current).filter(([id]) => imageIds.has(Number(id)))),
    )
    setPreviewFailures((current) => new Set([...current].filter((id) => imageIds.has(id))))

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

  const moveSelection = useCallback((direction: -1 | 1) => {
    setSelectedAssetId((currentId) => {
      const currentIndex = assets.findIndex((asset) => asset.id === currentId)
      if (currentIndex === -1 || assets.length === 0) return null
      return assets[(currentIndex + direction + assets.length) % assets.length].id
    })
  }, [assets])

  useEffect(() => {
    if (selectedAssetId === null) return

    if (!assets.some((asset) => asset.id === selectedAssetId)) {
      setSelectedAssetId(null)
      return
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'ArrowLeft') {
        event.preventDefault()
        moveSelection(-1)
      }
      if (event.key === 'ArrowRight') {
        event.preventDefault()
        moveSelection(1)
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [assets, moveSelection, selectedAssetId])

  const selectedPreviewUrl = selectedAsset ? previewUrls[selectedAsset.id] : undefined
  const selectedPreviewFailed = selectedAsset ? previewFailures.has(selectedAsset.id) : false

  const openAsset = (index: number) => {
    setDownloadError(null)
    setSelectedAssetId(assets[index].id)
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

  const openFilePicker = () => fileInputRef.current?.click()

  const handleFileInputChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files ? Array.from(event.target.files) : []
    if (fileInputRef.current) fileInputRef.current.value = ''
    if (files.length === 0 || !uploadSourceModule || uploadSourceId == null) return

    setUploadError(null)
    setUploading(true)
    const failures: string[] = []
    try {
      for (const file of files) {
        if (!isSupportedFileType(file, allowedMimePrefixes, allowedMimeTypes)) {
          failures.push(`${file.name} is not a supported file type.`)
          continue
        }
        if (file.size > maxFileSizeBytes) {
          failures.push(`${file.name} exceeds the ${Math.round(maxFileSizeBytes / (1024 * 1024))}MB upload limit.`)
          continue
        }
        try {
          await evidenceAssetsApi.upload(file, {
            source_module: uploadSourceModule,
            source_id: uploadSourceId,
            title: file.name,
            visibility: 'internal_customer',
          })
        } catch {
          failures.push(`${file.name} could not be uploaded.`)
        }
      }
      if (failures.length > 0) {
        setUploadError(failures.join(' '))
      }
      await onUploadComplete?.()
    } finally {
      setUploading(false)
    }
  }

  const uploadToolbar = uploadReady ? (
    <div className="mb-4 space-y-2">
      <div className="flex flex-wrap items-center gap-3">
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept={uploadAccept}
          className="hidden"
          onChange={(event) => void handleFileInputChange(event)}
          aria-label={uploadLabel}
          disabled={uploading}
        />
        <Button type="button" variant="outline" size="sm" onClick={openFilePicker} disabled={uploading}>
          {uploading ? (
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          ) : (
            <Upload className="h-4 w-4" aria-hidden="true" />
          )}
          {uploading ? 'Uploading…' : uploadLabel}
        </Button>
        <p className="text-xs text-muted-foreground">
          Images, video, or PDF. Max {Math.round(maxFileSizeBytes / (1024 * 1024))}MB per file.
        </p>
      </div>
      {uploadError ? <p className="text-sm text-destructive" role="alert">{uploadError}</p> : null}
    </div>
  ) : null

  if (loading) {
    return <p className={cn('text-sm text-muted-foreground', className)}>Loading evidence…</p>
  }

  if (loadFailed) {
    return (
      <p className={cn('text-sm text-muted-foreground', className)}>
        {loadFailureDescription}
      </p>
    )
  }

  if (assets.length === 0) {
    return (
      <div className={className}>
        {uploadToolbar}
        <div className="py-8 text-center text-muted-foreground">
          <FileText className="mx-auto mb-3 h-10 w-10 opacity-50" aria-hidden="true" />
          <p>{emptyTitle}</p>
          <p className="mt-1 text-sm">{emptyDescription}</p>
        </div>
      </div>
    )
  }

  return (
    <>
      <div className={className}>
        {uploadToolbar}
        <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-4">
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
                {canShowDelete ? (
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-sm"
                    className="absolute right-1 top-1 opacity-0 group-hover:opacity-100 focus-visible:opacity-100 text-destructive"
                    onClick={() => onDelete?.(asset.id)}
                    aria-label={`Delete ${label}`}
                  >
                    <Trash2 className="h-3 w-3" />
                  </Button>
                ) : null}
              </div>
            )
          })}
        </div>
      </div>

      <Dialog open={selectedAsset !== null} onOpenChange={(open) => !open && setSelectedAssetId(null)}>
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
                  {selectedPreviewFailed ? (
                    <>
                      <ImageOff className="mx-auto mb-2 h-10 w-10" aria-hidden="true" />
                      Preview unavailable. You can still download this file.
                    </>
                  ) : (
                    <>Loading preview…</>
                  )}
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
                    onClick={() => moveSelection(-1)}
                    aria-label="Previous evidence"
                  >
                    <ChevronLeft className="h-4 w-4" />
                  </Button>
                  <Button
                    type="button"
                    variant="secondary"
                    size="icon"
                    className="absolute right-3"
                    onClick={() => moveSelection(1)}
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
