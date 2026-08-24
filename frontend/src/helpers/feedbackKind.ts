/** Customer Feedback kinds. API vocabulary stays `complaint`; this is the discriminator. */

import type { FormField, FormTemplate } from '../services/api'

export type FeedbackKindCode = 'complaint' | 'compliment' | 'suggestion' | 'general'

export const FEEDBACK_KIND_OPTIONS: { value: FeedbackKindCode; label: string }[] = [
  { value: 'complaint', label: 'Complaint' },
  { value: 'compliment', label: 'Compliment' },
  { value: 'suggestion', label: 'Suggestion' },
  { value: 'general', label: 'General feedback' },
]

const LIGHT_CLOSE: ReadonlySet<FeedbackKindCode> = new Set(['compliment', 'general'])

export function parseFeedbackKind(value: string | undefined | null): FeedbackKindCode {
  if (value === 'compliment' || value === 'suggestion' || value === 'general' || value === 'complaint') {
    return value
  }
  return 'complaint'
}

export function reopenStatusForKind(kind: string | undefined | null): string {
  return LIGHT_CLOSE.has(parseFeedbackKind(kind)) ? 'acknowledged' : 'under_investigation'
}

export function lessonsRequiredForKind(kind: string | undefined | null): boolean {
  return !LIGHT_CLOSE.has(parseFeedbackKind(kind))
}

export function statusOptionsForKind(kind: string | undefined | null): string[] {
  switch (parseFeedbackKind(kind)) {
    case 'compliment':
      return ['received', 'acknowledged', 'closed']
    case 'general':
      return ['received', 'acknowledged', 'closed']
    case 'suggestion':
      return ['received', 'acknowledged', 'under_investigation', 'escalated', 'closed']
    default:
      return [
        'received',
        'acknowledged',
        'under_investigation',
        'pending_response',
        'awaiting_customer',
        'escalated',
        'resolved',
        'closed',
      ]
  }
}

const KIND_FIELD_NAMES = new Set(['feedback_kind', 'subject_name'])

export const PORTAL_FEEDBACK_KIND_FIELD: FormField = {
  id: 9101,
  name: 'feedback_kind',
  label: 'What kind of feedback',
  field_type: 'select',
  order: -2,
  is_required: true,
  width: 'full',
  default_value: 'complaint',
  options: FEEDBACK_KIND_OPTIONS.map(({ value, label }) => ({ value, label })),
}

export const PORTAL_COMPLIMENT_SUBJECT_FIELD: FormField = {
  id: 9102,
  name: 'subject_name',
  label: 'Who is this compliment about',
  field_type: 'text',
  order: -1,
  is_required: true,
  width: 'full',
  placeholder: 'Name of the staff member',
  show_condition: { field: 'feedback_kind', equals: 'compliment' },
}

function withPortalFeedbackCopy(template: FormTemplate): FormTemplate {
  return {
    ...template,
    name: template.name === 'Customer Complaint' ? 'Customer Feedback' : template.name,
    description:
      template.description === 'Submit customer complaints' ? 'Submit customer feedback' : template.description,
    steps: template.steps.map((step) => ({
      ...step,
      name: step.name === 'Complaint Details' ? 'Feedback Details' : step.name,
      description: step.description === 'Describe the complaint' ? 'Describe the feedback' : step.description,
      fields: step.fields.map((field) =>
        field.name === 'description' && field.label === 'Complaint Description'
          ? { ...field, label: 'Details', placeholder: 'Describe the feedback in detail...' }
          : field,
      ),
    })),
  }
}

function ensurePortalKindFields(template: FormTemplate): FormTemplate {
  const names = new Set(template.steps.flatMap((step) => step.fields.map((field) => field.name)))
  if (names.has('feedback_kind') && names.has('subject_name')) return template

  return {
    ...template,
    steps: template.steps.map((step, index) => {
      if (index !== template.steps.length - 1) return step
      const extra: FormField[] = []
      if (!names.has('feedback_kind')) extra.push(PORTAL_FEEDBACK_KIND_FIELD)
      if (!names.has('subject_name')) extra.push(PORTAL_COMPLIMENT_SUBJECT_FIELD)
      return { ...step, fields: [...extra, ...step.fields] }
    }),
  }
}

/** Flag off: strip kind fields so a published template cannot leak them. Flag on: inject + copy. */
export function applyFeedbackKindTemplate(template: FormTemplate, enabled: boolean): FormTemplate {
  if (template.form_type !== 'complaint') return template
  if (!enabled) {
    return {
      ...template,
      steps: template.steps.map((step) => ({
        ...step,
        fields: step.fields.filter((field) => !KIND_FIELD_NAMES.has(field.name)),
      })),
    }
  }
  return ensurePortalKindFields(withPortalFeedbackCopy(template))
}
