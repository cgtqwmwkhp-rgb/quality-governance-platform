/**
 * Detect Playwright / CUJ / UAT fixture templates that should not be offered
 * as real scheduling choices (PX-219 / PX-266).
 */

export type TemplateHonestyLike = {
  name?: string | null
  reference_number?: string | null
  description?: string | null
  tags?: Array<string | null | undefined> | null
}

const AUTOMATION_NAME_PATTERNS: RegExp[] = [
  /\bcuj[-_]?at[-_]?\d*\b/i,
  /\bplaywright\b/i,
  /\buat[-_]?thin\b/i,
  /\bcuj\s+audit\s+template\b/i,
  /\bautomated[-_\s]?test\b/i,
]

export function isAutomationTestTemplate(template: TemplateHonestyLike): boolean {
  const name = (template.name || '').trim()
  if (/^uat$/i.test(name) || /^test\s*3$/i.test(name)) {
    return true
  }

  const blob = [
    name,
    template.reference_number,
    template.description,
    ...(template.tags || []).map((tag) => tag ?? ''),
  ]
    .filter(Boolean)
    .join(' ')

  if (!blob) return false
  return AUTOMATION_NAME_PATTERNS.some((pattern) => pattern.test(blob))
}

export function partitionAutomationTemplates<T extends TemplateHonestyLike>(
  templates: T[],
): { operational: T[]; automation: T[] } {
  const operational: T[] = []
  const automation: T[] = []
  for (const template of templates) {
    if (isAutomationTestTemplate(template)) {
      automation.push(template)
    } else {
      operational.push(template)
    }
  }
  return { operational, automation }
}
