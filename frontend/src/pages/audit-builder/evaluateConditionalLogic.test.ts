import { describe, expect, it } from 'vitest'

import {
  evaluateRule,
  filterVisibleQuestionIds,
  isQuestionVisible,
} from './evaluateConditionalLogic'
import type { ConditionalLogicRule } from './types'

describe('evaluateRule', () => {
  it('matches equals case-insensitively', () => {
    const rule: ConditionalLogicRule = {
      source_question_id: 1,
      operator: 'equals',
      value: 'Yes',
      action: 'show',
    }
    expect(evaluateRule(rule, { 1: 'yes' })).toBe(true)
    expect(evaluateRule(rule, { 1: 'no' })).toBe(false)
  })

  it('inverts on not_equals', () => {
    const rule: ConditionalLogicRule = {
      source_question_id: 1,
      operator: 'not_equals',
      value: 'yes',
      action: 'hide',
    }
    expect(evaluateRule(rule, { 1: 'no' })).toBe(true)
    expect(evaluateRule(rule, { 1: 'yes' })).toBe(false)
  })

  it('checks contains on array answers', () => {
    const rule: ConditionalLogicRule = {
      source_question_id: 2,
      operator: 'contains',
      value: 'electrical',
      action: 'show',
    }
    expect(evaluateRule(rule, { 2: ['mechanical', 'electrical'] })).toBe(true)
    expect(evaluateRule(rule, { 2: ['mechanical'] })).toBe(false)
  })

  it('checks contains on string answers', () => {
    const rule: ConditionalLogicRule = {
      source_question_id: 2,
      operator: 'contains',
      value: 'fail',
      action: 'show',
    }
    expect(evaluateRule(rule, { 2: 'partial failure noted' })).toBe(true)
  })

  it('compares numerically for greater_than / less_than', () => {
    const gtRule: ConditionalLogicRule = {
      source_question_id: 3,
      operator: 'greater_than',
      value: 5,
      action: 'show',
    }
    const ltRule: ConditionalLogicRule = {
      source_question_id: 3,
      operator: 'less_than',
      value: 5,
      action: 'show',
    }
    expect(evaluateRule(gtRule, { 3: 10 })).toBe(true)
    expect(evaluateRule(gtRule, { 3: 2 })).toBe(false)
    expect(evaluateRule(ltRule, { 3: 2 })).toBe(true)
  })

  it('handles is_empty / is_not_empty', () => {
    const emptyRule: ConditionalLogicRule = {
      source_question_id: 4,
      operator: 'is_empty',
      action: 'hide',
    }
    const notEmptyRule: ConditionalLogicRule = {
      source_question_id: 4,
      operator: 'is_not_empty',
      action: 'show',
    }
    expect(evaluateRule(emptyRule, { 4: '' })).toBe(true)
    expect(evaluateRule(emptyRule, { 4: null })).toBe(true)
    expect(evaluateRule(emptyRule, {})).toBe(true)
    expect(evaluateRule(notEmptyRule, { 4: 'value' })).toBe(true)
    expect(evaluateRule(notEmptyRule, { 4: '' })).toBe(false)
  })

  it('tolerates string-keyed answer maps', () => {
    const rule: ConditionalLogicRule = {
      source_question_id: 1,
      operator: 'equals',
      value: 'yes',
      action: 'show',
    }
    expect(evaluateRule(rule, { '1': 'yes' })).toBe(true)
  })

  it('fails open for unknown operators', () => {
    const rule = {
      source_question_id: 1,
      operator: 'bogus',
      value: 'x',
      action: 'show',
    } as unknown as ConditionalLogicRule
    expect(evaluateRule(rule, { 1: 'anything' })).toBe(true)
  })
})

describe('isQuestionVisible', () => {
  it('is visible with no rules', () => {
    expect(isQuestionVisible(undefined, {})).toBe(true)
    expect(isQuestionVisible([], {})).toBe(true)
  })

  it('hides when a show rule condition is not met', () => {
    const rules: ConditionalLogicRule[] = [
      { source_question_id: 1, operator: 'equals', value: 'yes', action: 'show' },
    ]
    expect(isQuestionVisible(rules, { 1: 'yes' })).toBe(true)
    expect(isQuestionVisible(rules, { 1: 'no' })).toBe(false)
  })

  it('hides when a hide rule condition is met', () => {
    const rules: ConditionalLogicRule[] = [
      { source_question_id: 1, operator: 'equals', value: 'no', action: 'hide' },
    ]
    expect(isQuestionVisible(rules, { 1: 'no' })).toBe(false)
    expect(isQuestionVisible(rules, { 1: 'yes' })).toBe(true)
  })

  it('combines multiple rules with AND semantics', () => {
    const rules: ConditionalLogicRule[] = [
      { source_question_id: 1, operator: 'equals', value: 'yes', action: 'show' },
      { source_question_id: 2, operator: 'equals', value: 'critical', action: 'hide' },
    ]
    expect(isQuestionVisible(rules, { 1: 'yes', 2: 'minor' })).toBe(true)
    expect(isQuestionVisible(rules, { 1: 'no', 2: 'minor' })).toBe(false)
    expect(isQuestionVisible(rules, { 1: 'yes', 2: 'critical' })).toBe(false)
  })

  it('ignores rules with a non-visibility action', () => {
    const rules = [
      { source_question_id: 1, operator: 'equals', value: 'yes', action: 'require' },
    ] as unknown as ConditionalLogicRule[]
    expect(isQuestionVisible(rules, { 1: 'no' })).toBe(true)
  })
})

describe('filterVisibleQuestionIds', () => {
  it('filters questions by their conditionalLogicRules', () => {
    const questions = [
      { id: 1, conditionalLogicRules: undefined },
      {
        id: 2,
        conditionalLogicRules: [
          { source_question_id: 1, operator: 'equals', value: 'yes', action: 'show' },
        ] as ConditionalLogicRule[],
      },
    ]
    expect(filterVisibleQuestionIds(questions, { 1: 'no' })).toEqual(new Set([1]))
    expect(filterVisibleQuestionIds(questions, { 1: 'yes' })).toEqual(new Set([1, 2]))
  })
})
