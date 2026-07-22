export type QuestionType =
  | 'yes_no'
  | 'yes_no_na'
  | 'scale_1_5'
  | 'scale_1_10'
  | 'text_short'
  | 'text_long'
  | 'numeric'
  | 'date'
  | 'photo'
  | 'signature'
  | 'multi_choice'
  | 'checklist'
  | 'pass_fail'
  | 'user_select'
  | 'location_select'
  | 'customer_select'

export type ScoringMethod = 'weighted' | 'equal' | 'pass_fail' | 'points'

export interface QuestionOption {
  id: string
  label: string
  value: string
  score?: number
  isCorrect?: boolean
}

/** @deprecated Superseded by ConditionalLogicRule[] (array, show/hide semantics). */
export interface ConditionalLogic {
  enabled: boolean
  showWhen: 'equals' | 'not_equals' | 'contains' | 'greater_than' | 'less_than'
  dependsOnQuestionId: string
  value: string
}

/** Mirrors backend `ConditionalLogicRule` (src/api/schemas/audit.py) and the
 * evaluator in `evaluateConditionalLogic.ts` / `audit_conditional.py`. */
export interface ConditionalLogicRule {
  source_question_id: string | number
  operator: 'equals' | 'not_equals' | 'contains' | 'greater_than' | 'less_than' | 'is_empty' | 'is_not_empty'
  value?: string | number | boolean | null
  action: 'show' | 'hide'
}

/** Criticality gates: essential questions block completion + fail the run when
 * answered as a finding; required blocks completion; good_to_have never blocks. */
export type QuestionCriticality = 'essential' | 'required' | 'good_to_have'

/** Section-level composition/branching rule. Null/empty dimension = unrestricted. */
export interface SectionApplicabilityRules {
  assessmentModes?: string[] | null
  assetTypeIds?: number[] | null
}

/** Known assessment modes offered in the builder/execution header. Backend accepts any
 * string (free text up to 50 chars) but these are the modes the UI curates. */
export const ASSESSMENT_MODES: { value: string; label: string }[] = [
  { value: 'full', label: 'Full Assessment' },
  { value: 'spot_check', label: 'Spot Check' },
  { value: 'post_incident', label: 'Post-Incident' },
]

export interface QuestionStandardLink {
  id: string
  questionId: string
  scheme: string
  refId: string
  label: string
  confidence: number
  status: 'suggested' | 'accepted' | 'rejected' | 'stale'
  sourceFingerprint: string
  libraryVersion: string
}

export interface Question {
  id: string
  text: string
  description?: string
  type: QuestionType
  required: boolean
  weight: number
  options?: QuestionOption[]
  /** @deprecated use conditionalLogicRules */
  conditionalLogic?: ConditionalLogic
  /** Show/hide rule array — evaluated with AND semantics (all must pass to show). */
  conditionalLogicRules?: ConditionalLogicRule[]
  evidenceRequired: boolean
  evidenceType?: 'photo' | 'document' | 'signature' | 'any'
  isoClause?: string
  /** Multi-scheme Assist Map links (MAP-01..04) beyond free-text isoClause. */
  standardLinks?: QuestionStandardLink[]
  riskLevel?: 'critical' | 'high' | 'medium' | 'low'
  guidance?: string
  failureTriggersAction: boolean
  tags?: string[]
  positiveAnswer?: 'yes' | 'no'
  /** Essential/required/good_to_have — drives completion gates + the essential-fail scoring override. */
  criticality?: QuestionCriticality
}

export interface Section {
  id: string
  title: string
  description?: string
  icon?: string
  color?: string
  questions: Question[]
  isExpanded: boolean
  weight: number
  order: number
  /** Branching/composition rule: which assessment modes / asset types this section applies to. */
  applicabilityRules?: SectionApplicabilityRules | null
}

export interface AuditTemplate {
  id: string
  name: string
  description: string
  version: string
  status: 'draft' | 'published' | 'archived'
  category: string
  subcategory?: string
  isoStandards: string[]
  sections: Section[]
  scoringMethod: ScoringMethod
  passThreshold: number
  createdAt: string
  updatedAt: string
  createdBy: string
  tags: string[]
  estimatedDuration: number
  isLocked: boolean
}

export const SECTION_COLORS = [
  'from-blue-500 to-cyan-500',
  'from-lime-500 to-teal-500',
  'from-emerald-500 to-green-500',
  'from-orange-500 to-amber-500',
  'from-red-500 to-rose-500',
  'from-indigo-500 to-violet-500',
]

export const generateId = () => Math.random().toString(36).substring(2, 11)

export const createNewQuestion = (): Question => ({
  id: generateId(),
  text: '',
  type: 'yes_no',
  required: true,
  weight: 1,
  evidenceRequired: false,
  failureTriggersAction: false,
})

export const createNewSection = (order: number): Section => ({
  id: generateId(),
  title: `Section ${order}`,
  questions: [],
  isExpanded: true,
  weight: 1,
  order,
  color: SECTION_COLORS[order % SECTION_COLORS.length],
})
