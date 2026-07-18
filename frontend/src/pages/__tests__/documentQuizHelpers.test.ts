import { describe, expect, it } from 'vitest'
import {
  isQuizAiFallback,
  normalizeQuestionCountInput,
  sanitizeQuestionCount,
} from '../documentQuizHelpers'

describe('documentQuizHelpers', () => {
  it('sanitizes question count without leading zeros', () => {
    expect(sanitizeQuestionCount('010')).toBe(10)
    expect(normalizeQuestionCountInput('010')).toBe('10')
    expect(sanitizeQuestionCount('')).toBe(1)
    expect(sanitizeQuestionCount('99')).toBe(30)
  })

  it('detects AI fallback quiz drafts', () => {
    expect(
      isQuizAiFallback(
        [
          {
            type: 'open',
            question: 'Summarise the key compliance requirements in this document.',
            explanation: 'Fallback question — AI unavailable.',
          },
        ],
        5,
      ),
    ).toBe(true)

    expect(
      isQuizAiFallback(
        [
          { type: 'mcq', question: 'Q1', explanation: 'ok' },
          { type: 'mcq', question: 'Q2', explanation: 'ok' },
        ],
        2,
      ),
    ).toBe(false)
  })
})
