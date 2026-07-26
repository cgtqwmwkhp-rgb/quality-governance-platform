import { describe, expect, it } from 'vitest'
import {
  caseBreadcrumbLabel,
  hasMixedCaseReferenceFormats,
  isHexStyleCaseReference,
  isSequentialCaseReference,
  linkedAssetDisplayLabel,
  linkedContractDisplayLabel,
  linkedRiskDisplayLabel,
  parseCaseOccurredTime,
  sortByOccurredDesc,
} from '../caseRegisterHonesty'

describe('caseRegisterHonesty', () => {
  it('PX-126: distinguishes sequential and hex-style incident references', () => {
    expect(isSequentialCaseReference('INC-2026-0057')).toBe(true)
    expect(isHexStyleCaseReference('INC-2026-0057')).toBe(false)
    expect(isHexStyleCaseReference('INC-2026-CACDA723')).toBe(true)
    expect(isSequentialCaseReference('INC-2026-CACDA723')).toBe(false)
    expect(isHexStyleCaseReference('INC-2026-64A4C7E4')).toBe(true)
  })

  it('PX-126: detects a mixed reference page', () => {
    expect(
      hasMixedCaseReferenceFormats(['INC-2026-0057', 'INC-2026-CACDA723', 'INC-2026-0056']),
    ).toBe(true)
    expect(hasMixedCaseReferenceFormats(['INC-2026-0057', 'INC-2026-0056'])).toBe(false)
    expect(hasMixedCaseReferenceFormats(['INC-2026-CACDA723', 'INC-2026-64A4C7E4'])).toBe(false)
  })

  it('PX-124: sorts by occurred date newest first (not by API reported order)', () => {
    const rows = [
      { id: 1, incident_date: '2024-10-11', reference_number: 'INC-2026-0022' },
      { id: 2, incident_date: '2026-07-23', reference_number: 'INC-2026-0057' },
      { id: 3, incident_date: '2026-07-21', reference_number: 'INC-2026-0050' },
    ]
    const sorted = sortByOccurredDesc(
      rows,
      (row) => row.incident_date,
      (row) => row.id,
    )
    expect(sorted.map((row) => row.reference_number)).toEqual([
      'INC-2026-0057',
      'INC-2026-0050',
      'INC-2026-0022',
    ])
  })

  it('PX-124: missing dates sort after real dates', () => {
    const rows = [
      { id: 1, incident_date: null as string | null },
      { id: 2, incident_date: '2026-07-23' },
    ]
    const sorted = sortByOccurredDesc(rows, (row) => row.incident_date, (row) => row.id)
    expect(sorted.map((row) => row.id)).toEqual([2, 1])
    expect(parseCaseOccurredTime(null)).toBe(Number.NEGATIVE_INFINITY)
  })

  it('PX-174: breadcrumb prefers reference and never invents #id', () => {
    expect(caseBreadcrumbLabel('INC-2026-0059', 'Incident')).toBe('INC-2026-0059')
    expect(caseBreadcrumbLabel(null, 'Incident')).toBe('Incident')
    expect(caseBreadcrumbLabel('  ', 'Incident')).toBe('Incident')
    expect(caseBreadcrumbLabel(undefined, 'Complaint')).toBe('Complaint')
  })

  it('PX-174: linked asset/contract/risk labels hide surrogate numbers', () => {
    expect(linkedAssetDisplayLabel(40)).toBe('Linked asset')
    expect(linkedAssetDisplayLabel(null)).toBeNull()
    expect(linkedContractDisplayLabel('UKPN East', 12)).toBe('UKPN East')
    expect(linkedContractDisplayLabel(null, 12)).toBe('Contract on record')
    expect(linkedContractDisplayLabel(null, null)).toBe('Not provided')
    expect(linkedRiskDisplayLabel(204)).toBe('Linked risk')
  })
})
