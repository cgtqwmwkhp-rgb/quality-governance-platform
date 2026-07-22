/**
 * FE mirror of `src/domain/services/audit_conditional.py`.
 *
 * Given a question's `ConditionalLogicRule[]` and a map of `{ questionId: answer }`,
 * determines whether the question should be visible. A question with no rules is
 * always visible. Multiple rules combine with AND semantics: a "show" rule that
 * doesn't match hides the question; a "hide" rule that matches hides the question.
 */

import type { ConditionalLogicRule } from './types'

export type AnswerMap = Record<string | number, unknown>

const VISIBILITY_ACTIONS = new Set(['show', 'hide'])

function coerceKey(value: string | number): string {
  return String(value)
}

function getAnswerValue(answers: AnswerMap, questionId: string | number): unknown {
  if (questionId in answers) return answers[questionId]
  const key = coerceKey(questionId)
  if (key in answers) return answers[key]
  const numericKey = Number(key)
  if (!Number.isNaN(numericKey) && numericKey in answers) return answers[numericKey]
  return undefined
}

function isEmpty(value: unknown): boolean {
  if (value === null || value === undefined) return true
  if (typeof value === 'string') return value.trim() === ''
  if (Array.isArray(value)) return value.length === 0
  return false
}

function asNumber(value: unknown): number | null {
  if (value === null || value === undefined || value === '') return null
  const num = typeof value === 'boolean' ? NaN : Number(value)
  return Number.isNaN(num) ? null : num
}

function valuesMatch(answer: unknown, expected: unknown): boolean {
  if (answer === null || answer === undefined) return expected === null || expected === undefined
  if (typeof answer === 'boolean' || typeof expected === 'boolean') {
    return Boolean(answer) === Boolean(expected)
  }
  const answerNum = asNumber(answer)
  const expectedNum = asNumber(expected)
  if (answerNum !== null && expectedNum !== null) return answerNum === expectedNum
  return String(answer).trim().toLowerCase() === String(expected).trim().toLowerCase()
}

function contains(answer: unknown, expected: unknown): boolean {
  if (Array.isArray(answer)) return answer.some((item) => valuesMatch(item, expected))
  if (answer === null || answer === undefined) return false
  return String(answer).trim().toLowerCase().includes(String(expected).trim().toLowerCase())
}

/** Return true when `rule`'s condition is satisfied by `answers`. */
export function evaluateRule(rule: ConditionalLogicRule, answers: AnswerMap): boolean {
  const answer = getAnswerValue(answers, rule.source_question_id)
  const expected = rule.value

  switch (rule.operator) {
    case 'is_empty':
      return isEmpty(answer)
    case 'is_not_empty':
      return !isEmpty(answer)
    case 'equals':
      return valuesMatch(answer, expected)
    case 'not_equals':
      return !valuesMatch(answer, expected)
    case 'contains':
      return contains(answer, expected)
    case 'greater_than': {
      const a = asNumber(answer)
      const b = asNumber(expected)
      return a !== null && b !== null && a > b
    }
    case 'less_than': {
      const a = asNumber(answer)
      const b = asNumber(expected)
      return a !== null && b !== null && a < b
    }
    default:
      // Unknown operator: fail open (does not block visibility).
      return true
  }
}

/** Evaluate a question's rule array; default visible when there are no rules. */
export function isQuestionVisible(
  rules: ConditionalLogicRule[] | null | undefined,
  answers: AnswerMap,
): boolean {
  if (!rules || rules.length === 0) return true

  let visible = true
  for (const rule of rules) {
    if (!rule || !VISIBILITY_ACTIONS.has(rule.action)) continue
    const matched = evaluateRule(rule, answers)
    if (rule.action === 'show' && !matched) visible = false
    else if (rule.action === 'hide' && matched) visible = false
  }
  return visible
}

/** Return the ids of `questions` that are visible given the current `answers`. */
export function filterVisibleQuestionIds<
  T extends { id: string | number; conditionalLogicRules?: ConditionalLogicRule[] | null },
>(questions: T[], answers: AnswerMap): Set<string | number> {
  const visibleIds = new Set<string | number>()
  for (const question of questions) {
    if (isQuestionVisible(question.conditionalLogicRules, answers)) {
      visibleIds.add(question.id)
    }
  }
  return visibleIds
}
