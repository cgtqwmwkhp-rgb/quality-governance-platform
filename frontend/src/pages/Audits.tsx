import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  Plus,
  ClipboardCheck,
  Search,
  Calendar,
  MapPin,
  Target,
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  Clock,
  BarChart3,
  Loader2,
  FileText,
  Play,
} from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import {
  auditsApi,
  evidenceAssetsApi,
  externalAuditImportsApi,
  AuditRun,
  AuditFinding,
  AuditTemplate,
  AuditRunCreate,
  ExternalAuditType,
} from '../api/client'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Card, CardContent } from '../components/ui/Card'
import { Badge, type BadgeVariant } from '../components/ui/Badge'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '../components/ui/Dialog'
import { LoadingSkeleton } from '../components/ui/LoadingSkeleton'
import { EmptyState } from '../components/ui/EmptyState'
import { ToastContainer, useToast } from '../components/ui/Toast'
import { cn, decodeHtmlEntities } from '../helpers/utils'

type ViewMode = 'kanban' | 'list' | 'findings'
type AuditModalMode = 'schedule' | 'import'

// Form state for creating a new audit
interface CreateAuditForm {
  template_id: number | null
  title: string
  location: string
  scheduled_date: string
  external_audit_type: ExternalAuditType | ''
  source_origin: string
  assurance_scheme: string
  external_body_name: string
  external_auditor_name: string
  external_reference: string
}

const KANBAN_COLUMNS = [
  {
    id: 'scheduled',
    label: 'Scheduled',
    variant: 'info' as const,
    icon: Calendar,
  },
  {
    id: 'in_progress',
    label: 'In Progress',
    variant: 'warning' as const,
    icon: Clock,
  },
  {
    id: 'pending_review',
    label: 'Pending Review',
    variant: 'default' as const,
    icon: Target,
  },
  {
    id: 'completed',
    label: 'Completed',
    variant: 'success' as const,
    icon: CheckCircle2,
  },
]

const EXTERNAL_AUDIT_TYPE_OPTIONS: Array<{
  value: ExternalAuditType
  label: string
  description: string
  sourceOrigin: string
  defaultScheme: string
}> = [
  {
    value: 'customer',
    label: 'Customer Audit',
    description: 'Audits raised directly by a customer or client team.',
    sourceOrigin: 'customer',
    defaultScheme: 'Customer Audit',
  },
  {
    value: 'iso',
    label: 'ISO Audit',
    description: 'Certification or surveillance audits such as ISO 9001, 14001, or 45001.',
    sourceOrigin: 'certification',
    defaultScheme: '',
  },
  {
    value: 'planet_mark',
    label: 'Planet Mark',
    description: 'Planet Mark assessments and certification reviews.',
    sourceOrigin: 'certification',
    defaultScheme: 'Planet Mark',
  },
  {
    value: 'achilles_uvdb',
    label: 'Achilles / UVDB',
    description: 'Achilles, UVDB, or Verify-style external assurance audits.',
    sourceOrigin: 'third_party',
    defaultScheme: 'Achilles UVDB',
  },
  {
    value: 'other',
    label: 'Other External Audit',
    description: 'Any external audit that does not fit the main categories above.',
    sourceOrigin: 'third_party',
    defaultScheme: '',
  },
]

const INTAKE_TEMPLATE_TAG = 'external_audit_intake'

function hasTemplateTag(template: AuditTemplate, tag: string): boolean {
  return (template.tags || []).some((candidate) => candidate?.trim().toLowerCase() === tag)
}

function isSystemIntakeTemplate(template: AuditTemplate): boolean {
  return hasTemplateTag(template, INTAKE_TEMPLATE_TAG)
}

function getStructuredErrorMessage(error: unknown): string | null {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  if (typeof detail === 'string' && detail.trim()) {
    return detail
  }
  if (detail && typeof detail === 'object') {
    const message = (detail as { message?: unknown }).message
    if (typeof message === 'string' && message.trim()) {
      return message
    }
  }
  return null
}

function isExternalImportIntakeRun(audit: AuditRun): boolean {
  return audit.is_external_import_intake === true
}

const INITIAL_FORM_STATE: CreateAuditForm = {
  template_id: null,
  title: '',
  location: '',
  scheduled_date: new Date().toISOString().split('T')[0]!,
  external_audit_type: '',
  source_origin: 'internal',
  assurance_scheme: '',
  external_body_name: '',
  external_auditor_name: '',
  external_reference: '',
}

