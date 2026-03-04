import { useState, useEffect, useRef, useCallback } from 'react'
import {
  ArrowLeft,
  ChevronLeft,
  ChevronRight,
  Camera,
  Check,
  X,
  Minus,
  ChevronDown,
} from 'lucide-react'
import { useParams, useNavigate } from 'react-router-dom'
import { workforceApi, auditsApi, type AssessmentRun, type AuditQuestion } from '../../api/client'
import { Button } from '../../components/ui/Button'
import { Card, CardContent, CardHeader } from '../../components/ui/Card'
import { cn } from '../../helpers/utils'

type Verdict = 'competent' | 'not_competent' | 'na'

interface QuestionWithSection {
  id: number
  question_text: string
  help_text?: string
  criticality?: string
  section_title?: string
}

interface ResponseState {
  verdict: Verdict | null
  feedback: string
  supervisorNotes: string
  photoPreview: string | null
  signatureBase64: string | null
}

export default function AssessmentExecution() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [assessment, setAssessment] = useState<AssessmentRun | null>(null)
  const [templateName, setTemplateName] = useState<string>('')
  const [engineerName, setEngineerName] = useState<string>('')
  const [questions, setQuestions] = useState<QuestionWithSection[]>([])
  const [currentIndex, setCurrentIndex] = useState(0)
  const [responses, setResponses] = useState<Map<number, ResponseState>>(new Map())
  const [showSummary, setShowSummary] = useState(false)
  const [debriefNotes, setDebriefNotes] = useState('')
  const [finalSignature, setFinalSignature] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [guidanceOpen, setGuidanceOpen] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const flattenQuestions = useCallback((sections: { title: string; questions: AuditQuestion[] }[]): QuestionWithSection[] => {
    const flat: QuestionWithSection[] = []
    for (const sec of sections) {
      for (const q of sec.questions || []) {
        flat.push({
          id: q.id,
          question_text: q.question_text,
          help_text: q.help_text ?? undefined,
          criticality: (q as AuditQuestion & { criticality?: string }).criticality ?? undefined,
          section_title: sec.title,
        })
      }
    }
    return flat.sort((a, b) => a.id - b.id)
  }, [])

  useEffect(() => {
    const load = async () => {
      if (!id) return
      setLoading(true)
      setError(null)
      try {
        const runRes = await workforceApi.getAssessment(id)
        const run = runRes.data
        setAssessment(run)

        if (run.status === 'draft') {
          await workforceApi.startAssessment(id)
        }

        let template: { sections: { title: string; questions: AuditQuestion[] }[]; name: string } | null = null
        try {
          const t = await auditsApi.getTemplate(run.template_id)
          template = t.data
        } catch {
          // template might not exist
        }

        if (template?.sections) {
          const flat = flattenQuestions(
            template.sections.map((s) => ({
              title: s.title,
              questions: s.questions || [],
            }))
          )
          setQuestions(flat)
          setTemplateName(template.name)
        } else {
          setQuestions([])
          setTemplateName(run.title || 'Assessment')
        }

        try {
          const eng = await workforceApi.getEngineer(run.engineer_id)
          const name = eng.data.employee_number || `Engineer #${run.engineer_id}`
          setEngineerName(name)
        } catch {
          setEngineerName(`Engineer #${run.engineer_id}`)
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to load assessment')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [id, flattenQuestions])

  const question = questions[currentIndex]
  const totalQuestions = questions.length
  const answeredCount = Array.from(responses.values()).filter((r) => r.verdict !== null).length
  const progress = totalQuestions > 0 ? (answeredCount / totalQuestions) * 100 : 0

  const getResponse = (qId: number): ResponseState => {
    return (
      responses.get(qId) ?? {
        verdict: null,
        feedback: '',
        supervisorNotes: '',
        photoPreview: null,
        signatureBase64: null,
      }
    )
  }

  const setResponse = (qId: number, patch: Partial<ResponseState>) => {
    setResponses((prev) => {
      const next = new Map(prev)
      const cur = next.get(qId) ?? {
        verdict: null,
        feedback: '',
        supervisorNotes: '',
        photoPreview: null,
        signatureBase64: null,
      }
      next.set(qId, { ...cur, ...patch })
      return next
    })
  }

  const handlePhotoUpload = (e: React.ChangeEvent<HTMLInputElement>, qId: number) => {
    const file = e.target.files?.[0]
    if (!file?.type.startsWith('image/')) return
    const reader = new FileReader()
    reader.onload = () => setResponse(qId, { photoPreview: reader.result as string })
    reader.readAsDataURL(file)
  }

  const handlePrev = () => {
    if (currentIndex > 0) setCurrentIndex((i) => i - 1)
  }

  const handleNext = () => {
    if (currentIndex < totalQuestions - 1) setCurrentIndex((i) => i + 1)
    else setShowSummary(true)
  }

  const handleSubmit = async () => {
    if (!id) return
    setSubmitting(true)
    try {
      const failedQuestions: number[] = []
      for (const [qId, resp] of responses) {
        if (resp.verdict) {
          try {
            await workforceApi.createAssessmentResponse(id, {
              question_id: qId,
              verdict: resp.verdict,
              feedback: resp.feedback || undefined,
              supervisor_notes: resp.supervisorNotes || undefined,
            })
          } catch {
            failedQuestions.push(qId)
          }
        }
      }
      if (failedQuestions.length > 0) {
        setError(`Failed to save ${failedQuestions.length} response(s). Please retry.`)
        setSubmitting(false)
        return
      }
      if (debriefNotes || finalSignature) {
        await workforceApi.updateAssessment(id, {
          debrief_notes: debriefNotes,
          overall_notes: 'Assessment completed via digital execution',
          debrief_signature: finalSignature || undefined,
        })
      }
      await workforceApi.completeAssessment(id)
      navigate('/workforce/assessments')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to submit')
    } finally {
      setSubmitting(false)
    }
  }

  const competentCount = Array.from(responses.values()).filter((r) => r.verdict === 'competent').length
  const notCompetentCount = Array.from(responses.values()).filter((r) => r.verdict === 'not_competent').length
  const naCount = Array.from(responses.values()).filter((r) => r.verdict === 'na').length

  let outcome: 'Pass' | 'Fail' | 'Conditional' = 'Pass'
  if (notCompetentCount > 0) {
    const anyEssential = questions.some((q) => responses.get(q.id)?.verdict === 'not_competent' && q.criticality === 'essential')
    outcome = anyEssential ? 'Fail' : 'Conditional'
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[50vh] bg-background">
        <div className="animate-spin rounded-full h-12 w-12 border-4 border-primary/20 border-t-primary" />
      </div>
    )
  }

  if (error && !assessment) {
    return (
      <div className="space-y-6">
        <Button variant="ghost" size="icon" onClick={() => navigate('/workforce/assessments')}>
          <ArrowLeft className="w-4 h-4" />
        </Button>
        <Card className="border-destructive">
          <CardContent className="pt-6">
            <p className="text-destructive">{error}</p>
          </CardContent>
        </Card>
      </div>
    )
  }

  if (showSummary) {
    return (
      <div className="space-y-6 pb-8">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => setShowSummary(false)} aria-label="Back">
            <ArrowLeft className="w-4 h-4" />
          </Button>
          <div>
            <h1 className="text-2xl font-bold text-foreground">Assessment Summary</h1>
            <p className="text-muted-foreground text-sm">
              {assessment?.reference_number} · {engineerName} · {templateName}
            </p>
          </div>
        </div>

        <Card className="bg-card border-border">
          <CardHeader>
            <h2 className="text-lg font-semibold text-foreground">Overall Statistics</h2>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-3 gap-4">
              <div className="rounded-lg bg-success/10 border border-border p-4 text-center">
                <span className="text-2xl font-bold text-foreground">{competentCount}</span>
                <p className="text-sm text-muted-foreground">Competent</p>
              </div>
              <div className="rounded-lg bg-destructive/10 border border-border p-4 text-center">
                <span className="text-2xl font-bold text-foreground">{notCompetentCount}</span>
                <p className="text-sm text-muted-foreground">Not Competent</p>
              </div>
              <div className="rounded-lg bg-muted border border-border p-4 text-center">
                <span className="text-2xl font-bold text-foreground">{naCount}</span>
                <p className="text-sm text-muted-foreground">N/A</p>
              </div>
            </div>
            <div className="rounded-lg border border-border p-4 bg-card">
              <p className="text-sm text-muted-foreground mb-1">Outcome</p>
              <p
                className={cn(
                  'text-xl font-semibold',
                  outcome === 'Pass' && 'text-success',
                  outcome === 'Fail' && 'text-destructive',
                  outcome === 'Conditional' && 'text-warning'
                )}
              >
                {outcome}
              </p>
            </div>
            <div>
              <label htmlFor="assessmentexecution-field-0" className="block text-sm font-medium text-foreground mb-2">Overall debrief notes</label>
              <textarea id="assessmentexecution-field-0"
                value={debriefNotes}
                onChange={(e) => setDebriefNotes(e.target.value)}
                placeholder="Add overall debrief notes..."
                className="w-full min-h-[100px] rounded-lg border border-border bg-card px-4 py-3 text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>
            <div>
              <label htmlFor="assessmentexecution-field-1" className="block text-sm font-medium text-foreground mb-2">Engineer signature (final)</label>
              <div className="rounded-lg border border-dashed border-border bg-muted/20 min-h-[80px] flex items-center justify-center p-4">
                <input id="assessmentexecution-field-1"
                  type="text"
                  value={finalSignature ?? ''}
                  onChange={(e) => setFinalSignature(e.target.value || null)}
                  placeholder="Signature / type name to confirm"
                  className="w-full max-w-md px-4 py-2 rounded-lg border border-border bg-card text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary"
                />
              </div>
            </div>
            {error && (
              <div className="rounded-lg border border-destructive p-3">
                <p className="text-destructive text-sm">{error}</p>
              </div>
            )}
            <Button
              onClick={handleSubmit}
              disabled={submitting}
              className="w-full min-h-[48px] text-base"
            >
              {submitting ? 'Submitting...' : 'Submit Assessment'}
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  if (totalQuestions === 0) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => navigate('/workforce/assessments')}>
            <ArrowLeft className="w-4 h-4" />
          </Button>
          <div>
            <h1 className="text-2xl font-bold text-foreground">{assessment?.reference_number ?? 'Assessment'}</h1>
            <p className="text-muted-foreground text-sm">No questions in template</p>
          </div>
        </div>
        <Card>
          <CardContent className="pt-6">
            <p className="text-muted-foreground">This assessment template has no questions. Please configure the template first.</p>
          </CardContent>
        </Card>
      </div>
    )
  }

  const resp = getResponse(question.id)

  return (
    <div className="space-y-6 pb-8">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => navigate('/workforce/assessments')} aria-label="Back">
          <ArrowLeft className="w-4 h-4" />
        </Button>
        <div>
          <h1 className="text-2xl font-bold text-foreground">{assessment?.reference_number ?? 'Assessment'}</h1>
          <p className="text-muted-foreground text-sm">
            {engineerName} · {templateName} · {assessment?.scheduled_date ? new Date(assessment.scheduled_date).toLocaleDateString() : '—'}
          </p>
        </div>
      </div>

      <Card className="bg-card border-border">
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-foreground">Progress</span>
            <span className="text-sm text-muted-foreground">
              {answeredCount} / {totalQuestions} questions
            </span>
          </div>
          <div className="h-2 rounded-full bg-muted overflow-hidden mt-2">
            <div
              className="h-full bg-primary transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>
          <div className="flex gap-1 mt-2 flex-wrap">
            {questions.map((q, i) => (
              <button
                key={q.id}
                type="button"
                onClick={() => setCurrentIndex(i)}
                className={cn(
                  'w-8 h-8 rounded-md text-sm font-medium transition-colors',
                  i === currentIndex
                    ? 'bg-primary text-primary-foreground'
                    : responses.get(q.id)?.verdict
                      ? 'bg-muted text-foreground hover:bg-muted/80'
                      : 'bg-muted/50 text-muted-foreground hover:bg-muted'
                )}
                aria-label={`Question ${i + 1}`}
              >
                {i + 1}
              </button>
            ))}
          </div>
        </CardHeader>
      </Card>

      <Card className="bg-card border-border">
        <CardHeader>
          <div className="flex items-center justify-between gap-2 flex-wrap">
            <span className="text-xs text-muted-foreground uppercase tracking-wider">{question.section_title ?? 'Question'}</span>
            {question.criticality && (
              <span
                className={cn(
                  'px-2 py-0.5 rounded text-xs font-medium',
                  question.criticality === 'essential'
                    ? 'bg-destructive/20 text-destructive'
                    : 'bg-info/20 text-info'
                )}
              >
                {question.criticality === 'essential' ? 'Essential' : 'Good-to-Have'}
              </span>
            )}
          </div>
          <h2 className="text-lg font-semibold text-foreground mt-2">{question.question_text}</h2>
          {question.help_text && (
            <div className="mt-3">
              <button
                type="button"
                onClick={() => setGuidanceOpen((o) => !o)}
                className="text-sm text-muted-foreground flex items-center gap-1 hover:text-foreground"
              >
                Assessor guidance
                <ChevronDown className={cn('w-4 h-4 transition-transform', guidanceOpen && 'rotate-180')} />
              </button>
              {guidanceOpen && (
                <p className="mt-2 text-sm text-foreground pl-4 border-l-2 border-border">{question.help_text}</p>
              )}
            </div>
          )}
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <Button
              variant={resp.verdict === 'competent' ? 'success' : 'outline'}
              size="lg"
              className="min-h-[48px] gap-2 border border-border"
              onClick={() => setResponse(question.id, { verdict: 'competent' })}
            >
              <Check className="w-5 h-5" />
              Competent
            </Button>
            <Button
              variant={resp.verdict === 'not_competent' ? 'destructive' : 'outline'}
              size="lg"
              className="min-h-[48px] gap-2 border border-border"
              onClick={() => setResponse(question.id, { verdict: 'not_competent' })}
            >
              <X className="w-5 h-5" />
              Not Competent
            </Button>
            <Button
              variant={resp.verdict === 'na' ? 'secondary' : 'outline'}
              size="lg"
              className="min-h-[48px] gap-2 border border-border bg-muted/50"
              onClick={() => setResponse(question.id, { verdict: 'na' })}
            >
              <Minus className="w-5 h-5" />
              N/A
            </Button>
          </div>

          <div>
            <label htmlFor="assessmentexecution-field-2" className="block text-sm font-medium text-foreground mb-2">
              Feedback / Supervisor notes
              {resp.verdict === 'not_competent' && <span className="text-destructive ml-1">(required)</span>}
            </label>
            <textarea id="assessmentexecution-field-2"
              value={resp.feedback || resp.supervisorNotes}
              onChange={(e) =>
                setResponse(question.id, {
                  feedback: e.target.value,
                  supervisorNotes: e.target.value,
                })
              }
              placeholder="Add feedback for this question..."
              className="w-full min-h-[80px] rounded-lg border border-border bg-card px-4 py-3 text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary"
            />
          </div>

          <div>
            <span className="block text-sm font-medium text-foreground mb-2">Photo evidence</span>
            <div className="flex gap-4 flex-wrap">
              <div
                role="button"
                tabIndex={0}
                onClick={() => fileInputRef.current?.click()}
                onKeyDown={(e) => e.key === 'Enter' && fileInputRef.current?.click()}
                className="border-2 border-dashed border-border rounded-lg p-6 flex flex-col items-center justify-center gap-2 bg-muted/20 min-w-[140px] cursor-pointer hover:border-primary/50 focus:outline-none focus:ring-2 focus:ring-primary"
              >
                <Camera className="w-8 h-8 text-muted-foreground" />
                <span className="text-sm text-muted-foreground">Upload</span>
              </div>
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={(e) => handlePhotoUpload(e, question.id)}
              />
              {resp.photoPreview && (
                <div className="relative">
                  <img
                    src={resp.photoPreview}
                    alt="Evidence"
                    className="w-24 h-24 object-cover rounded-lg border border-border"
                  />
                  <button
                    type="button"
                    onClick={() => setResponse(question.id, { photoPreview: null })}
                    className="absolute -top-2 -right-2 w-6 h-6 rounded-full bg-destructive text-destructive-foreground flex items-center justify-center text-xs"
                  >
                    ×
                  </button>
                </div>
              )}
            </div>
          </div>

          <div>
            <label htmlFor="assessmentexecution-field-3" className="block text-sm font-medium text-foreground mb-2">Engineer sign-off (this item)</label>
            <div className="rounded-lg border border-dashed border-border bg-muted/20 min-h-[60px] flex items-center justify-center p-3">
              <input id="assessmentexecution-field-3"
                type="text"
                value={resp.signatureBase64 ?? ''}
                onChange={(e) => setResponse(question.id, { signatureBase64: e.target.value || null })}
                placeholder="Signature or type name"
                className="w-full max-w-xs px-3 py-2 rounded border border-border bg-card text-foreground placeholder:text-muted-foreground text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="flex justify-between gap-4">
        <Button
          variant="outline"
          disabled={currentIndex === 0}
          onClick={handlePrev}
          className="gap-2 min-h-[44px]"
        >
          <ChevronLeft className="w-4 h-4" />
          Previous
        </Button>
        <Button onClick={handleNext} className="gap-2 min-h-[44px]">
          {currentIndex < totalQuestions - 1 ? (
            <>
              Next
              <ChevronRight className="w-4 h-4" />
            </>
          ) : (
            'Review & Submit'
          )}
        </Button>
      </div>
    </div>
  )
}
