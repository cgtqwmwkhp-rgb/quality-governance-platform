import { describe, expect, it } from 'vitest'

import { buildQuestionPayload, mapApiToTemplate } from './templateHelpers'

describe('templateHelpers', () => {
  it('maps backend questions into builder state without losing evidence or auto-action flags', () => {
    const sectionIdMap: Record<string, number> = {}
    const questionIdMap: Record<string, number> = {}

    const template = mapApiToTemplate(
      {
        id: 7,
        name: 'Forklift inspection',
        description: 'Warehouse audit',
        version: 3,
        is_published: false,
        category: 'safety',
        scoring_method: 'weighted',
        passing_score: 80,
        created_at: '2026-03-20T10:00:00Z',
        updated_at: '2026-03-20T10:30:00Z',
        sections: [
          {
            id: 11,
            title: 'Vehicle',
            description: 'Core checks',
            weight: 1,
            sort_order: 0,
            questions: [
              {
                id: 13,
                question_text: 'Capture defect photo',
                question_type: 'yes_no',
                is_required: true,
                allow_na: true,
                weight: 2,
                evidence_requirements: {
                  required: true,
                  min_attachments: 1,
                  allowed_types: ['image'],
                  require_photo: true,
                },
                failure_triggers_action: true,
                risk_category: 'high',
                help_text: 'Upload a clear image for any failure',
                positive_answer: 'yes',
              },
            ],
          },
        ],
      },
      sectionIdMap,
      questionIdMap,
    )

    const question = template.sections[0]?.questions[0]
    expect(question).toMatchObject({
      type: 'yes_no_na',
      evidenceRequired: true,
      evidenceType: 'photo',
      failureTriggersAction: true,
      riskLevel: 'high',
      guidance: 'Upload a clear image for any failure',
    })
    expect(sectionIdMap['11']).toBe(11)
    expect(questionIdMap['13']).toBe(13)
  })

  it('builds canonical backend payloads from builder question types', () => {
    const payload = buildQuestionPayload(
      {
        id: 'q-1',
        text: 'Rate housekeeping',
        type: 'scale_1_10',
        required: true,
        weight: 1.5,
        evidenceRequired: true,
        evidenceType: 'document',
        failureTriggersAction: true,
        positiveAnswer: 'yes',
        options: [],
      },
      4,
      99,
    )

    expect(payload).toMatchObject({
      section_id: 99,
      question_type: 'rating',
      max_score: 10,
      max_value: 10,
      allow_na: false,
      failure_triggers_action: true,
      evidence_requirements: {
        required: true,
        min_attachments: 1,
        allowed_types: ['document'],
      },
    })
  })
})
