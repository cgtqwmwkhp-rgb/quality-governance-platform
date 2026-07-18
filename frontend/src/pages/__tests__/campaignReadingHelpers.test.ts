import { describe, expect, it } from 'vitest'
import {
  buildQuizAnswers,
  canCompleteCampaign,
  hasUnansweredQuiz,
  isOpenQuestion,
  isQuizRequired,
  quizQuestionLabel,
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
      ],
    } as DocumentCampaignQuiz

    expect(buildQuizAnswers(quiz, { 0: 'A', 1: 'Because' })).toEqual([
      { question_index: 0, selected_option: 'A' },
      { question_index: 1, text_answer: 'Because' },
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
    expect(isOpenQuestion({ question_type: 'mcq' })).toBe(false)
  })
})
