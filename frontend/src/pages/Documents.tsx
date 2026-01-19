import { useEffect, useState, useCallback } from 'react'
import { 
  Plus, X, Search, Upload, FileText, FileSpreadsheet, Image, File, 
  Eye, Download, Tag, Calendar, Sparkles, 
  CheckCircle2, Loader2, Grid3X3, List, 
  ChevronRight, ExternalLink, Brain, Zap
} from 'lucide-react'
import api from '../api/client'

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

const FILE_COLORS: Record<string, string> = {
  pdf: 'from-red-500 to-rose-500',
  docx: 'from-blue-500 to-indigo-500',
  doc: 'from-blue-500 to-indigo-500',
  xlsx: 'from-emerald-500 to-green-500',
  xls: 'from-emerald-500 to-green-500',
  csv: 'from-emerald-500 to-green-500',
  png: 'from-purple-500 to-pink-500',
  jpg: 'from-purple-500 to-pink-500',
  jpeg: 'from-purple-500 to-pink-500',
  md: 'from-slate-500 to-slate-600',
  txt: 'from-slate-500 to-slate-600',
}

const STATUS_COLORS: Record<string, string> = {
  indexed: 'bg-emerald-500/20 text-emerald-400',
  approved: 'bg-green-500/20 text-green-400',
  processing: 'bg-amber-500/20 text-amber-400',
  pending: 'bg-blue-500/20 text-blue-400',
  failed: 'bg-red-500/20 text-red-400',
}

