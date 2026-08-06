import { useEffect, useState } from 'react'
import { Loader2 } from 'lucide-react'
import api, { getApiErrorMessage } from '../api/client'
import { canPreviewInApp, DocumentPreview } from './DocumentPreview'
import { Button } from './ui/Button'

interface DocumentPdfPreviewProps {
  documentId: number
  fileType: string
  fileName: string
}

function contentTypeForDocument(fileType: string, fileName: string): string {
  const type = (fileType || '').toLowerCase().trim()
  if (type.includes('/')) return type
  if (type === 'pdf' || fileName.toLowerCase().endsWith('.pdf')) return 'application/pdf'
  if (['jpg', 'jpeg', 'png', 'gif', 'webp'].includes(type)) return `image/${type === 'jpg' ? 'jpeg' : type}`
  return type || 'application/octet-stream'
}

/**
 * Thin host wrapper: document library signed URL → DocumentPreview for Tier 1
 * consistency (PDF iframe / image). Non-previewable types keep open/download.
 */
export default function DocumentPdfPreview({
  documentId,
  fileType,
  fileName,
}: DocumentPdfPreviewProps) {
  const [url, setUrl] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false

    async function loadPreviewUrl() {
      setLoading(true)
      setError(null)
      try {
        const response = await api.get<{ signed_url: string }>(
          `/api/v1/documents/${documentId}/signed-url`,
          { params: { download: false } },
        )
        const rawUrl = response.data.signed_url
        const resolved = new URL(rawUrl, api.defaults.baseURL || window.location.origin).toString()
        if (!cancelled) setUrl(resolved)
      } catch (err) {
        if (!cancelled) setError(getApiErrorMessage(err))
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    void loadPreviewUrl()
    return () => {
      cancelled = true
    }
  }, [documentId])

  const contentType = contentTypeForDocument(fileType, fileName)
  const previewable = canPreviewInApp(contentType, fileName)

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-6 h-6 animate-spin text-primary" aria-hidden="true" />
      </div>
    )
  }

  if (error || !url) {
    return <p className="text-sm text-destructive">{error ?? 'Preview unavailable'}</p>
  }

  if (!previewable) {
    return (
      <div className="space-y-2 text-sm text-muted-foreground">
        <p>Inline preview is available for PDF and image documents.</p>
        <Button variant="outline" size="sm" asChild>
          <a href={url} target="_blank" rel="noopener noreferrer">
            Open {fileName}
          </a>
        </Button>
      </div>
    )
  }

  return (
    <div data-testid="document-pdf-preview">
      <DocumentPreview
        url={url}
        contentType={contentType}
        fileName={fileName}
        alt={fileName}
        className="w-full h-[min(70vh,640px)] rounded-lg border border-border bg-muted/20"
      />
    </div>
  )
}
