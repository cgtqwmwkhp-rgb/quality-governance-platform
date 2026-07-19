import type { LucideIcon } from 'lucide-react'
import { BarChart3, ClipboardList, Link2, Lock, Users } from 'lucide-react'

export type ImsSectionId = 'overview' | 'mapping' | 'audit' | 'review' | 'isms'

export const IMS_SECTION_IDS: ImsSectionId[] = [
  'overview',
  'mapping',
  'audit',
  'review',
  'isms',
]

export const IMS_DEFAULT_SECTION: ImsSectionId = 'overview'

export interface ImsSectionDef {
  id: ImsSectionId
  labelKey: string
  icon: LucideIcon
}

export const IMS_SECTIONS: ImsSectionDef[] = [
  { id: 'overview', labelKey: 'ims.shell.section.overview', icon: BarChart3 },
  { id: 'mapping', labelKey: 'ims.shell.section.mapping', icon: Link2 },
  { id: 'audit', labelKey: 'ims.shell.section.audit', icon: ClipboardList },
  { id: 'review', labelKey: 'ims.shell.section.review', icon: Users },
  { id: 'isms', labelKey: 'ims.shell.section.isms', icon: Lock },
]

export function parseImsSection(value: string | null): ImsSectionId {
  if (value && IMS_SECTION_IDS.includes(value as ImsSectionId)) {
    return value as ImsSectionId
  }
  return IMS_DEFAULT_SECTION
}

export function imsSectionQueryValue(section: ImsSectionId): string | null {
  return section === IMS_DEFAULT_SECTION ? null : section
}
