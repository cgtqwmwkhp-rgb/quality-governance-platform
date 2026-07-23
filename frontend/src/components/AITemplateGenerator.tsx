import { useCallback, useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { trackError } from '../utils/errorTracker'
import {
  Sparkles,
  Wand2,
  Loader2,
  CheckCircle2,
  Plus,
  AlertTriangle,
  X,
  Upload,
  Search,
  ChevronRight,
  ChevronLeft,
  Link2,
  FileText,
} from 'lucide-react'

// ============================================================================
// TYPES
// ============================================================================

interface GeneratedQuestion {
  id: string
  text: string
  type: string
  required: boolean
  weight: number
  riskLevel?: string
  evidenceRequired: boolean
  isoClause?: string
  guidance?: string
}

interface GeneratedSection {
  id: string
  title: string
  description: string
  questions: GeneratedQuestion[]
}

export interface AuditBuilderCasePrefill {
  type: string
  id: number
  label?: string
}

interface AITemplateGeneratorProps {
  onApply: (
    sections: GeneratedSection[],
    meta?: {
      briefId?: string
      sourceCaseRefs?: Array<{ type: string; id: number }>
      standardSuggestions?: unknown[]
    },
  ) => void
  onClose: () => void
  initialCaseRefs?: AuditBuilderCasePrefill[]
  onUseExistingTemplate?: (templateId: number) => void
}

type WizardStep = 'intent' | 'brief' | 'qa' | 'similar' | 'preview'

const PURPOSES = [
  { id: 'risk_audit', labelKey: 'auditBuilder.purpose.risk_audit' },
  { id: 'technical_assessment', labelKey: 'auditBuilder.purpose.technical_assessment' },
  { id: 'vehicle_asset_check', labelKey: 'auditBuilder.purpose.vehicle_asset_check' },
  { id: 'iso_scheme', labelKey: 'auditBuilder.purpose.iso_scheme' },
  { id: 'case_follow_up', labelKey: 'auditBuilder.purpose.case_follow_up' },
  { id: 'freeform', labelKey: 'auditBuilder.purpose.freeform' },
] as const

const SCOPES = [
  { id: 'incidents', labelKey: 'auditBuilder.scope.incidents' },
  { id: 'near_misses', labelKey: 'auditBuilder.scope.near_misses' },
  { id: 'rtas', labelKey: 'auditBuilder.scope.rtas' },
  { id: 'complaints', labelKey: 'auditBuilder.scope.complaints' },
  { id: 'engineers', labelKey: 'auditBuilder.scope.engineers' },
  { id: 'documents', labelKey: 'auditBuilder.scope.documents' },
] as const

const STANDARDS = [
  'ISO 9001',
  'ISO 27001',
  'ISO 45001',
  'ISO 14001',
  'UVDB-Achilles',
  'Planet Mark',
  'HSE',
] as const

interface BuilderBrief {
  brief_id: string
  purpose: string
  scopes: string[]
  case_refs: Array<{ type: string; id: number }>
  asset_hint: string
  standards: string[]
  themes: string[]
  upload_summaries: string[]
  research_findings: Array<{ title: string; summary: string; source_url?: string }>
  research_available: boolean
  proposed_sections: Array<{ title: string; rationale?: string }>
  open_questions: Array<{ id: string; prompt: string }>
  freeform_notes: string
  qa_answers: Record<string, string>
}

interface SimilarMatch {
  id: number
  name: string
  description?: string
  category?: string
  score: number
  question_sample?: string[]
}

// ============================================================================
// API HELPERS
// ============================================================================

async function postJson<T>(url: string, body: unknown): Promise<T> {
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!response.ok) {
    throw new Error(`${url} failed: ${response.status}`)
  }
  return response.json() as Promise<T>
}

async function summariseUpload(file: File, assetHint: string): Promise<string> {
  try {
    const form = new FormData()
    form.append('file', file)
    if (assetHint) form.append('asset_type', assetHint)
    const response = await fetch('/api/v1/ai-templates/from-document', {
      method: 'POST',
      body: form,
    })
    if (!response.ok) {
      return `Uploaded ${file.name} (summary unavailable)`
    }
    const data = (await response.json()) as {
      name?: string
      sections?: Array<{ title?: string }>
      summary?: string
    }
    const sectionTitles = (data.sections || [])
      .map((s) => s.title)
      .filter(Boolean)
      .slice(0, 4)
      .join(', ')
    return `${file.name}: ${data.summary || data.name || 'document'} — sections: ${sectionTitles || 'n/a'}`
  } catch {
    return `Uploaded ${file.name} (summary unavailable)`
  }
}

