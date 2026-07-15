/**
 * Canonical audit question type registry for builder ↔ API round-trip.
 * Mirrors `src/domain/constants/audit_question_types.py` and the API
 * allowlist in `src/api/schemas/audit.py`.
 */
import type { QuestionType } from './types'

/** Matches Field pattern on AuditQuestionBase.question_type. */
export const API_QUESTION_TYPES = [
  'text',
  'textarea',
  'number',
  'checkbox',
  'radio',
  'dropdown',
  'date',
  'datetime',
  'signature',
  'photo',
  'file',
  'rating',
  'yes_no',
  'pass_fail',
  'score',
] as const

export type ApiQuestionType = (typeof API_QUESTION_TYPES)[number]

/** Frontend audit-builder palette types. */
export const FE_BUILDER_QUESTION_TYPES: readonly QuestionType[] = [
  'yes_no',
  'yes_no_na',
  'pass_fail',
  'scale_1_5',
  'scale_1_10',
  'multi_choice',
  'checklist',
  'text_short',
  'text_long',
  'numeric',
  'date',
  'photo',
  'signature',
] as const

/** API types produced by the palette forward map. */
export const PALETTE_API_TYPES = [
  'yes_no',
  'pass_fail',
  'rating',
  'radio',
  'checkbox',
  'text',
  'textarea',
  'number',
  'date',
  'photo',
  'signature',
] as const

export interface ApiQuestionTypeSpec {
  questionType: string
  allowNa: boolean
  maxScore?: number
  maxValue?: number
}

const FE_TO_API: Record<QuestionType, ApiQuestionTypeSpec> = {
  yes_no: { questionType: 'yes_no', allowNa: false },
  yes_no_na: { questionType: 'yes_no', allowNa: true },
  scale_1_5: { questionType: 'rating', allowNa: false, maxScore: 5, maxValue: 5 },
  scale_1_10: { questionType: 'rating', allowNa: false, maxScore: 10, maxValue: 10 },
  text_short: { questionType: 'text', allowNa: false },
  text_long: { questionType: 'textarea', allowNa: false },
  numeric: { questionType: 'number', allowNa: false },
  date: { questionType: 'date', allowNa: false },
  photo: { questionType: 'photo', allowNa: false },
  signature: { questionType: 'signature', allowNa: false },
  multi_choice: { questionType: 'radio', allowNa: false },
  checklist: { questionType: 'checkbox', allowNa: false },
  pass_fail: { questionType: 'pass_fail', allowNa: false },
}

export function toApiQuestionType(feType: QuestionType): ApiQuestionTypeSpec {
  const spec = FE_TO_API[feType]
  if (!spec) {
    throw new Error(`Unknown frontend builder question type: ${feType}`)
  }
  return spec
}

export interface FromApiQuestionTypeOptions {
  allowNa?: boolean
  maxScore?: number | null
  maxValue?: number | null
}

/**
 * Map an API question_type (+ metadata) to a frontend builder type.
 *
 * Unavoidable collapses (no distinct palette peer):
 * - datetime → date
 * - dropdown → multi_choice (same as radio)
 * - file → text_short
 * - score → scale via rating metadata (same as rating)
 */
export function fromApiQuestionType(
  apiType: string,
  options: FromApiQuestionTypeOptions = {},
): QuestionType {
  const allowNa = options.allowNa ?? false
  const maxScore = options.maxScore
  const maxValue = options.maxValue

  switch (apiType) {
    case 'yes_no':
      return allowNa ? 'yes_no_na' : 'yes_no'
    case 'pass_fail':
      return 'pass_fail'
    case 'date':
    case 'datetime':
      return 'date'
    case 'textarea':
      return 'text_long'
    case 'number':
      return 'numeric'
    case 'photo':
      return 'photo'
    case 'signature':
      return 'signature'
    case 'radio':
    case 'dropdown':
      return 'multi_choice'
    case 'checkbox':
      return 'checklist'
    case 'rating':
    case 'score': {
      const scale = maxScore ?? maxValue ?? 5
      return scale > 5 ? 'scale_1_10' : 'scale_1_5'
    }
    case 'text':
      return 'text_short'
    case 'file':
      return 'text_short'
    default:
      return 'text_short'
  }
}
