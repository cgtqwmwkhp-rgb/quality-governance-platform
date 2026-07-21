import { describe, expect, it } from 'vitest'
import {
  CUSTOMERS_LOOKUP_CATEGORY,
  customerHintCodes,
  toCustomerSelectOptions,
} from '../customersCatalog'

describe('customersCatalog', () => {
  it('documents the customers lookup category key', () => {
    expect(CUSTOMERS_LOOKUP_CATEGORY).toBe('customers')
  })

  it('lists suggested customer codes for admins', () => {
    expect(customerHintCodes()).toContain('ukpn')
    expect(customerHintCodes()).toContain('openreach')
  })

  it('maps active lookup rows to sorted select options', () => {
    const options = toCustomerSelectOptions([
      { code: 'openreach', label: 'Openreach', is_active: true },
      { code: 'ukpn', label: 'UK Power Networks', is_active: true },
      { code: 'old', label: 'Retired', is_active: false },
    ])
    expect(options).toEqual([
      { value: 'openreach', label: 'Openreach' },
      { value: 'ukpn', label: 'UK Power Networks' },
    ])
  })
})
