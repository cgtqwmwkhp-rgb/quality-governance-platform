import { describe, expect, it } from 'vitest'
import {
  buildCampaignPayload,
  canLaunchCampaign,
  parseSpecificUserIds,
} from '../documentCampaignHelpers'

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
})
