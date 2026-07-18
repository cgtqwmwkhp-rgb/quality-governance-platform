import type {
  DocumentCampaignAssignment,
  DocumentCampaignQuiz,
  DocumentCampaignQuizAnswer,
} from '../api/client'

export const isQuizRequired = (assignment: DocumentCampaignAssignment) =>
  assignment.quiz_required ?? assignment.requires_quiz ?? false

export const quizQuestionLabel = (
  question: DocumentCampaignQuiz['questions'][number],
  index: number,
) => question.question_text ?? question.question ?? `Question ${index + 1}`

export const isOpenQuestion = (question: DocumentCampaignQuiz['questions'][number]) =>
  ['open_text', 'text', 'open'].includes(question.question_type ?? question.type ?? '')

export const buildQuizAnswers = (
  quiz: DocumentCampaignQuiz,
  values: Record<number, string>,
): DocumentCampaignQuizAnswer[] =>
  quiz.questions.map((question, index) => {
    const questionIndex = question.question_index ?? index
    const answer = values[questionIndex]
    return isOpenQuestion(question)
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

export const canCompleteCampaign = (
  assignment: DocumentCampaignAssignment,
  quizResult?: { passed?: boolean | null; quiz_passed?: boolean | null },
): boolean => {
  if (assignment.status === 'completed') return false
  if (!isQuizRequired(assignment)) return true
  return Boolean(quizResult?.passed ?? quizResult?.quiz_passed ?? assignment.quiz_passed)
}
