import { describe, expect, it } from 'vitest'
import type { FormTemplate } from '../../services/api'
import { applyFeedbackKindTemplate } from '../feedbackKind'

function complaintTemplate(): FormTemplate {
  return {
    id: 3,
    name: 'Customer Complaint',
    slug: 'complaint',
    description: 'Submit customer complaints',
    form_type: 'complaint',
    version: 1,
    is_active: true,
    is_published: true,
    allow_drafts: true,
    allow_attachments: true,
    require_signature: false,
    auto_assign_reference: true,
    notify_on_submit: true,
    steps: [
      {
        id: 1,
        name: 'Complaint Details',
        description: 'Describe the complaint',
        order: 0,
        fields: [
          {
            id: 7,
            name: 'description',
            label: 'Complaint Description',
            field_type: 'textarea',
            order: 0,
            is_required: true,
            width: 'full',
          },
          {
            id: 9101,
            name: 'feedback_kind',
            label: 'What kind of feedback',
            field_type: 'select',
            order: -2,
            is_required: true,
            width: 'full',
          },
        ],
      },
    ],
  }
}

describe('applyFeedbackKindTemplate', () => {
  it('strips kind fields when the flag is off', () => {
    const gated = applyFeedbackKindTemplate(complaintTemplate(), false)
    const names = gated.steps.flatMap((step) => step.fields.map((field) => field.name))
    expect(names).toEqual(['description'])
    expect(gated.name).toBe('Customer Complaint')
  })

  it('injects subject_name with show_condition and retitles when the flag is on', () => {
    const gated = applyFeedbackKindTemplate(complaintTemplate(), true)
    const fields = gated.steps[0].fields
    expect(gated.name).toBe('Customer Feedback')
    expect(fields.some((field) => field.name === 'feedback_kind')).toBe(true)
    const subject = fields.find((field) => field.name === 'subject_name')
    expect(subject?.show_condition).toEqual({ field: 'feedback_kind', equals: 'compliment' })
  })
})
