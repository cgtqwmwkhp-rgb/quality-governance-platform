import { describe, expect, it } from 'vitest'

import {
  buildSaveIssueModel,
  firstIssueQuestionId,
  fromPublishValidationErrors,
  parseFieldPathMessage,
} from '../saveErrorModel'

describe('saveErrorModel', () => {
  it('parses FastAPI 422 detail arrays with loc/msg (extra forbid)', () => {
    const model = buildSaveIssueModel(
      {
        response: {
          data: {
            detail: [
              {
                type: 'extra_forbidden',
                loc: ['body', 'risk_category'],
                msg: 'Extra inputs are not permitted',
                input: 'high',
              },
            ],
          },
        },
      },
      { questionId: 'q-13', sectionTitle: 'Vehicle', questionText: 'Capture defect photo' },
    )

    expect(model.issues).toHaveLength(1)
    expect(model.issues[0]).toMatchObject({
      field: 'risk_category',
      label: 'Risk level on a question',
      questionId: 'q-13',
      context: 'Vehicle: Capture defect photo',
      locPath: 'body -> risk_category',
    })
    expect(model.issues[0].action).toMatch(/Risk level \/ criticality/i)
    expect(model.summary).toMatch(/Risk level/i)
    expect(firstIssueQuestionId(model)).toBe('q-13')
  })

  it('parses string messages like body -> risk_category: Extra inputs…', () => {
    const parsed = parseFieldPathMessage('body -> risk_category: Extra inputs are not permitted')
    expect(parsed).toEqual({
      field: 'risk_category',
      locPath: 'body -> risk_category',
      msg: 'Extra inputs are not permitted',
    })

    const model = buildSaveIssueModel({
      response: {
        data: { detail: 'body -> risk_category: Extra inputs are not permitted' },
      },
    })
    expect(model.issues[0].field).toBe('risk_category')
    expect(model.issues[0].label).toBe('Risk level on a question')
    expect(model.issues[0].action.length).toBeGreaterThan(10)
  })

  it('handles nested detail objects with errors list', () => {
    const model = buildSaveIssueModel({
      response: {
        data: {
          detail: {
            message: 'Validation failed',
            errors: [
              { loc: ['body', 'question_text'], msg: 'Field required' },
              { loc: ['body', 'weight'], msg: 'ensure this value is greater than 0' },
            ],
          },
        },
      },
    })
    expect(model.issues).toHaveLength(2)
    expect(model.issues[0].field).toBe('question_text')
    expect(model.issues[1].field).toBe('weight')
    expect(model.summary).toMatch(/2 issues/i)
  })

  it('maps publish validation errors into the same issue shape', () => {
    const model = fromPublishValidationErrors(
      [
        'Template name is required.',
        'Vehicle, question 1: Question text is required.',
      ],
      { questionErrors: { 'q-1': ['Question text is required.'] }, firstQuestionId: 'q-1' },
    )
    expect(model.issues).toHaveLength(2)
    expect(model.issues[0].field).toBe('name')
    expect(model.issues[1].questionId).toBe('q-1')
    expect(model.summary).toMatch(/2 validation issues/i)
  })

  it('falls back for generic Error without API detail', () => {
    const model = buildSaveIssueModel(new Error('Network down'))
    expect(model.issues[0].raw).toBe('Network down')
    expect(model.summary).toMatch(/Save failed|Couldn’t save|Network/i)
  })
})
