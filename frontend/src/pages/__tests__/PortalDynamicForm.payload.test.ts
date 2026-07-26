import { describe, expect, it, vi } from 'vitest'

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

vi.mock('../../api/client', () => ({
  formTemplatesApi: { getBySlug: vi.fn() },
  lookupsApi: { list: vi.fn() },
  getApiErrorMessage: (err: unknown) => (err instanceof Error ? err.message : 'Request failed'),
}))

vi.mock('../../contexts/PortalAuthContext', () => ({
  usePortalAuth: () => ({ user: null }),
}))

import {
  REPORTER_PHONE_MAX_LENGTH,
  buildPortalReportPayload,
  classifyContactValue,
  validatePortalFormData,
} from '../PortalDynamicForm'

const AUTHED_USER = { name: 'Dana Reporter', email: 'dana.reporter@plantexpand.co.uk' }

function complaintForm(overrides: Record<string, unknown> = {}) {
  return {
    contract: 'ACME',
    complainant_name: 'Sam Complainant',
    complainant_contact: '07700 900123',
    complaint_date: '2026-07-26',
    description: 'The delivery arrived three days late and the crate was damaged.',
    ...overrides,
  }
}

function buildComplaint(
  formData: Record<string, unknown>,
  user: { name?: string; email?: string } | null = AUTHED_USER,
) {
  return buildPortalReportPayload({
    formType: 'complaint',
    formData,
    templateName: 'Customer Complaint',
    user,
  })
}

describe('classifyContactValue', () => {
  it('recognises email addresses', () => {
    expect(classifyContactValue('sam.complainant@averylongcompanyname.co.uk').kind).toBe('email')
  })

  it('recognises phone numbers in common UK formats', () => {
    expect(classifyContactValue('07700 900123').kind).toBe('phone')
    expect(classifyContactValue('+44 7700 900123').kind).toBe('phone')
    expect(classifyContactValue('(01234) 567-890').kind).toBe('phone')
  })

  it('treats free text and short digit strings as unknown', () => {
    expect(classifyContactValue('ask at reception').kind).toBe('unknown')
    expect(classifyContactValue('123').kind).toBe('unknown')
    expect(classifyContactValue('').kind).toBe('unknown')
    expect(classifyContactValue(undefined).kind).toBe('unknown')
    expect(classifyContactValue(null).kind).toBe('unknown')
  })
})

describe('PX-281 regression: complaint contact never violates the 20-char phone limit', () => {
  const CONTACT_VALUES = [
    'sam.complainant@averylongcompanyname.co.uk',
    'a.very.long.email.address.indeed@subdomain.example-company.org',
    '+44 7700 900123',
    '07700 900123',
    '(01234) 567-890',
    '0044 (0) 1234 567 890',
    '01234 567890 ext. 4471',
    'ask at reception, weekdays only',
    '   ',
    '',
  ]

  it.each(CONTACT_VALUES)(
    'keeps reporter_phone within the API limit for contact %j',
    (contactValue) => {
      const payload = buildComplaint(complaintForm({ complainant_contact: contactValue }))
      const phone = payload.reporter_phone ?? ''
      expect(phone.length).toBeLessThanOrEqual(REPORTER_PHONE_MAX_LENGTH)
    },
  )

  it('does not put an email address into reporter_phone', () => {
    const email = 'sam.complainant@averylongcompanyname.co.uk'
    expect(email.length).toBeGreaterThan(REPORTER_PHONE_MAX_LENGTH)

    const payload = buildComplaint(complaintForm({ complainant_contact: email }))

    expect(payload.reporter_phone).toBeUndefined()
  })

  it('never truncates the contact value: it stays in the reporter snapshot', () => {
    const email = 'sam.complainant@averylongcompanyname.co.uk'
    const payload = buildComplaint(complaintForm({ complainant_contact: email }))

    expect(payload.reporter_submission?.complainant_contact).toBe(email)
  })
})

