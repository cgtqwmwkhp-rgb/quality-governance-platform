import { describe, expect, it } from 'vitest'
import { mapBackendQuestionType } from '../AuditExecution'

describe('mapBackendQuestionType', () => {
  it('maps binary and text API types to execution widgets', () => {
    expect(mapBackendQuestionType({ question_type: 'yes_no' })).toBe('yes_no')
    expect(mapBackendQuestionType({ question_type: 'yes_no', allow_na: true })).toBe('yes_no_na')
    expect(mapBackendQuestionType({ question_type: 'pass_fail' })).toBe('pass_fail')
    expect(mapBackendQuestionType({ question_type: 'text' })).toBe('text_short')
    expect(mapBackendQuestionType({ question_type: 'textarea' })).toBe('text_long')
    expect(mapBackendQuestionType({ question_type: 'number' })).toBe('numeric')
  })

  it('does not collapse choice / media / rating types to text_short', () => {
    expect(mapBackendQuestionType({ question_type: 'checkbox' })).toBe('checklist')
    expect(mapBackendQuestionType({ question_type: 'radio' })).toBe('multi_choice')
    expect(mapBackendQuestionType({ question_type: 'dropdown' })).toBe('multi_choice')
    expect(mapBackendQuestionType({ question_type: 'photo' })).toBe('photo')
    expect(mapBackendQuestionType({ question_type: 'file' })).toBe('photo')
    expect(mapBackendQuestionType({ question_type: 'signature' })).toBe('signature')
    expect(mapBackendQuestionType({ question_type: 'rating' })).toBe('scale_1_5')
    expect(mapBackendQuestionType({ question_type: 'score', max_score: 10 })).toBe('scale_1_10')
    expect(mapBackendQuestionType({ question_type: 'date' })).toBe('date')
    expect(mapBackendQuestionType({ question_type: 'datetime' })).toBe('datetime')
  })

  it('maps entity-select types to themselves (no collapse to dropdown)', () => {
    expect(mapBackendQuestionType({ question_type: 'user_select' })).toBe('user_select')
    expect(mapBackendQuestionType({ question_type: 'location_select' })).toBe('location_select')
    expect(mapBackendQuestionType({ question_type: 'customer_select' })).toBe('customer_select')
  })

  it('keeps unknown types as text_short fallback only', () => {
    expect(mapBackendQuestionType({ question_type: 'unknown_future_type' })).toBe('text_short')
  })
})
