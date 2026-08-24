import { describe, expect, it } from 'vitest'
import cy from '../locales/cy.json'
import en from '../locales/en.json'

describe('Feedback register labels', () => {
  it('names the Safety hub child and register Feedback, not Complaints', () => {
    expect(en['nav.complaints']).toBe('Feedback')
    expect(en['complaints.title']).toBe('Feedback')
    expect(en['complaints.new']).toBe('New feedback')
    expect(en['complaints.subtitle']).toMatch(/compliments/i)
    expect(cy['nav.complaints']).toBe('Adborth')
    expect(cy['complaints.title']).toBe('Adborth')
  })
})
