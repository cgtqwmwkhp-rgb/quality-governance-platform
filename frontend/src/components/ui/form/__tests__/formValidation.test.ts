import { describe, expect, it } from 'vitest'
import {
  defaultRequiredMessage,
  fieldErrorId,
  fieldHintId,
  focusInvalidControl,
  isBlankValue,
  validateFields,
} from '../formValidation'

describe('isBlankValue', () => {
  it('treats null, undefined, whitespace strings and empty arrays as blank', () => {
    expect(isBlankValue(null)).toBe(true)
    expect(isBlankValue(undefined)).toBe(true)
    expect(isBlankValue('')).toBe(true)
    expect(isBlankValue('   ')).toBe(true)
    expect(isBlankValue([])).toBe(true)
  })

  it('does not treat false or zero as blank', () => {
    // A "No" answer and a zero count are answers, not omissions.
    expect(isBlankValue(false)).toBe(false)
    expect(isBlankValue(0)).toBe(false)
  })
})

describe('validateFields', () => {
  it('names the field in the default required message', () => {
    const outcome = validateFields({ customer_id: { label: 'Customer', required: true } }, {})
    expect(outcome.valid).toBe(false)
    expect(outcome.errors.customer_id).toBe('Customer is required')
  })

  it('honours a custom required message', () => {
    const outcome = validateFields(
      { audit_type: { label: 'Type', required: true, requiredMessage: 'Please choose a type' } },
      { audit_type: '' },
    )
    expect(outcome.errors.audit_type).toBe('Please choose a type')
  })

  it('reports the first invalid field in declaration order, not object insertion luck', () => {
    const outcome = validateFields(
      {
        first: { label: 'First', required: true },
        second: { label: 'Second', required: true },
      },
      { first: '', second: '' },
    )
    expect(outcome.firstInvalidField).toBe('first')
    expect(Object.keys(outcome.errors)).toEqual(['first', 'second'])
  })

  it('runs custom validators only when the required check passes', () => {
    const specs = {
      email: {
        label: 'Email',
        required: true,
        validate: (value: unknown) =>
          String(value).includes('@') ? null : 'Enter a valid email address',
      },
    }
    expect(validateFields(specs, { email: '' }).errors.email).toBe('Email is required')
    expect(validateFields(specs, { email: 'nope' }).errors.email).toBe(
      'Enter a valid email address',
    )
    expect(validateFields(specs, { email: 'a@b.c' }).valid).toBe(true)
  })

  it('passes the whole value bag to custom validators for cross-field rules', () => {
    const outcome = validateFields(
      {
        end: {
          label: 'End',
          validate: (value, values) =>
            Number(value) < Number(values.start) ? 'End must be after start' : null,
        },
      },
      { start: 5, end: 1 },
    )
    expect(outcome.errors.end).toBe('End must be after start')
  })

  it('is valid when nothing is required and nothing is supplied', () => {
    const outcome = validateFields({ note: { label: 'Note' } }, {})
    expect(outcome).toEqual({ valid: true, errors: {}, firstInvalidField: null })
  })
})

describe('id helpers', () => {
  it('derives error and hint ids from the control id', () => {
    expect(fieldErrorId('incident-customer')).toBe('incident-customer-error')
    expect(fieldHintId('incident-customer')).toBe('incident-customer-hint')
  })

  it('generates a message that includes the label', () => {
    expect(defaultRequiredMessage('Customer / contract')).toBe('Customer / contract is required')
  })
})

describe('focusInvalidControl', () => {
  it('scrolls the control into view and focuses it', () => {
    const input = document.createElement('input')
    input.id = 'target-control'
    const scrollIntoView = vi.fn()
    input.scrollIntoView = scrollIntoView
    document.body.appendChild(input)

    expect(focusInvalidControl('target-control')).toBe(true)
    expect(scrollIntoView).toHaveBeenCalledWith({ behavior: 'smooth', block: 'center' })
    expect(document.activeElement).toBe(input)

    input.remove()
  })

  it('reports failure rather than throwing when the control is not in the DOM', () => {
    expect(focusInvalidControl('does-not-exist')).toBe(false)
  })
})
