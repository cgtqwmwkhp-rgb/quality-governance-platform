import { describe, expect, it } from 'vitest'

import {
  buildSaveIssueModel,
  classifySaveTimeout,
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

describe('saveErrorModel timeout classification', () => {
  /** Shape the axios response interceptor produces for a write timeout. */
  const interceptorTimeout = (method = 'patch') => ({
    code: 'ECONNABORTED',
    message: 'timeout of 45000ms exceeded',
    isTimeout: true,
    maybeCommitted: true,
    classifiedMessage:
      'Request timed out. Your changes may already have been saved — refresh or check the list before trying again.',
    config: { method },
  })

  it('classifies an interceptor-flagged write timeout as maybe-committed', () => {
    expect(classifySaveTimeout(interceptorTimeout())).toEqual({
      isTimeout: true,
      maybeCommitted: true,
    })
  })

  it('classifies a raw axios timeout with no interceptor flags', () => {
    expect(
      classifySaveTimeout({
        code: 'ECONNABORTED',
        message: 'timeout of 45000ms exceeded',
        config: { method: 'post' },
      }),
    ).toEqual({ isTimeout: true, maybeCommitted: true })
    expect(
      classifySaveTimeout({ code: 'ECONNABORTED', message: 'timeout', config: { method: 'get' } }),
    ).toEqual({ isTimeout: true, maybeCommitted: false })
  })

  it('treats gateway timeout statuses as timeouts and other statuses as answers', () => {
    expect(classifySaveTimeout({ response: { status: 504 }, config: { method: 'post' } })).toEqual({
      isTimeout: true,
      maybeCommitted: true,
    })
    // A 422 that happens to mention "timeout" is still a validation answer.
    expect(
      classifySaveTimeout({
        message: 'Request failed with status code 422',
        response: { status: 422, data: { detail: 'session timeout policy invalid' } },
        config: { method: 'patch' },
      }),
    ).toEqual({ isTimeout: false, maybeCommitted: false })
  })

  it('does not classify plain network or validation failures as timeouts', () => {
    expect(classifySaveTimeout(new Error('Network Error'))).toEqual({
      isTimeout: false,
      maybeCommitted: false,
    })
    expect(classifySaveTimeout(undefined)).toEqual({ isTimeout: false, maybeCommitted: false })
  })

  it('builds a timeout model that does not read as a validation problem', () => {
    const model = buildSaveIssueModel(interceptorTimeout(), {
      questionId: 'q-7',
      sectionTitle: 'Vehicle',
      questionText: 'Capture defect photo',
      progress: '6 of 19 questions saved',
    })

    expect(model.isTimeout).toBe(true)
    expect(model.maybeCommitted).toBe(true)
    expect(model.issues).toHaveLength(1)
    expect(model.issues[0].label).toBe('Save timed out')
    expect(model.issues[0].field).toBeNull()
    expect(model.issues[0].context).toBe('6 of 19 questions saved')
    expect(model.summary).toContain('6 of 19 questions saved')
    expect(model.summary).toMatch(/may already have been saved/i)
    expect(model.summary).toMatch(/reload this template/i)
    // Must not imply the author has a field to fix, and must not offer
    // "Show question" (which would frame a timeout as a bad question).
    expect(model.summary).not.toMatch(/Review the highlighted details/i)
    expect(model.issues[0].action).not.toMatch(/Review the highlighted details/i)
    expect(model.issues[0].questionId).toBeUndefined()
    expect(firstIssueQuestionId(model)).toBeUndefined()
  })

  it('tells the user to retry when the timeout could not have committed', () => {
    const model = buildSaveIssueModel({
      code: 'ECONNABORTED',
      message: 'timeout of 30000ms exceeded',
      isTimeout: true,
      maybeCommitted: false,
      config: { method: 'get' },
    })

    expect(model.isTimeout).toBe(true)
    expect(model.maybeCommitted).toBe(false)
    expect(model.summary).toMatch(/check your connection/i)
    expect(model.summary).not.toMatch(/may already have been saved/i)
  })

  it('keeps validation copy for a 422 (no timeout hijack)', () => {
    const model = buildSaveIssueModel({
      response: { status: 422, data: { detail: [{ loc: ['body', 'weight'], msg: 'Field required' }] } },
      config: { method: 'patch' },
    })
    expect(model.isTimeout).toBeUndefined()
    expect(model.issues[0].field).toBe('weight')
  })
})
