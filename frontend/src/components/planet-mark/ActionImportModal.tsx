import { useState, useRef, useCallback, useEffect } from 'react'
import { X, Upload, Loader2, CheckCircle2, AlertTriangle, ChevronRight, FileText } from 'lucide-react'
import { planetMarkApi } from '../../api/client'

type Step = 'upload' | 'extracting' | 'review' | 'confirming' | 'done'

interface ExtractedRow {
  action_title: string
  description: string
  owner: string
  deadline: string | null
  category: string
  expected_reduction_pct: number
  confidence: number
  needs_review: boolean
}

interface ActionImportModalProps {
  yearId: number
  onClose: () => void
  onImported: (count: number) => void
}

export function ActionImportModal({ yearId, onClose, onImported }: ActionImportModalProps) {
  const [step, setStep] = useState<Step>('upload')
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [filename, setFilename] = useState('')
  const [rows, setRows] = useState<ExtractedRow[]>([])
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [warnings, setWarnings] = useState<string[]>([])
  const [extractionMethod, setExtractionMethod] = useState('')
  const [error, setError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const modalRef = useRef<HTMLDivElement>(null)
  const closeButtonRef = useRef<HTMLButtonElement>(null)

  // Focus trap: keep Tab/Shift-Tab inside the modal
  useEffect(() => {
    const el = modalRef.current
    if (!el) return
    const focusable = el.querySelectorAll<HTMLElement>(
      'a[href],button:not([disabled]),input,select,textarea,[tabindex]:not([tabindex="-1"])',
    )
    const first = focusable[0]
    const last = focusable[focusable.length - 1]
    first?.focus()
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { onClose(); return }
      if (e.key !== 'Tab') return
      if (e.shiftKey) {
        if (document.activeElement === first) { e.preventDefault(); last?.focus() }
      } else {
        if (document.activeElement === last) { e.preventDefault(); first?.focus() }
      }
    }
    el.addEventListener('keydown', handleKeyDown)
    return () => el.removeEventListener('keydown', handleKeyDown)
  }, [onClose])

  const handleFileSelect = useCallback(async (file: File) => {
    setError(null)
    setFilename(file.name)
    setStep('extracting')

    const fd = new FormData()
    fd.append('file', file)

    try {
      const res = await planetMarkApi.extractActionPlan(yearId, fd)
      const data = res.data
      setSessionId(data.session_id)
      setRows(data.rows)
      setWarnings(data.warnings)
      setExtractionMethod(data.extraction_method)
      setSelected(new Set(data.rows.map((_, i) => i)))
      setStep('review')
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Extraction failed')
      setStep('upload')
    }
  }, [yearId])

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    const file = e.dataTransfer.files[0]
    if (file) handleFileSelect(file)
  }

  const toggleRow = (idx: number) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(idx)) next.delete(idx)
      else next.add(idx)
      return next
    })
  }

  const toggleAll = () => {
    if (selected.size === rows.length) setSelected(new Set())
    else setSelected(new Set(rows.map((_, i) => i)))
  }

  const handleConfirm = async () => {
    if (!sessionId) return
    setStep('confirming')
    setError(null)
    try {
      const selectedIndices = Array.from(selected).sort((a, b) => a - b)
      const res = await planetMarkApi.confirmActionImport(yearId, sessionId, selectedIndices)
      onImported(res.data.created_count)
      setStep('done')
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Import failed')
      setStep('review')
    }
  }

  return (
    <div
      ref={modalRef}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-label="Import Action Plan"
    >
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-2xl mx-4 max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <div className="flex items-center gap-2">
            <FileText className="w-5 h-5 text-green-600" />
            <h2 className="text-base font-semibold text-gray-900">Import Action Plan</h2>
          </div>
          <button
            ref={closeButtonRef}
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors"
            aria-label="Close modal"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Step indicator */}
        <div className="flex items-center gap-2 px-6 py-3 bg-gray-50 border-b text-xs">
          {(['upload', 'review', 'done'] as Step[]).map((s, i) => (
            <div key={s} className="flex items-center gap-2">
              <span
                className={`w-6 h-6 rounded-full flex items-center justify-center font-bold
                  ${step === s || (step === 'extracting' && s === 'upload') || (step === 'confirming' && s === 'review')
                    ? 'bg-green-600 text-white'
                    : s === 'done' && step === 'done'
                    ? 'bg-green-600 text-white'
                    : 'bg-gray-200 text-gray-500'}`}
              >
                {i + 1}
              </span>
              <span className="text-gray-600 capitalize">{s}</span>
              {i < 2 && <ChevronRight className="w-3 h-3 text-gray-400" />}
            </div>
          ))}
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-6">
          {/* Upload step */}
          {(step === 'upload' || step === 'extracting') && (
            <div>
              <p className="text-sm text-gray-600 mb-4">
                Upload your Planet Mark action plan PDF or spreadsheet and the system will
                automatically extract improvement actions using AI.
              </p>
              <div
                className={`border-2 border-dashed rounded-lg p-10 text-center cursor-pointer transition-colors
                  ${step === 'extracting'
                    ? 'border-green-400 bg-green-50'
                    : 'border-gray-300 hover:border-green-400 hover:bg-green-50'}`}
                onDrop={handleDrop}
                onDragOver={(e) => e.preventDefault()}
                onClick={() => step !== 'extracting' && fileInputRef.current?.click()}
                role="button"
                tabIndex={0}
                aria-label="Upload action plan document"
                onKeyDown={(e) => {
                  if ((e.key === 'Enter' || e.key === ' ') && step !== 'extracting') {
                    e.preventDefault()
                    fileInputRef.current?.click()
                  }
                }}
              >
                {step === 'extracting' ? (
                  <div className="flex flex-col items-center gap-2">
                    <Loader2 className="w-10 h-10 text-green-600 animate-spin" />
                    <p className="font-medium text-green-700">Extracting actions using AI…</p>
                    <p className="text-xs text-gray-500">{filename}</p>
                  </div>
                ) : (
                  <div className="flex flex-col items-center gap-2">
                    <Upload className="w-10 h-10 text-gray-300" />
                    <p className="font-medium text-gray-600">Drag & drop or click to upload</p>
                    <p className="text-xs text-gray-400">PDF, Excel, CSV · max 20 MB</p>
                  </div>
                )}
              </div>
              {error && (
                <p className="text-sm text-red-600 mt-3 flex items-center gap-1.5" role="alert">
                  <AlertTriangle className="w-4 h-4" />
                  {error}
                </p>
              )}
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.xls,.xlsx,.csv"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0]
                  if (f) handleFileSelect(f)
                }}
                aria-hidden="true"
              />
            </div>
          )}

          {/* Review step */}
          {(step === 'review' || step === 'confirming') && (
            <div>
              <div className="flex items-center justify-between mb-3">
                <div>
                  <p className="text-sm font-medium text-gray-900">
                    {rows.length} action{rows.length !== 1 ? 's' : ''} extracted
                  </p>
                  <p className="text-xs text-gray-500 mt-0.5">
                    From: {filename} · Method: {extractionMethod}
                  </p>
                </div>
                <button
                  onClick={toggleAll}
                  className="text-xs text-blue-600 hover:underline"
                >
                  {selected.size === rows.length ? 'Deselect all' : 'Select all'}
                </button>
              </div>

              {warnings.length > 0 && (
                <div className="mb-3 p-3 bg-amber-50 border border-amber-200 rounded-md">
                  {warnings.map((w, i) => (
                    <p key={i} className="text-xs text-amber-700">{w}</p>
                  ))}
                </div>
              )}

              <div className="space-y-2 max-h-80 overflow-y-auto">
                {rows.map((row, idx) => (
                  <div
                    key={idx}
                    className={`flex gap-3 p-3 rounded-md border cursor-pointer transition-colors
                      ${selected.has(idx) ? 'bg-green-50 border-green-300' : 'bg-gray-50 border-gray-200'}
                      ${row.needs_review ? 'border-l-4 border-l-amber-400' : ''}`}
                    role="button"
                    tabIndex={0}
                    onClick={() => toggleRow(idx)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault()
                        toggleRow(idx)
                      }
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={selected.has(idx)}
                      onChange={() => toggleRow(idx)}
                      className="mt-0.5 w-4 h-4 rounded text-green-600"
                      aria-label={`Select action: ${row.action_title}`}
                    />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-900 truncate">{row.action_title}</p>
                      <div className="flex items-center gap-2 mt-0.5 text-xs text-gray-500">
                        {row.owner && <span>{row.owner}</span>}
                        {row.deadline && <span>· Due: {row.deadline}</span>}
                        <span
                          className={`ml-auto px-1.5 py-0.5 rounded text-xs font-medium
                            ${row.confidence >= 0.7 ? 'bg-green-100 text-green-700' : 'bg-amber-100 text-amber-700'}`}
                        >
                          {Math.round(row.confidence * 100)}% confidence
                        </span>
                      </div>
                      {row.needs_review && (
                        <p className="text-xs text-amber-600 mt-0.5 flex items-center gap-1">
                          <AlertTriangle className="w-3 h-3" />
                          Review recommended — data may be incomplete
                        </p>
                      )}
                    </div>
                  </div>
                ))}
              </div>

              {error && (
                <p className="text-sm text-red-600 mt-3 flex items-center gap-1.5" role="alert">
                  <AlertTriangle className="w-4 h-4" />
                  {error}
                </p>
              )}
            </div>
          )}

          {/* Done step */}
          {step === 'done' && (
            <div className="flex flex-col items-center justify-center py-10 gap-3">
              <CheckCircle2 className="w-16 h-16 text-green-500" />
              <h3 className="text-lg font-semibold text-gray-900">Import Complete</h3>
              <p className="text-sm text-gray-600 text-center">
                {selected.size} action{selected.size !== 1 ? 's' : ''} have been added to your
                improvement plan and are ready to track.
              </p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="border-t px-6 py-4 flex justify-between">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800 transition-colors"
          >
            {step === 'done' ? 'Close' : 'Cancel'}
          </button>

          {(step === 'review' || step === 'confirming') && (
            <button
              onClick={handleConfirm}
              disabled={selected.size === 0 || step === 'confirming'}
              className="flex items-center gap-1.5 px-5 py-2 bg-green-600 text-white text-sm font-medium rounded-lg hover:bg-green-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              {step === 'confirming' ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <CheckCircle2 className="w-4 h-4" />
              )}
              Import {selected.size} Action{selected.size !== 1 ? 's' : ''}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
