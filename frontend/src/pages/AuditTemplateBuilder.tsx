import { useState, useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router-dom'
import {
  Plus,
  Copy,
  Upload,
  Download,
  History,
  Camera,
  Award,
  FileText,
  HardHat,
  Leaf,
  Shield,
  Zap,
  Layers,
  Lock,
  Unlock,
} from 'lucide-react'
import AITemplateGenerator from '../components/AITemplateGenerator'
import { useLiveAnnouncer } from '../components/ui/LiveAnnouncer'
import { auditsApi, getApiErrorMessage } from '../api/client'
import type { AuditTemplate, Section, Question, ScoringMethod } from './audit-builder/types'
import { generateId, createNewSection, createNewQuestion } from './audit-builder/types'
import {
  mapApiToTemplate,
  mapAISectionsToLocal,
  buildQuestionPayload,
} from './audit-builder/templateHelpers'
import { QUESTION_TYPES } from './audit-builder/QuestionEditor'
import SectionEditor from './audit-builder/SectionEditor'
import TemplateHeader from './audit-builder/TemplateHeader'
import PublishDialog from './audit-builder/PublishDialog'

const CATEGORIES = [
  { id: 'quality', label: 'Quality Management', icon: Award, color: 'blue' },
  { id: 'safety', label: 'Health & Safety', icon: HardHat, color: 'orange' },
  { id: 'environment', label: 'Environmental', icon: Leaf, color: 'green' },
  { id: 'security', label: 'Security', icon: Shield, color: 'teal' },
  { id: 'compliance', label: 'Regulatory Compliance', icon: FileText, color: 'red' },
  { id: 'operational', label: 'Operational', icon: Zap, color: 'yellow' },
  { id: 'custom', label: 'Custom', icon: Layers, color: 'gray' },
]

const ISO_STANDARDS = [
  { id: 'iso9001', label: 'ISO 9001:2015', description: 'Quality Management' },
  { id: 'iso14001', label: 'ISO 14001:2015', description: 'Environmental Management' },
  { id: 'iso45001', label: 'ISO 45001:2018', description: 'Occupational Health & Safety' },
  { id: 'iso27001', label: 'ISO 27001:2022', description: 'Information Security' },
  { id: 'iso22000', label: 'ISO 22000:2018', description: 'Food Safety' },
  { id: 'iso50001', label: 'ISO 50001:2018', description: 'Energy Management' },
]

const CHOICE_BASED_TYPES = new Set<Question['type']>(['multi_choice', 'checklist'])

function getQuestionValidationErrors(question: Question): string[] {
  const errors: string[] = []
  if (!question.text.trim()) {
    errors.push('Question text is required.')
  }
  if (question.weight <= 0) {
    errors.push('Question weight must be greater than zero.')
  }
  if (CHOICE_BASED_TYPES.has(question.type)) {
    const options = question.options || []
    const populatedOptions = options.filter((option) => option.label.trim() && option.value.trim())
    if (populatedOptions.length < 2) {
      errors.push('Choice questions need at least two answer options.')
    }
    if (options.some((option) => !option.label.trim() || !option.value.trim())) {
      errors.push('Every answer option needs both a label and a value.')
    }
  }
  return errors
}

function getSectionValidationErrors(section: Section): string[] {
  const errors: string[] = []
  if (!section.title.trim()) {
    errors.push('Section title is required.')
  }
  if (section.questions.length === 0) {
    errors.push('Add at least one question to this section before publishing.')
  }
  return errors
}

function renderPreviewControl(question: Question) {
  switch (question.type) {
    case 'yes_no':
    case 'yes_no_na':
    case 'pass_fail': {
      const values =
        question.type === 'pass_fail'
          ? ['Pass', 'Fail']
          : question.type === 'yes_no_na'
            ? ['Yes', 'No', 'N/A']
            : ['Yes', 'No']
      return (
        <div className="flex flex-wrap gap-3">
          {values.map((value) => (
            <label key={value} className="flex items-center gap-2 text-sm text-foreground">
              <input type="radio" name={`preview-${question.id}`} disabled />
              {value}
            </label>
          ))}
        </div>
      )
    }
    case 'multi_choice':
      return (
        <div className="space-y-2">
          {(question.options || []).map((option) => (
            <label key={option.id} className="flex items-center gap-2 text-sm text-foreground">
              <input type="radio" name={`preview-${question.id}`} disabled />
              {option.label}
            </label>
          ))}
        </div>
      )
    case 'checklist':
      return (
        <div className="space-y-2">
          {(question.options || []).map((option) => (
            <label key={option.id} className="flex items-center gap-2 text-sm text-foreground">
              <input type="checkbox" disabled />
              {option.label}
            </label>
          ))}
        </div>
      )
    case 'text_long':
      return <textarea disabled rows={3} className="w-full rounded-lg border border-border bg-secondary px-3 py-2" />
    case 'numeric':
      return <input disabled type="number" className="w-full rounded-lg border border-border bg-secondary px-3 py-2" />
    case 'date':
      return <input disabled type="date" className="w-full rounded-lg border border-border bg-secondary px-3 py-2" />
    case 'scale_1_10':
    case 'scale_1_5': {
      const max = question.type === 'scale_1_10' ? 10 : 5
      return (
        <div className="flex flex-wrap gap-2">
          {Array.from({ length: max }, (_, index) => index + 1).map((value) => (
            <button
              key={value}
              type="button"
              disabled
              className="h-9 w-9 rounded-lg border border-border bg-secondary text-sm text-foreground"
            >
              {value}
            </button>
          ))}
        </div>
      )
    }
    case 'photo':
      return <div className="rounded-lg border border-dashed border-border bg-secondary px-3 py-6 text-sm text-muted-foreground">Photo evidence upload</div>
    case 'signature':
      return <div className="rounded-lg border border-dashed border-border bg-secondary px-3 py-6 text-sm text-muted-foreground">Signature capture</div>
    case 'text_short':
    default:
      return <input disabled type="text" className="w-full rounded-lg border border-border bg-secondary px-3 py-2" />
  }
}

export default function AuditTemplateBuilder() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { templateId } = useParams()
  const { announce } = useLiveAnnouncer()

  const [template, setTemplate] = useState<AuditTemplate>({
    id: templateId || generateId(),
    name: '',
    description: '',
    version: '1.0.0',
    status: 'draft',
    category: 'quality',
    isoStandards: [],
    sections: [createNewSection(1)],
    scoringMethod: 'weighted',
    passThreshold: 80,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    createdBy: 'Current User',
    tags: [],
    estimatedDuration: 60,
    isLocked: false,
  })

  const [activeTab, setActiveTab] = useState<'builder' | 'settings' | 'preview'>('builder')
  const [isSaving, setIsSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [showAIAssist, setShowAIAssist] = useState(false)
  const [showPublishDialog, setShowPublishDialog] = useState(false)
  const [backendId, setBackendId] = useState<number | null>(
    templateId && !isNaN(Number(templateId)) ? Number(templateId) : null,
  )
  const [isPublishing, setIsPublishing] = useState(false)
  const [isLoading, setIsLoading] = useState(!!templateId)
  const sectionIdMap = useRef<Record<string, number>>({})
  const questionIdMap = useRef<Record<string, number>>({})
  const deletedSectionIds = useRef<number[]>([])
  const deletedQuestionIds = useRef<number[]>([])
  const allQuestions = template.sections.flatMap((s) => s.questions)
  const validation = (() => {
    const questionErrors: Record<string, string[]> = {}
    const sectionErrors: Record<string, string[]> = {}
    const publishErrors: string[] = []

    if (!template.name.trim()) {
      publishErrors.push('Template name is required.')
    }
    if (template.sections.length === 0) {
      publishErrors.push('Add at least one section before publishing.')
    }
    if (allQuestions.length === 0) {
      publishErrors.push('Add at least one question before publishing.')
    }

    template.sections.forEach((section, index) => {
      const sectionValidationErrors = getSectionValidationErrors(section)
      if (sectionValidationErrors.length > 0) {
        sectionErrors[section.id] = sectionValidationErrors
        publishErrors.push(`Section ${index + 1}: ${sectionValidationErrors[0]}`)
      }
      section.questions.forEach((question, questionIndex) => {
        const questionValidationErrors = getQuestionValidationErrors(question)
        if (questionValidationErrors.length > 0) {
          questionErrors[question.id] = questionValidationErrors
          publishErrors.push(
            `${section.title || `Section ${index + 1}`}, question ${questionIndex + 1}: ${questionValidationErrors[0]}`,
          )
        }
      })
    })

    return {
      questionErrors,
      sectionErrors,
      publishErrors,
      hasBlockingPublishErrors: publishErrors.length > 0,
    }
  })()

  useEffect(() => {
    if (!templateId) return
    const numericId = Number(templateId)
    if (isNaN(numericId)) return
    ;(async () => {
      try {
        const { data } = await auditsApi.getTemplate(numericId)
        sectionIdMap.current = {}
        questionIdMap.current = {}
        deletedSectionIds.current = []
        deletedQuestionIds.current = []
        setTemplate(mapApiToTemplate(data, sectionIdMap.current, questionIdMap.current))
        setBackendId(data.id)
      } catch (error) {
        setSaveError(getApiErrorMessage(error))
      } finally {
        setIsLoading(false)
      }
    })()
  }, [templateId])

  const updateSections = (fn: (ss: Section[]) => Section[]) =>
    setTemplate((prev) => ({ ...prev, sections: fn(prev.sections) }))

  const handleAddSection = () => updateSections((ss) => [...ss, createNewSection(ss.length + 1)])
  const handleUpdateSection = (id: string, updates: Partial<Section>) =>
    updateSections((ss) => ss.map((s) => (s.id === id ? { ...s, ...updates } : s)))
  const handleDeleteSection = (id: string) => {
    const backendSectionId = sectionIdMap.current[id]
    if (backendSectionId) {
      deletedSectionIds.current.push(backendSectionId)
    }
    const section = template.sections.find((entry) => entry.id === id)
    section?.questions.forEach((question) => {
      const backendQuestionId = questionIdMap.current[question.id]
      if (backendQuestionId) {
        deletedQuestionIds.current.push(backendQuestionId)
      }
    })
    updateSections((ss) => ss.filter((s) => s.id !== id))
  }
  const handleAddQuestion = (sid: string) => {
    const q = createNewQuestion()
    updateSections((ss) =>
      ss.map((s) => (s.id === sid ? { ...s, questions: [...s.questions, q] } : s)),
    )
  }
  const handleUpdateQuestion = (sid: string, qid: string, updates: Partial<Question>) =>
    updateSections((ss) =>
      ss.map((s) =>
        s.id === sid
          ? { ...s, questions: s.questions.map((q) => (q.id === qid ? { ...q, ...updates } : q)) }
          : s,
      ),
    )
  const handleDeleteQuestion = (sid: string, qid: string) => {
    const backendQuestionId = questionIdMap.current[qid]
    if (backendQuestionId) {
      deletedQuestionIds.current.push(backendQuestionId)
    }
    updateSections((ss) =>
      ss.map((s) =>
        s.id === sid ? { ...s, questions: s.questions.filter((q) => q.id !== qid) } : s,
      ),
    )
  }
  const handleDuplicateQuestion = (sid: string, qid: string) =>
    updateSections((ss) =>
      ss.map((s) => {
        if (s.id !== sid) return s
        const i = s.questions.findIndex((q) => q.id === qid)
        if (i === -1) return s
        const dup = { ...s.questions[i], id: generateId(), text: `${s.questions[i].text} (Copy)` }
        const qs = [...s.questions]
        qs.splice(i + 1, 0, dup)
        return { ...s, questions: qs }
      }),
    )

  const handleSave = async () => {
    if (!template.name.trim()) {
      const msg = 'Template name is required'
      setSaveError(msg)
      announce(msg, 'assertive')
      return
    }
    setIsSaving(true)
    setSaveError(null)
    try {
      const payload = {
        name: template.name,
        description: template.description || undefined,
        category: template.category || undefined,
        scoring_method: template.scoringMethod,
        passing_score: template.passThreshold,
        pass_threshold: template.passThreshold,
        estimated_duration: template.estimatedDuration,
      }
      let tid = backendId
      if (tid) await auditsApi.updateTemplate(tid, payload)
      else {
        const { data } = await auditsApi.createTemplate(payload)
        tid = data.id
        setBackendId(tid)
      }

      for (const [sIdx, section] of template.sections.entries()) {
        let sid = sectionIdMap.current[section.id]
        const sp = {
          title: section.title,
          description: section.description,
          sort_order: sIdx,
          weight: section.weight,
        }
        if (sid) await auditsApi.updateSection(sid, sp)
        else {
          const { data } = await auditsApi.createSection(tid!, sp)
          sid = data.id
          sectionIdMap.current[section.id] = sid
        }
        for (const [qIdx, q] of section.questions.entries()) {
          const qbid = questionIdMap.current[q.id]
          if (qbid) await auditsApi.updateQuestion(qbid, buildQuestionPayload(q, qIdx))
          else {
            const { data } = await auditsApi.createQuestion(
              tid!,
              buildQuestionPayload(q, qIdx, sid),
            )
            questionIdMap.current[q.id] = data.id
          }
        }
      }

      for (const deletedQuestionId of [...new Set(deletedQuestionIds.current)]) {
        await auditsApi.deleteQuestion(deletedQuestionId)
      }
      deletedQuestionIds.current = []

      for (const deletedSectionId of [...new Set(deletedSectionIds.current)]) {
        await auditsApi.deleteSection(deletedSectionId)
      }
      deletedSectionIds.current = []
    } catch (error) {
      const msg = getApiErrorMessage(error)
      setSaveError(msg)
      announce(msg, 'assertive')
    } finally {
      setIsSaving(false)
    }
  }

  const handlePublish = async () => {
    if (validation.hasBlockingPublishErrors) {
      const msg =
        validation.publishErrors.length === 1
          ? validation.publishErrors[0]
          : `Fix ${validation.publishErrors.length} validation issues before publishing.`
      setSaveError(msg)
      announce(msg, 'assertive')
      setActiveTab('builder')
      setShowPublishDialog(false)
      return
    }
    if (!backendId) {
      const msg = 'Please save the template before publishing'
      setSaveError(msg)
      announce(msg, 'assertive')
      return
    }
    setIsPublishing(true)
    setSaveError(null)
    try {
      await auditsApi.publishTemplate(backendId)
      setTemplate((prev) => ({ ...prev, status: 'published' }))
      setShowPublishDialog(false)
    } catch (error) {
      const msg = getApiErrorMessage(error)
      setSaveError(msg)
      announce(msg, 'assertive')
    } finally {
      setIsPublishing(false)
    }
  }

  const totalQuestions = allQuestions.length
  const totalWeight = allQuestions.reduce((sum, q) => sum + q.weight, 0)
  const requiredQuestions = allQuestions.filter((q) => q.required).length
  const evidenceQuestions = allQuestions.filter((q) => q.evidenceRequired).length

  return (
    <div className="min-h-screen bg-background">
      <TemplateHeader
        templateName={template.name}
        templateStatus={template.status}
        templateVersion={template.version}
        totalQuestions={totalQuestions}
        activeTab={activeTab}
        onTabChange={setActiveTab}
        onNameChange={(name) => setTemplate((prev) => ({ ...prev, name }))}
        onBack={() => navigate('/audit-templates')}
        onSave={handleSave}
        isSaving={isSaving}
        onPublish={() => setShowPublishDialog(true)}
        canPublish={!!backendId && template.status !== 'published'}
        onAIAssist={() => setShowAIAssist(true)}
        saveError={saveError}
      />

      <main className="max-w-7xl mx-auto px-4 py-6">
        {isLoading ? (
          <div className="flex items-center justify-center py-20">
            <div className="w-8 h-8 border-4 border-primary/30 border-t-primary rounded-full animate-spin" />
          </div>
        ) : (
          <>
            {validation.publishErrors.length > 0 && (
              <div className="mb-6 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
                <p className="font-semibold">Template validation</p>
                <p className="mt-1">
                  Fix the highlighted authoring issues before publishing this template.
                </p>
              </div>
            )}
            {activeTab === 'builder' && (
              <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
                <div className="lg:col-span-1 space-y-4">
                  <div className="bg-card/50 border border-border rounded-2xl p-4">
                    <h3 className="text-sm font-semibold text-foreground mb-4">
                      {t('audit_builder.template_stats')}
                    </h3>
                    <div className="space-y-3">
                      {[
                        [t('audit_builder.sections'), template.sections.length],
                        [t('audit_builder.questions'), totalQuestions],
                        [t('audit_builder.required'), requiredQuestions],
                        [t('audit_builder.with_evidence'), evidenceQuestions],
                        [t('audit_builder.total_weight'), totalWeight],
                      ].map(([label, value]) => (
                        <div key={String(label)} className="flex justify-between">
                          <span className="text-sm text-muted-foreground">{label}</span>
                          <span className="text-sm font-medium text-foreground">{value}</span>
                        </div>
                      ))}
                      <div className="flex justify-between">
                        <span className="text-sm text-muted-foreground">
                          {t('audit_builder.pass_threshold')}
                        </span>
                        <span className="text-sm font-medium text-success">
                          {template.passThreshold}%
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="bg-card/50 border border-border rounded-2xl p-4">
                    <h3 className="text-sm font-semibold text-foreground mb-4">Quick Actions</h3>
                    <div className="space-y-2">
                      {[
                        { icon: Upload, label: t('audit_builder.import_excel') },
                        { icon: Download, label: t('audit_builder.export_template') },
                        { icon: Copy, label: t('audit_builder.duplicate_template') },
                        { icon: History, label: t('audit_builder.version_history') },
                      ].map(({ icon: Icon, label }) => (
                        <button
                          key={label}
                          className="w-full flex items-center gap-2 px-3 py-2 bg-secondary hover:bg-muted rounded-lg text-sm text-foreground transition-colors"
                        >
                          <Icon className="w-4 h-4" />
                          {label}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="bg-card/50 border border-border rounded-2xl p-4">
                    <h3 className="text-sm font-semibold text-foreground mb-4">
                      {t('audit_builder.iso_standards')}
                    </h3>
                    <div className="space-y-2">
                      {ISO_STANDARDS.map((standard) => (
                        <label key={standard.id} className="flex items-center gap-2 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={template.isoStandards.includes(standard.id)}
                            onChange={(e) => {
                              setTemplate((prev) => ({
                                ...prev,
                                isoStandards: e.target.checked
                                  ? [...prev.isoStandards, standard.id]
                                  : prev.isoStandards.filter((s) => s !== standard.id),
                              }))
                            }}
                            className="w-4 h-4 rounded border-input bg-input text-primary focus:ring-ring"
                          />
                          <div>
                            <p className="text-sm text-foreground">{standard.label}</p>
                            <p className="text-xs text-muted-foreground">{standard.description}</p>
                          </div>
                        </label>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="lg:col-span-3 space-y-4">
                  <div className="bg-card/50 border border-border rounded-2xl p-4">
                    <label
                      htmlFor="audittemplatebuilder-field-6"
                      className="block text-sm font-medium text-foreground mb-2"
                    >
                      {t('audit_builder.template_description')}
                    </label>
                    <textarea
                      id="audittemplatebuilder-field-6"
                      value={template.description}
                      onChange={(e) =>
                        setTemplate((prev) => ({ ...prev, description: e.target.value }))
                      }
                      placeholder="Describe the purpose and scope of this audit template..."
                      rows={2}
                      className="w-full px-3 py-2 bg-secondary border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-ring resize-none"
                    />
                  </div>
                  <div className="space-y-4">
                    {template.sections.map((section) => (
                      <SectionEditor
                        key={section.id}
                        section={section}
                        onUpdate={(updates) => handleUpdateSection(section.id, updates)}
                        onDelete={() => handleDeleteSection(section.id)}
                        onAddQuestion={() => handleAddQuestion(section.id)}
                        onUpdateQuestion={(qId, updates) =>
                          handleUpdateQuestion(section.id, qId, updates)
                        }
                        onDeleteQuestion={(qId) => handleDeleteQuestion(section.id, qId)}
                        onDuplicateQuestion={(qId) => handleDuplicateQuestion(section.id, qId)}
                        sectionValidationErrors={validation.sectionErrors[section.id] || []}
                        questionValidationErrors={validation.questionErrors}
                      />
                    ))}
                    <button
                      type="button"
                      onClick={handleAddSection}
                      className="w-full py-4 border-2 border-dashed border-border rounded-2xl text-muted-foreground hover:border-primary hover:text-primary transition-colors flex items-center justify-center gap-2"
                    >
                      <Plus className="w-5 h-5" />
                      {t('audit_builder.add_section')}
                    </button>
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'settings' && (
              <div className="max-w-2xl mx-auto space-y-6">
                <div className="bg-card/50 border border-border rounded-2xl p-6">
                  <h2 className="text-lg font-semibold text-foreground mb-6">
                    {t('audit_builder.template_settings')}
                  </h2>
                  <div className="space-y-6">
                    <div>
                      <span className="block text-sm font-medium text-foreground mb-2">
                        Category
                      </span>
                      <div className="grid grid-cols-2 gap-2">
                        {CATEGORIES.map((cat) => (
                          <button
                            key={cat.id}
                            type="button"
                            onClick={() => setTemplate((prev) => ({ ...prev, category: cat.id }))}
                            className={`flex items-center gap-3 p-3 rounded-xl border-2 transition-all ${
                              template.category === cat.id
                                ? 'border-primary bg-primary/10'
                                : 'border-border hover:border-input'
                            }`}
                          >
                            <cat.icon
                              className={`w-5 h-5 ${template.category === cat.id ? 'text-primary' : 'text-muted-foreground'}`}
                            />
                            <span className="text-sm text-foreground">{cat.label}</span>
                          </button>
                        ))}
                      </div>
                    </div>
                    <div>
                      <span className="block text-sm font-medium text-foreground mb-2">
                        Scoring Method
                      </span>
                      <div className="grid grid-cols-2 gap-2">
                        {(
                          [
                            {
                              id: 'weighted',
                              label: 'Weighted',
                              description: 'Questions have different weights',
                            },
                            {
                              id: 'equal',
                              label: 'Equal Weight',
                              description: 'All questions count equally',
                            },
                            {
                              id: 'pass_fail',
                              label: 'Pass/Fail',
                              description: 'Binary pass or fail result',
                            },
                            {
                              id: 'points',
                              label: 'Points Based',
                              description: 'Accumulate points',
                            },
                          ] as const
                        ).map((method) => (
                          <button
                            key={method.id}
                            type="button"
                            onClick={() =>
                              setTemplate((prev) => ({
                                ...prev,
                                scoringMethod: method.id as ScoringMethod,
                              }))
                            }
                            className={`p-3 rounded-xl border-2 text-left transition-all ${
                              template.scoringMethod === method.id
                                ? 'border-primary bg-primary/10'
                                : 'border-border hover:border-input'
                            }`}
                          >
                            <p className="text-sm font-medium text-foreground">{method.label}</p>
                            <p className="text-xs text-muted-foreground mt-1">
                              {method.description}
                            </p>
                          </button>
                        ))}
                      </div>
                    </div>
                    <div>
                      <label
                        htmlFor="audittemplatebuilder-field-7"
                        className="block text-sm font-medium text-foreground mb-2"
                      >
                        Pass Threshold: {template.passThreshold}%
                      </label>
                      <input
                        id="audittemplatebuilder-field-7"
                        type="range"
                        min="0"
                        max="100"
                        value={template.passThreshold}
                        onChange={(e) =>
                          setTemplate((prev) => ({
                            ...prev,
                            passThreshold: parseInt(e.target.value),
                          }))
                        }
                        className="w-full h-2 bg-input rounded-lg appearance-none cursor-pointer"
                      />
                      <div className="flex justify-between text-xs text-muted-foreground mt-1">
                        <span>0%</span>
                        <span>100%</span>
                      </div>
                    </div>
                    <div>
                      <label
                        htmlFor="audittemplatebuilder-field-8"
                        className="block text-sm font-medium text-foreground mb-2"
                      >
                        Estimated Duration (minutes)
                      </label>
                      <input
                        id="audittemplatebuilder-field-8"
                        type="number"
                        min="0"
                        value={template.estimatedDuration}
                        onChange={(e) =>
                          setTemplate((prev) => ({
                            ...prev,
                            estimatedDuration: parseInt(e.target.value) || 0,
                          }))
                        }
                        className="w-full px-3 py-2 bg-secondary border border-border rounded-lg text-foreground focus:outline-none focus:border-ring"
                      />
                    </div>
                    <div>
                      <label
                        htmlFor="audittemplatebuilder-field-9"
                        className="block text-sm font-medium text-foreground mb-2"
                      >
                        Version
                      </label>
                      <input
                        id="audittemplatebuilder-field-9"
                        type="text"
                        placeholder="1.0.0"
                        value={template.version}
                        onChange={(e) =>
                          setTemplate((prev) => ({ ...prev, version: e.target.value }))
                        }
                        className="w-full px-3 py-2 bg-secondary border border-border rounded-lg text-foreground focus:outline-none focus:border-ring"
                      />
                    </div>
                    <div className="flex items-center justify-between p-4 bg-secondary rounded-xl">
                      <div className="flex items-center gap-3">
                        {template.isLocked ? (
                          <Lock className="w-5 h-5 text-warning" />
                        ) : (
                          <Unlock className="w-5 h-5 text-muted-foreground" />
                        )}
                        <div>
                          <p className="text-sm font-medium text-foreground">Lock Template</p>
                          <p className="text-xs text-muted-foreground">
                            Prevent edits after publishing
                          </p>
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() =>
                          setTemplate((prev) => ({ ...prev, isLocked: !prev.isLocked }))
                        }
                        className={`relative w-12 h-6 rounded-full transition-colors ${template.isLocked ? 'bg-warning' : 'bg-muted'}`}
                      >
                        <span
                          className={`absolute top-1 w-4 h-4 bg-card rounded-full transition-transform ${template.isLocked ? 'translate-x-7' : 'translate-x-1'}`}
                        />
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'preview' && (
              <div className="max-w-2xl mx-auto">
                <div className="bg-card/50 border border-border rounded-2xl p-6">
                  <div className="text-center mb-8">
                    <h2 className="text-2xl font-bold text-foreground mb-2">
                      {template.name || t('audit_builder.untitled_template')}
                    </h2>
                    <p className="text-muted-foreground">{template.description}</p>
                    <div className="flex items-center justify-center gap-4 mt-4">
                      <span className="px-3 py-1 bg-primary/20 text-primary rounded-lg text-sm">
                        {totalQuestions} Questions
                      </span>
                      <span className="px-3 py-1 bg-input text-foreground rounded-lg text-sm">
                        ~{template.estimatedDuration} min
                      </span>
                      <span className="px-3 py-1 bg-success/20 text-success rounded-lg text-sm">
                        Pass: {template.passThreshold}%
                      </span>
                    </div>
                  </div>
                  {template.sections.map((section, sectionIndex) => (
                    <div key={section.id} className="mb-6">
                      <div className={`bg-gradient-to-r ${section.color} p-0.5 rounded-xl`}>
                        <div className="bg-card p-4 rounded-xl">
                          <h3 className="text-lg font-semibold text-foreground">
                            {sectionIndex + 1}. {section.title}
                          </h3>
                          {section.description && (
                            <p className="text-sm text-muted-foreground mt-1">
                              {section.description}
                            </p>
                          )}
                        </div>
                      </div>
                      <div className="mt-3 space-y-3 pl-4">
                        {section.questions.map((question, qIndex) => (
                          <div
                            key={question.id}
                            className="flex items-start gap-3 p-3 bg-secondary/50 rounded-lg"
                          >
                            <span className="text-sm text-muted-foreground">
                              {sectionIndex + 1}.{qIndex + 1}
                            </span>
                            <div className="flex-1">
                              <p className="text-sm text-foreground">
                                {question.text || 'Untitled question'}
                                {question.required && (
                                  <span className="text-destructive ml-1">*</span>
                                )}
                              </p>
                              <div className="flex items-center gap-2 mt-2">
                                <span className="text-xs text-muted-foreground bg-input px-2 py-0.5 rounded">
                                  {QUESTION_TYPES.find((qt) => qt.type === question.type)?.label}
                                </span>
                                {question.evidenceRequired && (
                                  <span className="text-xs text-info bg-info/10 px-2 py-0.5 rounded flex items-center gap-1">
                                    <Camera className="w-3 h-3" /> Evidence
                                  </span>
                                )}
                                {question.riskLevel && (
                                  <span
                                    className={`text-xs px-2 py-0.5 rounded ${
                                      question.riskLevel === 'critical'
                                        ? 'text-destructive bg-destructive/10'
                                        : question.riskLevel === 'high' ||
                                            question.riskLevel === 'medium'
                                          ? 'text-warning bg-warning/10'
                                          : 'text-success bg-success/10'
                                    }`}
                                  >
                                    {question.riskLevel} risk
                                  </span>
                                )}
                              </div>
                              <div className="mt-3">{renderPreviewControl(question)}</div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </main>

      <PublishDialog
        isOpen={showPublishDialog}
        onClose={() => setShowPublishDialog(false)}
        onConfirm={handlePublish}
        isPublishing={isPublishing}
        templateName={template.name}
        error={saveError}
      />

      {showAIAssist && (
        <AITemplateGenerator
          onClose={() => setShowAIAssist(false)}
          onApply={(gs) => {
            updateSections((ss) => [...ss, ...mapAISectionsToLocal(gs, ss.length)])
            setShowAIAssist(false)
          }}
        />
      )}
    </div>
  )
}
