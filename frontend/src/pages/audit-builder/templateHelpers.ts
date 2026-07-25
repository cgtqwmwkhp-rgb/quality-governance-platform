import type {
  AuditTemplate,
  Section,
  Question,
  QuestionType,
  ScoringMethod,
  QuestionStandardLink,
  ConditionalLogicRule,
  QuestionCriticality,
  SectionApplicabilityRules,
} from './types'
import type {
  AuditQuestionCreate,
  AuditQuestionUpdate,
  AuditSectionCreate,
  EvidenceRequirement,
} from '../../api/client'
import { generateId, createNewSection, SECTION_COLORS } from './types'
import { fromApiQuestionType, toApiQuestionType } from './questionTypeRegistry'
import { mergeSuggestedLinks } from '../builderMapAssistHonesty'
import type { MapW3StandardLink } from '../mapW3StaleRescoreHonesty'

const VALID_CRITICALITIES: QuestionCriticality[] = ['essential', 'required', 'good_to_have']

function mapCriticalityFromApi(value: unknown): QuestionCriticality | undefined {
  return VALID_CRITICALITIES.includes(value as QuestionCriticality)
    ? (value as QuestionCriticality)
    : undefined
}

function mapApplicabilityRulesFromApi(
  raw: unknown,
): SectionApplicabilityRules | undefined {
  if (!raw || typeof raw !== 'object') return undefined
  const rules = raw as { assessment_modes?: string[] | null; asset_type_ids?: number[] | null }
  if (!rules.assessment_modes && !rules.asset_type_ids) return undefined
  return {
    assessmentModes: rules.assessment_modes ?? null,
    assetTypeIds: rules.asset_type_ids ?? null,
  }
}

/**
 * Remap `conditional_logic[].source_question_id` from builder client ids
 * (generated string ids used while editing an unsaved question) to the
 * persisted numeric DB ids, using the same `questionIdMap` populated by the
 * create/update save loop. Rules already carrying a numeric/mapped id (e.g.
 * loaded from the API) pass through unchanged.
 */
export function remapConditionalLogicSourceIds(
  rules: ConditionalLogicRule[] | null | undefined,
  questionIdMap: Record<string, number>,
): ConditionalLogicRule[] | null | undefined {
  if (!rules || rules.length === 0) return rules
  return rules.map((rule) => {
    const backendId = questionIdMap[String(rule.source_question_id)]
    return backendId !== undefined ? { ...rule, source_question_id: backendId } : rule
  })
}

export function buildApplicabilityRulesPayload(
  rules: SectionApplicabilityRules | null | undefined,
): AuditSectionCreate['applicability_rules'] {
  if (!rules) return null
  const assessmentModes = rules.assessmentModes && rules.assessmentModes.length > 0 ? rules.assessmentModes : null
  const assetTypeIds = rules.assetTypeIds && rules.assetTypeIds.length > 0 ? rules.assetTypeIds : null
  if (!assessmentModes && !assetTypeIds) return null
  return { assessment_modes: assessmentModes, asset_type_ids: assetTypeIds }
}

/** Backend question types executable in AuditExecution (mirrors PR-A publish gate). */
export const EXECUTABLE_QUESTION_TYPES = [
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
  'rating',
  'yes_no',
  'pass_fail',
  'score',
  'user_select',
  'location_select',
  'customer_select',
] as const

/** Rejected at publish until execution + persistence exist. */
export const UNSUPPORTED_PUBLISH_QUESTION_TYPES = ['file'] as const

export function isPublishableQuestionType(questionType: string | undefined | null): boolean {
  if (!questionType) return false
  if ((UNSUPPORTED_PUBLISH_QUESTION_TYPES as readonly string[]).includes(questionType)) {
    return false
  }
  return (EXECUTABLE_QUESTION_TYPES as readonly string[]).includes(questionType)
}

export function getUnpublishableQuestionIssues(sections: Section[]): string[] {
  const issues: string[] = []
  sections.forEach((section, sectionIndex) => {
    section.questions.forEach((question, questionIndex) => {
      let apiType: string
      try {
        apiType = toApiQuestionType(question.type).questionType
      } catch {
        issues.push(
          `${section.title || `Section ${sectionIndex + 1}`}, question ${questionIndex + 1}: unknown question type.`,
        )
        return
      }
      if (!isPublishableQuestionType(apiType)) {
        issues.push(
          `${section.title || `Section ${sectionIndex + 1}`}, question ${questionIndex + 1}: "${apiType}" is not publishable (execution support missing).`,
        )
      }
    })
  })
  return issues
}

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
  regulatory_reference?: string | null
  assessor_guidance?: Record<string, unknown> | null
  assessor_guidance_json?: Record<string, unknown> | null
  criticality?: string | null
  conditional_logic?: ConditionalLogicRule[] | null
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

