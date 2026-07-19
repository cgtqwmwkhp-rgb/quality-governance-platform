import type { LucideIcon } from 'lucide-react'
import { BarChart3, Calendar, ClipboardList, Download, Link2 } from 'lucide-react'

export type UvdbSectionId = 'scores' | 'protocol' | 'audits' | 'mapping' | 'export'

export const UVDB_SECTION_IDS: UvdbSectionId[] = [
  'scores',
  'protocol',
  'audits',
  'mapping',
  'export',
]

export interface UvdbSectionDef {
  id: UvdbSectionId
  labelKey: string
  icon: LucideIcon
}

export const UVDB_SECTIONS: UvdbSectionDef[] = [
  { id: 'scores', labelKey: 'uvdb.shell.section.scores', icon: BarChart3 },
  { id: 'protocol', labelKey: 'uvdb.shell.section.protocol', icon: ClipboardList },
  { id: 'audits', labelKey: 'uvdb.shell.section.audits', icon: Calendar },
  { id: 'mapping', labelKey: 'uvdb.shell.section.mapping', icon: Link2 },
  { id: 'export', labelKey: 'uvdb.shell.section.export', icon: Download },
]

export function parseUvdbSection(
  value: string | null,
  options?: { auditRefHint?: boolean },
): UvdbSectionId {
  if (value && UVDB_SECTION_IDS.includes(value as UvdbSectionId)) {
    return value as UvdbSectionId
  }
  return options?.auditRefHint ? 'audits' : 'scores'
}
