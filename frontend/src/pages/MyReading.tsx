import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { BookOpen, CheckCircle2, ChevronDown, Clock, ExternalLink, Loader2, MessageSquare, Search } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import {
  documentCampaignApi,
  getApiErrorMessage,
  policyAcknowledgmentsApi,
  type DocumentCampaignAssignment,
  type DocumentCampaignQuiz,
  type DocumentCampaignQuizAnswer,
  type DocumentCampaignQuizResult,
  type PolicyAcknowledgment,
} from '../api/client'
import { toast } from '../contexts/ToastContext'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { EmptyState } from '../components/ui/EmptyState'
import { Input } from '../components/ui/Input'
import { Textarea } from '../components/ui/Textarea'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/Select'

const reportFailure = (err: unknown): string => {
  const message = getApiErrorMessage(err)
  toast.error(message)
  return message
}

type ReadingItem =
  | { source: 'policy'; item: PolicyAcknowledgment }
  | { source: 'campaign'; item: DocumentCampaignAssignment }

const isQuizRequired = (assignment: DocumentCampaignAssignment) =>
  assignment.quiz_required ?? assignment.requires_quiz ?? false

const quizQuestionLabel = (question: DocumentCampaignQuiz['questions'][number], index: number) =>
  question.question_text ?? question.question ?? `Question ${index + 1}`

const isOpenQuestion = (question: DocumentCampaignQuiz['questions'][number]) =>
  ['open_text', 'text'].includes(question.question_type ?? question.type ?? '')

