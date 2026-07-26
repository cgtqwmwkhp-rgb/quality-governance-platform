/**
 * DynamicFormRenderer - Best-in-class dynamic form rendering engine
 * Features:
 * - Renders any form configuration from API
 * - Auto-save drafts to localStorage
 * - Voice-to-text for text fields
 * - Real-time validation with helpful messages
 * - Conditional field visibility
 * - Progress tracking
 * - Offline-capable with sync
 */

import { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import { trackError } from '../../utils/errorTracker'
import { motion, AnimatePresence } from 'framer-motion'
import {
  ChevronRight,
  ChevronLeft,
  Check,
  Loader2,
  Save,
  Mic,
  MicOff,
  MapPin,
  X,
  AlertCircle,
  Info,
  Upload,
} from 'lucide-react'
import { Card } from '../ui/Card'
import { Button } from '../ui/Button'
import { Input } from '../ui/Input'
import { Textarea } from '../ui/Textarea'
import { cn } from '../../helpers/utils'
import { useVoiceToText } from '../../hooks/useVoiceToText'
import { useGeolocation } from '../../hooks/useGeolocation'
import type { FormTemplate, FormField } from '../../services/api'
import FuzzySearchDropdown from '../FuzzySearchDropdown'
import BodyInjurySelector, { InjurySelection } from '../BodyInjurySelector'

// ==================== Types ====================

export interface DynamicFormData {
  [key: string]: unknown
}

interface DynamicFormRendererProps {
  template: FormTemplate
  initialData?: DynamicFormData
  onSubmit: (data: DynamicFormData) => Promise<{ reference_number: string }>
  onCancel?: () => void
  contractOptions?: Array<{ value: string; label: string; sublabel?: string }>
  roleOptions?: Array<{ value: string; label: string }>
  medicalAssistanceOptions?: Array<{ value: string; label: string }>
  /**
   * Cross-field validation owned by the hosting page, keyed by field name.
   * Runs alongside per-step validation on Continue, and across every step on
   * Submit so a value entered on an earlier step cannot reach the server.
   */
  validateData?: (data: DynamicFormData) => Record<string, string>
}

// ==================== Upload Validation (PX-325 / PX-326) ====================

export const MAX_UPLOAD_BYTES = 10 * 1024 * 1024

const IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'heic', 'heif', 'bmp']
const DOCUMENT_EXTENSIONS = ['pdf', 'doc', 'docx', 'xls', 'xlsx', 'csv', 'txt', 'rtf']
const DOCUMENT_MIME_TYPES = [
  'application/pdf',
  'application/msword',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/vnd.ms-excel',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  'text/csv',
  'text/plain',
  'application/rtf',
]

