import { describe, expect, it } from 'vitest'

import { buildQuestionPayload, buildSectionPayload, mapApiToTemplate } from './templateHelpers'
import {
  EXECUTABLE_QUESTION_TYPES,
  UNSUPPORTED_PUBLISH_QUESTION_TYPES,
  buildApplicabilityRulesPayload,
  getUnpublishableQuestionIssues,
  isPublishableQuestionType,
  remapConditionalLogicSourceIds,
} from './templateHelpers'

describe('templateHelpers', () => {
  it('exposes publishable type guardrails aligned with PR-A backend', () => {
    expect(EXECUTABLE_QUESTION_TYPES).toContain('photo')
    expect(UNSUPPORTED_PUBLISH_QUESTION_TYPES).toContain('file')
    expect(isPublishableQuestionType('radio')).toBe(true)
    expect(isPublishableQuestionType('file')).toBe(false)
    expect(isPublishableQuestionType('unknown_type')).toBe(false)
  })

  it('publishes the entity-select question types added for user/location/customer pickers', () => {
    expect(EXECUTABLE_QUESTION_TYPES).toContain('user_select')
    expect(EXECUTABLE_QUESTION_TYPES).toContain('location_select')
    expect(EXECUTABLE_QUESTION_TYPES).toContain('customer_select')
    expect(isPublishableQuestionType('user_select')).toBe(true)
    expect(isPublishableQuestionType('location_select')).toBe(true)
    expect(isPublishableQuestionType('customer_select')).toBe(true)
  })

  it('flags unpublishable API question types', () => {
    expect(isPublishableQuestionType('file')).toBe(false)
    expect(getUnpublishableQuestionIssues([])).toEqual([])
  })

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

  it('maps criticality and conditional_logic from backend questions', () => {
    const sectionIdMap: Record<string, number> = {}
    const questionIdMap: Record<string, number> = {}

    const template = mapApiToTemplate(
      {
        id: 8,
        name: 'Lifting equipment inspection',
        description: '',
        version: 1,
        is_published: false,
        category: 'safety',
        scoring_method: 'weighted',
        passing_score: 80,
        created_at: '2026-03-20T10:00:00Z',
        sections: [
          {
            id: 21,
            title: 'Structural checks',
            weight: 1,
            sort_order: 0,
            applicability_rules: { assessment_modes: ['full'], asset_type_ids: [3, 4] },
            questions: [
              {
                id: 31,
                question_text: 'Are the chains free of damage?',
                question_type: 'yes_no',
                criticality: 'essential',
                conditional_logic: [
                  { source_question_id: 30, operator: 'equals', value: 'yes', action: 'show' },
                ],
              },
            ],
          },
        ],
      },
      sectionIdMap,
      questionIdMap,
    )

    const section = template.sections[0]
    const question = section.questions[0]
    expect(question.criticality).toBe('essential')
    expect(question.conditionalLogicRules).toEqual([
      { source_question_id: 30, operator: 'equals', value: 'yes', action: 'show' },
    ])
    expect(section.applicabilityRules).toEqual({
      assessmentModes: ['full'],
      assetTypeIds: [3, 4],
    })
  })

  it('ignores unrecognized criticality values from the backend', () => {
    const template = mapApiToTemplate(
      {
        id: 9,
        name: 'Test',
        version: 1,
        is_published: false,
        created_at: '2026-01-01T00:00:00Z',
        sections: [
          {
            id: 1,
            title: 'Section',
            weight: 1,
            sort_order: 0,
            questions: [
              { id: 1, question_text: 'Q1', question_type: 'yes_no', criticality: 'nonsense' },
            ],
          },
        ],
      },
      {},
      {},
    )
    expect(template.sections[0].questions[0].criticality).toBeUndefined()
  })

  it('builds question payloads carrying criticality and conditional_logic rules', () => {
    const payload = buildQuestionPayload(
      {
        id: 'q-2',
        text: 'Any spillages found?',
        type: 'yes_no',
        required: true,
        weight: 1,
        evidenceRequired: false,
        failureTriggersAction: false,
        criticality: 'essential',
        conditionalLogicRules: [
          { source_question_id: 'q-1', operator: 'equals', value: 'yes', action: 'show' },
        ],
      },
      0,
      5,
    )

    expect(payload).toMatchObject({
      section_id: 5,
      criticality: 'essential',
      conditional_logic: [{ source_question_id: 'q-1', operator: 'equals', value: 'yes', action: 'show' }],
    })
  })

  it('sends null conditional_logic when a question has no rules', () => {
    const payload = buildQuestionPayload(
      {
        id: 'q-3',
        text: 'Is area clean?',
        type: 'yes_no',
        required: true,
        weight: 1,
        evidenceRequired: false,
        failureTriggersAction: false,
      },
      0,
      5,
    )
    expect(payload.conditional_logic).toBeNull()
  })

  it('builds section applicability_rules payloads, collapsing empty arrays to null', () => {
    expect(
      buildApplicabilityRulesPayload({ assessmentModes: ['full'], assetTypeIds: [1, 2] }),
    ).toEqual({ assessment_modes: ['full'], asset_type_ids: [1, 2] })
    expect(buildApplicabilityRulesPayload({ assessmentModes: [], assetTypeIds: [] })).toBeNull()
    expect(buildApplicabilityRulesPayload(null)).toBeNull()
    expect(buildApplicabilityRulesPayload(undefined)).toBeNull()
  })

  it('remaps conditional_logic source_question_id from client ids to persisted DB ids', () => {
    const questionIdMap: Record<string, number> = { 'client-abc': 101, 'client-def': 102 }
    const remapped = remapConditionalLogicSourceIds(
      [
        { source_question_id: 'client-abc', operator: 'equals', value: 'yes', action: 'show' },
        { source_question_id: 'client-def', operator: 'is_empty', action: 'hide' },
      ],
      questionIdMap,
    )
    expect(remapped).toEqual([
      { source_question_id: 101, operator: 'equals', value: 'yes', action: 'show' },
      { source_question_id: 102, operator: 'is_empty', action: 'hide' },
    ])
  })

  it('leaves already-numeric (or unmapped) source_question_id untouched when remapping', () => {
    const rules = [{ source_question_id: 30, operator: 'equals' as const, value: 'yes', action: 'show' as const }]
    expect(remapConditionalLogicSourceIds(rules, {})).toEqual(rules)
    expect(remapConditionalLogicSourceIds(null, {})).toBeNull()
    expect(remapConditionalLogicSourceIds(undefined, {})).toBeUndefined()
    expect(remapConditionalLogicSourceIds([], { a: 1 })).toEqual([])
  })

  it('buildSectionPayload carries applicability_rules through to the API payload', () => {
    const payload = buildSectionPayload(
      {
        title: 'Vehicle checks',
        description: 'Core checks',
        weight: 1,
        applicabilityRules: { assessmentModes: ['spot_check'], assetTypeIds: null },
      },
      2,
    )
    expect(payload).toMatchObject({
      title: 'Vehicle checks',
      sort_order: 2,
      applicability_rules: { assessment_modes: ['spot_check'], asset_type_ids: null },
    })
  })
})
