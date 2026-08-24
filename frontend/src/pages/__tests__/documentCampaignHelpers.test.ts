import { describe, expect, it } from 'vitest'
import type { CampaignComplianceRow } from '../../api/documentCampaignClient'
import {
  buildCampaignPayload,
  campaignReference,
  campaignRingLabel,
  campaignRingPercent,
  campaignRingTone,
  canLaunchCampaign,
  formatCampaignListLabel,
  formatCampaignReference,
  isUatCampaignArtefact,
  parseSpecificUserIds,
  partitionUatCampaigns,
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

describe('campaign reference + UAT honesty (PX-222 / PX-221)', () => {
  it('formats CAM-YYYY-NNNN references', () => {
    expect(formatCampaignReference(16, '2026-03-01T00:00:00Z')).toBe('CAM-2026-0016')
    expect(formatCampaignReference(3, new Date('2025-12-15T00:00:00Z'))).toBe('CAM-2025-0003')
  })

  it('prefers title in list labels when present', () => {
    expect(
      formatCampaignListLabel({
        id: 16,
        title: 'Policy read',
        launched_at: '2026-01-10T00:00:00Z',
        created_at: '2026-01-01T00:00:00Z',
      }),
    ).toBe('CAM-2026-0016 · Policy read')
  })

  it('uses the stored reference in preference to anything rebuilt from the id', () => {
    expect(
      campaignReference(16, {
        reference_number: 'CAM-2026-0004',
        launched_at: '2026-01-10T00:00:00Z',
        created_at: '2026-01-01T00:00:00Z',
      }),
    ).toBe('CAM-2026-0004')
  })

  it('falls back to the derived reference only while a campaign has none stored', () => {
    expect(campaignReference(16, { reference_number: null, created_at: '2025-01-01T00:00:00Z' })).toBe(
      'CAM-2025-0016',
    )
    expect(campaignReference(16, { reference_number: '   ', created_at: '2025-01-01T00:00:00Z' })).toBe(
      'CAM-2025-0016',
    )
    expect(campaignReference(16, {})).toMatch(/^CAM-\d{4}-0016$/)
  })

  it('carries the stored reference through the list label the panels render', () => {
    expect(
      formatCampaignListLabel({
        id: 16,
        title: 'Policy read',
        reference_number: 'CAM-2026-0004',
        launched_at: '2026-01-10T00:00:00Z',
        created_at: '2026-01-01T00:00:00Z',
      }),
    ).toBe('CAM-2026-0004 · Policy read')
  })

  it('no longer lets two surfaces disagree about a draft campaign', () => {
    // The compliance table used to fall back to the *current* year for a draft
    // while the panel used created_at, so the same campaign read differently.
    const draft = { reference_number: 'CAM-2025-0009', launched_at: null, created_at: '2025-11-02T00:00:00Z' }
    expect(campaignReference(9, draft)).toBe(campaignReference(9, { ...draft }))
    expect(campaignReference(9, draft)).toBe('CAM-2025-0009')
  })

  it('flags UAT / thin-suite campaign artefacts without false positives', () => {
    expect(isUatCampaignArtefact({ title: 'UAT-TX-191150 d14' })).toBe(true)
    expect(isUatCampaignArtefact({ title: 'UAT-THIN camp bogus' })).toBe(true)
    expect(isUatCampaignArtefact({ document_title: 'Health & Safety Policy' })).toBe(false)
  })

  it('partitions operational campaigns from UAT artefacts', () => {
    const { operational, uatArtefacts } = partitionUatCampaigns([
      { title: 'Real policy campaign', document_title: 'HS Policy' },
      { title: 'UAT-TX-191150 d1', document_title: 'Doc' },
    ])
    expect(operational).toHaveLength(1)
    expect(uatArtefacts).toHaveLength(1)
  })
})