export default function Audits() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [audits, setAudits] = useState<AuditRun[]>([])
  const [findings, setFindings] = useState<AuditFinding[]>([])
  const [templates, setTemplates] = useState<AuditTemplate[]>([])
  const [loading, setLoading] = useState(true)
  const [viewMode, setViewMode] = useState<ViewMode>('kanban')
  const [searchTerm, setSearchTerm] = useState('')
  const [modalMode, setModalMode] = useState<AuditModalMode>('schedule')
  const [showModal, setShowModal] = useState(false)

  // Form state
  const [formData, setFormData] = useState<CreateAuditForm>(INITIAL_FORM_STATE)
  const [formError, setFormError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const [successTone, setSuccessTone] = useState<'success' | 'warning'>('success')
  const [showVersionSelector, setShowVersionSelector] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [reportFile, setReportFile] = useState<File | null>(null)
  const { toasts, dismiss: dismissToast } = useToast()

  const loadData = async () => {
    setLoadError(null)
    try {
      const [auditsRes, findingsRes, templatesRes] = await Promise.allSettled([
        auditsApi.listRuns(1, 100),
        auditsApi.listFindings(1, 100),
        auditsApi.listTemplates(1, 100, { is_published: true }),
      ])
      setAudits(auditsRes.status === 'fulfilled' ? auditsRes.value.data.items || [] : [])
      setFindings(findingsRes.status === 'fulfilled' ? findingsRes.value.data.items || [] : [])
      setTemplates(templatesRes.status === 'fulfilled' ? templatesRes.value.data.items || [] : [])
      const failures = [auditsRes, findingsRes, templatesRes].filter((r) => r.status === 'rejected')
      if (failures.length > 0) {
        setLoadError(`Failed to load some data. ${failures.length} of 3 requests failed.`)
      }
    } catch (err) {
      if (import.meta.env.DEV) console.error('Failed to load audits:', err)
      setLoadError('Failed to load audit data. Please try again.')
      setAudits([])
      setFindings([])
      setTemplates([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  const scheduleTemplates = useMemo(
    () => templates.filter((template) => !isSystemIntakeTemplate(template)),
    [templates],
  )

  const templateFamilies = useMemo(() => {
    const families = new Map<string, { key: string; label: string; versions: AuditTemplate[] }>()
    scheduleTemplates.forEach((template) => {
      const label = decodeHtmlEntities(template.name || 'Untitled Template').trim()
      const familyKey = `${label.toLowerCase()}::${(template.audit_type || '').toLowerCase()}`
      const existing = families.get(familyKey)
      if (existing) {
        existing.versions.push(template)
      } else {
        families.set(familyKey, {
          key: familyKey,
          label,
          versions: [template],
        })
      }
    })

    return Array.from(families.values())
      .map((family) => ({
        ...family,
        versions: [...family.versions].sort((a, b) => b.version - a.version),
      }))
      .sort((a, b) => a.label.localeCompare(b.label))
  }, [scheduleTemplates])

  const latestPublishedTemplates = useMemo(
    () =>
      templateFamilies
        .map((family) => family.versions[0])
        .filter((t): t is AuditTemplate => t != null),
    [templateFamilies],
  )

  const importPlaceholderTemplate = useMemo(
    () => latestPublishedTemplates[0] ?? templates[0] ?? null,
    [latestPublishedTemplates, templates],
  )

  const selectedTemplate = latestPublishedTemplates.find((template) => template.id === formData.template_id)
  const selectedTemplateFamily = useMemo(() => {
    if (!selectedTemplate) return null
    return (
      templateFamilies.find((family) =>
        family.versions.some((version) => version.id === selectedTemplate.id),
      ) ?? null
    )
  }, [selectedTemplate, templateFamilies])

  const latestSelectedTemplate =
    selectedTemplateFamily?.versions[0] ?? latestPublishedTemplates[0] ?? null

  const buildDefaultForm = (mode: AuditModalMode): CreateAuditForm => {
    const preferred = mode === 'import' ? importPlaceholderTemplate : latestPublishedTemplates[0] ?? null
    if (!preferred) {
      return {
        ...INITIAL_FORM_STATE,
        source_origin: mode === 'import' ? '' : 'internal',
      }
    }
    return {
      ...INITIAL_FORM_STATE,
      template_id: preferred.id,
      title: mode === 'schedule' ? decodeHtmlEntities(preferred.name) : '',
      source_origin: mode === 'import' ? '' : 'internal',
    }
  }

  const handleOpenModal = (mode: AuditModalMode) => {
    setModalMode(mode)
    setFormData(buildDefaultForm(mode))
    setFormError(null)
    setSuccessMessage(null)
    setSuccessTone('success')
    setShowVersionSelector(false)
    setReportFile(null)
    setShowModal(true)
  }

  const handleCloseModal = () => {
    setShowModal(false)
    setModalMode('schedule')
    setFormData(buildDefaultForm('schedule'))
    setFormError(null)
    setSuccessMessage(null)
    setSuccessTone('success')
    setShowVersionSelector(false)
    setReportFile(null)
  }

  const selectedExternalAuditType = useMemo(
    () =>
      EXTERNAL_AUDIT_TYPE_OPTIONS.find((option) => option.value === formData.external_audit_type) ?? null,
    [formData.external_audit_type],
  )

  const handleExternalAuditTypeChange = (value: string) => {
    const selectedOption =
      EXTERNAL_AUDIT_TYPE_OPTIONS.find((option) => option.value === value) ?? null

    setFormData((prev) => ({
      ...prev,
      external_audit_type: (selectedOption?.value ?? '') as CreateAuditForm['external_audit_type'],
      source_origin: selectedOption?.sourceOrigin ?? prev.source_origin,
      assurance_scheme: selectedOption?.defaultScheme || '',
      external_body_name:
        selectedOption?.value === 'customer'
          ? prev.external_body_name
          : selectedOption?.defaultScheme || prev.external_body_name,
    }))
  }

  const handleSubmitAudit = async (e: React.FormEvent) => {
    e.preventDefault()
    setFormError(null)

    if (modalMode === 'import') {
      if (!formData.external_audit_type) {
        setFormError('Please choose the external audit type')
        return
      }
      if (!formData.assurance_scheme.trim()) {
        setFormError('Please enter the audit scheme or standard')
        return
      }
      if (!reportFile) {
        setFormError('Please upload the external audit report')
        return
      }
      if (!formData.template_id) {
        setFormError('No published intake template is configured for external audit imports')
        return
      }
    } else if (!formData.template_id) {
      setFormError('Please select an audit template')
      return
    }

    setIsSubmitting(true)
    try {
      const payload: AuditRunCreate = {
        template_id: formData.template_id as number,
        title:
          formData.title ||
          (modalMode === 'import'
            ? selectedExternalAuditType?.label || formData.assurance_scheme || undefined
            : undefined),
        location: formData.location || undefined,
        scheduled_date: formData.scheduled_date || undefined,
        external_audit_type: formData.external_audit_type || undefined,
        source_origin: formData.source_origin || undefined,
        assurance_scheme: formData.assurance_scheme || undefined,
        external_body_name: formData.external_body_name || undefined,
        external_auditor_name: formData.external_auditor_name || undefined,
        external_reference: formData.external_reference || undefined,
      }

      const res = await auditsApi.createRun(payload)
      const result = res.data
      const isImportFlow = modalMode === 'import'
      let reportUploadFailed = false
      let successDetail = isImportFlow
        ? `External audit intake created successfully. Reference: ${result.reference_number}. The internal intake template was resolved automatically.`
        : `Audit scheduled successfully! Reference: ${result.reference_number}`
      let importJobId: number | null = null
      if (reportFile) {
        try {
          const uploadRes = await evidenceAssetsApi.upload(reportFile, {
            source_module: 'audit',
            source_id: result.id,
            title: formData.external_reference || reportFile.name,
            description:
              formData.assurance_scheme || formData.external_body_name
                ? `Uploaded source audit report for ${formData.assurance_scheme || 'external audit'}`
                : 'Uploaded source audit report',
            visibility: 'internal_customer',
          })

          await auditsApi.updateRun(result.id, {
            source_document_asset_id: uploadRes.data.id,
            source_document_label: uploadRes.data.original_filename,
          })
          successDetail += ` Report linked: ${uploadRes.data.original_filename}`
          if (isImportFlow) {
            const jobRes = await externalAuditImportsApi.createJob({
              audit_run_id: result.id,
              source_document_asset_id: uploadRes.data.id,
            })
            importJobId = jobRes.data.id
            await externalAuditImportsApi.queueJob(importJobId)
            successDetail += ` OCR and draft review have been queued for ${result.assurance_scheme || formData.assurance_scheme || 'this external audit'}.`
          }
        } catch (uploadErr: unknown) {
          reportUploadFailed = true
          const uploadErrorDetail = getStructuredErrorMessage(uploadErr)
          successDetail +=
            ' Intake created, but the source report upload failed. You can add the report from Evidence Assets.'
          if (uploadErrorDetail) {
            successDetail += ` Upload error: ${uploadErrorDetail}`
          }
          if (import.meta.env.DEV) console.error('Failed to upload audit source document:', uploadErr)
        }
      }

      setSuccessTone(reportUploadFailed ? 'warning' : 'success')
      setSuccessMessage(successDetail)

      await loadData()

      if (isImportFlow && !reportUploadFailed) {
        navigate(
          importJobId
            ? `/audits/${result.id}/import-review?jobId=${importJobId}`
            : `/audits/${result.id}/execute`,
        )
        return
      }

      // STATIC_UI_CONFIG_OK: UX delay to show success before closing modal
      setTimeout(() => {
        handleCloseModal()
        setSuccessMessage(null)
      }, 2000)
    } catch (err: unknown) {
      if (import.meta.env.DEV) console.error('Failed to create audit:', err)
      const errorMessage =
        getStructuredErrorMessage(err) ||
        (modalMode === 'import'
          ? 'Failed to create external audit intake. Please try again.'
          : 'Failed to schedule audit. Please try again.')
      setFormError(errorMessage)
    } finally {
      setIsSubmitting(false)
    }
  }

  const filteredAudits = useMemo(() => {
    const visibleAudits = audits.filter((audit) => !isExternalImportIntakeRun(audit))
    if (!searchTerm.trim()) return visibleAudits
    const term = searchTerm.toLowerCase()
    return visibleAudits.filter(
      (a) =>
        (a.title || '').toLowerCase().includes(term) ||
        (a.reference_number || '').toLowerCase().includes(term) ||
        (a.location || '').toLowerCase().includes(term) ||
        (a.assurance_scheme || '').toLowerCase().includes(term) ||
        (a.external_body_name || '').toLowerCase().includes(term),
    )
  }, [audits, searchTerm])

  const getAuditsByStatus = (status: string) => {
    return filteredAudits.filter((a) => a.status === status)
  }

  const getScoreColor = (percentage?: number) => {
    if (!percentage) return 'text-muted-foreground'
    if (percentage >= 90) return 'text-success'
    if (percentage >= 70) return 'text-warning'
    return 'text-destructive'
  }

  const getSeverityVariant = (severity: string) => {
    switch (severity) {
      case 'critical':
        return 'critical'
      case 'high':
        return 'high'
      case 'medium':
        return 'medium'
      case 'low':
        return 'low'
      case 'observation':
        return 'info'
      default:
        return 'secondary'
    }
  }

  const getStatusVariant = (status: string) => {
    switch (status) {
      case 'closed':
        return 'resolved'
      case 'open':
        return 'destructive'
      case 'in_progress':
        return 'in-progress'
      case 'pending_verification':
        return 'acknowledged'
      case 'deferred':
        return 'secondary'
      default:
        return 'secondary'
    }
  }

  const stats = {
    total: filteredAudits.length,
    inProgress: filteredAudits.filter((a) => a.status === 'in_progress').length,
    completed: filteredAudits.filter((a) => a.status === 'completed').length,
    avgScore:
      filteredAudits
        .filter((a) => a.score_percentage != null)
        .reduce((acc, a) => acc + (a.score_percentage ?? 0), 0) /
      (filteredAudits.filter((a) => a.score_percentage != null).length || 1),
    openFindings: findings.filter((f) => f.status === 'open').length,
  }
  if (loading) {
    return (
      <div className="p-6">
        <LoadingSkeleton variant="table" rows={5} columns={4} />
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {loadError && (
        <div className="bg-destructive/10 border border-destructive/30 rounded-xl p-4 flex items-center justify-between">
          <p className="text-sm text-destructive font-medium">{loadError}</p>
          <button
            onClick={loadData}
            className="px-3 py-1.5 text-sm font-medium bg-destructive text-white rounded-lg hover:bg-destructive/90"
          >
            {t('retry')}
          </button>
        </div>
      )}
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-foreground">Audit Management</h1>
          <p className="text-muted-foreground mt-1">
            Internal audits, imported external audits, inspections, and compliance checks
          </p>
        </div>
        <div className="flex items-center gap-3">
          {/* View Toggle */}
          <div className="flex bg-surface rounded-xl p-1 border border-border">
            {(['kanban', 'list', 'findings'] as ViewMode[]).map((mode) => (
              <button
                key={mode}
                onClick={() => setViewMode(mode)}
                aria-pressed={viewMode === mode}
                className={cn(
                  'px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200',
                  viewMode === mode
                    ? 'bg-primary text-primary-foreground shadow-sm'
                    : 'text-muted-foreground hover:text-foreground',
                )}
              >
                {mode === 'kanban' ? 'Board' : mode === 'findings' ? 'Findings' : 'List'}
              </button>
            ))}
          </div>
          <Button variant="outline" onClick={() => handleOpenModal('import')}>
            <FileText size={20} />
            Import External Audit
          </Button>
          <Button onClick={() => handleOpenModal('schedule')}>
            <Plus size={20} />
            Schedule Audit
          </Button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        {[
          {
            label: t('audits.stats.total'),
            value: stats.total,
            icon: ClipboardCheck,
            variant: 'info' as const,
          },
          {
            label: t('status.in_progress'),
            value: stats.inProgress,
            icon: Clock,
            variant: 'warning' as const,
          },
          {
            label: t('audits.stats.completed'),
            value: stats.completed,
            icon: CheckCircle2,
            variant: 'success' as const,
          },
          {
            label: t('audits.stats.avg_score'),
            value: `${(stats.avgScore ?? 0).toFixed(0)}%`,
            icon: BarChart3,
            variant: 'primary' as const,
          },
          {
            label: t('audits.stats.open_findings'),
            value: stats.openFindings,
            icon: AlertCircle,
            variant: 'destructive' as const,
          },
        ].map((stat) => (
          <Card key={stat.label} hoverable className="p-5">
            <div
              className={cn(
                'w-10 h-10 rounded-xl flex items-center justify-center mb-3',
                stat.variant === 'info' && 'bg-info/10 text-info',
                stat.variant === 'warning' && 'bg-warning/10 text-warning',
                stat.variant === 'success' && 'bg-success/10 text-success',
                stat.variant === 'primary' && 'bg-primary/10 text-primary',
                stat.variant === 'destructive' && 'bg-destructive/10 text-destructive',
              )}
            >
              <stat.icon className="w-5 h-5" />
            </div>
            <p className="text-2xl font-bold text-foreground">{stat.value}</p>
            <p className="text-sm text-muted-foreground">{stat.label}</p>
          </Card>
        ))}
      </div>

      {/* Search */}
      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
        <Input
          type="text"
          placeholder={t('audits.search_placeholder')}
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="pl-10"
        />
      </div>

      {/* Kanban View */}
      {viewMode === 'kanban' && (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6">
          {KANBAN_COLUMNS.map((column) => {
            const columnAudits = getAuditsByStatus(column.id)
            return (
              <div key={column.id}>
                {/* Column Header */}
                <div className="flex items-center gap-3 mb-4">
                  <div
                    className={cn(
                      'w-8 h-8 rounded-lg flex items-center justify-center',
                      column.variant === 'info' && 'bg-info/10 text-info',
                      column.variant === 'warning' && 'bg-warning/10 text-warning',
                      column.variant === 'success' && 'bg-success/10 text-success',
                      column.variant === 'default' && 'bg-primary/10 text-primary',
                    )}
                  >
                    <column.icon className="w-4 h-4" />
                  </div>
                  <h3 className="font-semibold text-foreground">{column.label}</h3>
                  <Badge variant="secondary" className="ml-auto">
                    {columnAudits.length}
                  </Badge>
                </div>

                {/* Column Content */}
                <div className="space-y-3 min-h-[200px] bg-surface rounded-2xl p-3 border border-border">
                  {columnAudits.length === 0 ? (
                    <div className="flex items-center justify-center h-32 text-muted-foreground">
                      <p className="text-sm">{t('audits.empty.title')}</p>
                    </div>
                  ) : (
                    columnAudits.map((audit) => (
                      <Card
                        key={audit.id}
                        hoverable
                        className="p-4 cursor-pointer"
                        role="button"
                        tabIndex={0}
                        onClick={() => navigate(`/audits/${audit.id}/execute`)}
                        onKeyDown={(e: React.KeyboardEvent) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault()
                            navigate(`/audits/${audit.id}/execute`)
                          }
                        }}
                      >
                        <div className="flex items-start justify-between mb-2">
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-xs text-primary">
                              {audit.reference_number}
                            </span>
                            <Badge
                              variant="secondary"
                              className="text-[10px] uppercase tracking-wide"
                            >
                              v{audit.template_version}
                            </Badge>
                          </div>
                          {audit.score_percentage != null && (
                            <span
                              className={cn(
                                'text-sm font-bold',
                                getScoreColor(audit.score_percentage),
                              )}
                            >
                              {audit.score_percentage.toFixed(0)}%
                            </span>
                          )}
                        </div>
                        <h4 className="font-medium text-foreground text-sm mb-2 line-clamp-2">
                          {audit.title || 'Untitled Audit'}
                        </h4>
                        {(audit.source_origin || audit.assurance_scheme) && (
                          <div className="flex flex-wrap gap-2 mb-2">
                            {audit.source_origin && (
                              <Badge variant="outline" className="text-[10px] uppercase tracking-wide">
                                {audit.source_origin.replace(/_/g, ' ')}
                              </Badge>
                            )}
                            {audit.assurance_scheme && (
                              <Badge variant="secondary" className="text-[10px]">
                                {audit.assurance_scheme}
                              </Badge>
                            )}
                          </div>
                        )}
                        {audit.location && (
                          <div className="flex items-center gap-1.5 text-xs text-muted-foreground mb-2">
                            <MapPin size={12} />
                            <span className="truncate">{audit.location}</span>
                          </div>
                        )}
                        <div className="flex items-center justify-between mt-2">
                          {audit.scheduled_date && (
                            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                              <Calendar size={12} />
                              <span>{new Date(audit.scheduled_date).toLocaleDateString()}</span>
                            </div>
                          )}
                          {(audit.status === 'scheduled' || audit.status === 'in_progress') && (
                            <Button
                              size="sm"
                              variant={audit.status === 'in_progress' ? 'default' : 'outline'}
                              onClick={(e) => {
                                e.stopPropagation()
                                navigate(`/audits/${audit.id}/execute`)
                              }}
                              className="text-xs h-7 px-2.5"
                            >
                              <Play size={12} />
                              {audit.status === 'in_progress' ? 'Continue' : 'Start'}
                            </Button>
                          )}
                        </div>
                      </Card>
                    ))
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* List View */}
      {viewMode === 'list' && (
        <Card>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-border">
                    <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                      {t('audits.table.reference')}
                    </th>
                    <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                      {t('audits.table.title')}
                    </th>
                    <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                      {t('audits.table.location')}
                    </th>
                    <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                      {t('audits.table.template')}
                    </th>
                    <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                      {t('audits.table.status')}
                    </th>
                    <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                      {t('audits.table.score')}
                    </th>
                    <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                      {t('audits.table.date')}
                    </th>
                    <th className="px-6 py-4 text-right text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                      <span className="sr-only">Actions</span>
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {filteredAudits.length === 0 ? (
                    <tr>
                      <td colSpan={8}>
                        <EmptyState
                          icon={<ClipboardCheck className="w-8 h-8 text-muted-foreground" />}
                          title={t('audits.empty.title')}
                          description={t(
                            'audits.empty.subtitle',
                            'No audits match your current filters.',
                          )}
                        />
                      </td>
                    </tr>
                  ) : (
                    filteredAudits.map((audit) => (
                      <tr
                        key={audit.id}
                        className="hover:bg-surface transition-colors cursor-pointer"
                        role="button"
                        tabIndex={0}
                        onClick={() => navigate(`/audits/${audit.id}/execute`)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault()
                            navigate(`/audits/${audit.id}/execute`)
                          }
                        }}
                      >
                        <td className="px-6 py-4">
                          <span className="font-mono text-sm text-primary">
                            {audit.reference_number}
                          </span>
                        </td>
                        <td className="px-6 py-4">
                          <p className="text-sm font-medium text-foreground truncate max-w-xs">
                            {audit.title || 'Untitled'}
                          </p>
                          {(audit.source_origin || audit.assurance_scheme || audit.external_body_name) && (
                            <div className="mt-1 flex flex-wrap gap-2">
                              {audit.source_origin && (
                                <Badge variant="outline" className="text-[10px] uppercase tracking-wide">
                                  {audit.source_origin.replace(/_/g, ' ')}
                                </Badge>
                              )}
                              {audit.assurance_scheme && (
                                <Badge variant="secondary" className="text-[10px]">
                                  {audit.assurance_scheme}
                                </Badge>
                              )}
                              {audit.external_body_name && (
                                <span className="text-xs text-muted-foreground">
                                  {audit.external_body_name}
                                </span>
                              )}
                            </div>
                          )}
                        </td>
                        <td className="px-6 py-4 text-sm text-foreground">
                          {audit.location || '-'}
                        </td>
                        <td className="px-6 py-4">
                          <Badge variant="secondary" className="text-xs">
                            v{audit.template_version}
                          </Badge>
                        </td>
                        <td className="px-6 py-4">
                          <Badge
                            variant={
                              audit.status === 'completed'
                                ? 'resolved'
                                : audit.status === 'in_progress'
                                  ? 'in-progress'
                                  : audit.status === 'pending_review'
                                    ? 'acknowledged'
                                    : 'submitted'
                            }
                          >
                            {(audit.status as string).replace(/_/g, ' ')}
                          </Badge>
                        </td>
                        <td className="px-6 py-4">
                          {audit.score_percentage != null ? (
                            <span
                              className={cn('font-bold', getScoreColor(audit.score_percentage))}
                            >
                              {audit.score_percentage.toFixed(0)}%
                            </span>
                          ) : (
                            <span className="text-muted-foreground">-</span>
                          )}
                        </td>
                        <td className="px-6 py-4 text-sm text-muted-foreground">
                          {audit.scheduled_date
                            ? new Date(audit.scheduled_date).toLocaleDateString()
                            : '-'}
                        </td>
                        <td className="px-6 py-4 text-right">
                          {audit.status === 'scheduled' || audit.status === 'in_progress' ? (
                            <Button
                              size="sm"
                              variant={audit.status === 'in_progress' ? 'default' : 'outline'}
                              onClick={(e) => {
                                e.stopPropagation()
                                navigate(`/audits/${audit.id}/execute`)
                              }}
                              className="text-xs h-7"
                            >
                              <Play size={12} />
                              {audit.status === 'in_progress' ? 'Continue' : 'Start'}
                            </Button>
                          ) : audit.status === 'completed' ? (
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={(e) => {
                                e.stopPropagation()
                                navigate(`/audits/${audit.id}/execute`)
                              }}
                              className="text-xs h-7"
                            >
                              View
                            </Button>
                          ) : null}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Findings View */}
      {viewMode === 'findings' && (
        <div className="space-y-4">
          {findings.length === 0 ? (
            <Card className="p-12 text-center">
              <AlertCircle className="w-12 h-12 mx-auto mb-4 text-muted-foreground/50" />
              <p className="text-muted-foreground">{t('audits.no_findings')}</p>
            </Card>
          ) : (
            findings.map((finding) => (
              <Card key={finding.id} hoverable className="p-5">
                <div className="flex items-start gap-4">
                  <div
                    className={cn(
                      'w-12 h-12 rounded-xl flex items-center justify-center',
                      finding.severity === 'critical' && 'bg-destructive/10 text-destructive',
                      finding.severity === 'high' && 'bg-warning/10 text-warning',
                      finding.severity === 'medium' && 'bg-warning/10 text-warning',
                      finding.severity === 'low' && 'bg-success/10 text-success',
                      !['critical', 'high', 'medium', 'low'].includes(finding.severity) &&
                        'bg-info/10 text-info',
                    )}
                  >
                    <AlertCircle className="w-6 h-6" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 mb-2">
                      <span className="font-mono text-xs text-primary">
                        {finding.reference_number}
                      </span>
                      <Badge variant={getSeverityVariant(finding.severity) as BadgeVariant}>
                        {finding.severity}
                      </Badge>
                      <Badge variant={getStatusVariant(finding.status) as BadgeVariant}>
                        {finding.status.replace('_', ' ')}
                      </Badge>
                    </div>
                    <h3 className="font-semibold text-foreground mb-1">{finding.title}</h3>
                    <p className="text-sm text-muted-foreground line-clamp-2">
                      {finding.description}
                    </p>
                    {finding.corrective_action_due_date && (
                      <div className="mt-3 flex items-center gap-2 text-xs text-muted-foreground">
                        <Calendar size={14} />
                        <span>
                          Due: {new Date(finding.corrective_action_due_date).toLocaleDateString()}
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              </Card>
            ))
          )}
        </div>
      )}

      {/* Create Audit Modal */}
      <Dialog open={showModal} onOpenChange={handleCloseModal}>
        <DialogContent className={modalMode === 'import' ? 'sm:max-w-3xl' : 'sm:max-w-lg'}>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <ClipboardCheck className="w-5 h-5 text-primary" />
              {modalMode === 'import' ? 'Create External Audit Intake' : 'Schedule New Audit'}
            </DialogTitle>
            <DialogDescription>
              {modalMode === 'import'
                ? 'Choose the external audit program, attach the report, and create the intake record that queues OCR review and downstream promotion.'
                : 'Select a published template and schedule an audit run.'}
            </DialogDescription>
          </DialogHeader>

          {successMessage ? (
            <div className="py-8 text-center">
              <div
                className={cn(
                  'w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4',
                  successTone === 'warning' ? 'bg-warning/10' : 'bg-success/10',
                )}
              >
                {successTone === 'warning' ? (
                  <AlertTriangle className="w-8 h-8 text-warning" />
                ) : (
                  <CheckCircle2 className="w-8 h-8 text-success" />
                )}
              </div>
              <p
                className={cn(
                  'text-lg font-semibold mb-2',
                  successTone === 'warning' ? 'text-warning' : 'text-foreground',
                )}
              >
                {successTone === 'warning'
                  ? modalMode === 'import'
                    ? 'Intake created with follow-up required'
                    : 'Audit created with follow-up required'
                  : modalMode === 'import'
                    ? 'External audit intake created'
                    : t('audits.scheduled_success')}
              </p>
              <p className="text-muted-foreground">{successMessage}</p>
            </div>
          ) : (
            <form onSubmit={handleSubmitAudit} className="space-y-5">
              {modalMode === 'schedule' ? (
                <div className="space-y-2">
                  <span className="text-sm font-medium text-foreground">
                    Audit Template <span className="text-destructive">*</span>
                  </span>
                  {latestPublishedTemplates.length === 0 ? (
                    <div className="p-4 rounded-xl bg-warning/10 border border-warning/20">
                      <p className="text-sm text-warning">
                        No published templates available. Please create and publish a template first
                        using the Audit Template Builder.
                      </p>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      <select
                        value={formData.template_id ?? ''}
                        onChange={(e) => {
                          const templateId = Number(e.target.value)
                          const template = latestPublishedTemplates.find(
                            (item) => item.id === templateId,
                          )
                          setFormData((prev) => ({
                            ...prev,
                            template_id: Number.isNaN(templateId) ? null : templateId,
                            title:
                              prev.title || (template?.name ? decodeHtmlEntities(template.name) : ''),
                          }))
                          setShowVersionSelector(false)
                        }}
                        className="w-full rounded-xl border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/30"
                      >
                        <option value="">Select a published template...</option>
                        {latestPublishedTemplates.map((template) => (
                          <option key={template.id} value={template.id}>
                            {decodeHtmlEntities(template.name)} (v{template.version}) -{' '}
                            {template.reference_number}
                          </option>
                        ))}
                      </select>
                      <p className="text-xs text-muted-foreground">
                        Showing {latestPublishedTemplates.length} published{' '}
                        {latestPublishedTemplates.length === 1 ? 'template' : 'templates'}. Only
                        published templates appear here &mdash; publish via the Template Builder.
                      </p>
                      {selectedTemplateFamily && selectedTemplateFamily.versions.length > 1 && (
                        <div className="rounded-xl border border-border bg-surface p-3 space-y-2">
                          <button
                            type="button"
                            onClick={() => setShowVersionSelector((prev) => !prev)}
                            className="text-xs font-medium text-primary hover:underline"
                          >
                            {showVersionSelector
                              ? 'Hide older versions'
                              : 'Need an older version? Choose here'}
                          </button>
                          {showVersionSelector && (
                            <select
                              value={formData.template_id ?? ''}
                              onChange={(e) => {
                                const templateId = Number(e.target.value)
                                const template = selectedTemplateFamily.versions.find(
                                  (item) => item.id === templateId,
                                )
                                setFormData((prev) => ({
                                  ...prev,
                                  template_id: Number.isNaN(templateId) ? null : templateId,
                                  title:
                                    prev.title ||
                                    (template?.name ? decodeHtmlEntities(template.name) : ''),
                                }))
                              }}
                              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/30"
                            >
                              {selectedTemplateFamily.versions.map((template) => (
                                <option key={template.id} value={template.id}>
                                  v{template.version} - {template.reference_number}
                                </option>
                              ))}
                            </select>
                          )}
                        </div>
                      )}
                      {latestSelectedTemplate &&
                        selectedTemplate?.id === latestSelectedTemplate.id && (
                          <p className="text-xs text-muted-foreground">
                            Using latest published version: v{latestSelectedTemplate.version}
                          </p>
                        )}
                      {selectedTemplate && (
                        <div className="rounded-xl border border-border bg-surface p-3">
                          <div className="flex items-center gap-2 mb-1">
                            <FileText className="w-4 h-4 text-primary" />
                            <p className="text-sm font-medium text-foreground">
                              {decodeHtmlEntities(selectedTemplate.name)}
                            </p>
                          </div>
                          <p className="text-xs text-muted-foreground">
                            {selectedTemplate.category || selectedTemplate.audit_type} • v
                            {selectedTemplate.version} • {selectedTemplate.reference_number}
                          </p>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ) : null}

              {/* Title */}
              <div className="space-y-2">
                <label htmlFor="audit-title" className="text-sm font-medium text-foreground">
                  Audit Title
                </label>
                <Input
                  id="audit-title"
                  type="text"
                  placeholder="e.g., Q1 2026 Safety Inspection - Site A"
                  value={formData.title}
                  onChange={(e) => setFormData((prev) => ({ ...prev, title: e.target.value }))}
                  maxLength={300}
                />
                <p className="text-xs text-muted-foreground">
                  Optional. Schedule mode defaults to the template name; import mode defaults to the selected source program.
                </p>
              </div>

              {/* Location */}
              <div className="space-y-2">
                <label htmlFor="audit-location" className="text-sm font-medium text-foreground">
                  Location
                </label>
                <Input
                  id="audit-location"
                  type="text"
                  placeholder="e.g., Warehouse B, Office Floor 3"
                  value={formData.location}
                  onChange={(e) =>
                    setFormData((prev) => ({
                      ...prev,
                      location: e.target.value,
                    }))
                  }
                  maxLength={200}
                />
              </div>

              {modalMode === 'import' ? (
                <>
                  <div className="rounded-xl border border-border bg-surface p-4 space-y-4">
                    <div className="rounded-lg border border-primary/20 bg-primary/5 p-3">
                      <p className="text-sm font-medium text-foreground">Import essentials</p>
                      <p className="mt-1 text-xs text-muted-foreground">
                        Choose the external program, attach the source report, and the platform will
                        resolve the internal intake checklist automatically.
                      </p>
                    </div>
                    <div className="space-y-2">
                      <label htmlFor="audit-import-type" className="text-sm font-medium text-foreground">
                        External Audit Program <span className="text-destructive">*</span>
                      </label>
                      <select
                        id="audit-import-type"
                        value={formData.external_audit_type}
                        onChange={(e) => handleExternalAuditTypeChange(e.target.value)}
                        className="w-full rounded-xl border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/30"
                      >
                        <option value="">Select external audit type...</option>
                        {EXTERNAL_AUDIT_TYPE_OPTIONS.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                      <p className="text-xs text-muted-foreground">
                        {selectedExternalAuditType?.description ||
                          'This drives the source metadata, searchability, and internal processing path for the import.'}
                      </p>
                    </div>

                    <div className="space-y-2">
                      <label htmlFor="audit-report-file" className="text-sm font-medium text-foreground">
                        Source Audit Report <span className="text-destructive">*</span>
                      </label>
                      <Input
                        id="audit-report-file"
                        type="file"
                        accept=".pdf,.doc,.docx,.xls,.xlsx"
                        onChange={(e) => setReportFile(e.target.files?.[0] ?? null)}
                      />
                      <p className="text-xs text-muted-foreground">
                        Upload the source report so the imported audit is linked into the shared evidence layer from day one.
                      </p>
                      {reportFile && (
                        <p className="text-xs text-primary">Selected file: {reportFile.name}</p>
                      )}
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <label htmlFor="audit-source-origin" className="text-sm font-medium text-foreground">
                          Source Origin
                        </label>
                        <Input
                          id="audit-source-origin"
                          type="text"
                          value={formData.source_origin}
                          readOnly
                        />
                      </div>
                      <div className="space-y-2">
                        <label htmlFor="audit-scheme" className="text-sm font-medium text-foreground">
                          Audit Scheme / Standard <span className="text-destructive">*</span>
                        </label>
                        <Input
                          id="audit-scheme"
                          type="text"
                          placeholder="e.g., ISO 9001 Surveillance, Planet Mark, Achilles UVDB"
                          value={formData.assurance_scheme}
                          onChange={(e) =>
                            setFormData((prev) => ({ ...prev, assurance_scheme: e.target.value }))
                          }
                          maxLength={100}
                        />
                      </div>
                    </div>
                  </div>

                  <div className="rounded-xl border border-border bg-surface p-4 space-y-4">
                    <div>
                      <p className="text-sm font-medium text-foreground">Supporting metadata</p>
                      <p className="mt-1 text-xs text-muted-foreground">
                        These details stay with the audit run and help reviewers validate the import context.
                      </p>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <label htmlFor="audit-external-body" className="text-sm font-medium text-foreground">
                          External Body / Customer
                        </label>
                        <Input
                          id="audit-external-body"
                          type="text"
                          placeholder="e.g., National Grid, BSI, Achilles, Planet Mark"
                          value={formData.external_body_name}
                          onChange={(e) =>
                            setFormData((prev) => ({ ...prev, external_body_name: e.target.value }))
                          }
                          maxLength={255}
                        />
                      </div>
                      <div className="space-y-2">
                        <label htmlFor="audit-external-auditor" className="text-sm font-medium text-foreground">
                          External Auditor / Assessor
                        </label>
                        <Input
                          id="audit-external-auditor"
                          type="text"
                          placeholder="Auditor or assessor name"
                          value={formData.external_auditor_name}
                          onChange={(e) =>
                            setFormData((prev) => ({ ...prev, external_auditor_name: e.target.value }))
                          }
                          maxLength={255}
                        />
                      </div>
                    </div>

                    <div className="space-y-2">
                      <label htmlFor="audit-external-reference" className="text-sm font-medium text-foreground">
                        External Reference
                      </label>
                      <Input
                        id="audit-external-reference"
                        type="text"
                        placeholder="Certificate number, report reference, or customer audit ID"
                        value={formData.external_reference}
                        onChange={(e) =>
                          setFormData((prev) => ({ ...prev, external_reference: e.target.value }))
                        }
                        maxLength={100}
                      />
                    </div>
                    <div className="rounded-lg border border-dashed border-border p-3">
                      <p className="text-xs uppercase tracking-wide text-muted-foreground">
                        Internal processing template
                      </p>
                      <p className="mt-1 text-sm text-foreground">
                        Assigned automatically by the server from the selected import program.
                      </p>
                      <p className="mt-1 text-xs text-muted-foreground">
                        The resolved template and version are shown after creation in the review workspace.
                      </p>
                    </div>
                  </div>
                </>
              ) : null}

              {/* Scheduled Date */}
              <div className="space-y-2">
                <label htmlFor="audit-date" className="text-sm font-medium text-foreground">
                  {modalMode === 'import' ? 'Audit Date' : 'Scheduled Date'}
                </label>
                <Input
                  id="audit-date"
                  type="date"
                  value={formData.scheduled_date}
                  onChange={(e) =>
                    setFormData((prev) => ({
                      ...prev,
                      scheduled_date: e.target.value,
                    }))
                  }
                  min={modalMode === 'schedule' ? new Date().toISOString().split('T')[0] : undefined}
                />
              </div>

              {/* Error Message */}
              {formError && (
                <div className="p-3 rounded-xl bg-destructive/10 border border-destructive/20 flex items-start gap-2">
                  <AlertCircle className="w-5 h-5 text-destructive flex-shrink-0 mt-0.5" />
                  <p className="text-sm text-destructive">{formError}</p>
                </div>
              )}

              {/* Footer */}
              <DialogFooter className="gap-2 sm:gap-0">
                <Button
                  type="button"
                  variant="outline"
                  onClick={handleCloseModal}
                  disabled={isSubmitting}
                >
                  {t('cancel')}
                </Button>
                <Button
                  type="submit"
                  disabled={
                    isSubmitting ||
                    (modalMode === 'schedule'
                      ? latestPublishedTemplates.length === 0 || !formData.template_id
                      : !formData.template_id)
                  }
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      {modalMode === 'import' ? 'Creating intake...' : t('audits.scheduling')}
                    </>
                  ) : (
                    <>
                      {modalMode === 'import' ? (
                        <FileText className="w-4 h-4" />
                      ) : (
                        <Calendar className="w-4 h-4" />
                      )}
                      {modalMode === 'import' ? 'Create Intake' : 'Schedule Audit'}
                    </>
                  )}
                </Button>
              </DialogFooter>
            </form>
          )}
        </DialogContent>
      </Dialog>
      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </div>
  )
}
