import { describe, expect, it } from 'vitest'
import {
  complaintDownstreamActionsHonesty,
  complaintDownstreamInvestigationHonesty,
  formatComplaintEvidenceRailSummary,
  readReporterPhotoCount,
} from '../complaintEvidenceHonesty'

describe('complaintEvidenceHonesty', () => {
  it('prefers evidence-asset counts over reporter metadata', () => {
    expect(
      formatComplaintEvidenceRailSummary({ assetCount: 2, reporterPhotoCount: 1 }),
    ).toBe('2 evidence assets')
    expect(
      formatComplaintEvidenceRailSummary({ assetCount: 0, reporterPhotoCount: 1 }),
    ).toMatch(/not on evidence spine/)
  })

  it('reads reporter photo counts from submission snapshots', () => {
    expect(readReporterPhotoCount({ photos: { count: 3 } })).toBe(3)
    expect(readReporterPhotoCount({})).toBe(0)
  })

  it('states investigation and actions downstream honesty', () => {
    expect(complaintDownstreamInvestigationHonesty(false)).toMatch(/No investigation yet/)
    expect(complaintDownstreamInvestigationHonesty(true)).toMatch(/downstream workspace/)
    expect(complaintDownstreamActionsHonesty(0)).toMatch(/No open actions/)
    expect(complaintDownstreamActionsHonesty(2)).toBe('2 open actions on this complaint.')
  })
})