export default function Documents() {
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

  // Filters
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
      // Simulate progress
      const progressInterval = setInterval(() => {
        setUploadProgress(prev => Math.min(prev + 10, 90))
      }, 200)
      
      await api.post('/api/v1/documents/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      
      clearInterval(progressInterval)
      setUploadProgress(100)
      
      // Reload documents
      await loadData()
      setShowUploadModal(false)
    } catch (err) {
      console.error('Upload failed:', err)
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
  const getFileColor = (type: string) => FILE_COLORS[type] || 'from-slate-500 to-slate-600'

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
      <div className="flex items-center justify-center h-64">
        <div className="relative">
          <div className="animate-spin rounded-full h-16 w-16 border-4 border-sky-500/20 border-t-sky-500"></div>
          <FileText className="absolute inset-0 m-auto w-6 h-6 text-sky-400" />
        </div>
      </div>
    )
  }

  return (
    <div 
      className="space-y-6 animate-fade-in"
      onDragEnter={handleDrag}
    >
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold bg-gradient-to-r from-sky-400 via-blue-400 to-indigo-400 bg-clip-text text-transparent">
            Document Library
          </h1>
          <p className="text-slate-400 mt-1">AI-powered document management with semantic search</p>
        </div>
        <button
          onClick={() => setShowUploadModal(true)}
          className="inline-flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-sky-500 via-blue-500 to-indigo-500
            text-white font-semibold rounded-xl hover:opacity-90 transition-all duration-200 
            shadow-lg shadow-sky-500/25 hover:shadow-xl hover:shadow-sky-500/30 hover:-translate-y-0.5"
        >
          <Upload size={20} />
          Upload Document
        </button>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            { label: 'Total Documents', value: stats.total_documents, icon: FileText, color: 'from-sky-500 to-blue-500' },
            { label: 'AI Indexed', value: stats.indexed_documents, icon: Brain, color: 'from-violet-500 to-purple-500' },
            { label: 'Semantic Chunks', value: stats.total_chunks.toLocaleString(), icon: Zap, color: 'from-amber-500 to-orange-500' },
            { label: 'Processing', value: stats.by_status?.processing || 0, icon: Loader2, color: 'from-emerald-500 to-green-500' },
          ].map((stat, index) => (
            <div 
              key={stat.label}
              className="relative overflow-hidden bg-slate-900/50 backdrop-blur-xl border border-slate-800 rounded-2xl p-5 
                hover:border-slate-700 transition-all duration-300 group animate-slide-in"
              style={{ animationDelay: `${index * 50}ms` }}
            >
              <div className={`absolute inset-0 bg-gradient-to-br ${stat.color} opacity-0 group-hover:opacity-5 transition-opacity`} />
              <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${stat.color} flex items-center justify-center mb-3`}>
                <stat.icon className="w-5 h-5 text-white" />
              </div>
              <p className="text-2xl font-bold text-white">{stat.value}</p>
              <p className="text-sm text-slate-400">{stat.label}</p>
            </div>
          ))}
        </div>
      )}

      {/* Search & Filters */}
      <div className="flex flex-col lg:flex-row gap-4">
        {/* Semantic Search */}
        <div className="flex-1 relative">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-500" />
          {isSearching && (
            <Loader2 className="absolute right-4 top-1/2 -translate-y-1/2 w-5 h-5 text-sky-400 animate-spin" />
          )}
          <input
            type="text"
            placeholder="AI-powered semantic search... (min 3 characters)"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-12 pr-12 py-3 bg-slate-900/50 border border-slate-800 rounded-xl
              text-white placeholder-slate-500 focus:outline-none focus:border-sky-500
              focus:ring-2 focus:ring-sky-500/20 transition-all duration-200"
          />
          {searchTerm.length >= 3 && (
            <div className="absolute left-0 right-0 top-full mt-1 flex items-center gap-2 text-xs text-sky-400">
              <Sparkles className="w-3 h-3" />
              <span>Using AI semantic search</span>
            </div>
          )}
        </div>

        {/* Filters */}
        <div className="flex gap-2">
          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
            className="px-4 py-3 bg-slate-900/50 border border-slate-800 rounded-xl
              text-white focus:outline-none focus:border-sky-500 appearance-none cursor-pointer"
          >
            <option value="">All Types</option>
            <option value="policy">Policies</option>
            <option value="procedure">Procedures</option>
            <option value="sop">SOPs</option>
            <option value="form">Forms</option>
            <option value="manual">Manuals</option>
          </select>

          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            className="px-4 py-3 bg-slate-900/50 border border-slate-800 rounded-xl
              text-white focus:outline-none focus:border-sky-500 appearance-none cursor-pointer"
          >
            <option value="">All Status</option>
            <option value="indexed">Indexed</option>
            <option value="approved">Approved</option>
            <option value="processing">Processing</option>
            <option value="pending">Pending</option>
          </select>

          {/* View Toggle */}
          <div className="flex bg-slate-800/50 rounded-xl p-1">
            <button
              onClick={() => setViewMode('grid')}
              className={`p-2 rounded-lg transition-all ${viewMode === 'grid' ? 'bg-sky-500 text-white' : 'text-slate-400 hover:text-white'}`}
            >
              <Grid3X3 size={20} />
            </button>
            <button
              onClick={() => setViewMode('list')}
              className={`p-2 rounded-lg transition-all ${viewMode === 'list' ? 'bg-sky-500 text-white' : 'text-slate-400 hover:text-white'}`}
            >
              <List size={20} />
            </button>
          </div>
        </div>
      </div>

      {/* Search Results */}
      {searchResults && searchResults.length > 0 && (
        <div className="bg-gradient-to-br from-sky-500/10 to-indigo-500/10 border border-sky-500/20 rounded-2xl p-4">
          <div className="flex items-center gap-2 mb-3">
            <Sparkles className="w-4 h-4 text-sky-400" />
            <span className="text-sm font-medium text-sky-400">AI Semantic Search Results</span>
            <span className="text-xs text-slate-500">({searchResults.length} matches)</span>
          </div>
          <div className="space-y-2">
            {searchResults.map((result, index) => (
              <div
                key={result.document_id}
                onClick={() => {
                  const doc = documents.find(d => d.id === result.document_id)
                  if (doc) setSelectedDocument(doc)
                }}
                className="flex items-center gap-4 p-3 bg-slate-800/50 rounded-xl hover:bg-slate-800 
                  cursor-pointer transition-colors animate-slide-in"
                style={{ animationDelay: `${index * 30}ms` }}
              >
                <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-sky-500/20 flex items-center justify-center">
                  <span className="text-sm font-bold text-sky-400">{(result.score * 100).toFixed(0)}%</span>
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs text-sky-400">{result.reference_number}</span>
                    <h4 className="text-sm font-medium text-white truncate">{result.title}</h4>
                  </div>
                  <p className="text-xs text-slate-400 line-clamp-1 mt-0.5">{result.chunk_preview}</p>
                </div>
                <ChevronRight className="w-4 h-4 text-slate-500" />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Documents Grid/List */}
      {viewMode === 'grid' ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {filteredDocuments.length === 0 ? (
            <div className="md:col-span-4 bg-slate-900/50 border border-slate-800 rounded-2xl p-12 text-center">
              <FileText className="w-16 h-16 mx-auto mb-4 text-slate-600" />
              <h3 className="text-lg font-semibold text-white mb-2">No Documents Found</h3>
              <p className="text-slate-400">Upload your first document to get started</p>
            </div>
          ) : (
            filteredDocuments.map((doc, index) => {
              const FileIcon = getFileIcon(doc.file_type)
              return (
                <div
                  key={doc.id}
                  onClick={() => setSelectedDocument(doc)}
                  className="bg-slate-900/50 backdrop-blur-xl border border-slate-800 rounded-2xl p-5
                    hover:border-sky-500/30 hover:shadow-lg hover:shadow-sky-500/10
                    transition-all duration-300 cursor-pointer group animate-slide-in"
                  style={{ animationDelay: `${index * 30}ms` }}
                >
                  {/* File Icon */}
                  <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${getFileColor(doc.file_type)} 
                    flex items-center justify-center mb-4 shadow-lg`}>
                    <FileIcon className="w-6 h-6 text-white" />
                  </div>

                  {/* Title & Meta */}
                  <div className="flex items-center gap-2 mb-2">
                    <span className="font-mono text-xs text-sky-400">{doc.reference_number}</span>
                    <span className={`px-1.5 py-0.5 text-[10px] font-medium rounded ${STATUS_COLORS[doc.status] || 'bg-slate-500/20 text-slate-400'}`}>
                      {doc.status}
                    </span>
                  </div>
                  <h3 className="font-semibold text-white truncate group-hover:text-sky-300 transition-colors mb-1">
                    {doc.title}
                  </h3>
                  
                  {/* AI Summary */}
                  {doc.ai_summary && (
                    <p className="text-xs text-slate-400 line-clamp-2 mb-3">{doc.ai_summary}</p>
                  )}

                  {/* Tags */}
                  {doc.ai_tags && doc.ai_tags.length > 0 && (
                    <div className="flex flex-wrap gap-1 mb-3">
                      {doc.ai_tags.slice(0, 3).map(tag => (
                        <span key={tag} className="px-2 py-0.5 text-[10px] bg-sky-500/10 text-sky-400 rounded-full">
                          {tag}
                        </span>
                      ))}
                      {doc.ai_tags.length > 3 && (
                        <span className="px-2 py-0.5 text-[10px] bg-slate-800 text-slate-400 rounded-full">
                          +{doc.ai_tags.length - 3}
                        </span>
                      )}
                    </div>
                  )}

                  {/* Footer */}
                  <div className="flex items-center justify-between text-xs text-slate-500 pt-2 border-t border-slate-800">
                    <span>{formatFileSize(doc.file_size)}</span>
                    <div className="flex items-center gap-3">
                      <span className="flex items-center gap-1">
                        <Eye className="w-3 h-3" />
                        {doc.view_count}
                      </span>
                      {doc.indexed_at && (
                        <span title="AI Indexed"><Sparkles className="w-3 h-3 text-sky-400" /></span>
                      )}
                    </div>
                  </div>
                </div>
              )
            })
          )}
        </div>
      ) : (
        /* List View */
        <div className="bg-slate-900/50 backdrop-blur-xl border border-slate-800 rounded-2xl overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-slate-800">
                <th className="px-6 py-4 text-left text-xs font-semibold text-slate-400 uppercase">Document</th>
                <th className="px-6 py-4 text-left text-xs font-semibold text-slate-400 uppercase">Type</th>
                <th className="px-6 py-4 text-left text-xs font-semibold text-slate-400 uppercase">Status</th>
                <th className="px-6 py-4 text-left text-xs font-semibold text-slate-400 uppercase">Size</th>
                <th className="px-6 py-4 text-left text-xs font-semibold text-slate-400 uppercase">Views</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {filteredDocuments.map((doc, index) => {
                const FileIcon = getFileIcon(doc.file_type)
                return (
                  <tr
                    key={doc.id}
                    onClick={() => setSelectedDocument(doc)}
                    className="hover:bg-slate-800/30 cursor-pointer animate-slide-in"
                    style={{ animationDelay: `${index * 20}ms` }}
                  >
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <div className={`w-10 h-10 rounded-lg bg-gradient-to-br ${getFileColor(doc.file_type)} 
                          flex items-center justify-center`}>
                          <FileIcon className="w-5 h-5 text-white" />
                        </div>
                        <div>
                          <p className="font-medium text-white">{doc.title}</p>
                          <p className="text-xs text-slate-500 font-mono">{doc.reference_number}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-sm text-slate-300 capitalize">{doc.document_type}</td>
                    <td className="px-6 py-4">
                      <span className={`px-2.5 py-1 text-xs font-medium rounded ${STATUS_COLORS[doc.status]}`}>
                        {doc.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm text-slate-400">{formatFileSize(doc.file_size)}</td>
                    <td className="px-6 py-4 text-sm text-slate-400">{doc.view_count}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Upload Modal */}
      {showUploadModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => !uploading && setShowUploadModal(false)} />
          <div 
            className={`relative w-full max-w-xl bg-slate-900 border rounded-2xl shadow-xl animate-fade-in
              ${dragActive ? 'border-sky-500 bg-sky-500/5' : 'border-slate-800'}`}
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
          >
            <div className="flex items-center justify-between p-6 border-b border-slate-800">
              <h2 className="text-lg font-semibold text-white">Upload Document</h2>
              <button
                onClick={() => !uploading && setShowUploadModal(false)}
                className="p-2 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
                disabled={uploading}
              >
                <X size={20} />
              </button>
            </div>
            
            <div className="p-6">
              {uploading ? (
                <div className="text-center py-8">
                  <Loader2 className="w-12 h-12 mx-auto mb-4 text-sky-400 animate-spin" />
                  <p className="text-white mb-2">Processing with AI...</p>
                  <div className="w-full h-2 bg-slate-800 rounded-full overflow-hidden">
                    <div 
                      className="h-full bg-gradient-to-r from-sky-500 to-indigo-500 transition-all duration-300"
                      style={{ width: `${uploadProgress}%` }}
                    />
                  </div>
                  <p className="text-sm text-slate-400 mt-2">Extracting metadata, generating embeddings...</p>
                </div>
              ) : (
                <div 
                  className={`border-2 border-dashed rounded-2xl p-12 text-center transition-colors
                    ${dragActive ? 'border-sky-500 bg-sky-500/5' : 'border-slate-700 hover:border-slate-600'}`}
                >
                  <Upload className="w-12 h-12 mx-auto mb-4 text-slate-500" />
                  <p className="text-white mb-2">Drag & drop your document here</p>
                  <p className="text-sm text-slate-400 mb-4">PDF, Word, Excel, Markdown, or Text files</p>
                  <label className="inline-flex items-center gap-2 px-4 py-2 bg-sky-500 text-white font-medium rounded-xl
                    hover:bg-sky-600 cursor-pointer transition-colors">
                    <Plus size={16} />
                    Browse Files
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
          </div>
        </div>
      )}

      {/* Document Detail Modal */}
      {selectedDocument && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setSelectedDocument(null)} />
          <div className="relative w-full max-w-4xl max-h-[90vh] bg-slate-900 border border-slate-800 rounded-2xl shadow-xl animate-fade-in overflow-hidden">
            <div className="flex items-center justify-between p-6 border-b border-slate-800">
              <div className="flex items-center gap-4">
                <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${getFileColor(selectedDocument.file_type)} 
                  flex items-center justify-center shadow-lg`}>
                  {(() => { const Icon = getFileIcon(selectedDocument.file_type); return <Icon className="w-6 h-6 text-white" /> })()}
                </div>
                <div>
                  <h2 className="text-lg font-semibold text-white">{selectedDocument.title}</h2>
                  <p className="text-sm text-slate-400 font-mono">{selectedDocument.reference_number}</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button className="p-2 rounded-lg bg-slate-800 text-slate-300 hover:text-white transition-colors">
                  <Download size={20} />
                </button>
                <button className="p-2 rounded-lg bg-slate-800 text-slate-300 hover:text-white transition-colors">
                  <ExternalLink size={20} />
                </button>
                <button
                  onClick={() => setSelectedDocument(null)}
                  className="p-2 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
                >
                  <X size={20} />
                </button>
              </div>
            </div>
            
            <div className="p-6 overflow-y-auto max-h-[calc(90vh-100px)] space-y-6">
              {/* AI Summary */}
              {selectedDocument.ai_summary && (
                <div className="bg-gradient-to-br from-sky-500/10 to-indigo-500/10 border border-sky-500/20 rounded-xl p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <Sparkles className="w-4 h-4 text-sky-400" />
                    <span className="text-sm font-medium text-sky-400">AI Summary</span>
                  </div>
                  <p className="text-slate-300">{selectedDocument.ai_summary}</p>
                </div>
              )}

              {/* Metadata Grid */}
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <div className="bg-slate-800/50 rounded-xl p-4">
                  <p className="text-xs text-slate-500 mb-1">Document Type</p>
                  <p className="text-white capitalize">{selectedDocument.document_type}</p>
                </div>
                <div className="bg-slate-800/50 rounded-xl p-4">
                  <p className="text-xs text-slate-500 mb-1">File Size</p>
                  <p className="text-white">{formatFileSize(selectedDocument.file_size)}</p>
                </div>
                <div className="bg-slate-800/50 rounded-xl p-4">
                  <p className="text-xs text-slate-500 mb-1">Status</p>
                  <span className={`px-2 py-0.5 text-xs font-medium rounded ${STATUS_COLORS[selectedDocument.status]}`}>
                    {selectedDocument.status}
                  </span>
                </div>
                <div className="bg-slate-800/50 rounded-xl p-4">
                  <p className="text-xs text-slate-500 mb-1">Sensitivity</p>
                  <p className="text-white capitalize">{selectedDocument.sensitivity}</p>
                </div>
              </div>

              {/* AI Tags */}
              {selectedDocument.ai_tags && selectedDocument.ai_tags.length > 0 && (
                <div>
                  <h3 className="text-sm font-medium text-slate-400 mb-2 flex items-center gap-2">
                    <Tag className="w-4 h-4" />
                    AI-Generated Tags
                  </h3>
                  <div className="flex flex-wrap gap-2">
                    {selectedDocument.ai_tags.map(tag => (
                      <span key={tag} className="px-3 py-1 text-sm bg-sky-500/10 text-sky-400 rounded-full border border-sky-500/20">
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Keywords */}
              {selectedDocument.ai_keywords && selectedDocument.ai_keywords.length > 0 && (
                <div>
                  <h3 className="text-sm font-medium text-slate-400 mb-2">Keywords</h3>
                  <div className="flex flex-wrap gap-2">
                    {selectedDocument.ai_keywords.map(keyword => (
                      <span key={keyword} className="px-2 py-0.5 text-xs bg-slate-800 text-slate-300 rounded">
                        {keyword}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Stats */}
              <div className="flex items-center gap-6 text-sm text-slate-400">
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
                  <span className="flex items-center gap-2 text-sky-400">
                    <CheckCircle2 className="w-4 h-4" />
                    AI Indexed
                  </span>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Drag Overlay */}
      {dragActive && (
        <div className="fixed inset-0 z-[60] bg-sky-500/10 backdrop-blur-sm flex items-center justify-center pointer-events-none">
          <div className="bg-slate-900 border-2 border-dashed border-sky-500 rounded-2xl p-12 text-center">
            <Upload className="w-16 h-16 mx-auto mb-4 text-sky-400" />
            <p className="text-xl font-semibold text-white">Drop your document here</p>
          </div>
        </div>
      )}
    </div>
  )
}
