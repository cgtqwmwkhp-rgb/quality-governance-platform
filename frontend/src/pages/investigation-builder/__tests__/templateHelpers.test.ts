import { describe, expect, it } from 'vitest'
import { fromApiQuestionType, toApiQuestionType } from '../../audit-builder/questionTypeRegistry'
import {
  buildStructurePayload,
  buildTemplateCreatePayload,
  mapApiToDraft,
} from '../templateHelpers'
import type { InvestigationTemplateDraft } from '../types'

describe('investigation-builder templateHelpers', () => {
  it('round-trips builder question types through API structure', () => {
    const draft: InvestigationTemplateDraft = {
      name: 'RCA',
      description: 'Root cause',
      version: '1.0',
      is_active: true,
      applicable_entity_types: ['complaint'],
      sections: [
        {
          id: 'sec-1',
          name: 'Overview',
          fields: [
            { id: 'f-1', label: 'Summary', type: 'text_long', required: true },
            { id: 'f-2', label: 'Severity', type: 'scale_1_5', required: false },
          ],
        },
      ],
    }

    const payload = buildTemplateCreatePayload(draft)
    expect(payload.structure.sections[0].fields[0]).toMatchObject({
      question_type: 'textarea',
      type: 'textarea',
      label: 'Summary',
      required: true,
    })
    expect(payload.structure.sections[0].fields[1]).toMatchObject({
      question_type: 'rating',
      max_score: 5,
    })

    const restored = mapApiToDraft({
      id: 1,
      name: draft.name,
      description: draft.description,
      version: draft.version,
      is_active: draft.is_active,
      applicable_entity_types: draft.applicable_entity_types,
      structure: payload.structure,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    })

    expect(restored.sections[0].fields[0].type).toBe('text_long')
    expect(restored.sections[0].fields[1].type).toBe('scale_1_5')
  })

  it('uses registry mapping for yes/no with N/A', () => {
    const structure = buildStructurePayload({
      name: '',
      description: '',
      version: '1.0',
      is_active: true,
      applicable_entity_types: ['near_miss'],
      sections: [
        {
          id: 's1',
          name: 'Check',
          fields: [{ id: 'q1', label: 'Applicable?', type: 'yes_no_na', required: true }],
        },
      ],
    })

    const field = structure.sections[0].fields[0]
    expect(field.question_type).toBe(toApiQuestionType('yes_no_na').questionType)
    expect(field.allow_na).toBe(true)

    const feType = fromApiQuestionType(String(field.question_type), { allowNa: field.allow_na })
    expect(feType).toBe('yes_no_na')
  })
})