export function formatFileSize(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)}MB`
  if (bytes >= 1024) return `${Math.round(bytes / 1024)}KB`
  return `${bytes} bytes`
}

function fileExtension(name: string): string {
  const dot = name.lastIndexOf('.')
  return dot > 0 ? name.slice(dot + 1).toLowerCase() : ''
}

export function isAllowedUploadFile(file: File, imagesOnly: boolean): boolean {
  const extension = fileExtension(file.name)
  const isImage = file.type.startsWith('image/') || IMAGE_EXTENSIONS.includes(extension)
  if (imagesOnly) return isImage
  return isImage || DOCUMENT_EXTENSIONS.includes(extension) || DOCUMENT_MIME_TYPES.includes(file.type)
}

export interface UploadValidationResult {
  accepted: File[]
  errors: string[]
}

/**
 * Screens a selection of files against the type and size rules before they are
 * added to the form, so the user is told immediately instead of discovering the
 * problem at submit time.
 */
export function validateUploadFiles(
  files: File[],
  options: { imagesOnly: boolean; maxBytes?: number },
): UploadValidationResult {
  const maxBytes = options.maxBytes ?? MAX_UPLOAD_BYTES
  const accepted: File[] = []
  const errors: string[] = []

  for (const file of files) {
    if (!isAllowedUploadFile(file, options.imagesOnly)) {
      errors.push(
        options.imagesOnly
          ? `"${file.name}" is not an image. Upload a JPG, PNG, GIF, WEBP or HEIC file.`
          : `"${file.name}" is not an accepted file type. Upload an image, PDF, Word, Excel, CSV or text file.`,
      )
      continue
    }
    if (file.size > maxBytes) {
      errors.push(
        `"${file.name}" is ${formatFileSize(file.size)}, which is over the ${formatFileSize(maxBytes)} limit.`,
      )
      continue
    }
    accepted.push(file)
  }

  return { accepted, errors }
}

// ==================== Draft Helpers (PX-300) ====================

function isEmptyValue(value: unknown): boolean {
  if (value === undefined || value === null || value === '') return true
  if (Array.isArray(value) && value.length === 0) return true
  return false
}

function isBinaryValue(value: unknown): boolean {
  if (typeof File !== 'undefined' && value instanceof File) return true
  if (typeof Blob !== 'undefined' && value instanceof Blob) return true
  return false
}

/**
 * Files cannot survive a JSON round-trip — they serialise to `{}` and come back
 * as objects with no `name`, which corrupts the upload field on restore. Drop
 * them rather than persisting placeholders.
 */
export function stripNonSerializableValues(data: DynamicFormData): DynamicFormData {
  const clean: DynamicFormData = {}
  for (const [key, value] of Object.entries(data)) {
    if (isBinaryValue(value)) continue
    if (Array.isArray(value)) {
      const items = value.filter((item) => !isBinaryValue(item))
      if (items.length !== value.length) {
        if (items.length > 0) clean[key] = items
        continue
      }
    }
    clean[key] = value
  }
  return clean
}

/**
 * A draft is only worth offering when it holds something the user actually
 * typed. Prefilled values (name, today's date, ...) are not user input, so a
 * draft equal to the prefill baseline must not trigger the restore prompt.
 */
export function draftHasUserInput(
  draft: DynamicFormData | null,
  baseline: DynamicFormData,
): boolean {
  if (!draft) return false
  return Object.entries(draft).some(([key, value]) => {
    if (isEmptyValue(value)) return false
    return JSON.stringify(value) !== JSON.stringify(baseline[key])
  })
}

// ==================== Auto-save Hook ====================

function useAutoSave(
  formSlug: string,
  data: DynamicFormData,
  enabled: boolean,
  baseline: DynamicFormData,
) {
  const storageKey = `draft_${formSlug}`
  const baselineRef = useRef(baseline)
  baselineRef.current = baseline

  useEffect(() => {
    if (!enabled) return

    const timer = setTimeout(() => {
      const serializable = stripNonSerializableValues(data)
      // Never persist a draft that is just the prefilled blank form, otherwise
      // every abandoned page load resurfaces as a meaningless "draft found".
      if (!draftHasUserInput(serializable, baselineRef.current)) {
        localStorage.removeItem(storageKey)
        return
      }
      localStorage.setItem(
        storageKey,
        JSON.stringify({
          data: serializable,
          savedAt: new Date().toISOString(),
        }),
      )
    }, 2000) // Debounce 2 seconds

    return () => clearTimeout(timer)
  }, [data, storageKey, enabled])

  const loadDraft = useCallback((): DynamicFormData | null => {
    try {
      const saved = localStorage.getItem(storageKey)
      if (saved) {
        const { data } = JSON.parse(saved)
        if (data && typeof data === 'object' && !Array.isArray(data)) {
          return data as DynamicFormData
        }
      }
    } catch {
      // Ignore parse errors
    }
    return null
  }, [storageKey])

  const clearDraft = useCallback(() => {
    localStorage.removeItem(storageKey)
  }, [storageKey])

  return { loadDraft, clearDraft }
}

// ==================== Field Renderer ====================

interface FieldRendererProps {
  field: FormField
  value: unknown
  onChange: (value: unknown) => void
  error?: string
  contractOptions?: Array<{ value: string; label: string; sublabel?: string }>
  roleOptions?: Array<{ value: string; label: string }>
  medicalAssistanceOptions?: Array<{ value: string; label: string }>
}

function FieldRenderer({
  field,
  value,
  onChange,
  error,
  contractOptions,
  roleOptions,
  medicalAssistanceOptions,
}: FieldRendererProps) {
  const {
    isListening,
    isSupported: voiceSupported,
    toggleListening,
  } = useVoiceToText({
    onResult: (transcript) => {
      const currentValue = (value as string) || ''
      onChange(currentValue + (currentValue ? ' ' : '') + transcript)
    },
  })

  const { isLoading: geoLoading, getLocationString, error: geoError } = useGeolocation()
  const [uploadErrors, setUploadErrors] = useState<string[]>([])

  const handleLocationDetect = async () => {
    const location = await getLocationString()
    if (location) {
      onChange(location)
    }
  }

  const handleFilesSelected = (input: HTMLInputElement, imagesOnly: boolean) => {
    const selected = input.files ? Array.from(input.files) : []
    // Reset so re-picking the same file after a rejection fires `change` again.
    input.value = ''
    if (selected.length === 0) return

    const existing = Array.isArray(value) ? (value as File[]) : []
    const { accepted, errors: rejections } = validateUploadFiles(selected, { imagesOnly })
    setUploadErrors(rejections)
    if (accepted.length > 0) {
      onChange([...existing, ...accepted])
    }
  }

  const widthClass =
    {
      full: 'col-span-2',
      half: 'col-span-1',
      third: 'col-span-1 md:col-span-1',
    }[field.width] || 'col-span-2'

  // Handle different field types
  switch (field.field_type) {
    case 'text':
    case 'email':
    case 'phone':
    case 'number':
      return (
        <div className={widthClass}>
          <label className="block text-sm font-medium text-foreground mb-2">
            {field.label}
            {field.is_required && <span className="text-destructive ml-1">*</span>}
          </label>
          <div className="relative">
            <Input
              type={field.field_type === 'phone' ? 'tel' : field.field_type}
              value={(value as string) || ''}
              onChange={(e) => onChange(e.target.value)}
              placeholder={field.placeholder}
              className={cn(error && 'border-destructive')}
            />
            {voiceSupported && ['text'].includes(field.field_type) && (
              <button
                type="button"
                onClick={toggleListening}
                className={cn(
                  'absolute right-2 top-1/2 -translate-y-1/2 p-1.5 rounded-full transition-colors',
                  isListening
                    ? 'bg-destructive text-white animate-pulse'
                    : 'bg-muted text-muted-foreground hover:bg-primary/10 hover:text-primary',
                )}
              >
                {isListening ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
              </button>
            )}
          </div>
          {field.help_text && (
            <p className="mt-1 text-xs text-muted-foreground flex items-center gap-1">
              <Info className="w-3 h-3" />
              {field.help_text}
            </p>
          )}
          {error && (
            <p className="mt-1 text-xs text-destructive flex items-center gap-1">
              <AlertCircle className="w-3 h-3" />
              {error}
            </p>
          )}
        </div>
      )

    case 'textarea':
    case 'rich_text':
      return (
        <div className={widthClass}>
          <label className="block text-sm font-medium text-foreground mb-2">
            {field.label}
            {field.is_required && <span className="text-destructive ml-1">*</span>}
          </label>
          <div className="relative">
            <Textarea
              value={(value as string) || ''}
              onChange={(e) => onChange(e.target.value)}
              placeholder={field.placeholder}
              rows={4}
              className={cn(error && 'border-destructive')}
            />
            {voiceSupported && (
              <button
                type="button"
                onClick={toggleListening}
                className={cn(
                  'absolute right-3 bottom-3 p-2 rounded-full transition-colors',
                  isListening
                    ? 'bg-destructive text-white animate-pulse'
                    : 'bg-primary/10 text-primary hover:bg-primary/20',
                )}
              >
                {isListening ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
              </button>
            )}
          </div>
          {isListening && (
            <p className="mt-1 text-xs text-primary animate-pulse flex items-center gap-1">
              <span className="w-2 h-2 bg-destructive rounded-full" />
              Listening... speak now
            </p>
          )}
          {field.help_text && !isListening && (
            <p className="mt-1 text-xs text-muted-foreground">{field.help_text}</p>
          )}
          {error && (
            <p className="mt-1 text-xs text-destructive flex items-center gap-1">
              <AlertCircle className="w-3 h-3" />
              {error}
            </p>
          )}
        </div>
      )

    case 'date':
      return (
        <div className={widthClass}>
          <label className="block text-sm font-medium text-foreground mb-2">
            {field.label}
            {field.is_required && <span className="text-destructive ml-1">*</span>}
          </label>
          <Input
            type="date"
            value={(value as string) || ''}
            onChange={(e) => onChange(e.target.value)}
            className={cn(error && 'border-destructive')}
          />
          {error && <p className="mt-1 text-xs text-destructive">{error}</p>}
        </div>
      )

    case 'time':
      return (
        <div className={widthClass}>
          <label className="block text-sm font-medium text-foreground mb-2">
            {field.label}
            {field.is_required && <span className="text-destructive ml-1">*</span>}
          </label>
          <Input
            type="time"
            value={(value as string) || ''}
            onChange={(e) => onChange(e.target.value)}
            className={cn(error && 'border-destructive')}
          />
          {error && <p className="mt-1 text-xs text-destructive">{error}</p>}
        </div>
      )

    case 'datetime':
      return (
        <div className={widthClass}>
          <label className="block text-sm font-medium text-foreground mb-2">
            {field.label}
            {field.is_required && <span className="text-destructive ml-1">*</span>}
          </label>
          <Input
            type="datetime-local"
            value={(value as string) || ''}
            onChange={(e) => onChange(e.target.value)}
            className={cn(error && 'border-destructive')}
          />
          {error && <p className="mt-1 text-xs text-destructive">{error}</p>}
        </div>
      )

    case 'select':
      // Use customer options for compatibility fields named either customer or contract.
      const selectOptions =
        field.name.toLowerCase().includes('customer') ||
        field.name.toLowerCase().includes('contract')
          ? contractOptions?.map((c) => ({
              value: c.value,
              label: c.label,
              sublabel: c.sublabel,
            })) || []
          : field.name.toLowerCase().includes('role')
            ? roleOptions?.map((r) => ({ value: r.value, label: r.label })) || []
            : field.name === 'medical_assistance'
              ? medicalAssistanceOptions || field.options || []
              : field.options || []

      return (
        <div className={widthClass}>
          <FuzzySearchDropdown
            label={field.label + (field.is_required ? ' *' : '')}
            options={selectOptions}
            value={(value as string) || ''}
            onChange={(v) => onChange(v)}
            placeholder={field.placeholder || 'Select...'}
          />
          {error && <p className="mt-1 text-xs text-destructive">{error}</p>}
        </div>
      )

    case 'radio':
    case 'toggle':
      return (
        <div className={widthClass}>
          <label className="block text-sm font-medium text-foreground mb-3">
            {field.label}
            {field.is_required && <span className="text-destructive ml-1">*</span>}
          </label>
          <div className="flex gap-3">
            {(
              field.options || [
                { value: 'yes', label: 'Yes' },
                { value: 'no', label: 'No' },
              ]
            ).map((option) => (
              <button
                key={option.value}
                type="button"
                onClick={() => onChange(option.value)}
                className={cn(
                  'flex-1 py-3 px-4 rounded-xl border-2 font-medium transition-all',
                  value === option.value
                    ? 'border-primary bg-primary/10 text-primary'
                    : 'border-border bg-card text-muted-foreground hover:border-primary/50',
                )}
              >
                {option.label}
              </button>
            ))}
          </div>
          {error && <p className="mt-2 text-xs text-destructive">{error}</p>}
        </div>
      )

    case 'checkbox':
    case 'multi_select':
      const selectedValues = (value as string[]) || []
      return (
        <div className={widthClass}>
          <label className="block text-sm font-medium text-foreground mb-3">
            {field.label}
            {field.is_required && <span className="text-destructive ml-1">*</span>}
          </label>
          <div className="space-y-2">
            {(field.options || []).map((option) => (
              <label
                key={option.value}
                className={cn(
                  'flex items-center gap-3 p-3 rounded-xl border cursor-pointer transition-all',
                  selectedValues.includes(option.value)
                    ? 'border-primary bg-primary/5'
                    : 'border-border hover:border-primary/50',
                )}
              >
                <input
                  type="checkbox"
                  checked={selectedValues.includes(option.value)}
                  onChange={(e) => {
                    if (e.target.checked) {
                      onChange([...selectedValues, option.value])
                    } else {
                      onChange(selectedValues.filter((v) => v !== option.value))
                    }
                  }}
                  className="rounded border-border text-primary focus:ring-primary"
                />
                <span className="text-foreground">{option.label}</span>
              </label>
            ))}
          </div>
          {error && <p className="mt-2 text-xs text-destructive">{error}</p>}
        </div>
      )

    case 'location':
      return (
        <div className={widthClass}>
          <label className="block text-sm font-medium text-foreground mb-2">
            {field.label}
            {field.is_required && <span className="text-destructive ml-1">*</span>}
          </label>
          <div className="relative">
            <MapPin className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
            <Input
              value={(value as string) || ''}
              onChange={(e) => onChange(e.target.value)}
              placeholder={field.placeholder || 'Enter location or use GPS'}
              className="pl-10 pr-20"
            />
            <button
              type="button"
              onClick={handleLocationDetect}
              disabled={geoLoading}
              className="absolute right-2 top-1/2 -translate-y-1/2 px-3 py-1.5 bg-primary/10 text-primary rounded-lg text-sm font-medium hover:bg-primary/20 transition-colors disabled:opacity-50"
            >
              {geoLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'GPS'}
            </button>
          </div>
          {geoError && <p className="mt-1 text-xs text-destructive">{geoError}</p>}
          {field.help_text && !geoError && (
            <p className="mt-1 text-xs text-muted-foreground">{field.help_text}</p>
          )}
          {error && <p className="mt-1 text-xs text-destructive">{error}</p>}
        </div>
      )

    case 'body_map':
      return (
        <div className={widthClass}>
          <label className="block text-sm font-medium text-foreground mb-2">
            {field.label}
            {field.is_required && <span className="text-destructive ml-1">*</span>}
          </label>
          <BodyInjurySelector
            injuries={(value as InjurySelection[]) || []}
            onChange={(injuries) => onChange(injuries)}
          />
          {error && <p className="mt-2 text-xs text-destructive">{error}</p>}
        </div>
      )

    case 'file':
    case 'image': {
      const files = Array.isArray(value) ? (value as File[]) : []
      const imagesOnly = field.field_type === 'image'
      return (
        <div className={widthClass}>
          <label className="block text-sm font-medium text-foreground mb-2">
            {field.label}
            {field.is_required && <span className="text-destructive ml-1">*</span>}
          </label>
          <div className="space-y-3">
            <label className="flex flex-col items-center justify-center p-6 border-2 border-dashed border-border rounded-xl cursor-pointer hover:border-primary/50 hover:bg-primary/5 transition-all">
              <Upload className="w-8 h-8 text-muted-foreground mb-2" />
              <span className="text-sm text-muted-foreground">
                {imagesOnly ? 'Upload photos' : 'Upload files'}
              </span>
              <input
                type="file"
                data-testid={`file-input-${field.name}`}
                accept={
                  imagesOnly ? 'image/*' : 'image/*,.pdf,.doc,.docx,.xls,.xlsx,.csv,.txt,.rtf'
                }
                multiple
                onChange={(e) => handleFilesSelected(e.target, imagesOnly)}
                className="hidden"
              />
            </label>
            <p className="text-xs text-muted-foreground">
              {imagesOnly
                ? `JPG, PNG, GIF, WEBP or HEIC. Up to ${formatFileSize(MAX_UPLOAD_BYTES)} per file.`
                : `Images, PDF, Word, Excel, CSV or text. Up to ${formatFileSize(MAX_UPLOAD_BYTES)} per file.`}
            </p>
            {uploadErrors.length > 0 && (
              <ul
                data-testid={`upload-errors-${field.name}`}
                role="alert"
                className="space-y-1 rounded-lg bg-destructive/10 p-3"
              >
                {uploadErrors.map((message) => (
                  <li
                    key={message}
                    className="flex items-start gap-1 text-xs text-destructive"
                  >
                    <AlertCircle className="w-3 h-3 mt-0.5 shrink-0" />
                    <span>{message}</span>
                  </li>
                ))}
              </ul>
            )}
            {files.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {files.map((file, index) => (
                  <div
                    key={`${file.name}-${index}`}
                    className="flex items-center gap-2 px-3 py-2 bg-muted rounded-lg"
                  >
                    <span className="text-sm text-foreground truncate max-w-[150px]">
                      {file.name}
                    </span>
                    <button
                      type="button"
                      onClick={() => onChange(files.filter((_, i) => i !== index))}
                      className="p-1 hover:bg-destructive/10 rounded"
                    >
                      <X className="w-3 h-3 text-destructive" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
          {error && <p className="mt-2 text-xs text-destructive">{error}</p>}
        </div>
      )
    }

    case 'signature':
      // Simplified signature - in production would use a canvas
      return (
        <div className={widthClass}>
          <label className="block text-sm font-medium text-foreground mb-2">
            {field.label}
            {field.is_required && <span className="text-destructive ml-1">*</span>}
          </label>
          <div className="h-32 border-2 border-dashed border-border rounded-xl flex items-center justify-center bg-muted/30">
            <p className="text-sm text-muted-foreground">Signature capture coming soon</p>
          </div>
        </div>
      )

    case 'rating':
      const rating = (value as number) || 0
      return (
        <div className={widthClass}>
          <label className="block text-sm font-medium text-foreground mb-2">
            {field.label}
            {field.is_required && <span className="text-destructive ml-1">*</span>}
          </label>
          <div className="flex gap-2">
            {[1, 2, 3, 4, 5].map((star) => (
              <button
                key={star}
                type="button"
                onClick={() => onChange(star)}
                className={cn(
                  'w-10 h-10 text-2xl transition-transform hover:scale-110',
                  star <= rating ? 'text-yellow-500' : 'text-muted',
                )}
              >
                ★
              </button>
            ))}
          </div>
        </div>
      )

    case 'heading':
      return (
        <div className="col-span-2">
          <h3 className="text-lg font-semibold text-foreground">{field.label}</h3>
          {field.help_text && (
            <p className="text-sm text-muted-foreground mt-1">{field.help_text}</p>
          )}
        </div>
      )

    case 'paragraph':
      return (
        <div className="col-span-2">
          <p className="text-sm text-muted-foreground">{field.label}</p>
        </div>
      )

    case 'divider':
      return (
        <div className="col-span-2">
          <hr className="border-border" />
        </div>
      )

    default:
      return (
        <div className={widthClass}>
          <label className="block text-sm font-medium text-foreground mb-2">{field.label}</label>
          <Input
            value={(value as string) || ''}
            onChange={(e) => onChange(e.target.value)}
            placeholder={field.placeholder}
          />
        </div>
      )
  }
}

// ==================== Main Component ====================

export default function DynamicFormRenderer({
  template,
  initialData = {},
  onSubmit,
  onCancel,
  contractOptions = [],
  roleOptions = [],
  medicalAssistanceOptions = [],
  validateData,
}: DynamicFormRendererProps) {
  const [currentStep, setCurrentStep] = useState(0)
  const [maxStepReached, setMaxStepReached] = useState(0)
  const [formData, setFormData] = useState<DynamicFormData>(initialData)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submittedRef, setSubmittedRef] = useState<string | null>(null)
  const [showDraftPrompt, setShowDraftPrompt] = useState(false)
  const [pendingDraft, setPendingDraft] = useState<DynamicFormData | null>(null)
  const [draftChecked, setDraftChecked] = useState(false)

  // The prefill baseline is whatever the page handed us on mount. Callers build
  // it inline, so re-reading the prop on every render would make it look like it
  // had changed continuously.
  const baselineRef = useRef<DynamicFormData>(initialData)

  const { loadDraft, clearDraft } = useAutoSave(
    template.slug,
    formData,
    // Pause auto-save while the restore prompt is open, so the blank form
    // cannot overwrite the very draft being offered.
    template.allow_drafts && !showDraftPrompt,
    baselineRef.current,
  )

  // `Array.prototype.sort` mutates in place; sorting the prop array directly
  // rewrites the caller's template on every render.
  const steps = useMemo(
    () => [...(template.steps ?? [])].sort((a, b) => a.order - b.order),
    [template.steps],
  )
  const stepCount = steps.length
  const activeStep = stepCount > 0 ? Math.min(currentStep, stepCount - 1) : 0
  const currentStepData = steps[activeStep]
  const isLastStep = stepCount > 0 && activeStep === stepCount - 1
  const progress = stepCount > 0 ? ((activeStep + 1) / stepCount) * 100 : 0

  // Offer a saved draft once on mount. Prefilled fields (name, today's date)
  // must not suppress the offer, so compare the draft against the prefill
  // baseline rather than checking whether any initial data exists.
  useEffect(() => {
    if (draftChecked) return
    setDraftChecked(true)
    if (!template.allow_drafts) return
    const draft = loadDraft()
    if (draftHasUserInput(draft, baselineRef.current)) {
      setPendingDraft(draft)
      setShowDraftPrompt(true)
    }
  }, [draftChecked, template.allow_drafts, loadDraft])

  const handleLoadDraft = () => {
    if (pendingDraft) {
      // Draft values win, but prefilled keys the draft never touched survive.
      setFormData({ ...baselineRef.current, ...pendingDraft })
    }
    setPendingDraft(null)
    setShowDraftPrompt(false)
  }

  const handleDiscardDraft = () => {
    clearDraft()
    setPendingDraft(null)
    setShowDraftPrompt(false)
  }

  const updateField = useCallback(
    (name: string, value: unknown) => {
      setFormData((prev) => ({ ...prev, [name]: value }))
      // Clear error when field is updated
      if (errors[name]) {
        setErrors((prev) => {
          const next = { ...prev }
          delete next[name]
          return next
        })
      }
    },
    [errors],
  )

  const validateStep = useCallback((): boolean => {
    const stepErrors: Record<string, string> = {}
    if (!currentStepData) return true

    for (const field of currentStepData.fields) {
      const value = formData[field.name]

      // Required validation
      if (field.is_required) {
        if (
          value === undefined ||
          value === null ||
          value === '' ||
          (Array.isArray(value) && value.length === 0)
        ) {
          stepErrors[field.name] = `${field.label} is required`
          continue
        }
      }

      // Skip other validations if field is empty and not required
      if (!value) continue

      // Min/max length for strings
      if (typeof value === 'string') {
        if (field.min_length && value.length < field.min_length) {
          stepErrors[field.name] = `Minimum ${field.min_length} characters required`
        }
        if (field.max_length && value.length > field.max_length) {
          stepErrors[field.name] = `Maximum ${field.max_length} characters allowed`
        }
      }

      // Pattern validation
      if (field.pattern && typeof value === 'string') {
        const regex = new RegExp(field.pattern)
        if (!regex.test(value)) {
          stepErrors[field.name] = `Invalid format`
        }
      }

      // Email validation
      if (field.field_type === 'email' && typeof value === 'string') {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
        if (!emailRegex.test(value)) {
          stepErrors[field.name] = 'Please enter a valid email address'
        }
      }
    }

    // Page-supplied rules, narrowed to the fields visible on this step.
    if (validateData) {
      const custom = validateData(formData)
      for (const field of currentStepData.fields) {
        const message = custom[field.name]
        if (message && !stepErrors[field.name]) {
          stepErrors[field.name] = message
        }
      }
    }

    setErrors(stepErrors)
    return Object.keys(stepErrors).length === 0
  }, [currentStepData, formData, validateData])

  const handleNext = useCallback(() => {
    if (stepCount === 0) return
    if (!validateStep()) return

    const target = Math.min(activeStep + 1, stepCount - 1)
    if (target === activeStep) return
    // Guard against a second click landing before the re-render: without this
    // both calls apply `prev + 1` and the user skips a step (and its validation).
    setCurrentStep((prev) => (prev === activeStep ? target : prev))
    setMaxStepReached((prev) => Math.max(prev, target))
  }, [activeStep, stepCount, validateStep])

  const handleBack = useCallback(() => {
    // Errors belong to the step being left; carrying them back highlights
    // same-named fields on the previous step.
    setErrors({})
    setCurrentStep((prev) => Math.max(prev - 1, 0))
  }, [])

  const handleStepSelect = useCallback(
    (index: number) => {
      if (index === activeStep || index < 0 || index > maxStepReached) return
      setErrors({})
      setCurrentStep(index)
    },
    [activeStep, maxStepReached],
  )

  const handleSubmit = async () => {
    if (!validateStep()) return

    // Submit validates only the final step, so a bad value captured on an
    // earlier step would otherwise reach the server. Re-check everything and
    // send the user back to the field at fault.
    if (validateData) {
      const custom = validateData(formData)
      const failedFields = Object.keys(custom)
      if (failedFields.length > 0) {
        setErrors(custom)
        const offendingStep = steps.findIndex((step) =>
          step.fields.some((field) => failedFields.includes(field.name)),
        )
        if (offendingStep >= 0 && offendingStep !== activeStep) {
          setCurrentStep(offendingStep)
          setMaxStepReached((prev) => Math.max(prev, offendingStep))
        }
        return
      }
    }

    setIsSubmitting(true)
    try {
      const result = await onSubmit(formData)
      clearDraft()
      setSubmittedRef(result.reference_number)
    } catch (error) {
      trackError(error, { component: 'DynamicFormRenderer', action: 'handleSubmit' })
      setErrors({ _form: 'Submission failed. Please try again.' })
    } finally {
      setIsSubmitting(false)
    }
  }

  // Success screen
  if (submittedRef) {
    return (
      <motion.div
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        className="flex flex-col items-center justify-center py-16 text-center"
      >
        <div className="w-20 h-20 bg-primary/10 rounded-full flex items-center justify-center mb-6">
          <Check className="w-10 h-10 text-primary" />
        </div>
        <h2 className="text-2xl font-bold text-foreground mb-2">Submitted Successfully!</h2>
        <p className="text-muted-foreground mb-4">Your reference number is:</p>
        <div className="text-3xl font-mono font-bold text-primary mb-8">{submittedRef}</div>
        <p className="text-sm text-muted-foreground max-w-md">
          Please save this reference number. You can use it to track the status of your submission.
        </p>
        {onCancel && (
          <Button onClick={onCancel} className="mt-8">
            Submit Another
          </Button>
        )}
      </motion.div>
    )
  }

  if (!currentStepData) {
    return (
      <Card className="p-6">
        <p className="text-sm text-muted-foreground">This form has no steps configured yet.</p>
      </Card>
    )
  }

  return (
    <div className="space-y-6">
      {/* Draft Prompt */}
      <AnimatePresence>
        {showDraftPrompt && (
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
          >
            <Card className="p-4 border-primary/30 bg-primary/5">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Save className="w-5 h-5 text-primary" />
                  <div>
                    <p className="font-medium text-foreground">Draft found</p>
                    <p className="text-sm text-muted-foreground">
                      Would you like to continue where you left off?
                    </p>
                  </div>
                </div>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" onClick={handleDiscardDraft}>
                    Start Fresh
                  </Button>
                  <Button size="sm" onClick={handleLoadDraft}>
                    Load Draft
                  </Button>
                </div>
              </div>
            </Card>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Progress Bar */}
      <div className="relative">
        <div className="h-2 bg-muted rounded-full overflow-hidden">
          <motion.div
            className="h-full bg-gradient-to-r from-primary to-primary/70"
            initial={{ width: 0 }}
            animate={{ width: `${progress}%` }}
            transition={{ duration: 0.3 }}
          />
        </div>
        <div className="flex justify-between mt-2">
          {steps.map((step, index) => {
            const isCurrent = index === activeStep
            const isVisited = index <= maxStepReached
            const isComplete = !isCurrent && index < maxStepReached
            return (
              <button
                key={step.id}
                type="button"
                data-testid={`step-indicator-${index}`}
                aria-current={isCurrent ? 'step' : undefined}
                onClick={() => handleStepSelect(index)}
                disabled={!isVisited}
                className={cn(
                  'flex items-center gap-2 text-xs font-medium transition-colors',
                  isCurrent && 'text-primary',
                  !isCurrent && isVisited && 'text-primary cursor-pointer hover:text-primary/80',
                  !isVisited && 'text-muted-foreground cursor-not-allowed',
                )}
              >
                <span
                  className={cn(
                    'w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold',
                    isCurrent && 'bg-primary text-primary-foreground',
                    !isCurrent && isVisited && 'bg-primary/20 text-primary',
                    !isVisited && 'bg-muted text-muted-foreground',
                  )}
                >
                  {isComplete ? <Check className="w-3 h-3" /> : index + 1}
                </span>
                <span className="hidden sm:inline">{step.name}</span>
              </button>
            )
          })}
        </div>
      </div>

      {/* Step Content */}
      <AnimatePresence mode="wait">
        <motion.div
          key={activeStep}
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -20 }}
          transition={{ duration: 0.2 }}
        >
          <Card className="p-6">
            <div className="mb-6">
              <h2 className="text-xl font-bold text-foreground">{currentStepData.name}</h2>
              {currentStepData.description && (
                <p className="text-muted-foreground mt-1">{currentStepData.description}</p>
              )}
            </div>

            <div className="grid grid-cols-2 gap-4">
              {[...currentStepData.fields]
                .sort((a, b) => a.order - b.order)
                .map((field) => (
                  <div key={field.id} data-testid={`field-${field.name}`}>
                    <FieldRenderer
                      field={field}
                      value={formData[field.name]}
                      onChange={(value) => updateField(field.name, value)}
                      error={errors[field.name]}
                      contractOptions={contractOptions}
                      roleOptions={roleOptions}
                      medicalAssistanceOptions={medicalAssistanceOptions}
                    />
                  </div>
                ))}
            </div>

            {errors._form && (
              <div className="mt-4 p-3 bg-destructive/10 text-destructive rounded-lg text-sm">
                {errors._form}
              </div>
            )}
          </Card>
        </motion.div>
      </AnimatePresence>

      {/* Navigation */}
      <div className="flex items-center justify-between">
        <Button
          variant="outline"
          onClick={activeStep === 0 ? onCancel : handleBack}
          disabled={isSubmitting}
        >
          <ChevronLeft className="w-4 h-4 mr-2" />
          {activeStep === 0 ? 'Cancel' : 'Back'}
        </Button>

        <div className="flex items-center gap-3">
          {template.allow_drafts && (
            <p className="text-xs text-muted-foreground flex items-center gap-1">
              <Save className="w-3 h-3" />
              Auto-saving draft
            </p>
          )}

          {isLastStep ? (
            <Button data-testid="submit-report-btn" onClick={handleSubmit} disabled={isSubmitting}>
              {isSubmitting ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Submitting...
                </>
              ) : (
                <>
                  <Check className="w-4 h-4 mr-2" />
                  Submit
                </>
              )}
            </Button>
          ) : (
            <Button onClick={handleNext}>
              Continue
              <ChevronRight className="w-4 h-4 ml-2" />
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}
