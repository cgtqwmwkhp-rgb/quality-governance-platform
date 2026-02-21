import { useEffect, useState, useCallback } from 'react'
import { 
  Plus, Search, Upload, FileText, FileSpreadsheet, Image, File, 
  Eye, Download, Tag, Calendar, Sparkles, 
  CheckCircle2, Loader2, Grid3X3, List, 
  ChevronRight, ExternalLink, Brain, Zap
} from 'lucide-react'
import api from '../api/client'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Card } from '../components/ui/Card'
import { Badge, type BadgeVariant } from '../components/ui/Badge'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '../components/ui/Dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/Select'
import { cn } from "../helpers/utils"
import { useToast, ToastContainer } from '../components/ui/Toast'
import { TableSkeleton } from '../components/ui/SkeletonLoader'

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
    case 'indexed': return 'resolved'
    case 'approved': return 'success'
    case 'processing': return 'in-progress'
    case 'pending': return 'submitted'
    case 'failed': return 'destructive'
    default: return 'secondary'
  }
}

export default function Documents() {
  const { toasts, show: showToast, dismiss: dismissToast } = useToast()
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
  const [filterType, setFilterType] = useState<string>('')
  const [filterStatus, setFilterStatus] = useState<string>('')

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      const [docsRes, statsRes] = await Promise.all([
        api.get('/api/v1/documents?page=1&page_size=50'),
        api.get('/api/v1/documents/stats/overview'),
      ])
      setDocuments(docsRes.data.items || [])
      setStats(statsRes.data)
    } catch (err) {
      console.error('Failed to load documents:', err)
      showToast('Failed to load documents. Please try again.', 'error')
      setDocuments([])
    } finally {
      setLoading(false)
    }
  }

  const handleSemanticSearch = useCallback(async (query: string) => {
    if (query.length < 3) {
      setSearchResults(null)
      return
    }

    setIsSearching(true)
    try {
      const response = await api.get(`/api/v1/documents/search/semantic?q=${encodeURIComponent(query)}&top_k=10`)
      setSearchResults(response.data.results)
    } catch (err) {
      console.error('Search failed:', err)
      showToast('Search failed. Please try again.', 'error')
      setSearchResults([])
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
      }
    }, 300)
    return () => clearTimeout(timer)
  }, [searchTerm, handleSemanticSearch])

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
    
    const formData = new FormData()
    formData.append('file', file)
    formData.append('title', file.name.replace(/\.[^/.]+$/, ''))
    formData.append('document_type', 'other')
    formData.append('sensitivity', 'internal')
    
    try {
      const progressInterval = setInterval(() => {
        setUploadProgress(prev => Math.min(prev + 10, 90))
      }, 200)
      
      await api.post('/api/v1/documents/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      
      clearInterval(progressInterval)
      setUploadProgress(100)
      
      await loadData()
      setShowUploadModal(false)
    } catch (err) {
      console.error('Upload failed:', err)
      showToast('Document upload failed. Please try again.', 'error')
    } finally {
      setUploading(false)
      setUploadProgress(0)
    }
  }

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  const getFileIcon = (type: string) => FILE_ICONS[type] || File

  const filteredDocuments = documents.filter(doc => {
    if (filterType && doc.document_type !== filterType) return false
    if (filterStatus && doc.status !== filterStatus) return false
    if (searchTerm && !searchResults) {
      return doc.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
             doc.reference_number.toLowerCase().includes(searchTerm.toLowerCase())
    }
    return true
  })

  if (loading) {
    return (
      <div className="p-6"><TableSkeleton rows={5} columns={4} /></div>
    )
  }

  return (
    <div className="space-y-6 animate-fade-in" onDragEnter={handleDrag}>
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-foreground">Document Library</h1>
          <p className="text-muted-foreground mt-1">AI-powered document management with semantic search</p>
        </div>
        <Button onClick={() => setShowUploadModal(true)}>
          <Upload size={20} />
          Upload Document
        </Button>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            { label: 'Total Documents', value: stats.total_documents, icon: FileText, variant: 'primary' as const },
            { label: 'AI Indexed', value: stats.indexed_documents, icon: Brain, variant: 'info' as const },
            { label: 'Semantic Chunks', value: stats.total_chunks.toLocaleString(), icon: Zap, variant: 'warning' as const },
            { label: 'Processing', value: stats.by_status?.['processing'] || 0, icon: Loader2, variant: 'success' as const },
          ].map((stat) => (
            <Card key={stat.label} hoverable className="p-5">
              <div className={cn(
                "w-10 h-10 rounded-xl flex items-center justify-center mb-3",
                stat.variant === 'primary' && "bg-primary/10 text-primary",
                stat.variant === 'info' && "bg-info/10 text-info",
                stat.variant === 'warning' && "bg-warning/10 text-warning",
                stat.variant === 'success' && "bg-success/10 text-success",
              )}>
                <stat.icon className="w-5 h-5" />
              </div>
              <p className="text-2xl font-bold text-foreground">{stat.value}</p>
              <p className="text-sm text-muted-foreground">{stat.label}</p>
            </Card>
          ))}
        </div>
      )}

      {/* Search & Filters */}
      <div className="flex flex-col lg:flex-row gap-4">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
          {isSearching && (
            <Loader2 className="absolute right-3 top-1/2 -translate-y-1/2 w-5 h-5 text-primary animate-spin" />
          )}
          <Input
            type="text"
            placeholder="AI-powered semantic search... (min 3 characters)"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-10 pr-10"
          />
          {searchTerm.length >= 3 && (
            <div className="absolute left-0 right-0 top-full mt-1 flex items-center gap-2 text-xs text-primary">
              <Sparkles className="w-3 h-3" />
              <span>Using AI semantic search</span>
            </div>
          )}
        </div>

        <div className="flex gap-2">
          <Select value={filterType} onValueChange={setFilterType}>
            <SelectTrigger className="w-[140px]">
              <SelectValue placeholder="All Types" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="">All Types</SelectItem>
              <SelectItem value="policy">Policies</SelectItem>
              <SelectItem value="procedure">Procedures</SelectItem>
              <SelectItem value="sop">SOPs</SelectItem>
              <SelectItem value="form">Forms</SelectItem>
              <SelectItem value="manual">Manuals</SelectItem>
            </SelectContent>
          </Select>

          <Select value={filterStatus} onValueChange={setFilterStatus}>
            <SelectTrigger className="w-[140px]">
              <SelectValue placeholder="All Status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="">All Status</SelectItem>
              <SelectItem value="indexed">Indexed</SelectItem>
              <SelectItem value="approved">Approved</SelectItem>
              <SelectItem value="processing">Processing</SelectItem>
              <SelectItem value="pending">Pending</SelectItem>
            </SelectContent>
          </Select>

          <div className="flex bg-surface rounded-xl p-1 border border-border">
            <button
              onClick={() => setViewMode('grid')}
              className={cn(
                "p-2 rounded-lg transition-all",
                viewMode === 'grid' ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground'
              )}
            >
              <Grid3X3 size={20} />
            </button>
            <button
              onClick={() => setViewMode('list')}
              className={cn(
                "p-2 rounded-lg transition-all",
                viewMode === 'list' ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground'
              )}
            >
              <List size={20} />
            </button>
          </div>
        </div>
      </div>

      {/* Search Results */}
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
                onClick={() => {
                  const doc = documents.find(d => d.id === result.document_id)
                  if (doc) setSelectedDocument(doc)
                }}
                className="flex items-center gap-4 p-3 bg-surface rounded-xl hover:bg-surface-hover cursor-pointer transition-colors"
              >
                <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-primary/20 flex items-center justify-center">
                  <span className="text-sm font-bold text-primary">{(result.score * 100).toFixed(0)}%</span>
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs text-primary">{result.reference_number}</span>
                    <h4 className="text-sm font-medium text-foreground truncate">{result.title}</h4>
                  </div>
                  <p className="text-xs text-muted-foreground line-clamp-1 mt-0.5">{result.chunk_preview}</p>
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
          {filteredDocuments.length === 0 ? (
            <div className="md:col-span-4">
              <Card className="p-12 text-center">
                <FileText className="w-16 h-16 mx-auto mb-4 text-muted-foreground/50" />
                <h3 className="text-lg font-semibold text-foreground mb-2">No Documents Found</h3>
                <p className="text-muted-foreground">Upload your first document to get started</p>
              </Card>
            </div>
          ) : (
            filteredDocuments.map((doc) => {
              const FileIcon = getFileIcon(doc.file_type)
              return (
                <Card
                  key={doc.id}
                  hoverable
                  onClick={() => setSelectedDocument(doc)}
                  className="p-5 cursor-pointer"
                >
                  <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center mb-4">
                    <FileIcon className="w-6 h-6 text-primary" />
                  </div>

                  <div className="flex items-center gap-2 mb-2">
                    <span className="font-mono text-xs text-primary">{doc.reference_number}</span>
                    <Badge variant={getStatusVariant(doc.status) as BadgeVariant} className="text-[10px]">
                      {doc.status}
                    </Badge>
                  </div>
                  <h3 className="font-semibold text-foreground truncate mb-1">
                    {doc.title}
                  </h3>
                  
                  {doc.ai_summary && (
                    <p className="text-xs text-muted-foreground line-clamp-2 mb-3">{doc.ai_summary}</p>
                  )}

                  {doc.ai_tags && doc.ai_tags.length > 0 && (
                    <div className="flex flex-wrap gap-1 mb-3">
                      {doc.ai_tags.slice(0, 3).map(tag => (
                        <span key={tag} className="px-2 py-0.5 text-[10px] bg-primary/10 text-primary rounded-full">
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
                        <span title="AI Indexed"><Sparkles className="w-3 h-3 text-primary" /></span>
                      )}
                    </div>
                  </div>
                </Card>
              )
            })
          )}
        </div>
      ) : (
        <Card className="overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-border">
                <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase">Document</th>
                <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase">Type</th>
                <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase">Status</th>
                <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase">Size</th>
                <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase">Views</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {filteredDocuments.map((doc) => {
                const FileIcon = getFileIcon(doc.file_type)
                return (
                  <tr
                    key={doc.id}
                    onClick={() => setSelectedDocument(doc)}
                    className="hover:bg-surface cursor-pointer"
                  >
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
                          <FileIcon className="w-5 h-5 text-primary" />
                        </div>
                        <div>
                          <p className="font-medium text-foreground">{doc.title}</p>
                          <p className="text-xs text-muted-foreground font-mono">{doc.reference_number}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-sm text-foreground capitalize">{doc.document_type}</td>
                    <td className="px-6 py-4">
                      <Badge variant={getStatusVariant(doc.status) as BadgeVariant}>
                        {doc.status}
                      </Badge>
                    </td>
                    <td className="px-6 py-4 text-sm text-muted-foreground">{formatFileSize(doc.file_size)}</td>
                    <td className="px-6 py-4 text-sm text-muted-foreground">{doc.view_count}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </Card>
      )}

      {/* Upload Modal */}
      <Dialog open={showUploadModal} onOpenChange={(open) => !uploading && setShowUploadModal(open)}>
        <DialogContent
          className={cn(dragActive && "border-primary bg-primary/5")}
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
        >
          <DialogHeader>
            <DialogTitle>Upload Document</DialogTitle>
          </DialogHeader>
          
          <div className="py-4">
            {uploading ? (
              <div className="text-center py-8">
                <Loader2 className="w-12 h-12 mx-auto mb-4 text-primary animate-spin" />
                <p className="text-foreground mb-2">Processing with AI...</p>
                <div className="w-full h-2 bg-surface rounded-full overflow-hidden">
                  <div 
                    className="h-full bg-gradient-brand transition-all duration-300"
                    style={{ width: `${uploadProgress}%` }}
                  />
                </div>
                <p className="text-sm text-muted-foreground mt-2">Extracting metadata, generating embeddings...</p>
              </div>
            ) : (
              <div 
                className={cn(
                  "border-2 border-dashed rounded-2xl p-12 text-center transition-colors",
                  dragActive ? 'border-primary bg-primary/5' : 'border-border hover:border-muted-foreground'
                )}
              >
                <Upload className="w-12 h-12 mx-auto mb-4 text-muted-foreground" />
                <p className="text-foreground mb-2">Drag & drop your document here</p>
                <p className="text-sm text-muted-foreground mb-4">PDF, Word, Excel, Markdown, or Text files</p>
                <label>
                  <Button asChild>
                    <span className="cursor-pointer">
                      <Plus size={16} />
                      Browse Files
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
                    {(() => { const Icon = getFileIcon(selectedDocument.file_type); return <Icon className="w-6 h-6 text-primary" /> })()}
                  </div>
                  <div>
                    <DialogTitle>{selectedDocument.title}</DialogTitle>
                    <p className="text-sm text-muted-foreground font-mono">{selectedDocument.reference_number}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2 mt-2">
                  <Button variant="outline" size="sm">
                    <Download size={16} />
                    Download
                  </Button>
                  <Button variant="outline" size="sm">
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
                    <Badge variant={getStatusVariant(selectedDocument.status) as BadgeVariant}>
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
                      {selectedDocument.ai_tags.map(tag => (
                        <span key={tag} className="px-3 py-1 text-sm bg-primary/10 text-primary rounded-full border border-primary/20">
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
                      {selectedDocument.ai_keywords.map(keyword => (
                        <span key={keyword} className="px-2 py-0.5 text-xs bg-surface text-muted-foreground rounded">
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
      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </div>
  )
}
