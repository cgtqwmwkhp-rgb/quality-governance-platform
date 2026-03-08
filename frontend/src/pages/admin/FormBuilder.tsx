import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router-dom'
import {
  ArrowLeft,
  Plus,
  Trash2,
  GripVertical,
  Save,
  Eye,
  Settings,
  ChevronDown,
  ChevronUp,
  Copy,
  Check,
  Loader2,
  HelpCircle,
} from 'lucide-react'
import { Card } from '../../components/ui/Card'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Textarea } from '../../components/ui/Textarea'
import { cn } from '../../helpers/utils'

// Field type definitions
const FIELD_TYPES = [
  { value: 'text', label: 'Text Input', icon: '📝' },
  { value: 'textarea', label: 'Long Text', icon: '📄' },
  { value: 'number', label: 'Number', icon: '🔢' },
  { value: 'email', label: 'Email', icon: '📧' },
  { value: 'phone', label: 'Phone', icon: '📞' },
  { value: 'date', label: 'Date', icon: '📅' },
  { value: 'time', label: 'Time', icon: '⏰' },
  { value: 'datetime', label: 'Date & Time', icon: '📆' },
  { value: 'select', label: 'Dropdown', icon: '🔽' },
  { value: 'multi_select', label: 'Multi-Select', icon: '☑️' },
  { value: 'radio', label: 'Radio Buttons', icon: '🔘' },
  { value: 'checkbox', label: 'Checkboxes', icon: '✅' },
  { value: 'toggle', label: 'Yes/No Toggle', icon: '🔀' },
  { value: 'file', label: 'File Upload', icon: '📎' },
  { value: 'image', label: 'Image Upload', icon: '🖼️' },
  { value: 'signature', label: 'Signature', icon: '✍️' },
  { value: 'location', label: 'Location/GPS', icon: '📍' },
  { value: 'body_map', label: 'Body Injury Map', icon: '🧍' },
  { value: 'rating', label: 'Star Rating', icon: '⭐' },
  { value: 'heading', label: 'Section Heading', icon: '📌' },
  { value: 'paragraph', label: 'Info Text', icon: 'ℹ️' },
  { value: 'divider', label: 'Divider Line', icon: '➖' },
]

interface FormField {
  id: string
  name: string
  label: string
  field_type: string
  order: number
  placeholder?: string
  help_text?: string
  is_required: boolean
  options?: Array<{ value: string; label: string }>
  width: string
}

interface FormStep {
  id: string
  name: string
  description?: string
  order: number
  icon?: string
  fields: FormField[]
  isExpanded: boolean
}

interface FormTemplate {
  id?: number
  name: string
  slug: string
  description?: string
  form_type: string
  icon?: string
  color?: string
  allow_drafts: boolean
  allow_attachments: boolean
  require_signature: boolean
  auto_assign_reference: boolean
  reference_prefix?: string
  notify_on_submit: boolean
  notification_emails?: string
  steps: FormStep[]
}

