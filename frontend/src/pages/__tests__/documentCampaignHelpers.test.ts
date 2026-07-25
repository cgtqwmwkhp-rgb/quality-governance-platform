import { describe, expect, it } from 'vitest'
import type { CampaignComplianceRow } from '../../api/documentCampaignClient'
import {
  buildCampaignPayload,
  campaignRingLabel,
  campaignRingPercent,
  campaignRingTone,
  canLaunchCampaign,
  parseSpecificUserIds,
} from '../documentCampaignHelpers'

function complianceRow(overrides: Partial<CampaignComplianceRow> = {}): CampaignComplianceRow {
  return {
    campaign_id: 1,
    document_id: 1,
    document_title: 'Doc',
    status: 'active',
    assigned: 10,
    completed: 7,
    pending: 2,
    overdue: 1,
    completion_rate: 70,
    reminder_offsets_hours: [24],
    launched_at: '2026-07-01T00:00:00Z',
    due_within_days: 14,
    ...overrides,
  }
}

describe('documentCampaignHelpers', () => {
  it('parses comma-separated user ids', () => {
    expect(parseSpecificUserIds('1, 2;3  4')).toEqual([1, 2, 3, 4])
    expect(parseSpecificUserIds('abc, 0, -1')).toEqual([])
  })

  it('builds audience-specific payload fields', () => {
    const payload = buildCampaignPayload(10, {
      dueWithinDays: 14,
      requireQuiz: true,
      requireSign: true,
      reminderHours: [720, 24],
      audience: {
        audienceType: 'specific_users',
        department: '',
        role: '',
        groupId: '',
        specificUserIds: '5,6',
        engineerIds: [],
      },
    })
    expect(payload.document_id).toBe(10)
    expect(payload.reminder_hours).toEqual([24, 720])
    expect(payload.audience_user_ids).toEqual([5, 6])
  })

  it('gates launch on approved quiz when require_quiz is enabled', () => {
    expect(canLaunchCampaign(true, false)).toBe(false)
    expect(canLaunchCampaign(true, true)).toBe(true)
    expect(canLaunchCampaign(false, false)).toBe(true)
  })

  it('builds a de-duplicated workforce engineer audience payload', () => {
    const payload = buildCampaignPayload(10, {
      dueWithinDays: 14,
      requireQuiz: false,
      requireSign: true,
      reminderHours: [24],
      audience: {
        audienceType: 'specific_engineers',
        department: '',
        role: '',
        groupId: '',
        specificUserIds: '',
        engineerIds: [8, 3, 8],
      },
    })

    expect(payload.audience_engineer_ids).toEqual([3, 8])
  })
})

describe('campaign ring helpers', () => {
  it('clamps completion_rate into a 0-100 integer', () => {
    expect(campaignRingPercent(complianceRow({ completion_rate: 70.6 }))).toBe(71)
    expect(campaignRingPercent(complianceRow({ completion_rate: -5 }))).toBe(0)
    expect(campaignRingPercent(complianceRow({ completion_rate: 140 }))).toBe(100)
    expect(campaignRingPercent(complianceRow({ completion_rate: Number.NaN }))).toBe(0)
  })

  it('flags destructive tone whenever anything is overdue, regardless of completion', () => {
    expect(campaignRingTone(complianceRow({ completion_rate: 100, overdue: 1 }))).toBe('destructive')
  })

  it('flags success tone at 100% complete with nothing overdue', () => {
    expect(campaignRingTone(complianceRow({ completion_rate: 100, overdue: 0 }))).toBe('success')
  })

  it('flags warning tone while in progress and not overdue', () => {
    expect(campaignRingTone(complianceRow({ completion_rate: 40, overdue: 0 }))).toBe('warning')
  })

  it('labels overdue campaigns explicitly for tooltip/aria text', () => {
    expect(campaignRingLabel(complianceRow({ completion_rate: 70, overdue: 2 }))).toBe(
      'Campaign 70% complete · 2 overdue',
    )
    expect(campaignRingLabel(complianceRow({ completion_rate: 100, overdue: 0 }))).toBe(
      'Campaign 100% complete',
    )
  })
})