async function searchCases(query: string): Promise<Array<{ type: string; id: number; title: string }>> {
  if (query.trim().length < 2) return []
  try {
    const params = new URLSearchParams({ q: query, page_size: '8' })
    const response = await fetch(`/api/v1/search?${params.toString()}`)
    if (!response.ok) return []
    const data = (await response.json()) as {
      results?: Array<{
        id: string
        type: string
        title: string
        module?: string
        entity_id?: number | null
      }>
    }
    const allowed = new Set(['incident', 'near_miss', 'rta', 'complaint'])
    return (data.results || [])
      .filter((r) => allowed.has((r.type || '').toLowerCase()))
      .map((r) => {
        const numeric =
          typeof r.entity_id === 'number' && r.entity_id > 0
            ? r.entity_id
            : Number(String(r.id).replace(/\D/g, ''))
        return {
          type: r.type.toLowerCase(),
          id: Number.isFinite(numeric) && numeric > 0 ? numeric : 0,
          title: r.title,
        }
      })
      .filter((r) => r.id > 0)
      .slice(0, 8)
  } catch {
    return []
  }
}

// ============================================================================
// MAIN COMPONENT
// ============================================================================

export default function AITemplateGenerator({
  onApply,
  onClose,
  initialCaseRefs,
  onUseExistingTemplate,
}: AITemplateGeneratorProps) {
  const { t } = useTranslation()
  const [step, setStep] = useState<WizardStep>('intent')
  const [purpose, setPurpose] = useState('risk_audit')
  const [scopes, setScopes] = useState<string[]>(['incidents', 'near_misses'])
  const [standards, setStandards] = useState<string[]>(['ISO 45001', 'HSE'])
  const [assetHint, setAssetHint] = useState('')
  const [freeformNotes, setFreeformNotes] = useState('')
  const [caseRefs, setCaseRefs] = useState<AuditBuilderCasePrefill[]>(initialCaseRefs || [])
  const [caseQuery, setCaseQuery] = useState('')
  const [caseHits, setCaseHits] = useState<Array<{ type: string; id: number; title: string }>>([])
  const [uploadSummaries, setUploadSummaries] = useState<string[]>([])
  const [includeResearch, setIncludeResearch] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [brief, setBrief] = useState<BuilderBrief | null>(null)
  const [qaAnswers, setQaAnswers] = useState<Record<string, string>>({})
  const [similar, setSimilar] = useState<SimilarMatch[]>([])
  const [gateAction, setGateAction] = useState<'build_new' | 'use_existing' | 'clone_reference'>(
    'build_new',
  )
  const [selectedSimilarId, setSelectedSimilarId] = useState<number | null>(null)
  const [gateReason, setGateReason] = useState('')
  const [generatedSections, setGeneratedSections] = useState<GeneratedSection[] | null>(null)
  const [selectedSections, setSelectedSections] = useState<Set<string>>(new Set())
  const [standardSuggestions, setStandardSuggestions] = useState<unknown[]>([])

  useEffect(() => {
    if (initialCaseRefs?.length) {
      setCaseRefs(initialCaseRefs)
      setPurpose('case_follow_up')
      setScopes((prev) => (prev.includes('near_misses') ? prev : [...prev, 'near_misses']))
    }
  }, [initialCaseRefs])

  useEffect(() => {
    let cancelled = false
    const handle = window.setTimeout(() => {
      void searchCases(caseQuery).then((hits) => {
        if (!cancelled) setCaseHits(hits)
      })
    }, 250)
    return () => {
      cancelled = true
      window.clearTimeout(handle)
    }
  }, [caseQuery])

  const stepIndex = useMemo(() => {
    const order: WizardStep[] = ['intent', 'brief', 'qa', 'similar', 'preview']
    return order.indexOf(step)
  }, [step])

  const toggleScope = (id: string) => {
    setScopes((prev) => (prev.includes(id) ? prev.filter((s) => s !== id) : [...prev, id]))
  }

  const toggleStandard = (id: string) => {
    setStandards((prev) => (prev.includes(id) ? prev.filter((s) => s !== id) : [...prev, id]))
  }

  const onFiles = async (files: FileList | null) => {
    if (!files?.length) return
    setBusy(true)
    setError(null)
    try {
      const summaries: string[] = []
      for (const file of Array.from(files).slice(0, 5)) {
        summaries.push(await summariseUpload(file, assetHint))
      }
      setUploadSummaries((prev) => [...prev, ...summaries].slice(0, 10))
    } catch (err) {
      setError(t('auditBuilder.errors.upload'))
      trackError(err, { component: 'AITemplateGenerator', action: 'onFiles' })
    } finally {
      setBusy(false)
    }
  }

  const gatherBrief = async () => {
    setBusy(true)
    setError(null)
    try {
      const data = await postJson<BuilderBrief>('/api/v1/ai-templates/gather-brief', {
        purpose,
        scopes,
        case_refs: caseRefs.map((c) => ({ type: c.type, id: c.id })),
        asset_hint: assetHint,
        standards,
        freeform_notes: freeformNotes,
        upload_summaries: uploadSummaries,
        include_research: includeResearch,
        include_workforce: purpose === 'technical_assessment' || scopes.includes('engineers'),
      })
      setBrief(data)
      setQaAnswers({})
      setStep('brief')
    } catch (err) {
      setError(t('auditBuilder.errors.brief'))
      trackError(err, { component: 'AITemplateGenerator', action: 'gatherBrief' })
    } finally {
      setBusy(false)
    }
  }

  const applyQa = async () => {
    if (!brief) return
    setBusy(true)
    setError(null)
    try {
      const data = await postJson<BuilderBrief>('/api/v1/ai-templates/apply-qa', {
        brief,
        answers: qaAnswers,
      })
      setBrief(data)
      const sim = await postJson<{ matches: SimilarMatch[] }>('/api/v1/ai-templates/similar-templates', {
        brief: data,
        limit: 5,
      })
      setSimilar(sim.matches || [])
      setStep('similar')
    } catch (err) {
      setError(t('auditBuilder.errors.qa'))
      trackError(err, { component: 'AITemplateGenerator', action: 'applyQa' })
    } finally {
      setBusy(false)
    }
  }

  const generate = async () => {
    if (!brief) return
    if (gateAction === 'use_existing' && selectedSimilarId && onUseExistingTemplate) {
      onUseExistingTemplate(selectedSimilarId)
      onClose()
      return
    }
    setBusy(true)
    setError(null)
    try {
      const data = await postJson<{
        action: string
        sections: GeneratedSection[]
        standard_suggestions?: unknown[]
        template_id?: number
        builder_meta?: { brief_id?: string; source_case_refs?: Array<{ type: string; id: number }> }
      }>('/api/v1/ai-templates/generate-from-brief', {
        brief,
        similar_gate_action: gateAction,
        similar_template_id: selectedSimilarId,
        similar_gate_reason: gateReason,
      })
      if (data.action === 'use_existing' && data.template_id && onUseExistingTemplate) {
        onUseExistingTemplate(data.template_id)
        onClose()
        return
      }
      const sections = data.sections || []
      setGeneratedSections(sections)
      setSelectedSections(new Set(sections.map((s) => s.id)))
      setStandardSuggestions(data.standard_suggestions || [])
      setStep('preview')
    } catch (err) {
      setError(t('auditBuilder.errors.generate'))
      trackError(err, { component: 'AITemplateGenerator', action: 'generate' })
    } finally {
      setBusy(false)
    }
  }

  const handleApply = useCallback(() => {
    if (!generatedSections) return
    const sectionsToApply = generatedSections.filter((s) => selectedSections.has(s.id))
    onApply(sectionsToApply, {
      briefId: brief?.brief_id,
      sourceCaseRefs: brief?.case_refs,
      standardSuggestions,
    })
  }, [brief, generatedSections, onApply, selectedSections, standardSuggestions])

  const totalQuestions =
    generatedSections
      ?.filter((s) => selectedSections.has(s.id))
      .reduce((sum, s) => sum + s.questions.length, 0) || 0

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div
        className="absolute inset-0 bg-black/70 backdrop-blur-sm"
        role="button"
        tabIndex={0}
        onClick={onClose}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') onClose()
        }}
      />

      <div className="relative w-full max-w-3xl max-h-[92vh] bg-card border border-border rounded-2xl shadow-2xl flex flex-col overflow-hidden">
        <div className="flex items-center justify-between p-5 border-b border-border">
          <div className="flex items-center gap-3">
            <div className="w-11 h-11 bg-primary rounded-xl flex items-center justify-center">
              <Wand2 className="w-5 h-5 text-primary-foreground" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-foreground">{t('auditBuilder.title')}</h2>
              <p className="text-sm text-muted-foreground">{t('auditBuilder.subtitle')}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-secondary text-muted-foreground hover:text-foreground transition-colors"
            aria-label={t('common.close', { defaultValue: 'Close' })}
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="px-5 pt-3 flex gap-2 text-xs text-muted-foreground">
          {['intent', 'brief', 'qa', 'similar', 'preview'].map((s, i) => (
            <span
              key={s}
              className={`px-2 py-1 rounded-md ${i === stepIndex ? 'bg-primary/15 text-primary' : 'bg-secondary'}`}
            >
              {t(`auditBuilder.steps.${s}`)}
            </span>
          ))}
        </div>

        <div className="flex-1 overflow-y-auto p-5 space-y-5">
          {error && (
            <div className="flex items-center gap-2 text-destructive text-sm">
              <AlertTriangle className="w-4 h-4" />
              {error}
            </div>
          )}

          {step === 'intent' && (
            <>
              <div>
                <h3 className="text-sm font-medium text-foreground mb-2">{t('auditBuilder.intentPurpose')}</h3>
                <div className="grid grid-cols-2 gap-2">
                  {PURPOSES.map((p) => (
                    <button
                      key={p.id}
                      type="button"
                      onClick={() => setPurpose(p.id)}
                      className={`p-3 rounded-xl border text-left text-sm ${
                        purpose === p.id
                          ? 'border-primary bg-primary/10'
                          : 'border-border bg-secondary hover:border-primary/40'
                      }`}
                    >
                      {t(p.labelKey)}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <h3 className="text-sm font-medium text-foreground mb-2">{t('auditBuilder.intentScopes')}</h3>
                <div className="flex flex-wrap gap-2">
                  {SCOPES.map((s) => (
                    <button
                      key={s.id}
                      type="button"
                      onClick={() => toggleScope(s.id)}
                      className={`px-3 py-1.5 rounded-lg text-xs border ${
                        scopes.includes(s.id)
                          ? 'border-primary bg-primary/10 text-foreground'
                          : 'border-border bg-secondary text-muted-foreground'
                      }`}
                    >
                      {t(s.labelKey)}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <h3 className="text-sm font-medium text-foreground mb-2">{t('auditBuilder.intentStandards')}</h3>
                <div className="flex flex-wrap gap-2">
                  {STANDARDS.map((s) => (
                    <button
                      key={s}
                      type="button"
                      onClick={() => toggleStandard(s)}
                      className={`px-3 py-1.5 rounded-lg text-xs border ${
                        standards.includes(s)
                          ? 'border-primary bg-primary/10'
                          : 'border-border bg-secondary text-muted-foreground'
                      }`}
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                <label className="block text-sm">
                  <span className="text-muted-foreground">{t('auditBuilder.assetHint')}</span>
                  <input
                    value={assetHint}
                    onChange={(e) => setAssetHint(e.target.value)}
                    className="mt-1 w-full px-3 py-2 rounded-xl bg-secondary border border-border"
                    placeholder="e.g. Williams Trailer / SEB winch"
                  />
                </label>
                <label className="flex items-center gap-2 text-sm mt-6">
                  <input
                    type="checkbox"
                    checked={includeResearch}
                    onChange={(e) => setIncludeResearch(e.target.checked)}
                  />
                  {t('auditBuilder.includeResearch')}
                </label>
              </div>

              <label className="block text-sm">
                <span className="text-muted-foreground">{t('auditBuilder.notes')}</span>
                <textarea
                  value={freeformNotes}
                  onChange={(e) => setFreeformNotes(e.target.value)}
                  rows={3}
                  className="mt-1 w-full px-3 py-2 rounded-xl bg-secondary border border-border resize-none"
                />
              </label>

              <div>
                <h3 className="text-sm font-medium text-foreground mb-2 flex items-center gap-2">
                  <Link2 className="w-4 h-4" />
                  {t('auditBuilder.linkCases')}
                </h3>
                {caseRefs.length > 0 && (
                  <div className="flex flex-wrap gap-2 mb-2">
                    {caseRefs.map((c) => (
                      <span
                        key={`${c.type}-${c.id}`}
                        className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-secondary text-xs"
                      >
                        {c.label || `${c.type} #${c.id}`}
                        <button
                          type="button"
                          onClick={() =>
                            setCaseRefs((prev) => prev.filter((x) => !(x.type === c.type && x.id === c.id)))
                          }
                          className="text-muted-foreground hover:text-foreground"
                        >
                          ×
                        </button>
                      </span>
                    ))}
                  </div>
                )}
                <div className="relative">
                  <Search className="w-4 h-4 absolute left-3 top-2.5 text-muted-foreground" />
                  <input
                    value={caseQuery}
                    onChange={(e) => setCaseQuery(e.target.value)}
                    className="w-full pl-9 pr-3 py-2 rounded-xl bg-secondary border border-border text-sm"
                    placeholder={t('auditBuilder.searchCases')}
                  />
                </div>
                {caseHits.length > 0 && (
                  <ul className="mt-2 border border-border rounded-xl divide-y divide-border overflow-hidden">
                    {caseHits.map((hit) => (
                      <li key={`${hit.type}-${hit.id}`}>
                        <button
                          type="button"
                          className="w-full text-left px-3 py-2 text-sm hover:bg-secondary"
                          onClick={() => {
                            setCaseRefs((prev) =>
                              prev.some((p) => p.type === hit.type && p.id === hit.id)
                                ? prev
                                : [...prev, { type: hit.type, id: hit.id, label: hit.title }],
                            )
                            setCaseQuery('')
                            setCaseHits([])
                          }}
                        >
                          <span className="text-muted-foreground mr-2">{hit.type}</span>
                          {hit.title}
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              <div>
                <h3 className="text-sm font-medium text-foreground mb-2 flex items-center gap-2">
                  <Upload className="w-4 h-4" />
                  {t('auditBuilder.uploads')}
                </h3>
                <label className="flex flex-col items-center justify-center gap-2 p-6 border border-dashed border-border rounded-xl cursor-pointer hover:border-primary/50 bg-secondary/40">
                  <FileText className="w-6 h-6 text-muted-foreground" />
                  <span className="text-sm text-muted-foreground">{t('auditBuilder.dropFiles')}</span>
                  <input
                    type="file"
                    className="hidden"
                    multiple
                    accept=".pdf,image/*"
                    onChange={(e) => void onFiles(e.target.files)}
                  />
                </label>
                {uploadSummaries.length > 0 && (
                  <ul className="mt-2 space-y-1 text-xs text-muted-foreground">
                    {uploadSummaries.map((u) => (
                      <li key={u.slice(0, 40)}>{u}</li>
                    ))}
                  </ul>
                )}
              </div>
            </>
          )}

          {step === 'brief' && brief && (
            <div className="space-y-4">
              <div>
                <h3 className="text-sm font-medium mb-2">{t('auditBuilder.briefThemes')}</h3>
                <ul className="space-y-1 text-sm text-muted-foreground">
                  {(brief.themes || []).slice(0, 12).map((theme) => (
                    <li key={theme}>• {theme}</li>
                  ))}
                  {!brief.themes?.length && <li>{t('auditBuilder.noThemes')}</li>}
                </ul>
              </div>
              <div>
                <h3 className="text-sm font-medium mb-2">{t('auditBuilder.briefSections')}</h3>
                <ul className="space-y-1 text-sm">
                  {(brief.proposed_sections || []).map((s) => (
                    <li key={s.title} className="flex gap-2">
                      <CheckCircle2 className="w-4 h-4 text-primary mt-0.5" />
                      <span>
                        {s.title}
                        {s.rationale ? (
                          <span className="text-muted-foreground"> — {s.rationale}</span>
                        ) : null}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <h3 className="text-sm font-medium mb-2">{t('auditBuilder.sources')}</h3>
                {brief.research_available ? (
                  <ul className="space-y-2 text-sm">
                    {(brief.research_findings || []).map((f) => (
                      <li key={f.title} className="p-2 rounded-lg bg-secondary border border-border">
                        <p className="font-medium">{f.title}</p>
                        <p className="text-muted-foreground text-xs mt-1">{f.summary}</p>
                        {f.source_url ? (
                          <a
                            href={f.source_url}
                            target="_blank"
                            rel="noreferrer"
                            className="text-primary text-xs break-all"
                          >
                            {f.source_url}
                          </a>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-sm text-muted-foreground">{t('auditBuilder.researchOffline')}</p>
                )}
              </div>
            </div>
          )}

          {step === 'qa' && brief && (
            <div className="space-y-4">
              <p className="text-sm text-muted-foreground">{t('auditBuilder.qaIntro')}</p>
              {(brief.open_questions || []).map((q) => (
                <label key={q.id} className="block text-sm">
                  <span className="text-foreground">{q.prompt}</span>
                  <textarea
                    value={qaAnswers[q.id] || ''}
                    onChange={(e) => setQaAnswers((prev) => ({ ...prev, [q.id]: e.target.value }))}
                    rows={2}
                    className="mt-1 w-full px-3 py-2 rounded-xl bg-secondary border border-border resize-none"
                  />
                </label>
              ))}
            </div>
          )}

          {step === 'similar' && (
            <div className="space-y-4">
              <p className="text-sm text-muted-foreground">{t('auditBuilder.similarIntro')}</p>
              {similar.length === 0 ? (
                <p className="text-sm">{t('auditBuilder.noSimilar')}</p>
              ) : (
                <ul className="space-y-2">
                  {similar.map((m) => (
                    <li
                      key={m.id}
                      className={`p-3 rounded-xl border ${
                        selectedSimilarId === m.id ? 'border-primary bg-primary/5' : 'border-border'
                      }`}
                    >
                      <button
                        type="button"
                        className="w-full text-left"
                        onClick={() => setSelectedSimilarId(m.id)}
                      >
                        <div className="flex justify-between gap-2">
                          <span className="font-medium text-sm">{m.name}</span>
                          <span className="text-xs text-muted-foreground">
                            {Math.round(m.score * 100)}%
                          </span>
                        </div>
                        {m.description ? (
                          <p className="text-xs text-muted-foreground mt-1">{m.description}</p>
                        ) : null}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
              <div className="flex flex-wrap gap-2">
                {(
                  [
                    ['build_new', 'auditBuilder.gate.buildNew'],
                    ['use_existing', 'auditBuilder.gate.useExisting'],
                    ['clone_reference', 'auditBuilder.gate.clone'],
                  ] as const
                ).map(([id, key]) => (
                  <button
                    key={id}
                    type="button"
                    disabled={id !== 'build_new' && !selectedSimilarId}
                    onClick={() => setGateAction(id)}
                    className={`px-3 py-1.5 rounded-lg text-xs border ${
                      gateAction === id ? 'border-primary bg-primary/10' : 'border-border bg-secondary'
                    } disabled:opacity-40`}
                  >
                    {t(key)}
                  </button>
                ))}
              </div>
              {gateAction === 'build_new' && similar.length > 0 && (
                <label className="block text-sm">
                  <span className="text-muted-foreground">{t('auditBuilder.gate.reason')}</span>
                  <input
                    value={gateReason}
                    onChange={(e) => setGateReason(e.target.value)}
                    className="mt-1 w-full px-3 py-2 rounded-xl bg-secondary border border-border"
                  />
                </label>
              )}
            </div>
          )}

          {step === 'preview' && generatedSections && (
            <div className="space-y-4">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-5 h-5 text-success" />
                <span className="font-medium">
                  {t('auditBuilder.generatedCount', { count: generatedSections.length })}
                </span>
              </div>
              {standardSuggestions.length > 0 && (
                <p className="text-xs text-muted-foreground">
                  {t('auditBuilder.standardsSuggested', { count: standardSuggestions.length })}
                </p>
              )}
              <div className="space-y-3">
                {generatedSections.map((section) => (
                  <div
                    key={section.id}
                    className={`border rounded-xl overflow-hidden ${
                      selectedSections.has(section.id)
                        ? 'border-primary/50 bg-primary/5'
                        : 'border-border bg-secondary/50'
                    }`}
                  >
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedSections((prev) => {
                          const next = new Set(prev)
                          if (next.has(section.id)) next.delete(section.id)
                          else next.add(section.id)
                          return next
                        })
                      }}
                      className="w-full flex items-center gap-3 p-4 text-left"
                    >
                      <div
                        className={`w-5 h-5 rounded border-2 flex items-center justify-center ${
                          selectedSections.has(section.id)
                            ? 'bg-primary border-primary'
                            : 'border-input'
                        }`}
                      >
                        {selectedSections.has(section.id) && (
                          <CheckCircle2 className="w-3 h-3 text-primary-foreground" />
                        )}
                      </div>
                      <div className="flex-1">
                        <p className="font-medium text-foreground">{section.title}</p>
                        <p className="text-sm text-muted-foreground">
                          {section.questions.length} {t('auditBuilder.questions')}
                        </p>
                      </div>
                    </button>
                    {selectedSections.has(section.id) && (
                      <div className="px-4 pb-4 space-y-2 border-t border-border/50 pt-3">
                        {section.questions.slice(0, 3).map((q) => (
                          <div key={q.id} className="flex items-start gap-2 text-sm">
                            <div className="w-1.5 h-1.5 rounded-full bg-primary mt-1.5" />
                            <span>{q.text}</span>
                          </div>
                        ))}
                        {section.questions.length > 3 && (
                          <p className="text-xs text-muted-foreground pl-3.5">
                            +{section.questions.length - 3} {t('auditBuilder.moreQuestions')}
                          </p>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="border-t border-border p-4 flex items-center justify-between bg-card gap-3">
          <button
            type="button"
            disabled={busy || step === 'intent'}
            onClick={() => {
              if (step === 'brief') setStep('intent')
              else if (step === 'qa') setStep('brief')
              else if (step === 'similar') setStep('qa')
              else if (step === 'preview') setStep('similar')
            }}
            className="px-3 py-2 rounded-lg bg-secondary text-foreground disabled:opacity-40 inline-flex items-center gap-1"
          >
            <ChevronLeft className="w-4 h-4" />
            {t('common.back', { defaultValue: 'Back' })}
          </button>

          <div className="flex gap-2">
            {step === 'intent' && (
              <button
                type="button"
                disabled={busy}
                onClick={() => void gatherBrief()}
                className="px-4 py-2 bg-primary text-primary-foreground rounded-lg inline-flex items-center gap-2 disabled:opacity-50"
              >
                {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                {t('auditBuilder.actions.gather')}
                <ChevronRight className="w-4 h-4" />
              </button>
            )}
            {step === 'brief' && (
              <button
                type="button"
                disabled={busy}
                onClick={() => setStep('qa')}
                className="px-4 py-2 bg-primary text-primary-foreground rounded-lg inline-flex items-center gap-2"
              >
                {t('auditBuilder.actions.continueQa')}
                <ChevronRight className="w-4 h-4" />
              </button>
            )}
            {step === 'qa' && (
              <button
                type="button"
                disabled={busy}
                onClick={() => void applyQa()}
                className="px-4 py-2 bg-primary text-primary-foreground rounded-lg inline-flex items-center gap-2 disabled:opacity-50"
              >
                {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                {t('auditBuilder.actions.checkSimilar')}
              </button>
            )}
            {step === 'similar' && (
              <button
                type="button"
                disabled={busy || (gateAction !== 'build_new' && !selectedSimilarId)}
                onClick={() => void generate()}
                className="px-4 py-2 bg-primary text-primary-foreground rounded-lg inline-flex items-center gap-2 disabled:opacity-50"
              >
                {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                {t('auditBuilder.actions.generate')}
              </button>
            )}
            {step === 'preview' && (
              <button
                type="button"
                disabled={selectedSections.size === 0}
                onClick={handleApply}
                className="px-4 py-2 bg-primary text-primary-foreground rounded-lg inline-flex items-center gap-2 disabled:opacity-50"
              >
                <Plus className="w-4 h-4" />
                {t('auditBuilder.actions.add', { sections: selectedSections.size, questions: totalQuestions })}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
