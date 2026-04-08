import { useState, useRef } from 'react'
import { Upload, CheckCircle2, XCircle, Loader2, File, Trash2 } from 'lucide-react'
import { planetMarkApi } from '../../api/client'

interface EvidenceUploadRowProps {
  yearId: number
  documentType: string
  evidenceCategory: string
  label: string
  description?: string
  required?: boolean
  onUploaded?: (evidenceId: number) => void
}

const ACCEPTED_TYPES = '.pdf,.jpg,.jpeg,.png,.webp,.xls,.xlsx,.csv'
const MAX_SIZE_MB = 20

export function EvidenceUploadRow({
  yearId,
  documentType,
  evidenceCategory,
  label,
  description,
  required = false,
  onUploaded,
}: EvidenceUploadRowProps) {
  const [state, setState] = useState<'idle' | 'uploading' | 'success' | 'error' | 'duplicate'>('idle')
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [uploadedName, setUploadedName] = useState<string | null>(null)
  const [uploadedId, setUploadedId] = useState<number | null>(null)
  const [period, setPeriod] = useState('')
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleFile = async (file: File) => {
    setErrorMsg(null)

    if (file.size > MAX_SIZE_MB * 1024 * 1024) {
      setErrorMsg(`File exceeds ${MAX_SIZE_MB} MB limit`)
      setState('error')
      return
    }

    const allowed = ['application/pdf', 'image/jpeg', 'image/png', 'image/webp',
      'application/vnd.ms-excel',
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      'text/csv']
    if (!allowed.includes(file.type) && file.type !== '') {
      setErrorMsg(`File type not supported. Please use PDF, image, Excel or CSV.`)
      setState('error')
      return
    }

    setState('uploading')
    const fd = new FormData()
    fd.append('file', file)
    fd.append('document_name', file.name)
    fd.append('document_type', documentType)
    fd.append('evidence_category', evidenceCategory)
    if (period) fd.append('period_covered', period)

    try {
      const res = await planetMarkApi.uploadEvidence(yearId, fd)
      if (res.data.duplicate) {
        setState('duplicate')
        setUploadedName(res.data.document_name)
        setUploadedId(res.data.id)
        onUploaded?.(res.data.id)
      } else {
        setState('success')
        setUploadedName(res.data.document_name)
        setUploadedId(res.data.id)
        onUploaded?.(res.data.id)
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Upload failed'
      setErrorMsg(msg)
      setState('error')
    }
  }

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) handleFile(file)
  }

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }

  const reset = () => {
    setState('idle')
    setErrorMsg(null)
    setUploadedName(null)
    setUploadedId(null)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  return (
    <div className="border rounded-lg p-4 mb-3 bg-white">
      <div className="flex items-start justify-between mb-2">
        <div>
          <span className="font-medium text-sm text-gray-900">
            {label}
            {required && <span className="text-red-500 ml-1" aria-label="required">*</span>}
          </span>
          {description && <p className="text-xs text-gray-500 mt-0.5">{description}</p>}
        </div>
        {(state === 'success' || state === 'duplicate') && (
          <button
            onClick={reset}
            className="text-gray-400 hover:text-red-500 transition-colors"
            aria-label="Remove uploaded file"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        )}
      </div>

      {state === 'idle' || state === 'error' ? (
        <div
          className={`border-2 border-dashed rounded-md p-4 text-center cursor-pointer transition-colors
            ${state === 'error' ? 'border-red-400 bg-red-50' : 'border-gray-300 hover:border-green-400 hover:bg-green-50'}`}
          onDrop={handleDrop}
          onDragOver={(e) => e.preventDefault()}
          onClick={() => fileInputRef.current?.click()}
          role="button"
          tabIndex={0}
          aria-label={`Upload ${label}`}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault()
              fileInputRef.current?.click()
            }
          }}
        >
          <Upload className="w-6 h-6 mx-auto mb-1 text-gray-400" />
          <p className="text-xs text-gray-500">Drag & drop or click to upload</p>
          <p className="text-xs text-gray-400 mt-0.5">PDF, Images, Excel, CSV · max {MAX_SIZE_MB} MB</p>
          {errorMsg && <p className="text-xs text-red-600 mt-1" role="alert">{errorMsg}</p>}

          <div className="mt-2">
            <label htmlFor={`period-${documentType}`} className="text-xs text-gray-500">Period covered (optional)</label>
            <input
              id={`period-${documentType}`}
              type="text"
              value={period}
              onChange={(e) => { e.stopPropagation(); setPeriod(e.target.value) }}
              onClick={(e) => e.stopPropagation()}
              placeholder="e.g. Jan–Dec 2024"
              className="mt-1 w-full text-xs border rounded px-2 py-1 focus:ring-1 focus:ring-green-500 outline-none"
            />
          </div>
        </div>
      ) : state === 'uploading' ? (
        <div className="flex items-center gap-2 text-sm text-gray-600 p-3 bg-gray-50 rounded-md">
          <Loader2 className="w-4 h-4 animate-spin text-green-600" />
          <span>Uploading…</span>
        </div>
      ) : state === 'success' ? (
        <div className="flex items-center gap-2 text-sm text-green-700 p-3 bg-green-50 rounded-md">
          <CheckCircle2 className="w-4 h-4" />
          <File className="w-4 h-4" />
          <span className="truncate max-w-xs">{uploadedName}</span>
          <span className="text-xs text-green-600 ml-auto">Uploaded (ID: {uploadedId})</span>
        </div>
      ) : state === 'duplicate' ? (
        <div className="flex items-center gap-2 text-sm text-amber-700 p-3 bg-amber-50 rounded-md">
          <XCircle className="w-4 h-4" />
          <span className="truncate max-w-xs">{uploadedName}</span>
          <span className="text-xs text-amber-600 ml-auto">Duplicate — existing record used</span>
        </div>
      ) : null}

      <input
        ref={fileInputRef}
        type="file"
        accept={ACCEPTED_TYPES}
        className="hidden"
        onChange={handleInputChange}
        aria-hidden="true"
      />
    </div>
  )
}
