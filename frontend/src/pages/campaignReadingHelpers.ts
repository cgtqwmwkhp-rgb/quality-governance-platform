import type {
  DocumentCampaignAssignment,
  DocumentCampaignQuiz,
  DocumentCampaignQuizAnswer,
  DocumentCampaignQuizResult,
  PolicyAcknowledgment,
  SignatureDisposition,
} from '../api/client'

export const MAX_QUIZ_ATTEMPTS = 3

export const isQuizRequired = (assignment: DocumentCampaignAssignment) =>
  assignment.quiz_required ?? assignment.requires_quiz ?? false

export const quizQuestionLabel = (
  question: DocumentCampaignQuiz['questions'][number],
  index: number,
) => question.question_text ?? question.question ?? `Question ${index + 1}`

export const isOpenQuestion = (question: DocumentCampaignQuiz['questions'][number]) =>
  ['open_text', 'text', 'open'].includes(question.question_type ?? question.type ?? '')

export const shouldRenderOpenQuestion = (question: DocumentCampaignQuiz['questions'][number]) =>
  isOpenQuestion(question) || !(question.options?.length)

export const buildQuizAnswers = (
  quiz: DocumentCampaignQuiz,
  values: Record<number, string>,
): DocumentCampaignQuizAnswer[] =>
  quiz.questions.map((question, index) => {
    const questionIndex = question.question_index ?? index
    const answer = values[questionIndex]
    return shouldRenderOpenQuestion(question)
      ? { question_index: questionIndex, text_answer: answer }
      : { question_index: questionIndex, selected_option: answer }
  })

export const hasUnansweredQuiz = (
  quiz: DocumentCampaignQuiz,
  values: Record<number, string>,
): boolean =>
  quiz.questions.some((question, index) => {
    const questionIndex = question.question_index ?? index
    return !values[questionIndex]?.trim()
  })

export const getQuizAttemptsUsed = (
  assignment: DocumentCampaignAssignment,
  quizResult?: DocumentCampaignQuizResult,
): number => quizResult?.quiz_attempts ?? assignment.quiz_attempts ?? 0

export const quizAttemptsRemaining = (
  assignment: DocumentCampaignAssignment,
  quizResult?: DocumentCampaignQuizResult,
): number => Math.max(0, MAX_QUIZ_ATTEMPTS - getQuizAttemptsUsed(assignment, quizResult))

export const canSubmitQuiz = (
  assignment: DocumentCampaignAssignment,
  quizResult?: DocumentCampaignQuizResult,
): boolean => {
  if (quizResult?.passed ?? quizResult?.quiz_passed) return false
  return getQuizAttemptsUsed(assignment, quizResult) < MAX_QUIZ_ATTEMPTS
}

export const canCompleteCampaign = (
  assignment: DocumentCampaignAssignment,
  quizResult?: { passed?: boolean | null; quiz_passed?: boolean | null },
): boolean => {
  if (assignment.status === 'completed') return false
  if (!isQuizRequired(assignment)) return true
  return Boolean(quizResult?.passed ?? quizResult?.quiz_passed ?? assignment.quiz_passed)
}

export const showQuestionGate = (
  assignment: DocumentCampaignAssignment,
  quizResult?: DocumentCampaignQuizResult,
): boolean => {
  if (!isQuizRequired(assignment)) return true
  return Boolean(quizResult?.passed ?? quizResult?.quiz_passed ?? assignment.quiz_passed)
}

export type QuestionGateChoice = 'yes' | 'no'
export type SignChoice = 'defer' | 'sign_now'

export const resolveSignatureDisposition = (
  hasQuestions: QuestionGateChoice | null,
  signChoice: SignChoice | null,
): SignatureDisposition | null => {
  if (hasQuestions === 'no') return 'signed'
  if (hasQuestions === 'yes' && signChoice === 'defer') return 'signature_deferred_pending_answer'
  if (hasQuestions === 'yes' && signChoice === 'sign_now') return 'signed_pending_hseq_answer'
  return null
}

