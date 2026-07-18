import { describe, expect, it } from 'vitest'
import {
  buildQuizAnswers,
  canCompleteCampaign,
  canProceedToCompletionFields,
  canSubmitQuiz,
  getQuizAttemptsUsed,
  hasUnansweredQuiz,
  isOpenQuestion,
  isQuizRequired,
  isSignatureRequiredForCompletion,
  MAX_QUIZ_ATTEMPTS,
  quizAttemptsRemaining,
  quizQuestionLabel,
  resolveSignatureDisposition,
  shouldRenderOpenQuestion,
} from '../campaignReadingHelpers'
import type { DocumentCampaignAssignment, DocumentCampaignQuiz } from '../../api/client'

describe('campaignReadingHelpers', () => {
  it('detects quiz requirement from alternate flags', () => {
    expect(isQuizRequired({ quiz_required: true } as DocumentCampaignAssignment)).toBe(true)
    expect(isQuizRequired({ requires_quiz: true } as DocumentCampaignAssignment)).toBe(true)
    expect(isQuizRequired({ quiz_required: false, requires_quiz: true } as DocumentCampaignAssignment)).toBe(false)
  })

  it('labels quiz questions with fallback text', () => {
    expect(quizQuestionLabel({ question_text: 'Safety first?' }, 0)).toBe('Safety first?')
    expect(quizQuestionLabel({}, 2)).toBe('Question 3')
  })

  it('builds MCQ and open-text answers', () => {
    const quiz = {
      questions: [
        { question_index: 0, question_type: 'mcq', options: ['A', 'B'] },
        { question_index: 1, question_type: 'open_text' },
        { question_index: 2, question_type: 'mcq', options: [] },
      ],
    } as DocumentCampaignQuiz

    expect(buildQuizAnswers(quiz, { 0: 'A', 1: 'Because', 2: 'Free text' })).toEqual([
      { question_index: 0, selected_option: 'A' },
      { question_index: 1, text_answer: 'Because' },
      { question_index: 2, text_answer: 'Free text' },
    ])
  })

  it('detects unanswered quiz fields', () => {
    const quiz = {
      questions: [{ question_index: 0 }, { question_index: 1 }],
    } as DocumentCampaignQuiz

    expect(hasUnansweredQuiz(quiz, { 0: 'yes' })).toBe(true)
    expect(hasUnansweredQuiz(quiz, { 0: 'yes', 1: 'done' })).toBe(false)
  })

  it('gates completion on quiz pass when required', () => {
    const assignment = { status: 'opened', quiz_required: true } as DocumentCampaignAssignment
    expect(canCompleteCampaign(assignment, { passed: false })).toBe(false)
    expect(canCompleteCampaign(assignment, { passed: true })).toBe(true)
    expect(canCompleteCampaign({ status: 'completed', quiz_required: true } as DocumentCampaignAssignment)).toBe(false)
  })

  it('treats open question types consistently', () => {
    expect(isOpenQuestion({ question_type: 'open_text' })).toBe(true)
    expect(isOpenQuestion({ type: 'open' })).toBe(true)
    expect(isOpenQuestion({ type: 'text' })).toBe(true)
    expect(isOpenQuestion({ question_type: 'mcq' })).toBe(false)
  })

  it('renders empty-option questions as open text', () => {
    expect(shouldRenderOpenQuestion({ question_type: 'mcq', options: [] })).toBe(true)
    expect(shouldRenderOpenQuestion({ question_type: 'mcq', options: ['A'] })).toBe(false)
  })

  it('tracks quiz attempts and submit eligibility', () => {
    const assignment = { quiz_attempts: 2 } as DocumentCampaignAssignment
    expect(getQuizAttemptsUsed(assignment)).toBe(2)
    expect(quizAttemptsRemaining(assignment)).toBe(1)
    expect(canSubmitQuiz(assignment)).toBe(true)
    expect(canSubmitQuiz({ quiz_attempts: MAX_QUIZ_ATTEMPTS } as DocumentCampaignAssignment)).toBe(false)
    expect(canSubmitQuiz(assignment, { passed: true })).toBe(false)
  })

  it('resolves signature disposition and requirements', () => {
    expect(resolveSignatureDisposition('no', null)).toBe('signed')
    expect(resolveSignatureDisposition('yes', 'defer')).toBe('signature_deferred_pending_answer')
    expect(resolveSignatureDisposition('yes', 'sign_now')).toBe('signed_pending_hseq_answer')
    expect(isSignatureRequiredForCompletion('no', null)).toBe(true)
    expect(isSignatureRequiredForCompletion('yes', 'defer')).toBe(false)
    expect(canProceedToCompletionFields('no', null, false)).toBe(true)
    expect(canProceedToCompletionFields('yes', 'defer', true)).toBe(true)
    expect(canProceedToCompletionFields('yes', null, true)).toBe(false)
  })
})
