import { describe, expect, it } from 'vitest'
import {
  IMS_DEFAULT_SECTION,
  IMS_SECTION_IDS,
  imsSectionQueryValue,
  parseImsSection,
} from '../imsDashboardHelpers'

describe('imsDashboardHelpers', () => {
  it('lists all IMS shell section IDs', () => {
    expect(IMS_SECTION_IDS).toEqual(['overview', 'mapping', 'audit', 'review', 'isms'])
  })

  it('parses section param with safe fallback to overview', () => {
    expect(parseImsSection(null)).toBe('overview')
    expect(parseImsSection('unknown')).toBe('overview')
    expect(parseImsSection('mapping')).toBe('mapping')
    expect(parseImsSection('isms')).toBe('isms')
  })

  it('omits default section from query patch values', () => {
    expect(imsSectionQueryValue(IMS_DEFAULT_SECTION)).toBeNull()
    expect(imsSectionQueryValue('audit')).toBe('audit')
  })
})
