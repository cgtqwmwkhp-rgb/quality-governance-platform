import { useState, useEffect, useCallback } from 'react'
import {
  ArrowLeft,
  ChevronLeft,
  ChevronRight,
  Check,
  X,
  Minus,
  ChevronDown,
} from 'lucide-react'
import { useParams, useNavigate } from 'react-router-dom'
import { workforceApi, auditsApi, type InductionRun, type AuditQuestion } from '../../api/client'
import { Button } from '../../components/ui/Button'
import { Card, CardContent, CardHeader } from '../../components/ui/Card'
import { cn } from '../../helpers/utils'
import { useTranslation } from 'react-i18next'

type Verdict = 'competent' | 'not_yet_competent' | 'na'

interface QuestionWithSection {
  id: number
  question_text: string
  help_text?: string
  criticality?: string
  section_title?: string
}

interface ResponseState {
  shownExplained: boolean
  verdict: Verdict | null
  supervisorNotes: string
}

export default function TrainingExecution() {
  const { t } = useTranslation()
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [induction, setInduction] = useState<InductionRun | null>(null)
  const [templateName, setTemplateName] = useState<string>('')
  const [engineerName, setEngineerName] = useState<string>('')
  const [questions, setQuestions] = useState<QuestionWithSection[]>([])
  const [currentIndex, setCurrentIndex] = useState(0)
  const [responses, setResponses] = useState<Map<number, ResponseState>>(new Map())
  const [showSummary, setShowSummary] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [guidanceOpen, setGuidanceOpen] = useState(false)

  const flattenQuestions = useCallback(
    (sections: { title: string; questions: AuditQuestion[] }[]): QuestionWithSection[] => {
      const flat: QuestionWithSection[] = []
      for (const sec of sections) {
        for (const q of sec.questions || []) {
          flat.push({
            id: q.id,
            question_text: q.question_text,
            help_text: q.help_text ?? undefined,
            criticality: q.criticality ?? undefined,
            section_title: sec.title,
          })
        }
      }
      return flat.sort((a, b) => a.id - b.id)
    },
    []
  )

  useEffect(() => {
    const load = async () => {
      if (!id) return
      setLoading(true)
      setError(null)
      try {
        const runRes = await workforceApi.getInduction(id)
        const run = runRes.data
        setInduction(run)

        if (run.status === 'draft') {
          await workforceApi.startInduction(id)
        }

        let template: { sections: { title: string; questions: AuditQuestion[] }[]; name: string } | null = null
        try {
          const templateRes = await auditsApi.getTemplate(run.template_id)
          template = templateRes.data
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
          setTemplateName(run.title || t('workforce.induction.title'))
        }

        try {
          const eng = await workforceApi.getEngineer(run.engineer_id)
          const name = eng.data.employee_number || `Engineer #${run.engineer_id}`
          setEngineerName(name)
        } catch {
          setEngineerName(`Engineer #${run.engineer_id}`)
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to load induction')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [id, flattenQuestions, t])

  const question = questions[currentIndex]
  const totalQuestions = questions.length
  const answeredCount = Array.from(responses.values()).filter((r) => r.verdict !== null).length
  const progress = totalQuestions > 0 ? (answeredCount / totalQuestions) * 100 : 0

  const getResponse = (qId: number): ResponseState => {
    return (
      responses.get(qId) ?? {
        shownExplained: false,
        verdict: null,
        supervisorNotes: '',
      }
    )
  }

  const setResponse = (qId: number, patch: Partial<ResponseState>) => {
    setResponses((prev) => {
      const next = new Map(prev)
      const cur = next.get(qId) ?? {
        shownExplained: false,
        verdict: null,
        supervisorNotes: '',
      }
      next.set(qId, { ...cur, ...patch })
      return next
    })
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
      const failedItems: number[] = []
      for (const [qId, resp] of responses) {
        if (resp.verdict) {
          try {
            await workforceApi.createInductionResponse(id, {
              question_id: qId,
              shown_explained: resp.shownExplained,
              understanding: resp.verdict,
              supervisor_notes: resp.supervisorNotes || undefined,
            })
          } catch {
            failedItems.push(qId)
          }
        }
      }
      if (failedItems.length > 0) {
        setError(`Failed to save ${failedItems.length} response(s). Please retry.`)
        setSubmitting(false)
        return
      }
      await workforceApi.completeInduction(id)
      navigate('/workforce/training')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to submit')
    } finally {
      setSubmitting(false)
    }
  }

  const competentCount = Array.from(responses.values()).filter((r) => r.verdict === 'competent').length
  const notYetCompetentCount = Array.from(responses.values()).filter((r) => r.verdict === 'not_yet_competent').length
  const naCount = Array.from(responses.values()).filter((r) => r.verdict === 'na').length

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[50vh] bg-background">
        <div className="animate-spin rounded-full h-12 w-12 border-4 border-primary/20 border-t-primary" />
      </div>
    )
  }

  if (error && !induction) {
    return (
      <div className="space-y-6">
        <Button variant="ghost" size="icon" onClick={() => navigate('/workforce/training')}>
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
            <h1 className="text-2xl font-bold text-foreground">{t('workforce.induction.summary')}</h1>
            <p className="text-muted-foreground text-sm">
              {induction?.reference_number} · {engineerName} · {templateName}
            </p>
          </div>
        </div>

        <Card className="bg-card border-border">
          <CardHeader>
            <h2 className="text-lg font-semibold text-foreground">{t('workforce.common.overall_statistics')}</h2>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-3 gap-4">
              <div className="rounded-lg bg-success/10 border border-border p-4 text-center">
                <span className="text-2xl font-bold text-foreground">{competentCount}</span>
                <p className="text-sm text-muted-foreground">{t('workforce.competency.competent')}</p>
              </div>
              <div className="rounded-lg bg-destructive/10 border border-border p-4 text-center">
                <span className="text-2xl font-bold text-foreground">{notYetCompetentCount}</span>
                <p className="text-sm text-muted-foreground">{t('workforce.competency.not_yet_competent')}</p>
              </div>
              <div className="rounded-lg bg-muted border border-border p-4 text-center">
                <span className="text-2xl font-bold text-foreground">{naCount}</span>
                <p className="text-sm text-muted-foreground">{t('workforce.common.na')}</p>
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
              {submitting ? 'Submitting...' : t('workforce.common.submit_induction')}
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
          <Button variant="ghost" size="icon" onClick={() => navigate('/workforce/training')}>
            <ArrowLeft className="w-4 h-4" />
          </Button>
          <div>
            <h1 className="text-2xl font-bold text-foreground">{induction?.reference_number ?? t('workforce.induction.title')}</h1>
            <p className="text-muted-foreground text-sm">{t('workforce.common.no_questions')}</p>
          </div>
        </div>
        <Card>
          <CardContent className="pt-6">
            <p className="text-muted-foreground">{t('workforce.common.no_questions_description')}</p>
          </CardContent>
        </Card>
      </div>
    )
  }

  const resp = getResponse(question.id)

  return (
    <div className="space-y-6 pb-8">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => navigate('/workforce/training')} aria-label="Back">
          <ArrowLeft className="w-4 h-4" />
        </Button>
        <div>
          <h1 className="text-2xl font-bold text-foreground">{induction?.reference_number ?? t('workforce.induction.title')}</h1>
          <p className="text-muted-foreground text-sm">
            {engineerName} · {templateName} · {induction?.scheduled_date ? new Date(induction.scheduled_date).toLocaleDateString() : '—'}
          </p>
        </div>
      </div>

      <Card className="bg-card border-border">
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-foreground">{t('workforce.common.progress')}</span>
            <span className="text-sm text-muted-foreground">
              {answeredCount} / {totalQuestions} {t('workforce.common.items')}
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
                aria-label={`${t('workforce.common.item')} ${i + 1}`}
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
            <span className="text-xs text-muted-foreground uppercase tracking-wider">{question.section_title ?? t('workforce.common.item')}</span>
            {question.criticality && (
              <span
                className={cn(
                  'px-2 py-0.5 rounded text-xs font-medium',
                  question.criticality === 'essential'
                    ? 'bg-destructive/20 text-destructive'
                    : 'bg-info/20 text-info'
                )}
              >
                {question.criticality === 'essential' ? t('workforce.common.essential') : t('workforce.common.good_to_have')}
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
                {t('workforce.common.guidance')}
                <ChevronDown className={cn('w-4 h-4 transition-transform', guidanceOpen && 'rotate-180')} />
              </button>
              {guidanceOpen && (
                <p className="mt-2 text-sm text-foreground pl-4 border-l-2 border-border">{question.help_text}</p>
              )}
            </div>
          )}
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={resp.shownExplained}
                onChange={(e) => setResponse(question.id, { shownExplained: e.target.checked })}
                className="rounded border-border h-5 w-5"
              />
              <span className="text-sm font-medium text-foreground">{t('workforce.induction.shown_explained')}</span>
            </label>
          </div>

          <div>
            <span className="block text-sm font-medium text-foreground mb-3">
              {t('workforce.induction.verdict')}
            </span>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <Button
                variant={resp.verdict === 'competent' ? 'success' : 'outline'}
                size="lg"
                className="min-h-[48px] gap-2 border border-border"
                onClick={() => setResponse(question.id, { verdict: 'competent' })}
              >
                <Check className="w-5 h-5" />
                {t('workforce.competency.competent')}
              </Button>
              <Button
                variant={resp.verdict === 'not_yet_competent' ? 'destructive' : 'outline'}
                size="lg"
                className="min-h-[48px] gap-2 border border-border"
                onClick={() => setResponse(question.id, { verdict: 'not_yet_competent' })}
              >
                <X className="w-5 h-5" />
                {t('workforce.competency.not_yet_competent')}
              </Button>
              <Button
                variant={resp.verdict === 'na' ? 'secondary' : 'outline'}
                size="lg"
                className="min-h-[48px] gap-2 border border-border bg-muted/50"
                onClick={() => setResponse(question.id, { verdict: 'na' })}
              >
                <Minus className="w-5 h-5" />
                {t('workforce.common.na')}
              </Button>
            </div>
          </div>

          <div>
            <label htmlFor="trainingexecution-field-0" className="block text-sm font-medium text-foreground mb-2">
              {t('workforce.common.supervisor_notes')}
              {resp.verdict === 'not_yet_competent' && <span className="text-destructive ml-1">{t('workforce.common.recommended')}</span>}
            </label>
            <textarea id="trainingexecution-field-0"
              value={resp.supervisorNotes}
              onChange={(e) => setResponse(question.id, { supervisorNotes: e.target.value })}
              placeholder={t('workforce.common.supervisor_notes_placeholder')}
              className="w-full min-h-[80px] rounded-lg border border-border bg-card px-4 py-3 text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary"
            />
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
          {t('common.previous')}
        </Button>
        <Button onClick={handleNext} className="gap-2 min-h-[44px]">
          {currentIndex < totalQuestions - 1 ? (
            <>
              {t('common.next')}
              <ChevronRight className="w-4 h-4" />
            </>
          ) : (
            t('workforce.common.review_submit')
          )}
        </Button>
      </div>
    </div>
  )
}