function mapStandardLinksFromGuidance(
  questionId: string,
  guidance: Record<string, unknown> | null | undefined,
): QuestionStandardLink[] {
  const raw = guidance?.map_standard_links
  if (!Array.isArray(raw)) return []
  const allowed = new Set(['suggested', 'accepted', 'rejected', 'stale'])
  return raw
    .filter((row): row is Record<string, unknown> => Boolean(row) && typeof row === 'object')
    .map((row) => {
      const statusRaw = String(row.status ?? 'suggested')
      const status = (
        allowed.has(statusRaw) ? statusRaw : 'suggested'
      ) as QuestionStandardLink['status']
      return {
        id: String(row.id ?? `${questionId}-${row.refId ?? row.ref_id}`),
        questionId: String(row.questionId ?? questionId),
        scheme: String(row.scheme ?? 'ISO'),
        refId: String(row.refId ?? row.ref_id ?? ''),
        label: String(row.label ?? row.refId ?? row.ref_id ?? ''),
        confidence: Number(row.confidence ?? 0),
        status,
        sourceFingerprint: String(row.sourceFingerprint ?? ''),
        libraryVersion: String(row.libraryVersion ?? 'builder-map-v1'),
      }
    })
    .filter((link) => link.refId)
}

function mapApiQuestion(q: BackendQuestion, questionIdMap: Record<string, number>): Question {
  const id = String(q.id)
  questionIdMap[id] = q.id
  const guidance = q.assessor_guidance ?? q.assessor_guidance_json ?? null
  const standardLinks = mapStandardLinksFromGuidance(id, guidance)
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
    isoClause: q.regulatory_reference || undefined,
    standardLinks,
    criticality: mapCriticalityFromApi(q.criticality),
    conditionalLogicRules: q.conditional_logic ?? undefined,
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
      applicabilityRules: mapApplicabilityRulesFromApi(s.applicability_rules ?? s.applicability_rules_json),
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

/** Group raw Assist Map suggestions (builder or Check & Challenge coach) by question id. */
function groupStandardSuggestionsByQuestion(
  standardSuggestions: unknown[] | undefined,
): Map<string, MapW3StandardLink[]> {
  const byQuestion = new Map<string, MapW3StandardLink[]>()
  for (const raw of standardSuggestions || []) {
    if (!raw || typeof raw !== 'object') continue
    const row = raw as Record<string, unknown>
    const questionId = String(row.questionId ?? row.question_id ?? '')
    const refId = String(row.refId ?? row.ref_id ?? '')
    if (!questionId || !refId) continue
    const link: MapW3StandardLink = {
      id: String(row.id ?? `sug_${questionId}_${refId}`),
      questionId,
      scheme: String(row.scheme ?? 'ISO'),
      refId,
      label: String(row.label ?? refId),
      confidence: Number(row.confidence ?? 0),
      status: 'suggested',
      sourceFingerprint: String(row.sourceFingerprint ?? ''),
      libraryVersion: String(row.libraryVersion ?? 'builder-map-v1'),
    }
    const list = byQuestion.get(questionId) || []
    list.push(link)
    byQuestion.set(questionId, list)
  }
  return byQuestion
}

export function mapAISectionsToLocal(
  generatedSections: any[],
  existingSectionCount: number,
  standardSuggestions?: unknown[],
): Section[] {
  const suggestionsByQuestion = groupStandardSuggestionsByQuestion(standardSuggestions)
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
      standardLinks: mergeSuggestedLinks([], suggestionsByQuestion.get(String(q.id)) || []),
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
    criticality: q.criticality,
    conditional_logic: q.conditionalLogicRules?.length ? q.conditionalLogicRules : null,
  }
  if (sectionId !== undefined) return { ...base, section_id: sectionId }
  return base
}

/** Build the section create/update payload, including composition rules. */
export function buildSectionPayload(
  section: Pick<Section, 'title' | 'description' | 'weight' | 'applicabilityRules'>,
  sortOrder: number,
): AuditSectionCreate {
  return {
    title: section.title,
    description: section.description,
    sort_order: sortOrder,
    weight: section.weight,
    applicability_rules: buildApplicabilityRulesPayload(section.applicabilityRules),
  }
}
