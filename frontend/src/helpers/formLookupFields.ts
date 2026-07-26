/** Lookup-backed form fields — mirrors backend form_publish_validation + DynamicFormRenderer. */

export type FormFieldShape = {
  name: string
  label?: string
  field_type: string
  is_required?: boolean
  options?: Array<{ value: string; label: string }>
}

export type FormStepShape = {
  fields?: FormFieldShape[]
}

export type FormTemplateShape = {
  steps?: FormStepShape[]
}

const LOOKUP_SELECT_TYPES = new Set(['select', 'multi_select'])

const EXACT_FIELD_LOOKUPS: Record<string, string> = {
  person_role: 'workforce_roles',
  medical_assistance: 'medical_assistance',
}

export function resolveLookupCategory(field: FormFieldShape): string | null {
  const fieldType = (field.field_type || '').toLowerCase()
  if (!LOOKUP_SELECT_TYPES.has(fieldType)) return null

  const name = (field.name || '').trim().toLowerCase()
  if (!name) return null

  if (name in EXACT_FIELD_LOOKUPS) return EXACT_FIELD_LOOKUPS[name]
  if (name.includes('customer') || name.includes('contract')) return 'customers'
  if (name.endsWith('_role') || name === 'role' || name.includes('role')) return 'workforce_roles'

  const inline = field.options || []
  if (inline.length > 0) return null

  return null
}

export function templateRequiresLookupCategory(
  template: FormTemplateShape,
  category: string,
): boolean {
  for (const step of template.steps || []) {
    for (const field of step.fields || []) {
      if (!field.is_required) continue
      if (resolveLookupCategory(field) === category) return true
    }
  }
  return false
}

export type CatalogCounts = {
  customers: number
  workforceRoles: number
}

export function buildPortalCatalogWarnings(
  template: FormTemplateShape,
  counts: CatalogCounts,
): string[] {
  const warnings: string[] = []

  if (
    templateRequiresLookupCategory(template, 'customers') &&
    counts.customers === 0
  ) {
    warnings.push(
      'No active customers found. An admin must add Customers under Admin → Lookups → Customers.',
    )
  }

  if (
    templateRequiresLookupCategory(template, 'workforce_roles') &&
    counts.workforceRoles === 0
  ) {
    warnings.push(
      'No workforce roles found. An admin must configure Lookups → Workforce Roles.',
    )
  }

  return warnings
}

export function formatCatalogWarning(warnings: string[]): string | null {
  return warnings.length ? warnings.join(' ') : null
}
