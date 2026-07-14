import { useEffect, useState, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { trackError } from '../utils/errorTracker'
import {
  Plus,
  Search,
  Upload,
  FileText,
  FileSpreadsheet,
  Image,
  File,
  Eye,
  Download,
  Tag,
  Calendar,
  Sparkles,
  CheckCircle2,
  Loader2,
  Grid3X3,
  List,
  ChevronRight,
  ExternalLink,
  Brain,
  Zap,
} from 'lucide-react'
import api, { getApiErrorMessage } from '../api/client'
import { toast } from '../contexts/ToastContext'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Card } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { EmptyState } from '../components/ui/EmptyState'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '../components/ui/Dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/Select'
import { cn } from '../helpers/utils'
import { LibraryShell } from './LibraryShell'

/** Surface operator-visible failures (banner + toast). Never silent. */
const reportFailure = (
  err: unknown,
  setError: (message: string | null) => void,
): string => {
  const message = getApiErrorMessage(err)
  setError(message)
  toast.error(message)
  return message
}

interface Document {
  id: number
  reference_number: string
  title: string
  description?: string
  file_name: string
  file_type: string
  file_size: number
  document_type: string
  category?: string
  department?: string
  sensitivity: string
  status: string
  version: string
  ai_summary?: string
  ai_tags?: string[]
  ai_keywords?: string[]
  page_count?: number
  word_count?: number
  view_count: number
  download_count: number
  is_public: boolean
  created_at: string
  indexed_at?: string
}

interface DocumentStats {
  total_documents: number
  indexed_documents: number
  total_chunks: number
  by_status: Record<string, number>
  by_type: Record<string, number>
}

interface SearchResult {
  document_id: number
  reference_number: string
  title: string
  score: number
  chunk_preview: string
  page_number?: number
  heading?: string
}

type ViewMode = 'grid' | 'list'
const UPLOAD_TIMEOUT_MS = 120000
const ALL_TYPES_VALUE = 'all-types'
const ALL_STATUS_VALUE = 'all-status'

const FILE_ICONS: Record<string, typeof FileText> = {
  pdf: FileText,
  docx: FileText,
  doc: FileText,
  xlsx: FileSpreadsheet,
  xls: FileSpreadsheet,
  csv: FileSpreadsheet,
  png: Image,
  jpg: Image,
  jpeg: Image,
  md: FileText,
  txt: FileText,
}

const getStatusVariant = (status: string) => {
  switch (status) {
    case 'indexed':
      return 'resolved'
    case 'approved':
      return 'success'
    case 'processing':
      return 'in-progress'
    case 'pending':
      return 'submitted'
    case 'failed':
      return 'destructive'
    default:
      return 'secondary'
  }
}

