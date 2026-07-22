import { AxiosError, type InternalAxiosRequestConfig } from 'axios'
import { describe, expect, it } from 'vitest'

import {
  buildAuditResponseSavePayload,
  formatMissingQuestionsMessage,
  mergeAuditResponseJson,
  parseMissingQuestionIdsFromError,
  responseRowIsEmpty,
} from '../auditAnswerIntegrity'
import { calculateVisibleRunScore, scorePayloadForQuestion } from '../AuditExecution'

describe('auditAnswerIntegrity helpers', () => {
  it('merges evidence_asset_ids with checklist selected values', () => {
    expect(
      mergeAuditResponseJson(
        { response: ['a', 'b'], evidenceAssetIds: [10, 11] },
        'checklist',
      ),
    ).toEqual({
      evidence_asset_ids: [10, 11],
      selected: ['a', 'b'],
    })
  })

  it('persists is_na and radio selected in save payloads', () => {
    const payload = buildAuditResponseSavePayload(
      { response: 'na', notes: 'not applicable here' },
      {
        type: 'yes_no_na',
        weight: 1,
        maxScore: 1,
        positiveAnswer: 'yes',
      },
      scorePayloadForQuestion,
    )
    expect(payload.is_na).toBe(true)
    expect(payload.response_value).toBe('na')

    const radioPayload = buildAuditResponseSavePayload(
      { response: 'major' },
      {
        type: 'multi_choice',
        weight: 1,
        options: [{ value: 'major', label: 'Major' }],
      },
      scorePayloadForQuestion,
    )
    expect(radioPayload.response_json).toEqual({ selected: 'major' })

    const userSelectPayload = buildAuditResponseSavePayload(
      { response: '42', entityLabel: 'Jane Doe' },
      {
        type: 'user_select',
        weight: 1,
      },
      scorePayloadForQuestion,
    )
    expect(userSelectPayload.response_value).toBe('42')
    expect(userSelectPayload.response_json).toEqual({ entity_label: 'Jane Doe' })
    expect(userSelectPayload.score).toBe(1)
  })

  it('treats N/A and evidence rows as non-empty for save', () => {
    expect(responseRowIsEmpty({ response: 'na' })).toBe(false)
    expect(responseRowIsEmpty({ response: null, evidenceAssetIds: [7] })).toBe(false)
    expect(responseRowIsEmpty({ response: null })).toBe(true)
  })

  it('parses missing_question_ids from unified API error envelope', () => {
    const error = new AxiosError('Request failed', 'ERR_BAD_REQUEST')
    error.response = {
      status: 400,
      statusText: 'Bad Request',
      headers: {},
      config: {} as InternalAxiosRequestConfig,
      data: {
        error: {
          message: 'All required audit questions must be answered before completion',
          details: {
            missing_question_ids: [12, 15],
          },
        },
      },
    }

    expect(parseMissingQuestionIdsFromError(error)).toEqual([12, 15])
    expect(formatMissingQuestionsMessage(2)).toMatch(/2 required questions/)
  })

  it('live score ignores answers on hidden questions', () => {
    const questions = [
      { id: '1', type: 'pass_fail', maxScore: 1, positiveAnswer: 'pass' as const },
      { id: '2', type: 'pass_fail', maxScore: 1, positiveAnswer: 'pass' as const },
    ]
    const responses = {
      '1': { response: 'pass' },
      '2': { response: 'fail' },
    }
    const allVisible = calculateVisibleRunScore(questions, responses, () => true)
    expect(allVisible).toBe(50)

    const hiddenFail = calculateVisibleRunScore(questions, responses, (q) => q.id !== '2')
    expect(hiddenFail).toBe(100)
  })
})
