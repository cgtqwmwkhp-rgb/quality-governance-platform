import { AxiosError, type InternalAxiosRequestConfig } from 'axios'
import { describe, expect, it } from 'vitest'

import {
  buildAuditResponseSavePayload,
  formatMissingQuestionsMessage,
  mergeAuditResponseJson,
  parseMissingQuestionIdsFromError,
  responseRowIsEmpty,
} from '../auditAnswerIntegrity'
import { scorePayloadForQuestion } from '../AuditExecution'

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
})
