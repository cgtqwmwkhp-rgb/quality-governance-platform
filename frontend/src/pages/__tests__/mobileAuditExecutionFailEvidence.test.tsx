import { describe, expect, it } from 'vitest'
import {
  canAdvancePastFailEvidenceGate,
  isFailEvidenceGateActive,
  isQuestionFinding,
  shouldShowFailEvidencePanel,
} from '../AuditExecution'

describe('MobileAuditExecution fail evidence parity', () => {
  const actionQuestion = {
    type: 'yes_no',
    positiveAnswer: undefined,
    evidenceRequired: false,
    failureTriggersAction: true,
  }

  it('shares desktop gate rules for inverted NO findings', () => {
    expect(isQuestionFinding(actionQuestion, 'no')).toBe(true)
    expect(
      isFailEvidenceGateActive(actionQuestion, { response: 'no', evidenceAssetIds: [] }),
    ).toBe(true)
    expect(
      shouldShowFailEvidencePanel(actionQuestion, { response: 'no' }),
    ).toBe(true)
    expect(
      canAdvancePastFailEvidenceGate(actionQuestion, {
        response: 'no',
        evidenceAssetIds: [12],
      }),
    ).toBe(true)
  })
})