export default function MyReading() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [policyItems, setPolicyItems] = useState<PolicyAcknowledgment[]>([])
  const [campaignItems, setCampaignItems] = useState<DocumentCampaignAssignment[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [acknowledgingId, setAcknowledgingId] = useState<number | null>(null)
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
  const [snoozingCampaignId, setSnoozingCampaignId] = useState<number | null>(null)
  const [questionTitles, setQuestionTitles] = useState<Record<number, string>>({})
  const [questionBodies, setQuestionBodies] = useState<Record<number, string>>({})
  const [askingQuestionId, setAskingQuestionId] = useState<number | null>(null)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('all')

  const loadAssignments = useCallback(async () => {
    setLoading(true)
    setError(null)
    const [policies, campaigns] = await Promise.allSettled([
      policyAcknowledgmentsApi.listMyPending(),
      documentCampaignApi.listMyAssignments(),
    ])

    if (policies.status === 'fulfilled') {
      setPolicyItems(policies.value.data.items ?? [])
    } else {
      setPolicyItems([])
    }
    if (campaigns.status === 'fulfilled') {
      setCampaignItems(campaigns.value.data.items ?? [])
    } else {
      setCampaignItems([])
    }
    if (policies.status === 'rejected' || campaigns.status === 'rejected') {
      const failedRequest =
        policies.status === 'rejected'
          ? policies.reason
          : campaigns.status === 'rejected'
            ? campaigns.reason
            : null
      setError(reportFailure(failedRequest))
    }
    setLoading(false)
  }, [])

  useEffect(() => {
    void loadAssignments()
  }, [loadAssignments])

  const handleOpen = async (item: PolicyAcknowledgment) => {
    try {
      await policyAcknowledgmentsApi.recordOpen(item.id)
      window.open(`/documents/${item.policy_id}?tab=qa`, '_blank', 'noopener,noreferrer')
    } catch (err) {
      reportFailure(err)
    }
  }

  const handleAcknowledge = async (item: PolicyAcknowledgment) => {
    setAcknowledgingId(item.id)
    try {
      await policyAcknowledgmentsApi.acknowledge(item.id, {
        acceptance_statement: 'I have read and understood this document.',
      })
      toast.success('Acknowledgment recorded')
      setPolicyItems((prev) => prev.filter((i) => i.id !== item.id))
    } catch (err) {
      reportFailure(err)
    } finally {
      setAcknowledgingId(null)
    }
  }

  const handleOpenCampaign = async (item: DocumentCampaignAssignment) => {
    setOpeningCampaignId(item.id)
    try {
      await documentCampaignApi.openAssignment(item.id)
      setCampaignItems((prev) =>
        prev.map((assignment) =>
          assignment.id === item.id ? { ...assignment, status: 'opened' } : assignment,
        ),
      )
      navigate(`/documents/${item.document_id}`)
    } catch (err) {
      reportFailure(err)
    } finally {
      setOpeningCampaignId(null)
    }
  }

  const handleToggleCampaignComplete = async (item: DocumentCampaignAssignment) => {
    if (expandedCampaignId === item.id) {
      setExpandedCampaignId(null)
      return
    }
    setExpandedCampaignId(item.id)
    setAcceptanceStatements((prev) => ({
      ...prev,
      [item.id]:
        prev[item.id] ?? t('my_reading.acceptance_default'),
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
    const unanswered = quiz.questions.some((question, index) => !values[question.question_index ?? index]?.trim())
    if (unanswered) {
      toast.error(t('my_reading.complete_all_quiz_questions'))
      return
    }
    const answers: DocumentCampaignQuizAnswer[] = quiz.questions.map((question, index) => {
      const questionIndex = question.question_index ?? index
      const answer = values[questionIndex]
      return isOpenQuestion(question)
        ? { question_index: questionIndex, text_answer: answer }
        : { question_index: questionIndex, selected_option: answer }
    })

    setSubmittingQuizId(item.id)
    try {
      const response = await documentCampaignApi.submitQuiz(item.id, answers)
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
    if (isQuizRequired(item) && !(quizResult?.passed ?? quizResult?.quiz_passed ?? item.quiz_passed)) {
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
      setCampaignItems((prev) =>
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

  const handleAskHsecQuestion = async (item: DocumentCampaignAssignment) => {
    const body = questionBodies[item.id]?.trim()
    if (!body) {
      toast.error(t('my_reading.question_body_required'))
      return
    }
    setAskingQuestionId(item.id)
    try {
      const title = questionTitles[item.id]?.trim()
      await documentCampaignApi.askAssignmentQuestion(item.id, {
        ...(title ? { title } : {}),
        body,
      })
      toast.success(t('my_reading.question_sent'))
      setQuestionBodies((prev) => ({ ...prev, [item.id]: '' }))
      setQuestionTitles((prev) => ({ ...prev, [item.id]: '' }))
    } catch (err) {
      reportFailure(err)
    } finally {
      setAskingQuestionId(null)
    }
  }


  const handleSnoozeCampaign = async (item: DocumentCampaignAssignment) => {
    if (item.status !== 'pending' && item.status !== 'overdue') return
    setSnoozingCampaignId(item.id)
    try {
      const response = await documentCampaignApi.snoozeAssignment(item.id, 24)
      setCampaignItems((prev) =>
        prev.map((assignment) =>
          assignment.id === item.id
            ? { ...assignment, snooze_until: response.data.snooze_until }
            : assignment,
        ),
      )
      toast.success(t('my_reading.snooze_success'))
    } catch (err) {
      reportFailure(err)
    } finally {
      setSnoozingCampaignId(null)
    }
  }

  const items = useMemo<ReadingItem[]>(
    () => [
      ...policyItems.map((item): ReadingItem => ({ source: 'policy', item })),
      ...campaignItems.map((item): ReadingItem => ({ source: 'campaign', item })),
    ],
    [campaignItems, policyItems],
  )

  const filteredItems = useMemo(() => {
    const q = search.trim().toLowerCase()
    return items.filter(({ item, source }) => {
      if (statusFilter !== 'all' && item.status !== statusFilter) return false
      if (!q) return true
      if (source === 'policy') {
        return (
          String(item.policy_id).includes(q) ||
          (item.policy_version ?? '').toLowerCase().includes(q) ||
          (item.status ?? '').toLowerCase().includes(q)
        )
      }
      return [item.document_id, item.document_title, item.campaign_title, item.status]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(q))
    })
  }, [items, search, statusFilter])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 text-primary animate-spin" />
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-fade-in" data-testid="my-reading-page">
      <div>
        <h1 className="text-2xl font-bold text-foreground">My Reading</h1>
        <p className="text-muted-foreground mt-1">
          {t('my_reading.subtitle')}
        </p>
      </div>

      <div className="flex flex-col sm:flex-row gap-3" data-testid="my-reading-filters">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <Input
            type="search"
            placeholder={t('my_reading.search_placeholder')}
            aria-label={t('my_reading.search_placeholder')}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-10"
            data-testid="my-reading-search"
          />
        </div>
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger
            className="w-full sm:w-48"
            aria-label={t('my_reading.filter_by_status')}
            data-testid="my-reading-status-filter"
          >
            <SelectValue placeholder={t('my_reading.status')} />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{t('my_reading.all_statuses')}</SelectItem>
            <SelectItem value="pending">{t('my_reading.pending')}</SelectItem>
            <SelectItem value="opened">{t('my_reading.opened')}</SelectItem>
            <SelectItem value="completed">{t('my_reading.completed')}</SelectItem>
            <SelectItem value="overdue">{t('my_reading.overdue')}</SelectItem>
          </SelectContent>
        </Select>
        <Button type="button" variant="outline" data-testid="my-reading-filter-apply">
          {t('my_reading.filter')}
        </Button>
      </div>

      {error && (
        <div className="rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {filteredItems.length === 0 ? (
        <EmptyState
          icon={<BookOpen className="w-8 h-8 text-muted-foreground" />}
          title={items.length === 0 ? t('my_reading.all_caught_up') : t('my_reading.no_matching_reads')}
          description={
            items.length === 0
              ? t('my_reading.empty_description')
              : t('my_reading.no_matching_description')
          }
        />
      ) : (
        <div className="space-y-3">
          {filteredItems.map(({ source, item }) => (
            <Card key={`${source}-${item.id}`} className="p-4">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <Badge variant="submitted">{item.status}</Badge>
                    <Badge variant="outline">
                      {source === 'policy' ? t('my_reading.source_policy') : t('my_reading.source_campaign')}
                    </Badge>
                    {source === 'policy' && item.policy_version && (
                      <span className="text-xs text-muted-foreground">v{item.policy_version}</span>
                    )}
                    {source === 'campaign' && item.document_version && (
                      <span className="text-xs text-muted-foreground">v{item.document_version}</span>
                    )}
                  </div>
                  <p className="font-medium text-foreground">
                    {source === 'policy'
                      ? `Policy #${item.policy_id}`
                      : item.document_title ?? `${t('my_reading.document')} #${item.document_id}`}
                  </p>
                  {source === 'campaign' && item.campaign_title && (
                    <p className="text-sm text-muted-foreground">{item.campaign_title}</p>
                  )}
                  <p className="text-sm text-muted-foreground">
                    {t('my_reading.due')} {item.due_date ? new Date(item.due_date).toLocaleDateString() : t('my_reading.not_set')}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  {source === 'policy' ? (
                    <>
                      <Button variant="outline" size="sm" onClick={() => void handleOpen(item)}>
                        <ExternalLink className="w-4 h-4 mr-2" />
                        {t('my_reading.open_read')}
                      </Button>
                      <Button variant="outline" size="sm" asChild>
                        <Link to={`/documents/${item.policy_id}?tab=qa`}>Q&A</Link>
                      </Button>
                      <Button
                        size="sm"
                        onClick={() => void handleAcknowledge(item)}
                        disabled={acknowledgingId === item.id}
                        data-testid={`my-reading-acknowledge-${item.id}`}
                        aria-label={`Acknowledge policy ${item.policy_id}`}
                      >
                        {acknowledgingId === item.id ? (
                          <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        ) : (
                          <CheckCircle2 className="w-4 h-4 mr-2" />
                        )}
                        {t('my_reading.acknowledge')}
                      </Button>
                    </>
                  ) : (
                    <>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => void handleOpenCampaign(item)}
                        disabled={openingCampaignId === item.id}
                      >
                        {openingCampaignId === item.id ? (
                          <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        ) : (
                          <ExternalLink className="w-4 h-4 mr-2" />
                        )}
                        {t('my_reading.open_read')}
                      </Button>

                      {(item.status === 'pending' || item.status === 'overdue') && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => void handleSnoozeCampaign(item)}
                          disabled={snoozingCampaignId === item.id}
                          data-testid={`my-reading-snooze-${item.id}`}
                        >
                          {snoozingCampaignId === item.id ? (
                            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                          ) : (
                            <Clock className="w-4 h-4 mr-2" />
                          )}
                          {t('my_reading.snooze_24h')}
                        </Button>
                      )}
                      <Button
                        size="sm"
                        onClick={() => void handleToggleCampaignComplete(item)}
                        disabled={item.status === 'completed'}
                        aria-expanded={expandedCampaignId === item.id}
                      >
                        <ChevronDown className="w-4 h-4 mr-2" />
                        {item.status === 'completed' ? t('my_reading.completed') : t('my_reading.complete')}
                      </Button>
                    </>
                  )}
                </div>
              </div>
              {source === 'campaign' && expandedCampaignId === item.id && (
                <div className="mt-5 border-t pt-5 space-y-5" data-testid={`campaign-complete-${item.id}`}>
                  {item.status !== 'completed' && (
                    <section className="space-y-3" data-testid={`campaign-ask-hsec-${item.id}`}>
                      <div className="flex items-center gap-2">
                        <MessageSquare className="w-4 h-4 text-primary" />
                        <h2 className="font-medium">{t('my_reading.ask_hsec_title')}</h2>
                      </div>
                      <p className="text-sm text-muted-foreground">{t('my_reading.ask_hsec_help')}</p>
                      <label className="block text-sm font-medium" htmlFor={`question-title-${item.id}`}>
                        {t('my_reading.question_title_optional')}
                      </label>
                      <Input
                        id={`question-title-${item.id}`}
                        value={questionTitles[item.id] ?? ''}
                        onChange={(event) =>
                          setQuestionTitles((prev) => ({ ...prev, [item.id]: event.target.value }))
                        }
                        placeholder={t('my_reading.question_title_placeholder')}
                      />
                      <label className="block text-sm font-medium" htmlFor={`question-body-${item.id}`}>
                        {t('my_reading.question_body')}
                      </label>
                      <Textarea
                        id={`question-body-${item.id}`}
                        value={questionBodies[item.id] ?? ''}
                        onChange={(event) =>
                          setQuestionBodies((prev) => ({ ...prev, [item.id]: event.target.value }))
                        }
                        placeholder={t('my_reading.question_body_placeholder')}
                      />
                      <Button
                        type="button"
                        variant="outline"
                        onClick={() => void handleAskHsecQuestion(item)}
                        disabled={askingQuestionId === item.id}
                      >
                        {askingQuestionId === item.id && (
                          <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        )}
                        {t('my_reading.ask_hsec_submit')}
                      </Button>
                    </section>
                  )}
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
                              <legend className="text-sm font-medium">{quizQuestionLabel(question, index)}</legend>
                              {isOpenQuestion(question) ? (
                                <Textarea
                                  value={answer}
                                  onChange={(event) =>
                                    setQuizAnswers((prev) => ({
                                      ...prev,
                                      [item.id]: { ...prev[item.id], [questionIndex]: event.target.value },
                                    }))
                                  }
                                  aria-label={quizQuestionLabel(question, index)}
                                />
                              ) : (
                                <div className="space-y-2">
                                  {(question.options ?? []).map((option) => (
                                    <label key={option} className="flex items-center gap-2 text-sm">
                                      <input
                                        type="radio"
                                        name={`quiz-${item.id}-${questionIndex}`}
                                        value={option}
                                        checked={answer === option}
                                        onChange={(event) =>
                                          setQuizAnswers((prev) => ({
                                            ...prev,
                                            [item.id]: { ...prev[item.id], [questionIndex]: event.target.value },
                                          }))
                                        }
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
                            score: quizResults[item.id].score ?? quizResults[item.id].quiz_score ?? 0,
                          })}{' '}
                          — {(quizResults[item.id].passed ?? quizResults[item.id].quiz_passed)
                            ? t('my_reading.passed')
                            : t('my_reading.not_passed')}
                        </p>
                      )}
                      <Button
                        type="button"
                        variant="outline"
                        onClick={() => void handleSubmitQuiz(item)}
                        disabled={quizLoadingId === item.id || submittingQuizId === item.id}
                      >
                        {submittingQuizId === item.id && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
                        {t('my_reading.submit_quiz')}
                      </Button>
                    </section>
                  )}
                  <section className="space-y-3">
                    <label className="block text-sm font-medium" htmlFor={`acceptance-${item.id}`}>
                      {t('my_reading.acceptance_statement')}
                    </label>
                    <Textarea
                      id={`acceptance-${item.id}`}
                      value={acceptanceStatements[item.id] ?? ''}
                      onChange={(event) =>
                        setAcceptanceStatements((prev) => ({ ...prev, [item.id]: event.target.value }))
                      }
                    />
                    <label className="block text-sm font-medium" htmlFor={`signature-${item.id}`}>
                      {t('my_reading.signature_optional')}
                    </label>
                    <Input
                      id={`signature-${item.id}`}
                      value={signatures[item.id] ?? ''}
                      onChange={(event) => setSignatures((prev) => ({ ...prev, [item.id]: event.target.value }))}
                      placeholder={t('my_reading.signature_placeholder')}
                    />
                    <Button
                      type="button"
                      onClick={() => void handleCompleteCampaign(item)}
                      disabled={completingCampaignId === item.id}
                    >
                      {completingCampaignId === item.id && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
                      <CheckCircle2 className="w-4 h-4 mr-2" />
                      {t('my_reading.complete_assignment')}
                    </Button>
                  </section>
                </div>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
