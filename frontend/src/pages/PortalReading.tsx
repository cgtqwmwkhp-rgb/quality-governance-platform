import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  ArrowLeft,
  BookOpen,
  CheckCircle2,
  ChevronDown,
  ExternalLink,
  Loader2,
  MessageCircleQuestion,
} from 'lucide-react'
import { useTranslation } from 'react-i18next'
import {
  documentCampaignApi,
  getApiErrorMessage,
  knowledgeBankApi,
  type DocumentCampaignAssignment,
  type DocumentCampaignQuiz,
  type DocumentCampaignQuizResult,
} from '../api/client'
import { toast } from '../contexts/ToastContext'
import { useLiveAnnouncer } from '../components/ui/LiveAnnouncer'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { EmptyState } from '../components/ui/EmptyState'
import { Input } from '../components/ui/Input'
import { Textarea } from '../components/ui/Textarea'
import {
  buildQuizAnswers,
  canCompleteCampaign,
  hasUnansweredQuiz,
  isOpenQuestion,
  isQuizRequired,
  quizQuestionLabel,
} from './campaignReadingHelpers'

const reportFailure = (err: unknown): string => {
  const message = getApiErrorMessage(err)
  toast.error(message)
  return message
}

function formatDue(due?: string | null): string | null {
  if (!due) return null
  const d = new Date(due)
  if (Number.isNaN(d.getTime())) return null
  return d.toLocaleDateString()
}

