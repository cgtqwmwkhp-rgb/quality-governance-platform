import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import {
  ArrowLeft,
  Loader2,
  Plus,
  Save,
  Trash2,
  Layers,
  FileText,
} from 'lucide-react'
import { FE_BUILDER_QUESTION_TYPES } from '../audit-builder/questionTypeRegistry'
import { QUESTION_TYPES } from '../audit-builder/QuestionEditor'
import { investigationsApi, getApiErrorMessage } from '../../api/client'
import type { InvestigationTemplate } from '../../api/investigationsClient'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Textarea } from '../../components/ui/Textarea'
import { Card } from '../../components/ui/Card'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../../components/ui/Select'
import { cn } from '../../helpers/utils'
import {
  APPLICABLE_ENTITY_TYPES,
  createNewField,
  createNewSection,
  createEmptyDraft,
  type ApplicableEntityType,
  type InvestigationTemplateDraft,
} from './types'
import {
  buildTemplateCreatePayload,
  buildTemplateUpdatePayload,
  mapApiToDraft,
} from './templateHelpers'

const QUESTION_TYPE_LABELS = Object.fromEntries(
  QUESTION_TYPES.map((entry) => [entry.type, entry.label]),
) as Record<string, string>

function TemplateListView() {
  const navigate = useNavigate()
  const [templates, setTemplates] = useState<InvestigationTemplate[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      setLoading(true)
      setError('')
      try {
        const response = await investigationsApi.listTemplates({ page: 1, page_size: 50 })
        if (!cancelled) {
          setTemplates(response.data.items ?? [])
        }
      } catch (err) {
        if (!cancelled) {
          setError(getApiErrorMessage(err, 'Failed to load investigation templates'))
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <Link
            to="/investigations"
            className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground mb-2"
          >
            <ArrowLeft size={16} aria-hidden="true" />
            Back to Investigations
          </Link>
          <h1 className="text-3xl font-bold text-foreground">Investigation Templates</h1>
          <p className="text-muted-foreground mt-1">
            Build RCA templates using the shared question type registry (Wave 1).
          </p>
        </div>
        <Button onClick={() => navigate('/investigations/templates/builder/new')}>
          <Plus size={20} aria-hidden="true" />
          New Template
        </Button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-48">
          <Loader2 className="w-8 h-8 text-primary animate-spin" />
        </div>
      ) : error ? (
        <Card className="p-6 text-destructive">{error}</Card>
      ) : templates.length === 0 ? (
        <Card className="p-8 text-center">
          <Layers className="mx-auto mb-3 text-muted-foreground" size={32} aria-hidden="true" />
          <p className="text-muted-foreground mb-4">No investigation templates yet.</p>
          <Button onClick={() => navigate('/investigations/templates/builder/new')}>
            Create your first template
          </Button>
        </Card>
      ) : (
        <div className="grid gap-4">
          {templates.map((template) => (
            <Card
              key={template.id}
              className="p-5 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4"
            >
              <div>
                <h2 className="font-semibold text-foreground">{template.name}</h2>
                <p className="text-sm text-muted-foreground mt-1">
                  v{template.version} · {(template.structure?.sections as unknown[] | undefined)?.length ?? 0}{' '}
                  sections
                </p>
              </div>
              <Button
                variant="outline"
                onClick={() => navigate(`/investigations/templates/builder/${template.id}/edit`)}
              >
                <FileText size={16} aria-hidden="true" />
                Edit
              </Button>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}

function TemplateEditorView({ templateId }: { templateId?: string }) {
  const navigate = useNavigate()
  const isNew = !templateId
  const [draft, setDraft] = useState<InvestigationTemplateDraft>(createEmptyDraft())
  const [loading, setLoading] = useState(!isNew)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [saveError, setSaveError] = useState('')

  const paletteTypes = useMemo(
    () =>
      FE_BUILDER_QUESTION_TYPES.map((type) => ({
        type,
        label: QUESTION_TYPE_LABELS[type] ?? type,
      })),
    [],
  )

  useEffect(() => {
    if (isNew) {
      return
    }
    let cancelled = false
    ;(async () => {
      setLoading(true)
      setError('')
      try {
        const response = await investigationsApi.getTemplate(Number(templateId))
        if (!cancelled) {
          setDraft(mapApiToDraft(response.data))
        }
      } catch (err) {
        if (!cancelled) {
          setError(getApiErrorMessage(err, 'Failed to load template'))
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    })()
    return () => {
      cancelled = true
    }
  }, [isNew, templateId])

  const toggleEntityType = useCallback((value: ApplicableEntityType) => {
    setDraft((current) => {
      const selected = current.applicable_entity_types.includes(value)
      const applicable_entity_types = selected
        ? current.applicable_entity_types.filter((item) => item !== value)
        : [...current.applicable_entity_types, value]
      return { ...current, applicable_entity_types }
    })
  }, [])

  const handleSave = async () => {
    if (!draft.name.trim()) {
      setSaveError('Template name is required.')
      return
    }
    if (draft.applicable_entity_types.length === 0) {
      setSaveError('Select at least one applicable entity type.')
      return
    }

    setSaving(true)
    setSaveError('')
    try {
      if (isNew) {
        const response = await investigationsApi.createTemplate(buildTemplateCreatePayload(draft))
        navigate(`/investigations/templates/builder/${response.data.id}/edit`, { replace: true })
      } else {
        await investigationsApi.updateTemplate(Number(templateId), buildTemplateUpdatePayload(draft))
      }
    } catch (err) {
      setSaveError(getApiErrorMessage(err, 'Failed to save template'))
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 text-primary animate-spin" />
      </div>
    )
  }

  if (error) {
    return (
      <Card className="p-6 space-y-4">
        <p className="text-destructive">{error}</p>
        <Button variant="outline" onClick={() => navigate('/investigations/templates/builder')}>
          Back to templates
        </Button>
      </Card>
    )
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <Link
            to="/investigations/templates/builder"
            className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground mb-2"
          >
            <ArrowLeft size={16} aria-hidden="true" />
            All templates
          </Link>
          <h1 className="text-3xl font-bold text-foreground">
            {isNew ? 'New Investigation Template' : 'Edit Investigation Template'}
          </h1>
          <p className="text-muted-foreground mt-1">
            Question types from the Wave 1 audit registry ({FE_BUILDER_QUESTION_TYPES.length} palette
            types).
          </p>
        </div>
        <Button onClick={handleSave} disabled={saving}>
          {saving ? <Loader2 className="animate-spin" size={18} /> : <Save size={18} aria-hidden="true" />}
          Save template
        </Button>
      </div>

      {saveError ? <Card className="p-4 text-destructive text-sm">{saveError}</Card> : null}

      <Card className="p-6 space-y-4">
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <label className="text-sm font-medium text-foreground" htmlFor="template-name">
              Name
            </label>
            <Input
              id="template-name"
              value={draft.name}
              onChange={(event) => setDraft((current) => ({ ...current, name: event.target.value }))}
              placeholder="Incident RCA Template"
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-foreground" htmlFor="template-version">
              Version
            </label>
            <Input
              id="template-version"
              value={draft.version}
              onChange={(event) => setDraft((current) => ({ ...current, version: event.target.value }))}
            />
          </div>
        </div>
        <div className="space-y-2">
          <label className="text-sm font-medium text-foreground" htmlFor="template-description">
            Description
          </label>
          <Textarea
            id="template-description"
            value={draft.description}
            onChange={(event) =>
              setDraft((current) => ({ ...current, description: event.target.value }))
            }
            rows={2}
          />
        </div>
        <div className="space-y-2">
          <span className="text-sm font-medium text-foreground">Applicable entity types</span>
          <div className="flex flex-wrap gap-2">
            {APPLICABLE_ENTITY_TYPES.map((entry) => {
              const selected = draft.applicable_entity_types.includes(entry.value)
              return (
                <button
                  key={entry.value}
                  type="button"
                  onClick={() => toggleEntityType(entry.value)}
                  className={cn(
                    'rounded-full border px-3 py-1 text-sm transition-colors',
                    selected
                      ? 'border-primary bg-primary/10 text-primary'
                      : 'border-border text-muted-foreground hover:border-primary/40',
                  )}
                >
                  {entry.label}
                </button>
              )
            })}
          </div>
        </div>
      </Card>

      <div className="space-y-4">
        {draft.sections.map((section, sectionIndex) => (
          <Card key={section.id} className="p-6 space-y-4">
            <div className="flex items-start gap-3">
              <Input
                value={section.name}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    sections: current.sections.map((item, index) =>
                      index === sectionIndex ? { ...item, name: event.target.value } : item,
                    ),
                  }))
                }
                className="font-semibold"
              />
              <Button
                variant="ghost"
                size="icon"
                aria-label="Remove section"
                disabled={draft.sections.length <= 1}
                onClick={() =>
                  setDraft((current) => ({
                    ...current,
                    sections: current.sections.filter((_, index) => index !== sectionIndex),
                  }))
                }
              >
                <Trash2 size={16} />
              </Button>
            </div>

            <div className="space-y-3">
              {section.fields.map((field, fieldIndex) => (
                <div
                  key={field.id}
                  className="grid gap-3 rounded-lg border border-border p-4 md:grid-cols-[1fr_180px_100px_auto]"
                >
                  <Input
                    value={field.label}
                    placeholder="Question label"
                    onChange={(event) =>
                      setDraft((current) => ({
                        ...current,
                        sections: current.sections.map((item, sIndex) =>
                          sIndex === sectionIndex
                            ? {
                                ...item,
                                fields: item.fields.map((f, fIndex) =>
                                  fIndex === fieldIndex ? { ...f, label: event.target.value } : f,
                                ),
                              }
                            : item,
                        ),
                      }))
                    }
                  />
                  <Select
                    value={field.type}
                    onValueChange={(value) =>
                      setDraft((current) => ({
                        ...current,
                        sections: current.sections.map((item, sIndex) =>
                          sIndex === sectionIndex
                            ? {
                                ...item,
                                fields: item.fields.map((f, fIndex) =>
                                  fIndex === fieldIndex
                                    ? { ...f, type: value as typeof field.type }
                                    : f,
                                ),
                              }
                            : item,
                        ),
                      }))
                    }
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Type" />
                    </SelectTrigger>
                    <SelectContent>
                      {paletteTypes.map((entry) => (
                        <SelectItem key={entry.type} value={entry.type}>
                          {entry.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <label className="flex items-center gap-2 text-sm text-foreground">
                    <input
                      type="checkbox"
                      checked={field.required}
                      onChange={(event) =>
                        setDraft((current) => ({
                          ...current,
                          sections: current.sections.map((item, sIndex) =>
                            sIndex === sectionIndex
                              ? {
                                  ...item,
                                  fields: item.fields.map((f, fIndex) =>
                                    fIndex === fieldIndex
                                      ? { ...f, required: event.target.checked }
                                      : f,
                                  ),
                                }
                              : item,
                          ),
                        }))
                      }
                    />
                    Required
                  </label>
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label="Remove question"
                    onClick={() =>
                      setDraft((current) => ({
                        ...current,
                        sections: current.sections.map((item, sIndex) =>
                          sIndex === sectionIndex
                            ? {
                                ...item,
                                fields: item.fields.filter((_, fIndex) => fIndex !== fieldIndex),
                              }
                            : item,
                        ),
                      }))
                    }
                  >
                    <Trash2 size={16} />
                  </Button>
                </div>
              ))}
            </div>

            <Button
              variant="outline"
              size="sm"
              onClick={() =>
                setDraft((current) => ({
                  ...current,
                  sections: current.sections.map((item, index) =>
                    index === sectionIndex
                      ? { ...item, fields: [...item.fields, createNewField()] }
                      : item,
                  ),
                }))
              }
            >
              <Plus size={16} aria-hidden="true" />
              Add question
            </Button>
          </Card>
        ))}
      </div>

      <Button
        variant="outline"
        onClick={() =>
          setDraft((current) => ({
            ...current,
            sections: [...current.sections, createNewSection(current.sections.length + 1)],
          }))
        }
      >
        <Plus size={16} aria-hidden="true" />
        Add section
      </Button>
    </div>
  )
}

export default function InvestigationTemplateBuilder() {
  const location = useLocation()
  const isNew = location.pathname.endsWith('/new')
  const editMatch = location.pathname.match(/\/builder\/(\d+)\/edit$/)
  const templateId = editMatch?.[1]
  const isEditor = isNew || Boolean(templateId)

  if (isEditor) {
    return <TemplateEditorView templateId={isNew ? undefined : templateId} />
  }

  return <TemplateListView />
}
