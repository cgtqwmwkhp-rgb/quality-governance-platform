import { describe, expect, it } from 'vitest'
import { getReportSectionsForLevel } from '../hsg245ReportSections'

describe('HSG245 report section gating', () => {
  it('keeps a minimal report to facts, immediate actions, and sign-off', () => {
    expect(getReportSectionsForLevel('minimal').map((section) => section.id)).toEqual([
      'event-details',
      'immediate-actions',
      'signoff',
    ])
  })

  it('includes the complete detailed analysis pack only at HIGH', () => {
    const mediumSections = getReportSectionsForLevel('medium').map((section) => section.id)
    const highSections = getReportSectionsForLevel('high').map((section) => section.id)

    expect(mediumSections).not.toContain('hsg245-analysis')
    expect(highSections).toEqual(expect.arrayContaining([
      'hsg245-analysis',
      'capa',
      'fishbone',
      'management-review',
    ]))
  })
})
