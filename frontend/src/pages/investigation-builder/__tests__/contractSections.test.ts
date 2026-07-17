import { describe, expect, it } from 'vitest'
import {
  assessContractCompliance,
  createInc043ScaffoldSections,
  isGenericStarterDraft,
  isInc043Scaffold,
  matchesContractSection,
  INC043_CONTRACT_SECTIONS,
} from '../contractSections'
import type { InvestigationSection } from '../types'

describe('investigation-builder contractSections', () => {
  it('creates seven INC043 scaffold sections with stable ids', () => {
    const sections = createInc043ScaffoldSections()
    expect(sections).toHaveLength(7)
    expect(sections.map((section) => section.id)).toEqual(
      INC043_CONTRACT_SECTIONS.map((spec) => spec.key),
    )
    expect(isInc043Scaffold(sections)).toBe(true)
  })

  it('detects generic single-section starter drafts', () => {
    const generic: InvestigationSection[] = [{ id: 'abc', name: 'Section 1', fields: [] }]
    expect(isGenericStarterDraft(generic)).toBe(true)
    expect(isGenericStarterDraft(createInc043ScaffoldSections())).toBe(false)
  })

  it('matches sections by id or keyword', () => {
    const byKeyword: InvestigationSection = {
      id: 'custom-1',
      name: 'Evidence & Information',
      fields: [],
    }
    expect(matchesContractSection(byKeyword, INC043_CONTRACT_SECTIONS[2])).toBe(true)
  })

  it('assesses compliance as missing, partial, or complete', () => {
    const sections: InvestigationSection[] = [
      { id: 'section_1_basic_info', name: '1. Basic Information', fields: [{ id: 'f1', label: 'X', type: 'text_long', required: true }] },
      { id: 'section_4_timeline', name: '4. Timeline of Events', fields: [] },
    ]
    const checklist = assessContractCompliance(sections)
    expect(checklist[0]?.status).toBe('complete')
    expect(checklist[1]?.status).toBe('missing')
    expect(checklist[3]?.status).toBe('partial')
  })
})
