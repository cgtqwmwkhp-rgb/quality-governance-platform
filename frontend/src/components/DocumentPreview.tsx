import { useEffect, useState } from 'react'
import { FileText, ImageOff, Loader2 } from 'lucide-react'
import { cn } from '../helpers/utils'

export type PreviewKind = 'image' | 'pdf' | 'video' | 'audio' | 'text' | 'unsupported'

export type DocumentPreviewProps = {
  /** Inline signed URL (or blob URL) for the file. */
  url?: string | null
  contentType: string
  fileName?: string
  alt?: string
  /** True while the caller is still resolving a signed URL. */
  loading?: boolean
  /** True when the caller failed to resolve a signed URL. */
  loadFailed?: boolean
  className?: string
  onLoadError?: () => void
}

const PDF_MIME = 'application/pdf'
const TEXT_MIMES = new Set([
  'text/plain',
  'text/csv',
  'text/tab-separated-values',
  'application/csv',
])

function extensionOf(fileName?: string): string {
  if (!fileName) return ''
  const idx = fileName.lastIndexOf('.')
  return idx >= 0 ? fileName.slice(idx + 1).toLowerCase() : ''
}

/**
 * Route a content type (and optional filename) to a native in-app preview kind.
 * Tier 1: image / pdf / video / audio. Tier 2: plain text / csv.
 */
export function resolvePreviewKind(contentType: string, fileName?: string): PreviewKind {
  const mime = (contentType || '').toLowerCase().split(';')[0].trim()
  const ext = extensionOf(fileName)

  if (mime.startsWith('image/') || ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'svg'].includes(ext)) {
    return 'image'
  }
  if (mime === PDF_MIME || ext === 'pdf') {
    return 'pdf'
  }
  if (mime.startsWith('video/') || ['mp4', 'webm', 'ogg', 'mov', 'm4v'].includes(ext)) {
    return 'video'
  }
  if (mime.startsWith('audio/') || ['mp3', 'wav', 'ogg', 'm4a', 'aac', 'flac'].includes(ext)) {
    return 'audio'
  }
  if (TEXT_MIMES.has(mime) || ['txt', 'csv', 'tsv', 'log', 'md'].includes(ext)) {
    return 'text'
  }
  return 'unsupported'
}

export function isTier1Preview(kind: PreviewKind): boolean {
  return kind === 'image' || kind === 'pdf' || kind === 'video' || kind === 'audio'
}

export function canPreviewInApp(contentType: string, fileName?: string): boolean {
  const kind = resolvePreviewKind(contentType, fileName)
  return kind !== 'unsupported'
}

function UnsupportedPreview({ message }: { message: string }) {
  return (
    <div className="p-8 text-center text-sm text-muted-foreground">
      <FileText className="mx-auto mb-2 h-10 w-10" aria-hidden="true" />
      {message}
    </div>
  )
}

function TextPreview({ url, fileName }: { url: string; fileName?: string }) {
  const [text, setText] = useState<string | null>(null)
  const [error, setError] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    const controller = new AbortController()

    setLoading(true)
    setError(false)
    setText(null)

    void fetch(url, { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        const body = await response.text()
        // Cap display so huge CSVs do not freeze the lightbox.
        const capped = body.length > 200_000 ? `${body.slice(0, 200_000)}\n\n… truncated …` : body
        if (!cancelled) setText(capped)
      })
      .catch(() => {
        if (!cancelled) setError(true)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
      controller.abort()
    }
  }, [url])

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8 text-sm text-muted-foreground">
        <Loader2 className="mr-2 h-5 w-5 animate-spin" aria-hidden="true" />
        Loading preview…
      </div>
    )
  }

  if (error || text == null) {
    return (
      <UnsupportedPreview message="This text file could not be previewed here. Download it to view." />
    )
  }

  return (
    <pre
      className="max-h-[60vh] w-full overflow-auto whitespace-pre-wrap break-words rounded-lg bg-background p-4 text-left text-xs text-foreground"
      aria-label={`Preview of ${fileName || 'text file'}`}
    >
      {text}
    </pre>
  )
}

/**
 * Native in-app document preview for EvidenceGallery lightbox and similar hosts.
 * Prefer iframe / media elements over download-only for Tier 1 mime types.
 */
export function DocumentPreview({
  url,
  contentType,
  fileName,
  alt,
  loading = false,
  loadFailed = false,
  className,
  onLoadError,
}: DocumentPreviewProps) {
  const kind = resolvePreviewKind(contentType, fileName)
  const label = alt || fileName || 'Evidence preview'

  if (loading) {
    return (
      <div
        className={cn('flex min-h-64 items-center justify-center p-8 text-sm text-muted-foreground', className)}
        data-testid="document-preview-loading"
      >
        <Loader2 className="mr-2 h-5 w-5 animate-spin" aria-hidden="true" />
        Loading preview…
      </div>
    )
  }

  if (loadFailed || !url) {
    return (
      <div
        className={cn('flex min-h-64 items-center justify-center', className)}
        data-testid="document-preview-failed"
      >
        <div className="p-8 text-center text-sm text-muted-foreground">
          <ImageOff className="mx-auto mb-2 h-10 w-10" aria-hidden="true" />
          Preview unavailable. You can still download this file.
        </div>
      </div>
    )
  }

  if (kind === 'unsupported') {
    return (
      <div className={cn('flex min-h-64 items-center justify-center', className)} data-testid="document-preview-unsupported">
        <UnsupportedPreview message="This file cannot be previewed here. Download it to view." />
      </div>
    )
  }

  if (kind === 'image') {
    return (
      <div className={cn('flex min-h-64 items-center justify-center', className)} data-testid="document-preview-image">
        <img
          src={url}
          alt={label}
          className="max-h-[60vh] max-w-full object-contain"
          onError={onLoadError}
        />
      </div>
    )
  }

  if (kind === 'pdf') {
    return (
      <div className={cn('min-h-64 w-full', className)} data-testid="document-preview-pdf">
        <iframe
          src={url}
          title={`Preview of ${label}`}
          className="h-[min(60vh,640px)] w-full rounded-lg border border-border bg-background"
        />
      </div>
    )
  }

  if (kind === 'video') {
    return (
      <div className={cn('flex min-h-64 w-full items-center justify-center', className)} data-testid="document-preview-video">
        <video
          src={url}
          controls
          className="max-h-[60vh] max-w-full"
          onError={onLoadError}
        >
          Your browser does not support video playback.
        </video>
      </div>
    )
  }

  if (kind === 'audio') {
    return (
      <div className={cn('flex min-h-64 w-full flex-col items-center justify-center gap-3 p-8', className)} data-testid="document-preview-audio">
        <FileText className="h-10 w-10 text-muted-foreground" aria-hidden="true" />
        <p className="text-sm text-muted-foreground">{label}</p>
        <audio src={url} controls className="w-full max-w-md" onError={onLoadError}>
          Your browser does not support audio playback.
        </audio>
      </div>
    )
  }

  // Tier 2: text / csv
  return (
    <div className={cn('min-h-64 w-full', className)} data-testid="document-preview-text">
      <TextPreview url={url} fileName={fileName} />
    </div>
  )
}

export default DocumentPreview
