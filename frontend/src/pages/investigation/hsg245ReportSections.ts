export type ReportLevel = 'minimal' | 'low' | 'medium' | 'high'

export interface Hsg245ReportSection {
  id: string
  title: string
  minimumLevel: ReportLevel
  detail: string
}

const LEVEL_ORDER: Record<ReportLevel, number> = {
  minimal: 0,
  low: 1,
  medium: 2,
  high: 3,
}

export const HSG245_REPORT_SECTIONS: Hsg245ReportSection[] = [
  {
    id: 'event-details',
    title: 'Event details and evidence',
    minimumLevel: 'minimal',
    detail: 'Facts, location, people involved, evidence references, and potential worst consequence.',
  },
  {
    id: 'immediate-actions',
    title: 'Immediate actions and local lessons',
    minimumLevel: 'minimal',
    detail: 'Containment, actions taken, ownership, and local learning before recurrence.',
  },
  {
    id: 'findings',
    title: 'Investigation findings',
    minimumLevel: 'low',
    detail: 'What happened, why it happened, and contributing factors at a proportionate depth.',
  },
  {
    id: 'root-cause',
    title: 'Root cause analysis',
    minimumLevel: 'medium',
    detail: 'Concise 5 Whys and a root-cause statement; HIGH expands this with corroborating evidence.',
  },
  {
    id: 'hsg245-analysis',
    title: 'HSG245 cause analysis',
    minimumLevel: 'high',
    detail: 'Analyse place, plant, people, and process across immediate, underlying, and root causes.',
  },
  {
    id: 'capa',
    title: 'SMART CAPA plan',
    minimumLevel: 'high',
    detail: 'Corrective and preventive actions with owner, due date, resources, verification, and effectiveness review.',
  },
  {
    id: 'fishbone',
    title: 'Fishbone analysis',
    minimumLevel: 'high',
    detail: 'Structured causes across people, methods, materials, equipment, environment, and measurement.',
  },
  {
    id: 'management-review',
    title: 'Management-system and risk-assessment review',
    minimumLevel: 'high',
    detail: 'Review risk assessment, procedures, competency, supervision, and systemic control improvements.',
  },
  {
    id: 'signoff',
    title: 'Sign-off and approval',
    minimumLevel: 'minimal',
    detail: 'Investigator, reviewer, and required approval records.',
  },
]

export function getReportSectionsForLevel(level: string | null | undefined): Hsg245ReportSection[] {
  const resolvedLevel: ReportLevel = level && level in LEVEL_ORDER ? (level as ReportLevel) : 'medium'
  return HSG245_REPORT_SECTIONS.filter(
    (section) => LEVEL_ORDER[section.minimumLevel] <= LEVEL_ORDER[resolvedLevel],
  )
}
