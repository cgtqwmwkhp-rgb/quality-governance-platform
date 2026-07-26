import { describe, expect, it } from 'vitest'

import {
  buildPortalCatalogWarnings,
  formatCatalogWarning,
  resolveLookupCategory,
  templateRequiresLookupCategory,
} from '../formLookupFields'

describe('formLookupFields', () => {
  it('maps person_role select to workforce_roles', () => {
    expect(
      resolveLookupCategory({
        name: 'person_role',
        field_type: 'select',
        is_required: true,
      }),
    ).toBe('workforce_roles')
  })

  it('does not map free-text complainant_role to a lookup', () => {
    expect(
      resolveLookupCategory({
        name: 'complainant_role',
        field_type: 'text',
        is_required: false,
      }),
    ).toBeNull()
  })

  it('maps contract select to customers', () => {
    expect(
      resolveLookupCategory({
        name: 'contract',
        field_type: 'select',
        is_required: true,
      }),
    ).toBe('customers')
  })

  it('detects when a template requires workforce_roles', () => {
    const incidentTemplate = {
      steps: [
        {
          fields: [
            { name: 'person_role', field_type: 'select', is_required: true },
          ],
        },
      ],
    }
    expect(templateRequiresLookupCategory(incidentTemplate, 'workforce_roles')).toBe(true)
  })

  it('does not warn about workforce roles on complaint forms (PX-284)', () => {
    const complaintTemplate = {
      steps: [
        {
          fields: [
            { name: 'contract', field_type: 'select', is_required: true },
            { name: 'complainant_role', field_type: 'text', is_required: false },
          ],
        },
      ],
    }
    expect(templateRequiresLookupCategory(complaintTemplate, 'workforce_roles')).toBe(false)
    const warnings = buildPortalCatalogWarnings(complaintTemplate, {
      customers: 0,
      workforceRoles: 0,
    })
    expect(warnings).toEqual([
      'No active customers found. An admin must add Customers under Admin → Lookups → Customers.',
    ])
    expect(formatCatalogWarning(warnings)).toContain('Customers')
    expect(formatCatalogWarning(warnings)).not.toContain('workforce roles')
  })
})
