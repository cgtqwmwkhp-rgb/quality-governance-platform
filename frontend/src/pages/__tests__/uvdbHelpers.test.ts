import { describe, expect, it } from 'vitest'
import {
  UVDB_SECTION_IDS,
  UVDB_SECTIONS,
  parseUvdbSection,
} from '../uvdbHelpers'

describe('uvdbHelpers', () => {
  it('defines five shell sections in display order', () => {
    expect(UVDB_SECTION_IDS).toEqual(['scores', 'protocol', 'audits', 'mapping', 'export'])
    expect(UVDB_SECTIONS.map((section) => section.id)).toEqual(UVDB_SECTION_IDS)
  })

  it('defaults to scores when section param is missing or invalid', () => {
    expect(parseUvdbSection(null)).toBe('scores')
    expect(parseUvdbSection('')).toBe('scores')
    expect(parseUvdbSection('dashboard')).toBe('scores')
  })

  it('opens audits when auditRef hint is present without a section', () => {
    expect(parseUvdbSection(null, { auditRefHint: true })).toBe('audits')
  })

  it('parses known section ids from the URL', () => {
    expect(parseUvdbSection('export')).toBe('export')
    expect(parseUvdbSection('mapping')).toBe('mapping')
  })
})