describe('buildPortalReportPayload contact routing', () => {
  it('keeps a valid short phone number in reporter_phone', () => {
    const payload = buildComplaint(complaintForm({ complainant_contact: '07700 900123' }))

    expect(payload.reporter_phone).toBe('07700 900123')
    expect(payload.description).not.toContain('Complainant contact')
  })

  it('uses the contact email as reporter_email when nobody is signed in', () => {
    const email = 'sam.complainant@averylongcompanyname.co.uk'
    const payload = buildComplaint(complaintForm({ complainant_contact: email }), null)

    expect(payload.reporter_email).toBe(email)
    expect(payload.reporter_phone).toBeUndefined()
  })

  it('preserves the signed-in user email for My Reports linkage and records the complainant email in the details', () => {
    const email = 'sam.complainant@averylongcompanyname.co.uk'
    const payload = buildComplaint(complaintForm({ complainant_contact: email }))

    expect(payload.reporter_email).toBe(AUTHED_USER.email)
    expect(payload.description).toContain(`Complainant contact: ${email}`)
  })

  it('does not duplicate the contact into the details when it matches the signed-in user', () => {
    const payload = buildComplaint(
      complaintForm({ complainant_contact: AUTHED_USER.email.toUpperCase() }),
    )

    expect(payload.reporter_email).toBe(AUTHED_USER.email)
    expect(payload.description).not.toContain('Complainant contact')
  })

  it('routes an over-long phone number into the details rather than reporter_phone', () => {
    const longPhone = '0044 (0) 1234 567 890'
    expect(classifyContactValue(longPhone).kind).toBe('phone')
    expect(longPhone.length).toBeGreaterThan(REPORTER_PHONE_MAX_LENGTH)

    const payload = buildComplaint(complaintForm({ complainant_contact: longPhone }))

    expect(payload.reporter_phone).toBeUndefined()
    expect(payload.description).toContain(`Complainant contact: ${longPhone}`)
  })

  it.each([
    'ask at reception, weekdays only',
    '01234 567890 ext. 4471',
  ])('routes unrecognised free text (%j) into the details', (contactValue) => {
    const payload = buildComplaint(complaintForm({ complainant_contact: contactValue }))

    expect(payload.reporter_phone).toBeUndefined()
    expect(payload.description).toContain(`Complainant contact: ${contactValue}`)
  })

  it('still satisfies the API description minimum when the user typed almost nothing', () => {
    const payload = buildComplaint(complaintForm({ description: 'late' }))

    expect(payload.description.length).toBeGreaterThanOrEqual(10)
  })
})

describe('buildPortalReportPayload behaviour preserved for other form types', () => {
  it('does not set reporter_phone for a near miss and bridges the customer to department', () => {
    const payload = buildPortalReportPayload({
      formType: 'near-miss',
      formData: {
        contract: 'ACME',
        location: 'Bay 4',
        description: 'A pallet shifted while being lifted but nobody was underneath.',
      },
      templateName: 'Near Miss Report',
      user: AUTHED_USER,
    })

    expect(payload.report_type).toBe('near_miss')
    expect(payload.department).toBe('ACME')
    expect(payload.reporter_phone).toBeUndefined()
    expect(payload.reporter_email).toBe(AUTHED_USER.email)
  })

  it('does not bridge the customer to department for incidents', () => {
    const payload = buildPortalReportPayload({
      formType: 'incident',
      formData: {
        contract: 'ACME',
        person_name: 'Dana Reporter',
        description: 'A colleague slipped on a wet floor near the loading bay entrance.',
      },
      templateName: 'Incident Report',
      user: AUTHED_USER,
    })

    expect(payload.report_type).toBe('incident')
    expect(payload.department).toBeUndefined()
    expect(payload.reporter_name).toBe('Dana Reporter')
  })
})

describe('validatePortalFormData', () => {
  it('blocks a phone number longer than the API allows, with an actionable message', () => {
    const errors = validatePortalFormData({
      complainant_contact: '0044 (0) 1234 567 890',
    })

    expect(errors.complainant_contact).toBeDefined()
    expect(errors.complainant_contact).toContain(String(REPORTER_PHONE_MAX_LENGTH))
    expect(errors.complainant_contact).toContain('email')
  })

  it('allows a long email address, because it is not sent as a phone number', () => {
    expect(
      validatePortalFormData({
        complainant_contact: 'a.very.long.email.address.indeed@subdomain.example-company.org',
      }),
    ).toEqual({})
  })

  it('allows a normal phone number and an empty contact', () => {
    expect(validatePortalFormData({ complainant_contact: '+44 7700 900123' })).toEqual({})
    expect(validatePortalFormData({})).toEqual({})
  })
})