export default function PortalReading() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { announce } = useLiveAnnouncer()
  const focusAssignmentId = searchParams.get('assignment')

  const [items, setItems] = useState<DocumentCampaignAssignment[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [openingCampaignId, setOpeningCampaignId] = useState<number | null>(null)
  const [expandedCampaignId, setExpandedCampaignId] = useState<number | null>(null)
  const [quizLoadingId, setQuizLoadingId] = useState<number | null>(null)
  const [quizzes, setQuizzes] = useState<Record<number, DocumentCampaignQuiz>>({})
  const [quizAnswers, setQuizAnswers] = useState<Record<number, Record<number, string>>>({})
  const [quizResults, setQuizResults] = useState<Record<number, DocumentCampaignQuizResult>>({})
  const [submittingQuizId, setSubmittingQuizId] = useState<number | null>(null)
  const [acceptanceStatements, setAcceptanceStatements] = useState<Record<number, string>>({})
  const [signatures, setSignatures] = useState<Record<number, string>>({})
  const [completingCampaignId, setCompletingCampaignId] = useState<number | null>(null)
  const [questionDrafts, setQuestionDrafts] = useState<Record<number, string>>({})
  const [askingQuestionId, setAskingQuestionId] = useState<number | null>(null)
  const [expandedQuestionId, setExpandedQuestionId] = useState<number | null>(null)

  const loadAssignments = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await documentCampaignApi.listMyAssignments()
      setItems(response.data.items ?? [])
    } catch (err) {
      setItems([])
      setError(reportFailure(err))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    announce('Document campaigns loaded')
    void loadAssignments()
  }, [announce, loadAssignments])

  useEffect(() => {
    if (!focusAssignmentId || loading) return
    const id = Number(focusAssignmentId)
    if (!Number.isFinite(id)) return
    setExpandedCampaignId(id)
    setAcceptanceStatements((prev) => ({
      ...prev,
      [id]: prev[id] ?? t('my_reading.acceptance_default'),
    }))
    const item = items.find((assignment) => assignment.id === id)
    if (!item || !isQuizRequired(item) || quizzes[id]) return

    setQuizLoadingId(id)
    void documentCampaignApi
      .getAssignmentQuiz(id)
      .then((response) => {
        setQuizzes((prev) => ({ ...prev, [id]: response.data }))
      })
      .catch((err) => {
        reportFailure(err)
      })
      .finally(() => {
        setQuizLoadingId(null)
      })
  }, [focusAssignmentId, items, loading, quizzes, t])

  const pendingItems = useMemo(
    () => items.filter((item) => item.status !== 'completed'),
    [items],
  )

  const handleOpenCampaign = async (item: DocumentCampaignAssignment) => {
    setOpeningCampaignId(item.id)
    try {
      await documentCampaignApi.openAssignment(item.id)
      setItems((prev) =>
        prev.map((assignment) =>
          assignment.id === item.id ? { ...assignment, status: 'opened' } : assignment,
        ),
      )
      window.open(`/documents/${item.document_id}`, '_blank', 'noopener,noreferrer')
    } catch (err) {
      reportFailure(err)
    } finally {
      setOpeningCampaignId(null)
    }
  }

  const handleToggleComplete = async (item: DocumentCampaignAssignment) => {
    if (expandedCampaignId === item.id) {
      setExpandedCampaignId(null)
      return
    }
    setExpandedCampaignId(item.id)
    setAcceptanceStatements((prev) => ({
      ...prev,
      [item.id]: prev[item.id] ?? t('my_reading.acceptance_default'),
    }))
    if (!isQuizRequired(item) || quizzes[item.id]) return

    setQuizLoadingId(item.id)
    try {
      const response = await documentCampaignApi.getAssignmentQuiz(item.id)
      setQuizzes((prev) => ({ ...prev, [item.id]: response.data }))
    } catch (err) {
      reportFailure(err)
    } finally {
      setQuizLoadingId(null)
    }
  }

  const handleSubmitQuiz = async (item: DocumentCampaignAssignment) => {
    const quiz = quizzes[item.id]
    if (!quiz) return
    const values = quizAnswers[item.id] ?? {}
    if (hasUnansweredQuiz(quiz, values)) {
      toast.error(t('my_reading.complete_all_quiz_questions'))
      return
    }

    setSubmittingQuizId(item.id)
    try {
      const response = await documentCampaignApi.submitQuiz(
        item.id,
        buildQuizAnswers(quiz, values),
      )
      setQuizResults((prev) => ({ ...prev, [item.id]: response.data }))
      toast.success(
        (response.data.passed ?? response.data.quiz_passed)
          ? t('my_reading.quiz_passed')
          : t('my_reading.quiz_submitted'),
      )
    } catch (err) {
      reportFailure(err)
    } finally {
      setSubmittingQuizId(null)
    }
  }

  const handleCompleteCampaign = async (item: DocumentCampaignAssignment) => {
    const quizResult = quizResults[item.id]
    if (!canCompleteCampaign(item, quizResult)) {
      toast.error(t('my_reading.pass_quiz_before_completing'))
      return
    }
    const acceptanceStatement = acceptanceStatements[item.id]?.trim()
    if (!acceptanceStatement) {
      toast.error(t('my_reading.acceptance_required'))
      return
    }
    setCompletingCampaignId(item.id)
    try {
      const response = await documentCampaignApi.completeAssignment(item.id, {
        acceptance_statement: acceptanceStatement,
        ...(signatures[item.id]?.trim() ? { signature_data: signatures[item.id].trim() } : {}),
      })
      setItems((prev) =>
        prev.map((assignment) =>
          assignment.id === item.id
            ? { ...assignment, ...response.data, status: response.data.status || 'completed' }
            : assignment,
        ),
      )
      setExpandedCampaignId(null)
      toast.success(t('my_reading.completed_successfully'))
    } catch (err) {
      reportFailure(err)
    } finally {
      setCompletingCampaignId(null)
    }
  }

  const handleAskQuestion = async (item: DocumentCampaignAssignment) => {
    const body = questionDrafts[item.id]?.trim()
    if (!body) {
      toast.error(t('portal_reading.question_required'))
      return
    }
    setAskingQuestionId(item.id)
    try {
      const threadResponse = await knowledgeBankApi.createThread(item.document_id, {
        title: body.slice(0, 80),
        version: item.document_version ?? undefined,
      })
      await knowledgeBankApi.postMessage(threadResponse.data.id, { body })
      setQuestionDrafts((prev) => ({ ...prev, [item.id]: '' }))
      setExpandedQuestionId(null)
      toast.success(t('portal_reading.question_sent'))
    } catch (err) {
      reportFailure(err)
    } finally {
      setAskingQuestionId(null)
    }
  }

  return (
    <div data-testid="portal-reading" className="min-h-screen bg-surface">
      <header className="bg-card/95 backdrop-blur-lg border-b border-border sticky top-0 z-40">
        <div className="max-w-lg mx-auto px-4 sm:px-6 py-4 flex items-center gap-4">
          <button
            type="button"
            aria-label="Back to My Work"
            onClick={() => navigate('/portal/work')}
            className="w-11 h-11 flex items-center justify-center rounded-xl bg-surface hover:bg-muted transition-colors"
          >
            <ArrowLeft className="w-5 h-5 text-foreground" />
          </button>
          <div className="flex items-center gap-2">
            <BookOpen className="w-5 h-5 text-primary" />
            <span className="font-semibold text-foreground">{t('portal_reading.title')}</span>
          </div>
        </div>
      </header>

      <main className="max-w-lg mx-auto px-4 sm:px-6 py-6 pb-12 space-y-6">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">{t('portal_reading.heading')}</h1>
          <p className="text-muted-foreground text-sm mt-1">{t('portal_reading.subtitle')}</p>
        </div>

        {loading ? (
          <div className="flex justify-center py-16">
            <Loader2 className="w-8 h-8 text-primary animate-spin" />
          </div>
        ) : error ? (
          <div
            data-testid="portal-reading-error"
            className="rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive"
          >
            {error}
            <div className="mt-3">
              <Button variant="outline" size="lg" className="w-full min-h-12" onClick={() => void loadAssignments()}>
                Retry
              </Button>
            </div>
          </div>
        ) : pendingItems.length === 0 ? (
          <EmptyState
            className="py-12"
            icon={<BookOpen className="w-8 h-8 text-muted-foreground" />}
            title={t('portal_reading.all_caught_up')}
            description={t('portal_reading.empty_description')}
          />
        ) : (
          <div className="space-y-4">
            {pendingItems.map((item) => {
              const dueLabel = formatDue(item.due_date ?? item.due_at)
              const isExpanded = expandedCampaignId === item.id
              const isQuestionExpanded = expandedQuestionId === item.id
              return (
                <Card key={item.id} className="p-4" data-testid={`portal-reading-assignment-${item.id}`}>
                  <div className="space-y-3">
                    <div>
                      <div className="flex flex-wrap items-center gap-2 mb-2">
                        <Badge variant="submitted">{item.status}</Badge>
                        {isQuizRequired(item) && (
                          <Badge variant="outline">{t('my_reading.quiz')}</Badge>
                        )}
                      </div>
                      <p className="font-medium text-foreground text-lg leading-snug">
                        {item.document_title ?? `${t('my_reading.document')} #${item.document_id}`}
                      </p>
                      {item.campaign_title && (
                        <p className="text-sm text-muted-foreground mt-1">{item.campaign_title}</p>
                      )}
                      <p className="text-sm text-muted-foreground mt-1">
                        {t('my_reading.due')} {dueLabel ?? t('my_reading.not_set')}
                      </p>
                    </div>

                    <div className="flex flex-col gap-2">
                      <Button
                        variant="outline"
                        size="lg"
                        className="w-full min-h-12 text-base"
                        onClick={() => void handleOpenCampaign(item)}
                        disabled={openingCampaignId === item.id}
                      >
                        {openingCampaignId === item.id ? (
                          <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                        ) : (
                          <ExternalLink className="w-5 h-5 mr-2" />
                        )}
                        {t('my_reading.open_read')}
                      </Button>

                      <Button
                        variant="outline"
                        size="lg"
                        className="w-full min-h-12 text-base"
                        aria-expanded={isQuestionExpanded}
                        onClick={() =>
                          setExpandedQuestionId(isQuestionExpanded ? null : item.id)
                        }
                      >
                        <MessageCircleQuestion className="w-5 h-5 mr-2" />
                        {t('portal_reading.ask_question')}
                      </Button>

                      <Button
                        size="lg"
                        className="w-full min-h-12 text-base"
                        onClick={() => void handleToggleComplete(item)}
                        disabled={item.status === 'completed'}
                        aria-expanded={isExpanded}
                      >
                        <ChevronDown className={`w-5 h-5 mr-2 transition-transform ${isExpanded ? 'rotate-180' : ''}`} />
                        {item.status === 'completed'
                          ? t('my_reading.completed')
                          : t('my_reading.complete')}
                      </Button>
                    </div>

                    {isQuestionExpanded && (
                      <div
                        className="border-t pt-4 space-y-3"
                        data-testid={`portal-reading-question-${item.id}`}
                      >
                        <p className="text-sm text-muted-foreground">
                          {t('portal_reading.question_hint')}
                        </p>
                        <Textarea
                          value={questionDrafts[item.id] ?? ''}
                          onChange={(event) =>
                            setQuestionDrafts((prev) => ({ ...prev, [item.id]: event.target.value }))
                          }
                          placeholder={t('portal_reading.question_placeholder')}
                          className="min-h-24 text-base"
                          aria-label={t('portal_reading.ask_question')}
                        />
                        <Button
                          type="button"
                          size="lg"
                          className="w-full min-h-12"
                          onClick={() => void handleAskQuestion(item)}
                          disabled={askingQuestionId === item.id}
                        >
                          {askingQuestionId === item.id && (
                            <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                          )}
                          {t('portal_reading.send_question')}
                        </Button>
                      </div>
                    )}

                    {isExpanded && (
                      <div
                        className="border-t pt-4 space-y-5"
                        data-testid={`portal-reading-complete-${item.id}`}
                      >
                        {isQuizRequired(item) && (
                          <section className="space-y-3">
                            <div>
                              <h2 className="font-medium">{t('my_reading.quiz')}</h2>
                              {quizzes[item.id]?.pass_mark != null && (
                                <p className="text-sm text-muted-foreground">
                                  {t('my_reading.pass_mark', { score: quizzes[item.id].pass_mark })}
                                </p>
                              )}
                            </div>
                            {quizLoadingId === item.id ? (
                              <Loader2 className="w-5 h-5 animate-spin text-primary" />
                            ) : (
                              quizzes[item.id]?.questions.map((question, index) => {
                                const questionIndex = question.question_index ?? index
                                const answer = quizAnswers[item.id]?.[questionIndex] ?? ''
                                return (
                                  <fieldset key={questionIndex} className="space-y-2">
                                    <legend className="text-sm font-medium">
                                      {quizQuestionLabel(question, index)}
                                    </legend>
                                    {isOpenQuestion(question) ? (
                                      <Textarea
                                        value={answer}
                                        onChange={(event) =>
                                          setQuizAnswers((prev) => ({
                                            ...prev,
                                            [item.id]: {
                                              ...prev[item.id],
                                              [questionIndex]: event.target.value,
                                            },
                                          }))
                                        }
                                        className="min-h-20 text-base"
                                        aria-label={quizQuestionLabel(question, index)}
                                      />
                                    ) : (
                                      <div className="space-y-2">
                                        {(question.options ?? []).map((option) => (
                                          <label
                                            key={option}
                                            className="flex items-center gap-3 text-base min-h-12 px-3 rounded-lg border border-border"
                                          >
                                            <input
                                              type="radio"
                                              name={`portal-quiz-${item.id}-${questionIndex}`}
                                              value={option}
                                              checked={answer === option}
                                              onChange={(event) =>
                                                setQuizAnswers((prev) => ({
                                                  ...prev,
                                                  [item.id]: {
                                                    ...prev[item.id],
                                                    [questionIndex]: event.target.value,
                                                  },
                                                }))
                                              }
                                              className="w-5 h-5"
                                            />
                                            {option}
                                          </label>
                                        ))}
                                      </div>
                                    )}
                                  </fieldset>
                                )
                              })
                            )}
                            {quizResults[item.id] && (
                              <p className="text-sm font-medium" role="status">
                                {t('my_reading.quiz_score', {
                                  score:
                                    quizResults[item.id].score ??
                                    quizResults[item.id].quiz_score ??
                                    0,
                                })}{' '}
                                —{' '}
                                {(quizResults[item.id].passed ?? quizResults[item.id].quiz_passed)
                                  ? t('my_reading.passed')
                                  : t('my_reading.not_passed')}
                              </p>
                            )}
                            <Button
                              type="button"
                              variant="outline"
                              size="lg"
                              className="w-full min-h-12"
                              onClick={() => void handleSubmitQuiz(item)}
                              disabled={quizLoadingId === item.id || submittingQuizId === item.id}
                            >
                              {submittingQuizId === item.id && (
                                <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                              )}
                              {t('my_reading.submit_quiz')}
                            </Button>
                          </section>
                        )}
                        <section className="space-y-3">
                          <label
                            className="block text-sm font-medium"
                            htmlFor={`portal-acceptance-${item.id}`}
                          >
                            {t('my_reading.acceptance_statement')}
                          </label>
                          <Textarea
                            id={`portal-acceptance-${item.id}`}
                            value={acceptanceStatements[item.id] ?? ''}
                            onChange={(event) =>
                              setAcceptanceStatements((prev) => ({
                                ...prev,
                                [item.id]: event.target.value,
                              }))
                            }
                            className="min-h-20 text-base"
                          />
                          <label
                            className="block text-sm font-medium"
                            htmlFor={`portal-signature-${item.id}`}
                          >
                            {t('my_reading.signature_optional')}
                          </label>
                          <Input
                            id={`portal-signature-${item.id}`}
                            value={signatures[item.id] ?? ''}
                            onChange={(event) =>
                              setSignatures((prev) => ({ ...prev, [item.id]: event.target.value }))
                            }
                            placeholder={t('my_reading.signature_placeholder')}
                            className="min-h-12 text-base"
                          />
                          <Button
                            type="button"
                            size="lg"
                            className="w-full min-h-12"
                            onClick={() => void handleCompleteCampaign(item)}
                            disabled={completingCampaignId === item.id}
                          >
                            {completingCampaignId === item.id && (
                              <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                            )}
                            <CheckCircle2 className="w-5 h-5 mr-2" />
                            {t('my_reading.complete_assignment')}
                          </Button>
                        </section>
                      </div>
                    )}
                  </div>
                </Card>
              )
            })}
          </div>
        )}
      </main>
    </div>
  )
}
