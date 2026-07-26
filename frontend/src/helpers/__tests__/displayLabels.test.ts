import { describe, expect, it } from 'vitest'
import {
  formatCodedValue,
  formatFieldName,
  formatPermissionCode,
  humaniseCodedText,
  isOpaqueIdentifier,
} from '../displayLabels'

describe('formatCodedValue', () => {
  it('reads snake_case as a sentence (PX-199 collision type)', () => {
    expect(formatCodedValue('object_strike')).toBe('Struck a stationary object')
    expect(formatCodedValue('vehicle_rollover')).toBe('Vehicle rollover')
  })

  it('handles the other coded shapes the API emits', () => {
    expect(formatCodedValue('REPORTED')).toBe('Reported')
    expect(formatCodedValue('PENDING_REVIEW')).toBe('Pending review')
    expect(formatCodedValue('near-miss')).toBe('Near miss')
    expect(formatCodedValue('daysLost')).toBe('Days lost')
    expect(formatCodedValue('pending_actions')).toBe('Pending actions')
    expect(formatCodedValue('actions_in_progress')).toBe('Actions in progress')
  })

  it('unwraps a Python enum repr (PX-207)', () => {
    expect(formatCodedValue('ComplaintStatus.ACKNOWLEDGED')).toBe('Acknowledged')
    expect(formatCodedValue('ComplaintStatus.UNDER_INVESTIGATION')).toBe('Under investigation')
  })

  it('keeps acronyms uppercase rather than sentence-casing them', () => {
    expect(formatCodedValue('riddor_reportable')).toBe('RIDDOR reportable')
    expect(formatCodedValue('is_lti')).toBe('Is LTI')
    expect(formatCodedValue('RTA')).toBe('RTA')
  })

  it('leaves free text alone', () => {
    // collision_type is a free-text column: a real sentence must survive intact.
    expect(formatCodedValue('Reversed into a bollard')).toBe('Reversed into a bollard')
    expect(formatCodedValue('  Rear-ended at a junction  ')).toBe('Rear-ended at a junction')
  })

  it('does not mangle a dotted value that is not an enum repr', () => {
    expect(formatCodedValue('Report.PDF')).toBe('Report.PDF')
    expect(formatCodedValue('v11.8')).toBe('v11.8')
  })

  it('returns an empty string for absent values', () => {
    expect(formatCodedValue(null)).toBe('')
    expect(formatCodedValue(undefined)).toBe('')
    expect(formatCodedValue('   ')).toBe('')
  })
})

describe('formatFieldName', () => {
  it('turns settings keys into labels (PX-198)', () => {
    expect(formatFieldName('company_name')).toBe('Company name')
    expect(formatFieldName('company_logo_url')).toBe('Company logo URL')
    expect(formatFieldName('incident_sla_hours')).toBe('Incident SLA hours')
    expect(formatFieldName('require_mfa')).toBe('Require MFA')
  })

  it('replaces column names that stay jargon when formatted mechanically', () => {
    expect(formatFieldName('next_review_date')).toBe('Review due date')
    expect(formatFieldName('role_key')).toBe('Workforce role')
    expect(formatFieldName('external_id')).toBe('External reference')
  })

  it('returns an empty string for absent keys', () => {
    expect(formatFieldName(null)).toBe('')
    expect(formatFieldName('')).toBe('')
  })
})

describe('formatPermissionCode', () => {
  it('uses the plain-English wording for a known permission (PX-144)', () => {
    expect(formatPermissionCode('investigation:approve_customer_omit')).toBe(
      'Approve leaving a section out of the customer pack',
    )
  })

  it('never returns the raw code for an unknown permission', () => {
    expect(formatPermissionCode('audit:close_finding')).toBe('Close finding (Audit)')
    expect(formatPermissionCode('rta:export')).toBe('Export (RTA)')
    expect(formatPermissionCode('admin')).toBe('Admin')
  })

  it('returns an empty string for absent codes', () => {
    expect(formatPermissionCode(undefined)).toBe('')
  })
})

describe('humaniseCodedText', () => {
  it('scrubs Python enum reprs out of a server error (PX-207)', () => {
    expect(
      humaniseCodedText(
        "Cannot transition from 'ComplaintStatus.ACKNOWLEDGED' to 'ComplaintStatus.RESOLVED'",
      ),
    ).toBe("Cannot transition from 'Acknowledged' to 'Resolved'")
  })

  it('scrubs raw enum values the server passes through as data', () => {
    expect(humaniseCodedText("Cannot transition from 'acknowledged' to 'resolved'")).toBe(
      "Cannot transition from 'Acknowledged' to 'Resolved'",
    )
    expect(humaniseCodedText('Source record NEAR_MISS_REPORT is closed')).toBe(
      'Source record Near miss report is closed',
    )
  })

  it('leaves prose and references untouched', () => {
    expect(humaniseCodedText('The reference CAPA-2026-0015 is already closed.')).toBe(
      'The reference CAPA-2026-0015 is already closed.',
    )
    expect(humaniseCodedText("You don't have access to this record.")).toBe(
      "You don't have access to this record.",
    )
  })

  it('returns an empty string for absent text', () => {
    expect(humaniseCodedText(null)).toBe('')
  })
})

describe('isOpaqueIdentifier', () => {
  it('recognises a generated surrogate key (PX-215)', () => {
    expect(isOpaqueIdentifier('6a03cef1-7e69-45e0-b745-f675b942f57f')).toBe(true)
    expect(isOpaqueIdentifier('9f2b1c4d8e7a6b5c4d3e2f1a0b9c8d7e')).toBe(true)
  })

  it('does not flag references a user would recognise', () => {
    expect(isOpaqueIdentifier('asset-55')).toBe(false)
    expect(isOpaqueIdentifier('PX-2026-0014')).toBe(false)
    // A long numeric serial is all hex characters but is not a digest.
    expect(isOpaqueIdentifier('123456789012345678901234')).toBe(false)
    expect(isOpaqueIdentifier('')).toBe(false)
    expect(isOpaqueIdentifier(null)).toBe(false)
  })
})
