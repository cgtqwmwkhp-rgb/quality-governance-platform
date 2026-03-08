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

export type ScoringMethod = 'weighted' | 'equal' | 'pass_fail' | 'points'

export interface QuestionOption {
  id: string
  label: string
  value: string
  score?: number
  isCorrect?: boolean
}

export interface ConditionalLogic {
  enabled: boolean
  showWhen: 'equals' | 'not_equals' | 'contains' | 'greater_than' | 'less_than'
  dependsOnQuestionId: string
  value: string
}

export interface Question {
  id: string
  text: string
  description?: string
  type: QuestionType
  required: boolean
  weight: number
  options?: QuestionOption[]
  conditionalLogic?: ConditionalLogic
  evidenceRequired: boolean
  evidenceType?: 'photo' | 'document' | 'signature' | 'any'
  isoClause?: string
  riskLevel?: 'critical' | 'high' | 'medium' | 'low'
  guidance?: string
  failureTriggersAction: boolean
  tags?: string[]
  positiveAnswer?: 'yes' | 'no'
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
