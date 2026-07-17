import type { InvestigationSection } from './types'
import { generateId } from './types'

/** INC043 worked-example section contract (Plantexpand investigation report). */
export interface Inc043ContractSectionSpec {
  key: string
  title: string
  summary: string
  matchKeywords: string[]
}

export const INC043_CONTRACT_SECTIONS: Inc043ContractSectionSpec[] = [
  {
    key: 'section_1_basic_info',
    title: '1. Basic Information',
    summary: 'Date/time, site, people, witnesses, reporter, risk category, brief description',
    matchKeywords: ['basic', 'information', 'details', 'incident event'],
  },
  {
    key: 'section_2_immediate_consequences',
    title: '2. Immediate Consequences',
    summary: 'Injuries, property or equipment damage, immediate actions taken',
    matchKeywords: ['immediate', 'consequence', 'injur', 'damage'],
  },
  {
    key: 'section_3_evidence',
    title: '3. Evidence & Information',
    summary: 'Photos, emails, RAMS, DRA, toolbox talks, qualifications, method statements',
    matchKeywords: ['evidence', 'information', 'document', 'appendix'],
  },
  {
    key: 'section_4_timeline',
    title: '4. Timeline of Events',
    summary: 'Chronology with actors and timestamps',
    matchKeywords: ['timeline', 'chronolog', 'events'],
  },
  {
    key: 'section_5_root_cause',
    title: '5. Root Cause Analysis',
    summary: 'Immediate, underlying, and contributing causes (5-Why style)',
    matchKeywords: ['root cause', 'rca', 'why', 'contributing'],
  },
  {
    key: 'section_6_capa',
    title: '6. Corrective & Preventive Actions',
    summary: 'Actions, responsible persons, due dates',
    matchKeywords: ['corrective', 'preventive', 'capa', 'action'],
  },
  {
    key: 'section_7_lessons',
    title: '7. Lessons Learned',
    summary: 'Key takeaways and systemic improvements',
    matchKeywords: ['lesson', 'learned', 'takeaway', 'conclusion', 'finding'],
  },
]

export type ContractSectionStatus = 'complete' | 'partial' | 'missing'

export interface ContractSectionCheckItem {
  key: string
  title: string
  summary: string
  status: ContractSectionStatus
  matchedSectionId?: string
  fieldCount: number
}

function normalizeToken(value: string): string {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim()
}

function sectionTokens(section: InvestigationSection): string {
  return normalizeToken(`${section.id} ${section.name}`)
}

export function matchesContractSection(
  section: InvestigationSection,
  spec: Inc043ContractSectionSpec,
): boolean {
  if (section.id === spec.key) {
    return true
  }
  const tokens = sectionTokens(section)
  return spec.matchKeywords.some((keyword) => tokens.includes(normalizeToken(keyword)))
}

export function findMatchingSection(
  sections: InvestigationSection[],
  spec: Inc043ContractSectionSpec,
): InvestigationSection | undefined {
  return sections.find((section) => matchesContractSection(section, spec))
}

export function assessContractCompliance(
  sections: InvestigationSection[],
): ContractSectionCheckItem[] {
  return INC043_CONTRACT_SECTIONS.map((spec) => {
    const matched = findMatchingSection(sections, spec)
    if (!matched) {
      return {
        key: spec.key,
        title: spec.title,
        summary: spec.summary,
        status: 'missing',
        fieldCount: 0,
      }
    }

    const fieldCount = matched.fields.length
    return {
      key: spec.key,
      title: spec.title,
      summary: spec.summary,
      status: fieldCount > 0 ? 'complete' : 'partial',
      matchedSectionId: matched.id,
      fieldCount,
    }
  })
}

export function countContractSectionsPresent(checklist: ContractSectionCheckItem[]): number {
  return checklist.filter((item) => item.status !== 'missing').length
}

export function isInc043Scaffold(sections: InvestigationSection[]): boolean {
  if (sections.length !== INC043_CONTRACT_SECTIONS.length) {
    return false
  }
  return INC043_CONTRACT_SECTIONS.every(
    (spec, index) =>
      sections[index]?.id === spec.key && normalizeToken(sections[index]?.name ?? '') === normalizeToken(spec.title),
  )
}

export function isGenericStarterDraft(sections: InvestigationSection[]): boolean {
  return (
    sections.length === 1 &&
    normalizeToken(sections[0]?.name ?? '') === 'section 1' &&
    sections[0]?.fields.length === 0
  )
}

export function createInc043ScaffoldSections(): InvestigationSection[] {
  return INC043_CONTRACT_SECTIONS.map((spec) => ({
    id: spec.key,
    name: spec.title,
    fields: [],
  }))
}

/** Seed scaffold with one placeholder question per section for quick starts. */
export function createInc043ScaffoldSectionsWithPlaceholders(): InvestigationSection[] {
  return INC043_CONTRACT_SECTIONS.map((spec) => ({
    id: spec.key,
    name: spec.title,
    fields: [
      {
        id: generateId(),
        label: `${spec.title.replace(/^\d+\.\s*/, '')} — primary response`,
        type: 'text_long' as const,
        required: true,
      },
    ],
  }))
}