export const isSignatureRequiredForCompletion = (
  hasQuestions: QuestionGateChoice | null,
  signChoice: SignChoice | null,
): boolean => {
  if (hasQuestions === 'no') return true
  if (hasQuestions === 'yes' && signChoice === 'sign_now') return true
  return false
}

export const canProceedToCompletionFields = (
  hasQuestions: QuestionGateChoice | null,
  signChoice: SignChoice | null,
  questionSent: boolean,
): boolean => {
  if (hasQuestions === null) return false
  if (hasQuestions === 'no') return true
  if (!questionSent) return false
  return signChoice !== null
}

export async function resolveAssignmentDocumentUrl(
  assignmentId: number,
  getAssignmentDocumentUrl: (id: number) => Promise<{ data: { signed_url: string } }>,
  apiBaseUrl?: string,
): Promise<string> {
  const response = await getAssignmentDocumentUrl(assignmentId)
  const rawUrl = response.data.signed_url
  return new URL(rawUrl, apiBaseUrl || window.location.origin).toString()
}

/** Campaign assignments that still require engineer action (SSOT for reading queue). */
export const isActiveCampaignAssignment = (assignment: DocumentCampaignAssignment): boolean =>
  assignment.status !== 'completed'

/**
 * True when a legacy policy-ack row refers to the same controlled document as an active campaign.
 * Matches document_id (legacy UI conflation) and linked_policy_id when present on the assignment.
 */
export const policyAckMatchesCampaignDocument = (
  policyAck: PolicyAcknowledgment,
  assignment: DocumentCampaignAssignment,
): boolean => {
  if (!isActiveCampaignAssignment(assignment)) return false
  if (assignment.document_id === policyAck.policy_id) return true
  if (
    assignment.linked_policy_id != null &&
    assignment.linked_policy_id === policyAck.policy_id
  ) {
    return true
  }
  return false
}

export const findCampaignAssignmentForPolicyAck = (
  policyAck: PolicyAcknowledgment,
  campaigns: DocumentCampaignAssignment[],
): DocumentCampaignAssignment | undefined =>
  campaigns.find((assignment) => policyAckMatchesCampaignDocument(policyAck, assignment))

export type SuppressedPolicyAck = {
  policyAck: PolicyAcknowledgment
  campaignAssignmentId: number
}

/** Prefer campaign assignments; hide policy-ack cards that duplicate active campaign work. */
export const partitionReadingQueue = (
  policyAcks: PolicyAcknowledgment[],
  campaigns: DocumentCampaignAssignment[],
): {
  activeCampaigns: DocumentCampaignAssignment[]
  visiblePolicyAcks: PolicyAcknowledgment[]
  suppressedPolicyAcks: SuppressedPolicyAck[]
} => {
  const activeCampaigns = campaigns.filter(isActiveCampaignAssignment)
  const visiblePolicyAcks: PolicyAcknowledgment[] = []
  const suppressedPolicyAcks: SuppressedPolicyAck[] = []

  for (const policyAck of policyAcks) {
    const match = findCampaignAssignmentForPolicyAck(policyAck, activeCampaigns)
    if (match) {
      suppressedPolicyAcks.push({ policyAck, campaignAssignmentId: match.id })
    } else {
      visiblePolicyAcks.push(policyAck)
    }
  }

  return { activeCampaigns, visiblePolicyAcks, suppressedPolicyAcks }
}

export const unifiedReadingQueueCount = (
  activeCampaigns: DocumentCampaignAssignment[],
  visiblePolicyAcks: PolicyAcknowledgment[],
): number => activeCampaigns.length + visiblePolicyAcks.length

export const portalCampaignReadingHref = (assignmentId: number): string =>
  `/portal/reading?assignment=${assignmentId}`