export default function Documents() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const searchInputRef = useRef<HTMLInputElement>(null)
  const [documents, setDocuments] = useState<Document[]>([])
  const [stats, setStats] = useState<DocumentStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [viewMode, setViewMode] = useState<ViewMode>('grid')
  const [searchTerm, setSearchTerm] = useState('')
  const [searchResults, setSearchResults] = useState<SearchResult[] | null>(null)
  const [isSearching, setIsSearching] = useState(false)
  const [showUploadModal, setShowUploadModal] = useState(false)
  const [selectedDocument, setSelectedDocument] = useState<Document | null>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [dragActive, setDragActive] = useState(false)
  const [filterType, setFilterType] = useState<string>(ALL_TYPES_VALUE)
  const [filterStatus, setFilterStatus] = useState<string>(ALL_STATUS_VALUE)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [docsUnavailable, setDocsUnavailable] = useState(false)
  const [statsUnavailable, setStatsUnavailable] = useState(false)
  const [searchUnavailable, setSearchUnavailable] = useState(false)
  const [partialLoadWarning, setPartialLoadWarning] = useState<string | null>(null)

  const loadData = useCallback(async (docType?: string, status?: string) => {
    setLoadError(null)
    setPartialLoadWarning(null)
    setDocsUnavailable(false)
    setStatsUnavailable(false)
    try {
      const params = new URLSearchParams({ page: '1', page_size: '50' })
      if (docType) params.set('document_type', docType)
      if (status) params.set('status', status)
      const [docsResult, statsResult] = await Promise.allSettled([
        api.get(`/api/v1/documents/?${params}`),
        api.get('/api/v1/documents/stats/overview'),
      ])

      const docsFailed = docsResult.status === 'rejected'
      const statsFailed = statsResult.status === 'rejected'
      setDocsUnavailable(docsFailed)
      setStatsUnavailable(statsFailed)

      if (docsFailed && statsFailed) {
        const reason =
          docsResult.status === 'rejected' ? docsResult.reason : (statsResult as PromiseRejectedResult).reason
        trackError(reason, { component: 'Documents', action: 'load' })
        setDocuments([])
        setStats(null)
        reportFailure(reason, setLoadError)
        return
      }

      if (docsFailed) {
        const reason = (docsResult as PromiseRejectedResult).reason
        trackError(reason, { component: 'Documents', action: 'load' })
        setDocuments([])
        reportFailure(reason, setLoadError)
      } else {
        setDocuments(docsResult.value.data.items || [])
      }

      if (statsFailed) {
        const reason = (statsResult as PromiseRejectedResult).reason
        trackError(reason, { component: 'Documents', action: 'stats' })
        setStats(null)
        const warning = 'Document stats unavailable — library list may still be live.'
        setPartialLoadWarning(warning)
        toast.warning(warning)
      } else {
        setStats(statsResult.value.data)
      }
    } catch (err) {
      trackError(err, { component: 'Documents', action: 'load' })
      setDocuments([])
      setStats(null)
      setDocsUnavailable(true)
      setStatsUnavailable(true)
      reportFailure(err, setLoadError)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadData()
  }, [loadData])

  useEffect(() => {
    loadData(
      filterType === ALL_TYPES_VALUE ? undefined : filterType,
      filterStatus === ALL_STATUS_VALUE ? undefined : filterStatus,
    )
  }, [filterType, filterStatus, loadData])

  const handleSemanticSearch = useCallback(async (query: string) => {
    if (query.length < 3) {
      setSearchResults(null)
      setSearchUnavailable(false)
      return
    }

    setIsSearching(true)
    setSearchUnavailable(false)
    try {
      const response = await api.get(
        `/api/v1/documents/search/semantic?q=${encodeURIComponent(query)}&top_k=10`,
      )
      setSearchResults(response.data.results)
    } catch (err) {
      trackError(err, { component: 'Documents', action: 'search' })
      // Do not set [] — empty results look like "no matches". Mark unavailable instead.
      setSearchResults(null)
      setSearchUnavailable(true)
      toast.error(`Semantic search unavailable: ${getApiErrorMessage(err)}`)
    } finally {
      setIsSearching(false)
    }
  }, [])

  useEffect(() => {
    const timer = setTimeout(() => {
      if (searchTerm.length >= 3) {
        handleSemanticSearch(searchTerm)
      } else {
        setSearchResults(null)
        setSearchUnavailable(false)
      }
    }, 300)
    return () => clearTimeout(timer)
  }, [searchTerm, handleSemanticSearch])

  /** Keyboard `/` focuses library search (skip when typing in another field). */
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== '/' || event.metaKey || event.ctrlKey || event.altKey) return
      const target = event.target as HTMLElement | null
      const tag = target?.tagName?.toLowerCase()
      if (
        tag === 'input' ||
        tag === 'textarea' ||
        tag === 'select' ||
        target?.isContentEditable
      ) {
        return
      }
      event.preventDefault()
      searchInputRef.current?.focus()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [])

  const focusLibrarySearch = useCallback(() => {
    searchInputRef.current?.focus()
  }, [])

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true)
    } else if (e.type === 'dragleave') {
      setDragActive(false)
    }
  }

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      await handleFileUpload(e.dataTransfer.files[0])
    }
  }

  const handleFileUpload = async (file: File) => {
    setUploading(true)
    setUploadProgress(0)
    setUploadError(null)

    const formData = new FormData()
    formData.append('file', file)
    formData.append('title', file.name.replace(/\.[^/.]+$/, ''))
    formData.append('document_type', 'other')
    formData.append('sensitivity', 'internal')

    let progressInterval: ReturnType<typeof setInterval> | undefined
    try {
      progressInterval = setInterval(() => {
        setUploadProgress((prev) => Math.min(prev + 10, 90))
      }, 200)

      await api.post('/api/v1/documents/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: UPLOAD_TIMEOUT_MS,
      })

      setUploadProgress(100)
      toast.success('Document uploaded')

      await loadData(
        filterType === ALL_TYPES_VALUE ? undefined : filterType,
        filterStatus === ALL_STATUS_VALUE ? undefined : filterStatus,
      )
      setShowUploadModal(false)
    } catch (err) {
      trackError(err, { component: 'Documents', action: 'upload' })
      reportFailure(err, setUploadError)
    } finally {
      if (progressInterval) clearInterval(progressInterval)
      setUploading(false)
      setUploadProgress(0)
    }
  }

  const resolveSignedUrl = useCallback(async (documentId: number, download = true) => {
    const response = await api.get(`/api/v1/documents/${documentId}/signed-url`, {
      params: { download },
    })
    const rawUrl = response.data.signed_url as string
    return new URL(rawUrl, api.defaults.baseURL || window.location.origin).toString()
  }, [])

  const handleDocumentOpen = useCallback(
    async (documentId: number, download = true) => {
      try {
        const signedUrl = await resolveSignedUrl(documentId, download)
        if (download) {
          const link = window.document.createElement('a')
          link.href = signedUrl
          link.target = '_blank'
          link.rel = 'noopener noreferrer'
          link.click()
          return
        }
        window.open(signedUrl, '_blank', 'noopener,noreferrer')
      } catch (err) {
        trackError(err, { component: 'Documents', action: download ? 'download' : 'open' })
        reportFailure(err, setLoadError)
      }
    },
    [resolveSignedUrl],
  )

  const isLive = !loading && !docsUnavailable && !statsUnavailable && !loadError
  const isPartial = !loading && (docsUnavailable || statsUnavailable) && !(docsUnavailable && statsUnavailable)

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  const getFileIcon = (type: string) => FILE_ICONS[type] || File

  const filteredDocuments = documents.filter((doc) => {
    if (searchTerm && !searchResults) {
      return (
        doc.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
        doc.reference_number.toLowerCase().includes(searchTerm.toLowerCase())
      )
    }
    return true
  })

  const keywordMatchCount = searchTerm.trim()
    ? documents.filter(
        (doc) =>
          doc.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
          doc.reference_number.toLowerCase().includes(searchTerm.toLowerCase()),
      ).length
    : null

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 text-primary animate-spin" />
      </div>
    )
  }

  return (
    // eslint-disable-next-line jsx-a11y/no-noninteractive-element-interactions -- drag-and-drop is mouse-only; upload button provides keyboard access
    <div onDragEnter={handleDrag} role="region" aria-label="Document library">
      <LibraryShell
        activeView="documents"
        actions={
          <Button onClick={() => setShowUploadModal(true)}>
            <Upload size={20} />
            {t('documents.upload')}
          </Button>
        }
      >
      <div className="flex flex-wrap items-center gap-2">
        {isLive && (
          <Badge variant="secondary" data-testid="documents-live-badge">
            Live data
          </Badge>
        )}
        {isPartial && (
          <Badge variant="outline" data-testid="documents-partial-badge">
            Partial data — some sources unavailable
          </Badge>
        )}
      </div>
      {loadError && (
        <div className="bg-destructive/10 text-destructive p-4 rounded-lg" role="alert" data-testid="documents-load-error">
          {loadError}
        </div>
      )}
      {partialLoadWarning && !loadError && (
        <div className="bg-warning/10 text-warning p-4 rounded-lg" role="status" data-testid="documents-partial-warning">
          {partialLoadWarning}
        </div>
      )}
      {uploadError && (
        <div className="bg-destructive/10 text-destructive p-4 rounded-lg" role="alert">
          {uploadError}
        </div>
      )}

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            {
              label: t('documents.stats.total'),
              value: stats.total_documents,
              icon: FileText,
              variant: 'primary' as const,
            },
            {
              label: t('documents.stats.indexed'),
              value: stats.indexed_documents,
              icon: Brain,
              variant: 'info' as const,
            },
            {
              label: t('documents.stats.chunks'),
              value: stats.total_chunks.toLocaleString(),
              icon: Zap,
              variant: 'warning' as const,
            },
            {
              label: t('documents.stats.processing'),
              value: stats.by_status?.processing || 0,
              icon: Loader2,
              variant: 'success' as const,
            },
          ].map((stat) => (
            <Card key={stat.label} hoverable className="p-5">
              <div
                className={cn(
                  'w-10 h-10 rounded-xl flex items-center justify-center mb-3',
                  stat.variant === 'primary' && 'bg-primary/10 text-primary',
                  stat.variant === 'info' && 'bg-info/10 text-info',
                  stat.variant === 'warning' && 'bg-warning/10 text-warning',
                  stat.variant === 'success' && 'bg-success/10 text-success',
                )}
              >
                <stat.icon className="w-5 h-5" />
              </div>
              <p className="text-2xl font-bold text-foreground">{stat.value}</p>
              <p className="text-sm text-muted-foreground">{stat.label}</p>
            </Card>
          ))}
        </div>
      )}

      {/* Search & Filters — discoverable via label + `/` shortcut */}
      <div className="flex flex-col lg:flex-row gap-4">
        <div className="flex-1 space-y-1.5">
          <div className="flex items-center justify-between gap-2">
            <label htmlFor="documents-library-search" className="text-sm font-medium text-foreground">
              Search library
            </label>
            <span className="text-xs text-muted-foreground" data-testid="documents-search-shortcut-hint">
              Press <kbd className="rounded border border-border bg-muted px-1.5 py-0.5 font-mono text-[10px]">/</kbd> to focus
            </span>
          </div>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" aria-hidden="true" />
            {isSearching && (
              <Loader2 className="absolute right-3 top-1/2 -translate-y-1/2 w-5 h-5 text-primary animate-spin" aria-hidden="true" />
            )}
            <Input
              ref={searchInputRef}
              id="documents-library-search"
              data-testid="documents-library-search"
              type="search"
              role="searchbox"
              aria-label="Search document library"
              placeholder="Search by title or reference… (AI semantic from 3 characters)"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-10 pr-10"
            />
          </div>
          <div
            className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground"
            data-testid="documents-search-status"
          >
            {searchTerm.trim() ? (
              <>
                <span>
                  Showing{' '}
                  <strong className="text-foreground">{filteredDocuments.length}</strong>
                  {' '}in list
                  {keywordMatchCount != null ? (
                    <>
                      {' '}· keyword matches:{' '}
                      <strong className="text-foreground">{keywordMatchCount}</strong>
                    </>
                  ) : null}
                </span>
                {searchTerm.length >= 3 && searchUnavailable ? (
                  <span className="text-warning" data-testid="documents-search-count-unavailable">
                    · Semantic count unavailable (not zero)
                  </span>
                ) : null}
                {searchTerm.length >= 3 && !searchUnavailable && searchResults ? (
                  <span>
                    · Semantic:{' '}
                    <strong className="text-foreground">{searchResults.length}</strong>
                  </span>
                ) : null}
                {searchTerm.length >= 3 && !searchUnavailable ? (
                  <span className="inline-flex items-center gap-1 text-primary">
                    <Sparkles className="w-3 h-3" /> AI semantic search
                  </span>
                ) : null}
              </>
            ) : (
              <span>Type to filter, or press / — counts never invent a zero when search is unavailable.</span>
            )}
          </div>
        </div>

        <div className="flex gap-2">
          <Select value={filterType} onValueChange={setFilterType}>
            <SelectTrigger className="w-[140px]" aria-label="Filter by document type">
              <SelectValue placeholder="All Types" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL_TYPES_VALUE}>All Types</SelectItem>
              <SelectItem value="policy">Policies</SelectItem>
              <SelectItem value="procedure">Procedures</SelectItem>
              <SelectItem value="sop">SOPs</SelectItem>
              <SelectItem value="form">Forms</SelectItem>
              <SelectItem value="manual">Manuals</SelectItem>
            </SelectContent>
          </Select>

          <Select value={filterStatus} onValueChange={setFilterStatus}>
            <SelectTrigger className="w-[140px]" aria-label="Filter by document status">
              <SelectValue placeholder="All Status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL_STATUS_VALUE}>All Status</SelectItem>
              <SelectItem value="indexed">Indexed</SelectItem>
              <SelectItem value="approved">Approved</SelectItem>
              <SelectItem value="processing">Processing</SelectItem>
              <SelectItem value="pending">Pending</SelectItem>
            </SelectContent>
          </Select>

          <div className="flex bg-surface rounded-xl p-1 border border-border">
            <button
              type="button"
              aria-label="Grid view"
              aria-pressed={viewMode === 'grid'}
              onClick={() => setViewMode('grid')}
              className={cn(
                'p-2 rounded-lg transition-all',
                viewMode === 'grid'
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:text-foreground',
              )}
            >
              <Grid3X3 size={20} aria-hidden="true" />
            </button>
            <button
              type="button"
              aria-label="List view"
              aria-pressed={viewMode === 'list'}
              onClick={() => setViewMode('list')}
              className={cn(
                'p-2 rounded-lg transition-all',
                viewMode === 'list'
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:text-foreground',
              )}
            >
              <List size={20} aria-hidden="true" />
            </button>
          </div>
        </div>
      </div>

      {/* Search Results */}
      {searchUnavailable && searchTerm.length >= 3 && (
        <Card className="p-4 border-warning/30 bg-warning/5" data-testid="documents-search-unavailable">
          <p className="text-sm text-warning font-medium">Semantic search unavailable</p>
          <p className="text-xs text-muted-foreground mt-1">
            Live search could not be loaded — do not treat this as zero matches. Title filter still
            applies below.
          </p>
        </Card>
      )}
      {searchResults && searchResults.length > 0 && (
        <Card className="p-4 border-primary/20 bg-primary/5">
          <div className="flex items-center gap-2 mb-3">
            <Sparkles className="w-4 h-4 text-primary" />
            <span className="text-sm font-medium text-primary">AI Semantic Search Results</span>
            <span className="text-xs text-muted-foreground">({searchResults.length} matches)</span>
          </div>
          <div className="space-y-2">
            {searchResults.map((result) => (
              <div
                key={result.document_id}
                onClick={() => navigate(`/documents/${result.document_id}`)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    navigate(`/documents/${result.document_id}`)
                  }
                }}
                role="button"
                tabIndex={0}
                className="flex items-center gap-4 p-3 bg-surface rounded-xl hover:bg-surface-hover cursor-pointer transition-colors"
              >
                <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-primary/20 flex items-center justify-center">
                  <span className="text-sm font-bold text-primary">
                    {((result.score ?? 0) * 100).toFixed(0)}%
                  </span>
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs text-primary">
                      {result.reference_number}
                    </span>
                    <h2 className="text-sm font-medium text-foreground truncate">{result.title}</h2>
                  </div>
                  <p className="text-xs text-muted-foreground line-clamp-1 mt-0.5">
                    {result.chunk_preview}
                  </p>
                </div>
                <ChevronRight className="w-4 h-4 text-muted-foreground" />
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Documents Grid/List */}
      {viewMode === 'grid' ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {docsUnavailable ? (
            <div className="md:col-span-4" data-testid="documents-list-unavailable">
              <EmptyState
                icon={<FileText className="w-8 h-8 text-warning" />}
                title="Documents unavailable"
                description="The library list could not be loaded — this is not an empty library. Retry or check connectivity."
              />
            </div>
          ) : filteredDocuments.length === 0 ? (
            <div className="md:col-span-4" data-testid="documents-empty">
              <EmptyState
                icon={<Search className="w-8 h-8 text-muted-foreground" />}
                title={
                  searchTerm.trim()
                    ? 'No matching documents'
                    : t('documents.empty.title')
                }
                description={
                  searchTerm.trim()
                    ? `No list matches for “${searchTerm}”.${
                        searchUnavailable
                          ? ' Semantic search is unavailable — this is not a confirmed global zero.'
                          : ''
                      }`
                    : 'Press / or use Search library to find policies, procedures, and SOPs.'
                }
              />
              <div className="flex justify-center mt-4">
                <Button
                  type="button"
                  variant="outline"
                  data-testid="documents-search-empty-cta"
                  onClick={focusLibrarySearch}
                >
                  <Search className="w-4 h-4" />
                  {searchTerm.trim() ? 'Refine search' : 'Search library'}
                </Button>
              </div>
            </div>
          ) : (
            filteredDocuments.map((doc) => {
              const FileIcon = getFileIcon(doc.file_type)
              return (
                <Card
                  key={doc.id}
                  hoverable
                  onClick={() => navigate(`/documents/${doc.id}`)}
                  className="p-5 cursor-pointer"
                >
                  <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center mb-4">
                    <FileIcon className="w-6 h-6 text-primary" />
                  </div>

                  <div className="flex items-center gap-2 mb-2">
                    <span className="font-mono text-xs text-primary">{doc.reference_number}</span>
                    <Badge variant={getStatusVariant(doc.status) as any} className="text-[10px]">
                      {doc.status}
                    </Badge>
                  </div>
                  <h2 className="font-semibold text-foreground truncate mb-1 text-base">{doc.title}</h2>

                  {doc.ai_summary && (
                    <p className="text-xs text-muted-foreground line-clamp-2 mb-3">
                      {doc.ai_summary}
                    </p>
                  )}

                  {doc.ai_tags && doc.ai_tags.length > 0 && (
                    <div className="flex flex-wrap gap-1 mb-3">
                      {doc.ai_tags.slice(0, 3).map((tag) => (
                        <span
                          key={tag}
                          className="px-2 py-0.5 text-[10px] bg-primary/10 text-primary rounded-full"
                        >
                          {tag}
                        </span>
                      ))}
                      {doc.ai_tags.length > 3 && (
                        <span className="px-2 py-0.5 text-[10px] bg-surface text-muted-foreground rounded-full">
                          +{doc.ai_tags.length - 3}
                        </span>
                      )}
                    </div>
                  )}

                  <div className="flex items-center justify-between text-xs text-muted-foreground pt-2 border-t border-border">
                    <span>{formatFileSize(doc.file_size)}</span>
                    <div className="flex items-center gap-3">
                      <span className="flex items-center gap-1">
                        <Eye className="w-3 h-3" />
                        {doc.view_count}
                      </span>
                      {doc.indexed_at && (
                        <span title="AI Indexed">
                          <Sparkles className="w-3 h-3 text-primary" />
                        </span>
                      )}
                    </div>
                  </div>
                </Card>
              )
            })
          )}
        </div>
      ) : docsUnavailable ? (
        <div data-testid="documents-list-unavailable">
          <EmptyState
            icon={<FileText className="w-8 h-8 text-warning" />}
            title="Documents unavailable"
            description="The library list could not be loaded — this is not an empty library. Retry or check connectivity."
          />
        </div>
      ) : (
        <Card className="overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-border">
                <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase">
                  {t('documents.table.document')}
                </th>
                <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase">
                  {t('common.type')}
                </th>
                <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase">
                  {t('common.status')}
                </th>
                <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase">
                  {t('documents.table.size')}
                </th>
                <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase">
                  {t('documents.table.views')}
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {filteredDocuments.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-6 py-8" data-testid="documents-empty">
                    <EmptyState
                      icon={<Search className="w-8 h-8 text-muted-foreground" />}
                      title={
                        searchTerm.trim()
                          ? 'No matching documents'
                          : t('documents.empty.title')
                      }
                      description={
                        searchTerm.trim()
                          ? `No list matches for “${searchTerm}”.${
                              searchUnavailable
                                ? ' Semantic search is unavailable — this is not a confirmed global zero.'
                                : ''
                            }`
                          : 'Press / or use Search library to find policies, procedures, and SOPs.'
                      }
                    />
                    <div className="flex justify-center mt-4">
                      <Button
                        type="button"
                        variant="outline"
                        data-testid="documents-search-empty-cta"
                        onClick={focusLibrarySearch}
                      >
                        <Search className="w-4 h-4" />
                        {searchTerm.trim() ? 'Refine search' : 'Search library'}
                      </Button>
                    </div>
                  </td>
                </tr>
              ) : (
                filteredDocuments.map((doc) => {
                const FileIcon = getFileIcon(doc.file_type)
                return (
                  <tr
                    key={doc.id}
                    onClick={() => navigate(`/documents/${doc.id}`)}
                    className="hover:bg-surface cursor-pointer"
                  >
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
                          <FileIcon className="w-5 h-5 text-primary" />
                        </div>
                        <div>
                          <p className="font-medium text-foreground">{doc.title}</p>
                          <p className="text-xs text-muted-foreground font-mono">
                            {doc.reference_number}
                          </p>
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-sm text-foreground capitalize">
                      {doc.document_type}
                    </td>
                    <td className="px-6 py-4">
                      <Badge variant={getStatusVariant(doc.status) as any}>{doc.status}</Badge>
                    </td>
                    <td className="px-6 py-4 text-sm text-muted-foreground">
                      {formatFileSize(doc.file_size)}
                    </td>
                    <td className="px-6 py-4 text-sm text-muted-foreground">{doc.view_count}</td>
                  </tr>
                )
              })
              )}
            </tbody>
          </table>
        </Card>
      )}

      {/* Upload Modal */}
      <Dialog
        open={showUploadModal}
        onOpenChange={(open) => !uploading && setShowUploadModal(open)}
      >
        <DialogContent
          className={cn(dragActive && 'border-primary bg-primary/5')}
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
        >
          <DialogHeader>
            <DialogTitle>{t('documents.upload')}</DialogTitle>
            <DialogDescription>Upload governance evidence for durable storage and semantic indexing.</DialogDescription>
          </DialogHeader>

          <div className="py-4">
            {uploading ? (
              <div className="text-center py-8">
                <Loader2 className="w-12 h-12 mx-auto mb-4 text-primary animate-spin" />
                <p className="text-foreground mb-2">{t('documents.processing')}</p>
                <div className="w-full h-2 bg-surface rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-brand transition-all duration-300"
                    style={{ width: `${uploadProgress}%` }}
                  />
                </div>
                <p className="text-sm text-muted-foreground mt-2">
                  Extracting metadata, generating embeddings...
                </p>
              </div>
            ) : (
              <div
                className={cn(
                  'border-2 border-dashed rounded-2xl p-12 text-center transition-colors',
                  dragActive
                    ? 'border-primary bg-primary/5'
                    : 'border-border hover:border-muted-foreground',
                )}
              >
                <Upload className="w-12 h-12 mx-auto mb-4 text-muted-foreground" />
                <p className="text-foreground mb-2">{t('documents.drag_drop')}</p>
                <p className="text-sm text-muted-foreground mb-4">
                  PDF, Word, Excel, Markdown, or Text files
                </p>
                <label>
                  <Button asChild>
                    <span className="cursor-pointer">
                      <Plus size={16} />
                      {t('documents.browse_files')}
                    </span>
                  </Button>
                  <input
                    type="file"
                    className="hidden"
                    accept=".pdf,.doc,.docx,.xls,.xlsx,.csv,.md,.txt,.png,.jpg,.jpeg"
                    onChange={(e) => e.target.files?.[0] && handleFileUpload(e.target.files[0])}
                  />
                </label>
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>

      {/* Document Detail Modal */}
      <Dialog open={!!selectedDocument} onOpenChange={() => setSelectedDocument(null)}>
        <DialogContent className="max-w-4xl max-h-[90vh] overflow-hidden">
          {selectedDocument && (
            <>
              <DialogHeader>
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center">
                    {(() => {
                      const Icon = getFileIcon(selectedDocument.file_type)
                      return <Icon className="w-6 h-6 text-primary" />
                    })()}
                  </div>
                  <div>
                    <DialogTitle>{selectedDocument.title}</DialogTitle>
                    <p className="text-sm text-muted-foreground font-mono">
                      {selectedDocument.reference_number}
                    </p>
                  </div>
                </div>
                <DialogDescription>
                  Review extracted metadata and open the stored source document.
                </DialogDescription>
                <div className="flex items-center gap-2 mt-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => void handleDocumentOpen(selectedDocument.id, true)}
                  >
                    <Download size={16} />
                    {t('common.download')}
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => void handleDocumentOpen(selectedDocument.id, false)}
                  >
                    <ExternalLink size={16} />
                    Open
                  </Button>
                </div>
              </DialogHeader>

              <div className="overflow-y-auto max-h-[calc(90vh-160px)] space-y-6 py-4">
                {selectedDocument.ai_summary && (
                  <Card className="p-4 border-primary/20 bg-primary/5">
                    <div className="flex items-center gap-2 mb-2">
                      <Sparkles className="w-4 h-4 text-primary" />
                      <span className="text-sm font-medium text-primary">AI Summary</span>
                    </div>
                    <p className="text-foreground">{selectedDocument.ai_summary}</p>
                  </Card>
                )}

                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                  <Card className="p-4">
                    <p className="text-xs text-muted-foreground mb-1">Document Type</p>
                    <p className="text-foreground capitalize">{selectedDocument.document_type}</p>
                  </Card>
                  <Card className="p-4">
                    <p className="text-xs text-muted-foreground mb-1">File Size</p>
                    <p className="text-foreground">{formatFileSize(selectedDocument.file_size)}</p>
                  </Card>
                  <Card className="p-4">
                    <p className="text-xs text-muted-foreground mb-1">Status</p>
                    <Badge variant={getStatusVariant(selectedDocument.status) as any}>
                      {selectedDocument.status}
                    </Badge>
                  </Card>
                  <Card className="p-4">
                    <p className="text-xs text-muted-foreground mb-1">Sensitivity</p>
                    <p className="text-foreground capitalize">{selectedDocument.sensitivity}</p>
                  </Card>
                </div>

                {selectedDocument.ai_tags && selectedDocument.ai_tags.length > 0 && (
                  <div>
                    <h3 className="text-sm font-medium text-muted-foreground mb-2 flex items-center gap-2">
                      <Tag className="w-4 h-4" />
                      AI-Generated Tags
                    </h3>
                    <div className="flex flex-wrap gap-2">
                      {selectedDocument.ai_tags.map((tag) => (
                        <span
                          key={tag}
                          className="px-3 py-1 text-sm bg-primary/10 text-primary rounded-full border border-primary/20"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {selectedDocument.ai_keywords && selectedDocument.ai_keywords.length > 0 && (
                  <div>
                    <h3 className="text-sm font-medium text-muted-foreground mb-2">Keywords</h3>
                    <div className="flex flex-wrap gap-2">
                      {selectedDocument.ai_keywords.map((keyword) => (
                        <span
                          key={keyword}
                          className="px-2 py-0.5 text-xs bg-surface text-muted-foreground rounded"
                        >
                          {keyword}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                <div className="flex items-center gap-6 text-sm text-muted-foreground">
                  <span className="flex items-center gap-2">
                    <Eye className="w-4 h-4" />
                    {selectedDocument.view_count} views
                  </span>
                  <span className="flex items-center gap-2">
                    <Download className="w-4 h-4" />
                    {selectedDocument.download_count} downloads
                  </span>
                  <span className="flex items-center gap-2">
                    <Calendar className="w-4 h-4" />
                    {new Date(selectedDocument.created_at).toLocaleDateString()}
                  </span>
                  {selectedDocument.indexed_at && (
                    <span className="flex items-center gap-2 text-primary">
                      <CheckCircle2 className="w-4 h-4" />
                      AI Indexed
                    </span>
                  )}
                </div>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>

      {/* Drag Overlay */}
      {dragActive && (
        <div className="fixed inset-0 z-[60] bg-primary/10 backdrop-blur-sm flex items-center justify-center pointer-events-none">
          <Card className="p-12 text-center border-2 border-dashed border-primary">
            <Upload className="w-16 h-16 mx-auto mb-4 text-primary" />
            <p className="text-xl font-semibold text-foreground">Drop your document here</p>
          </Card>
        </div>
      )}
      </LibraryShell>
    </div>
  )
}
