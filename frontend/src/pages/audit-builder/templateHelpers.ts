import type { AuditTemplate, Section, Question, QuestionType, ScoringMethod } from './types'
import type { AuditQuestionCreate, AuditQuestionUpdate, EvidenceRequirement } from '../../api/client'
import { generateId, createNewSection, SECTION_COLORS } from './types'
import { fromApiQuestionType, toApiQuestionType } from './questionTypeRegistry'

type BackendQuestion = {
  id: number
  question_text: string
  description?: string
  question_type?: string
  is_required?: boolean
  weight?: number
  options?: Array<{
    label: string
    value: string
    score?: number
    is_correct?: boolean
  }>
  evidence_requirements?: EvidenceRequirement | null
  failure_triggers_action?: boolean
  risk_category?: string
  help_text?: string
  positive_answer?: 'yes' | 'no'
  allow_na?: boolean
  max_score?: number | null
  max_value?: number | null
}

function mapBackendQuestionType(q: BackendQuestion): QuestionType {
  return fromApiQuestionType(q.question_type ?? 'text', {
    allowNa: q.allow_na,
    maxScore: q.max_score,
    maxValue: q.max_value,
  })
}

function inferEvidenceType(
  evidenceRequirements?: EvidenceRequirement | null,
): Question['evidenceType'] | undefined {
  if (!evidenceRequirements?.required) return undefined
  if (evidenceRequirements.require_signature) return 'signature'
  if (evidenceRequirements.require_photo) return 'photo'
  if (
    evidenceRequirements.allowed_types?.length === 1 &&
    evidenceRequirements.allowed_types[0] === 'document'
  ) {
    return 'document'
  }
  return 'any'
}

function buildEvidenceRequirements(question: Question): EvidenceRequirement | undefined {
  if (!question.evidenceRequired) return undefined

  const allowedTypes =
    question.evidenceType === 'document'
      ? ['document']
      : question.evidenceType === 'photo'
        ? ['image']
        : question.evidenceType === 'signature'
          ? ['image']
          : ['image', 'document', 'video']

  return {
    required: true,
    min_attachments: 1,
    max_attachments: 10,
    allowed_types: allowedTypes,
    require_photo: question.evidenceType === 'photo',
    require_signature: question.evidenceType === 'signature',
  }
}

function mapApiQuestion(q: BackendQuestion, questionIdMap: Record<string, number>): Question {
  const id = String(q.id)
  questionIdMap[id] = q.id
  return {
    id,
    text: q.question_text,
    description: q.description,
    type: mapBackendQuestionType(q),
    required: q.is_required ?? true,
    weight: q.weight ?? 1,
    options: q.options?.map((o: any) => ({
      id: generateId(),
      label: o.label,
      value: o.value,
      score: o.score,
      isCorrect: o.is_correct,
    })),
    evidenceRequired: Boolean(q.evidence_requirements?.required),
    evidenceType: inferEvidenceType(q.evidence_requirements),
    failureTriggersAction: q.failure_triggers_action ?? false,
    riskLevel: q.risk_category as Question['riskLevel'],
    guidance: q.help_text,
    positiveAnswer: q.positive_answer || undefined,
  }
}

export function mapApiToTemplate(
  data: any,
  sectionIdMap: Record<string, number>,
  questionIdMap: Record<string, number>,
): AuditTemplate {
  const mappedSections: Section[] = data.sections.map((s: any, idx: number) => {
    const id = String(s.id)
    sectionIdMap[id] = s.id
    return {
      id,
      title: s.title,
      description: s.description,
      questions: s.questions.map((q: any) => mapApiQuestion(q, questionIdMap)),
      isExpanded: true,
      weight: s.weight,
      order: s.sort_order,
      color: SECTION_COLORS[idx % SECTION_COLORS.length],
    }
  })

  return {
    id: String(data.id),
    name: data.name,
    description: data.description || '',
    version: String(data.version),
    status: data.is_published ? 'published' : 'draft',
    category: data.category || 'quality',
    isoStandards: [],
    sections: mappedSections.length > 0 ? mappedSections : [createNewSection(1)],
    scoringMethod: (data.scoring_method || 'weighted') as ScoringMethod,
    passThreshold: data.passing_score || 80,
    createdAt: data.created_at,
    updatedAt: data.updated_at || data.created_at,
    createdBy: 'Current User',
    tags: [],
    estimatedDuration: 60,
    isLocked: false,
  }
}

export function mapAISectionsToLocal(
  generatedSections: any[],
  existingSectionCount: number,
): Section[] {
  return generatedSections.map((gs, idx) => ({
    id: gs.id,
    title: gs.title,
    description: gs.description,
    questions: gs.questions.map((q: any) => ({
      id: q.id,
      text: q.text,
      type: q.type as QuestionType,
      required: q.required,
      weight: q.weight,
      riskLevel: q.riskLevel as Question['riskLevel'],
      evidenceRequired: q.evidenceRequired,
      isoClause: q.isoClause,
      guidance: q.guidance,
      failureTriggersAction: false,
    })),
    isExpanded: true,
    weight: 1,
    order: existingSectionCount + idx,
    color: SECTION_COLORS[(existingSectionCount + idx) % SECTION_COLORS.length],
  }))
}

export function buildQuestionPayload(q: Question, sortOrder: number): AuditQuestionUpdate
export function buildQuestionPayload(
  q: Question,
  sortOrder: number,
  sectionId: number,
): AuditQuestionCreate
export function buildQuestionPayload(
  q: Question,
  sortOrder: number,
  sectionId?: number,
): AuditQuestionCreate | AuditQuestionUpdate {
  const apiType = toApiQuestionType(q.type)
  const base = {
    question_text: q.text,
    question_type: apiType.questionType,
    description: q.description,
    help_text: q.guidance,
    is_required: q.required,
    allow_na: apiType.allowNa,
    max_score: apiType.maxScore,
    max_value: apiType.maxValue,
    weight: q.weight,
    sort_order: sortOrder,
    options: q.options?.length
      ? q.options.map((o) => ({
          value: o.value,
          label: o.label,
          score: o.score,
          is_correct: o.isCorrect,
        }))
      : undefined,
    evidence_requirements: buildEvidenceRequirements(q),
    failure_triggers_action: q.failureTriggersAction,
    risk_category: q.riskLevel,
    positive_answer: q.positiveAnswer || undefined,
  }
  if (sectionId !== undefined) return { ...base, section_id: sectionId }
  return base
}
