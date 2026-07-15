import { toApiQuestionType, fromApiQuestionType } from '../audit-builder/questionTypeRegistry'
import type { InvestigationTemplate } from '../../api/investigationsClient'
import type { InvestigationField, InvestigationSection, InvestigationTemplateDraft } from './types'
import { createEmptyDraft, generateId } from './types'

interface ApiStructureField {
  id?: string
  label?: string
  type?: string
  question_type?: string
  required?: boolean
  allow_na?: boolean
  max_score?: number
  max_value?: number
}

interface ApiStructureSection {
  id?: string
  name?: string
  fields?: ApiStructureField[]
}

export interface ApiStructure extends Record<string, unknown> {
  sections: ApiStructureSection[]
}

function mapApiField(field: ApiStructureField): InvestigationField {
  const apiType = field.question_type ?? field.type ?? 'text'
  return {
    id: field.id ?? generateId(),
    label: field.label ?? '',
    type: fromApiQuestionType(apiType, {
      allowNa: field.allow_na,
      maxScore: field.max_score,
      maxValue: field.max_value,
    }),
    required: field.required ?? false,
  }
}

function mapApiSection(section: ApiStructureSection, index: number): InvestigationSection {
  return {
    id: section.id ?? generateId(),
    name: section.name ?? `Section ${index + 1}`,
    fields: (section.fields ?? []).map(mapApiField),
  }
}

export function mapApiToDraft(template: InvestigationTemplate): InvestigationTemplateDraft {
  const structure = template.structure as unknown as ApiStructure
  const sections = (structure.sections ?? []).map(mapApiSection)

  return {
    name: template.name,
    description: template.description ?? '',
    version: template.version,
    is_active: template.is_active,
    applicable_entity_types: template.applicable_entity_types as InvestigationTemplateDraft['applicable_entity_types'],
    sections: sections.length > 0 ? sections : createEmptyDraft().sections,
  }
}

export function buildStructurePayload(draft: InvestigationTemplateDraft): ApiStructure {
  return {
    sections: draft.sections.map((section) => ({
      id: section.id,
      name: section.name,
      fields: section.fields.map((field) => {
        const spec = toApiQuestionType(field.type)
        return {
          id: field.id,
          label: field.label,
          type: spec.questionType,
          question_type: spec.questionType,
          required: field.required,
          ...(spec.allowNa ? { allow_na: true } : {}),
          ...(spec.maxScore != null ? { max_score: spec.maxScore, max_value: spec.maxValue } : {}),
        }
      }),
    })),
  }
}

export function buildTemplateCreatePayload(draft: InvestigationTemplateDraft) {
  return {
    name: draft.name.trim(),
    description: draft.description.trim() || undefined,
    version: draft.version,
    is_active: draft.is_active,
    applicable_entity_types: draft.applicable_entity_types,
    structure: buildStructurePayload(draft),
  }
}

export function buildTemplateUpdatePayload(draft: InvestigationTemplateDraft) {
  return buildTemplateCreatePayload(draft)
}
