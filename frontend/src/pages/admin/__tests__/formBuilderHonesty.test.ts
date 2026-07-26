import { describe, expect, it } from 'vitest'
import {
  buildActiveFormsStatHonesty,
  formBuilderEmptyStateCopy,
} from '../formBuilderHonesty'

describe('formBuilderHonesty', () => {
  it('does not present zero builder templates as healthy live forms (PX-186)', () => {
    const honesty = buildActiveFormsStatHonesty(0)
    expect(honesty.zeroIsNotAbsenceOfLiveForms).toBe(true)
    expect(honesty.label).toMatch(/Form Builder/i)
    expect(honesty.change.toLowerCase()).toMatch(/not managed here|live portal/)
  })

  it('keeps a normal label when templates exist', () => {
    const honesty = buildActiveFormsStatHonesty(6)
    expect(honesty.zeroIsNotAbsenceOfLiveForms).toBe(false)
    expect(honesty.label).toBe('Active Forms')
  })

  it('explains empty Form Builder catalogue honestly (PX-272)', () => {
    const empty = formBuilderEmptyStateCopy({ hasSearchOrFilter: false })
    expect(empty.title).toMatch(/Form Builder/i)
    expect(empty.body.toLowerCase()).toMatch(/live portal intake/)
    expect(empty.body.toLowerCase()).not.toMatch(/get started by creating your first form/)
  })
})