export default function FormBuilder() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { templateId } = useParams()
  const isEditing = !!templateId

  const [template, setTemplate] = useState<FormTemplate>({
    name: '',
    slug: '',
    description: '',
    form_type: 'incident',
    allow_drafts: true,
    allow_attachments: true,
    require_signature: false,
    auto_assign_reference: true,
    reference_prefix: 'INC',
    notify_on_submit: true,
    notification_emails: '',
    steps: [
      {
        id: 'step-1',
        name: 'Step 1',
        description: '',
        order: 0,
        fields: [],
        isExpanded: true,
      },
    ],
  })

  const [showSettings, setShowSettings] = useState(false)
  const [showFieldPalette, setShowFieldPalette] = useState(false)
  const [selectedStepId, setSelectedStepId] = useState<string | null>('step-1')
  const [isSaving, setIsSaving] = useState(false)
  const [saveSuccess, setSaveSuccess] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  // Load existing template if editing
  useEffect(() => {
    if (templateId) {
      // In real implementation, fetch from API
      // For now, use placeholder
    }
  }, [templateId])

  const generateSlug = (name: string) => {
    return name
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/(^-|-$)/g, '')
  }

  const handleNameChange = (name: string) => {
    setTemplate((prev) => ({
      ...prev,
      name,
      slug: prev.slug || generateSlug(name),
    }))
  }

  const addStep = () => {
    const newStep: FormStep = {
      id: `step-${Date.now()}`,
      name: `Step ${template.steps.length + 1}`,
      description: '',
      order: template.steps.length,
      fields: [],
      isExpanded: true,
    }
    setTemplate((prev) => ({
      ...prev,
      steps: [...prev.steps, newStep],
    }))
    setSelectedStepId(newStep.id)
  }

  const removeStep = (stepId: string) => {
    if (template.steps.length <= 1) return
    setTemplate((prev) => ({
      ...prev,
      steps: prev.steps.filter((s) => s.id !== stepId),
    }))
  }

  const toggleStepExpanded = (stepId: string) => {
    setTemplate((prev) => ({
      ...prev,
      steps: prev.steps.map((s) => (s.id === stepId ? { ...s, isExpanded: !s.isExpanded } : s)),
    }))
  }

  const updateStep = (stepId: string, updates: Partial<FormStep>) => {
    setTemplate((prev) => ({
      ...prev,
      steps: prev.steps.map((s) => (s.id === stepId ? { ...s, ...updates } : s)),
    }))
  }

  const addField = (stepId: string, fieldType: string) => {
    const fieldDef = FIELD_TYPES.find((f) => f.value === fieldType)
    const step = template.steps.find((s) => s.id === stepId)
    if (!step) return

    const newField: FormField = {
      id: `field-${Date.now()}`,
      name: `field_${step.fields.length + 1}`,
      label: fieldDef?.label || 'New Field',
      field_type: fieldType,
      order: step.fields.length,
      is_required: false,
      width: 'full',
    }

    updateStep(stepId, {
      fields: [...step.fields, newField],
    })
    setShowFieldPalette(false)
  }

  const updateField = (stepId: string, fieldId: string, updates: Partial<FormField>) => {
    const step = template.steps.find((s) => s.id === stepId)
    if (!step) return

    updateStep(stepId, {
      fields: step.fields.map((f) => (f.id === fieldId ? { ...f, ...updates } : f)),
    })
  }

  const removeField = (stepId: string, fieldId: string) => {
    const step = template.steps.find((s) => s.id === stepId)
    if (!step) return

    updateStep(stepId, {
      fields: step.fields.filter((f) => f.id !== fieldId),
    })
  }

  const handleSave = async () => {
    setIsSaving(true)
    setSaveError(null)
    try {
      // In real implementation, save to API
      await new Promise((resolve) => setTimeout(resolve, 1000))
      setSaveSuccess(true)
      setTimeout(() => setSaveSuccess(false), 2000)
    } catch {
      console.error('Failed to save template')
      setSaveError(t('admin.forms.save_error'))
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="min-h-screen bg-surface">
      {/* Header */}
      <header className="bg-card border-b border-border sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={() => navigate('/admin/forms')}
              className="w-10 h-10 flex items-center justify-center rounded-xl bg-surface hover:bg-muted transition-colors"
            >
              <ArrowLeft className="w-5 h-5 text-foreground" />
            </button>
            <div>
              <h1 className="text-lg font-bold text-foreground">
                {isEditing ? t('admin.forms.edit_form') : t('admin.forms.create_new_form')}
              </h1>
              <p className="text-sm text-muted-foreground">{t('admin.forms.design_subtitle')}</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <Button variant="outline" onClick={() => setShowSettings(!showSettings)}>
              <Settings className="w-4 h-4 mr-2" />
              {t('common.settings')}
            </Button>
            <Button variant="outline">
              <Eye className="w-4 h-4 mr-2" />
              {t('admin.forms.preview')}
            </Button>
            <div className="flex flex-col items-end">
              <Button onClick={handleSave} disabled={isSaving}>
                {isSaving ? (
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                ) : saveSuccess ? (
                  <Check className="w-4 h-4 mr-2" />
                ) : (
                  <Save className="w-4 h-4 mr-2" />
                )}
                {saveSuccess ? t('admin.forms.saved') : t('admin.forms.save_form')}
              </Button>
              {saveError && <p className="text-sm text-destructive mt-2">{saveError}</p>}
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main Form Builder */}
          <div className="lg:col-span-2 space-y-6">
            {/* Form Details */}
            <Card className="p-6">
              <h2 className="text-lg font-semibold text-foreground mb-4">
                {t('admin.forms.form_details')}
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label
                    htmlFor="formbuilder-field-0"
                    className="block text-sm font-medium text-foreground mb-2"
                  >
                    {t('admin.forms.form_name')}
                  </label>
                  <Input
                    id="formbuilder-field-0"
                    value={template.name}
                    onChange={(e) => handleNameChange(e.target.value)}
                    placeholder="e.g. Incident Report Form"
                  />
                </div>
                <div>
                  <label
                    htmlFor="formbuilder-field-1"
                    className="block text-sm font-medium text-foreground mb-2"
                  >
                    {t('admin.forms.form_type')}
                  </label>
                  <select
                    id="formbuilder-field-1"
                    value={template.form_type}
                    onChange={(e) =>
                      setTemplate((prev) => ({ ...prev, form_type: e.target.value }))
                    }
                    className="w-full px-3 py-2 bg-card border border-border rounded-lg text-foreground focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
                  >
                    <option value="incident">Incident Report</option>
                    <option value="near_miss">Near Miss</option>
                    <option value="complaint">Complaint</option>
                    <option value="rta">Road Traffic Collision</option>
                    <option value="audit">Audit Checklist</option>
                    <option value="custom">Custom Form</option>
                  </select>
                </div>
                <div className="md:col-span-2">
                  <label
                    htmlFor="formbuilder-field-2"
                    className="block text-sm font-medium text-foreground mb-2"
                  >
                    {t('common.description')}
                  </label>
                  <Textarea
                    id="formbuilder-field-2"
                    value={template.description || ''}
                    onChange={(e) =>
                      setTemplate((prev) => ({ ...prev, description: e.target.value }))
                    }
                    placeholder="Describe what this form is used for..."
                    rows={2}
                  />
                </div>
              </div>
            </Card>

            {/* Steps */}
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold text-foreground">
                  {t('admin.forms.form_steps')}
                </h2>
                <Button variant="outline" size="sm" onClick={addStep}>
                  <Plus className="w-4 h-4 mr-2" />
                  {t('admin.forms.add_step')}
                </Button>
              </div>

              {template.steps.map((step, stepIndex) => (
                <Card key={step.id} className="overflow-hidden">
                  {/* Step Header */}
                  <div
                    className={cn(
                      'flex items-center justify-between p-4 cursor-pointer',
                      selectedStepId === step.id ? 'bg-primary/5' : 'bg-surface',
                    )}
                    onClick={() => {
                      setSelectedStepId(step.id)
                      toggleStepExpanded(step.id)
                    }}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault()
                        setSelectedStepId(step.id)
                        toggleStepExpanded(step.id)
                      }
                    }}
                    role="button"
                    tabIndex={0}
                  >
                    <div className="flex items-center gap-3">
                      <GripVertical className="w-5 h-5 text-muted-foreground cursor-grab" />
                      <div className="w-8 h-8 rounded-full bg-primary/10 text-primary flex items-center justify-center text-sm font-bold">
                        {stepIndex + 1}
                      </div>
                      <div>
                        <input
                          type="text"
                          value={step.name}
                          onChange={(e) => {
                            e.stopPropagation()
                            updateStep(step.id, { name: e.target.value })
                          }}
                          onClick={(e) => e.stopPropagation()}
                          className="font-medium text-foreground bg-transparent border-none focus:outline-none focus:ring-0"
                        />
                        <p className="text-sm text-muted-foreground">{step.fields.length} fields</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {template.steps.length > 1 && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            removeStep(step.id)
                          }}
                          className="p-2 hover:bg-destructive/10 rounded-lg transition-colors"
                        >
                          <Trash2 className="w-4 h-4 text-destructive" />
                        </button>
                      )}
                      {step.isExpanded ? (
                        <ChevronUp className="w-5 h-5 text-muted-foreground" />
                      ) : (
                        <ChevronDown className="w-5 h-5 text-muted-foreground" />
                      )}
                    </div>
                  </div>

                  {/* Step Fields */}
                  {step.isExpanded && (
                    <div className="p-4 border-t border-border space-y-3">
                      {step.fields.length === 0 ? (
                        <div className="text-center py-8 text-muted-foreground">
                          <HelpCircle className="w-12 h-12 mx-auto mb-2 opacity-50" />
                          <p>{t('admin.forms.no_fields')}</p>
                          <p className="text-sm">{t('admin.forms.no_fields_hint')}</p>
                        </div>
                      ) : (
                        step.fields.map((field) => (
                          <div
                            key={field.id}
                            className="flex items-center gap-3 p-3 bg-surface rounded-lg border border-border group"
                          >
                            <GripVertical className="w-4 h-4 text-muted-foreground cursor-grab" />
                            <div className="flex-1 grid grid-cols-3 gap-3">
                              <Input
                                value={field.label}
                                onChange={(e) =>
                                  updateField(step.id, field.id, { label: e.target.value })
                                }
                                placeholder="Field Label"
                                className="text-sm"
                              />
                              <select
                                value={field.field_type}
                                onChange={(e) =>
                                  updateField(step.id, field.id, { field_type: e.target.value })
                                }
                                className="px-3 py-2 bg-card border border-border rounded-lg text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
                              >
                                {FIELD_TYPES.map((ft) => (
                                  <option key={ft.value} value={ft.value}>
                                    {ft.icon} {ft.label}
                                  </option>
                                ))}
                              </select>
                              <div className="flex items-center gap-2">
                                <label
                                  htmlFor="formbuilder-field-3"
                                  className="flex items-center gap-2 text-sm text-muted-foreground"
                                >
                                  <input
                                    id="formbuilder-field-3"
                                    type="checkbox"
                                    checked={field.is_required}
                                    onChange={(e) =>
                                      updateField(step.id, field.id, {
                                        is_required: e.target.checked,
                                      })
                                    }
                                    className="rounded border-border"
                                  />
                                  Required
                                </label>
                              </div>
                            </div>
                            <button
                              onClick={() => removeField(step.id, field.id)}
                              className="p-2 opacity-0 group-hover:opacity-100 hover:bg-destructive/10 rounded-lg transition-all"
                            >
                              <Trash2 className="w-4 h-4 text-destructive" />
                            </button>
                          </div>
                        ))
                      )}

                      {/* Add Field Button */}
                      <div className="relative">
                        <Button
                          variant="outline"
                          size="sm"
                          className="w-full border-dashed"
                          onClick={() => {
                            setSelectedStepId(step.id)
                            setShowFieldPalette(!showFieldPalette)
                          }}
                        >
                          <Plus className="w-4 h-4 mr-2" />
                          Add Field
                        </Button>

                        {/* Field Palette */}
                        {showFieldPalette && selectedStepId === step.id && (
                          <div className="absolute top-full left-0 right-0 mt-2 bg-card border border-border rounded-xl shadow-lg z-10 p-4 max-h-64 overflow-y-auto">
                            <p className="text-xs text-muted-foreground mb-2 font-medium">
                              Select Field Type
                            </p>
                            <div className="grid grid-cols-3 gap-2">
                              {FIELD_TYPES.map((ft) => (
                                <button
                                  key={ft.value}
                                  onClick={() => addField(step.id, ft.value)}
                                  className="flex items-center gap-2 p-2 text-sm text-left hover:bg-surface rounded-lg transition-colors"
                                >
                                  <span>{ft.icon}</span>
                                  <span className="text-foreground">{ft.label}</span>
                                </button>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </Card>
              ))}
            </div>
          </div>

          {/* Settings Panel */}
          <div className="space-y-6">
            <Card className="p-6">
              <h3 className="font-semibold text-foreground mb-4">
                {t('admin.forms.form_settings')}
              </h3>
              <div className="space-y-4">
                <div>
                  <label
                    htmlFor="formbuilder-field-4"
                    className="block text-sm font-medium text-foreground mb-2"
                  >
                    {t('admin.forms.reference_prefix')}
                  </label>
                  <Input
                    id="formbuilder-field-4"
                    value={template.reference_prefix || ''}
                    onChange={(e) =>
                      setTemplate((prev) => ({
                        ...prev,
                        reference_prefix: e.target.value.toUpperCase(),
                      }))
                    }
                    placeholder="e.g. INC"
                    maxLength={10}
                  />
                  <p className="text-xs text-muted-foreground mt-1">
                    References will be: {template.reference_prefix || 'REF'}-2026-0001
                  </p>
                </div>

                <div className="space-y-3">
                  <label
                    htmlFor="formbuilder-field-5"
                    className="flex items-center justify-between"
                  >
                    <span className="text-sm text-foreground">{t('admin.forms.allow_drafts')}</span>
                    <input
                      id="formbuilder-field-5"
                      type="checkbox"
                      checked={template.allow_drafts}
                      onChange={(e) =>
                        setTemplate((prev) => ({ ...prev, allow_drafts: e.target.checked }))
                      }
                      className="rounded border-border"
                    />
                  </label>

                  <label
                    htmlFor="formbuilder-field-6"
                    className="flex items-center justify-between"
                  >
                    <span className="text-sm text-foreground">
                      {t('admin.forms.allow_attachments')}
                    </span>
                    <input
                      id="formbuilder-field-6"
                      type="checkbox"
                      checked={template.allow_attachments}
                      onChange={(e) =>
                        setTemplate((prev) => ({
                          ...prev,
                          allow_attachments: e.target.checked,
                        }))
                      }
                      className="rounded border-border"
                    />
                  </label>

                  <label
                    htmlFor="formbuilder-field-7"
                    className="flex items-center justify-between"
                  >
                    <span className="text-sm text-foreground">
                      {t('admin.forms.require_signature')}
                    </span>
                    <input
                      id="formbuilder-field-7"
                      type="checkbox"
                      checked={template.require_signature}
                      onChange={(e) =>
                        setTemplate((prev) => ({
                          ...prev,
                          require_signature: e.target.checked,
                        }))
                      }
                      className="rounded border-border"
                    />
                  </label>

                  <label
                    htmlFor="formbuilder-field-8"
                    className="flex items-center justify-between"
                  >
                    <span className="text-sm text-foreground">
                      {t('admin.forms.notify_on_submit')}
                    </span>
                    <input
                      id="formbuilder-field-8"
                      type="checkbox"
                      checked={template.notify_on_submit}
                      onChange={(e) =>
                        setTemplate((prev) => ({
                          ...prev,
                          notify_on_submit: e.target.checked,
                        }))
                      }
                      className="rounded border-border"
                    />
                  </label>
                </div>

                {template.notify_on_submit && (
                  <div>
                    <label
                      htmlFor="formbuilder-field-9"
                      className="block text-sm font-medium text-foreground mb-2"
                    >
                      {t('admin.forms.notification_emails')}
                    </label>
                    <Input
                      id="formbuilder-field-9"
                      value={template.notification_emails || ''}
                      onChange={(e) =>
                        setTemplate((prev) => ({
                          ...prev,
                          notification_emails: e.target.value,
                        }))
                      }
                      placeholder="email@example.com, another@example.com"
                    />
                    <p className="text-xs text-muted-foreground mt-1">
                      {t('admin.forms.notification_emails_hint')}
                    </p>
                  </div>
                )}
              </div>
            </Card>

            <Card className="p-6">
              <h3 className="font-semibold text-foreground mb-4">
                {t('admin.forms.quick_actions')}
              </h3>
              <div className="space-y-2">
                <Button variant="outline" className="w-full justify-start">
                  <Copy className="w-4 h-4 mr-2" />
                  {t('admin.forms.duplicate_form')}
                </Button>
                <Button
                  variant="outline"
                  className="w-full justify-start text-destructive hover:bg-destructive/10"
                >
                  <Trash2 className="w-4 h-4 mr-2" />
                  {t('admin.forms.delete_form')}
                </Button>
              </div>
            </Card>
          </div>
        </div>
      </div>
    </div>
  )
}
