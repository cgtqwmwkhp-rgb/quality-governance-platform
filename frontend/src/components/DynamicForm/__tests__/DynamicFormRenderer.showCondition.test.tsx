/**
 * Hidden required fields must not block Continue / Submit.
 * Compliment subject is required only when feedback_kind is compliment.
 */
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { FormTemplate } from '../../../services/api'

vi.mock('../../../hooks/useVoiceToText', () => ({
  useVoiceToText: () => ({ isListening: false, isSupported: false, toggleListening: vi.fn() }),
}))

vi.mock('../../../hooks/useGeolocation', () => ({
  useGeolocation: () => ({ isLoading: false, getLocationString: vi.fn(), error: null }),
}))

vi.mock('framer-motion', () => {
  const Passthrough = ({ children, ...props }: { children?: ReactNode; [key: string]: unknown }) => {
    const { initial: _i, animate: _a, exit: _e, transition: _t, ...rest } = props
    return <div {...rest}>{children}</div>
  }
  return {
    AnimatePresence: ({ children }: { children?: ReactNode }) => <>{children}</>,
    motion: new Proxy({}, { get: () => Passthrough }),
  }
})

import DynamicFormRenderer from '../DynamicFormRenderer'

function template(): FormTemplate {
  return {
    id: 3,
    name: 'Customer Feedback',
    slug: 'complaint-show-condition',
    form_type: 'complaint',
    version: 1,
    is_active: true,
    is_published: true,
    allow_drafts: false,
    allow_attachments: false,
    require_signature: false,
    auto_assign_reference: true,
    notify_on_submit: true,
    steps: [
      {
        id: 1,
        name: 'Feedback Details',
        order: 0,
        fields: [
          {
            id: 1,
            name: 'feedback_kind',
            label: 'What kind of feedback',
            field_type: 'select',
            order: 0,
            is_required: true,
            width: 'full',
            options: [
              { value: 'complaint', label: 'Complaint' },
              { value: 'compliment', label: 'Compliment' },
            ],
          },
          {
            id: 2,
            name: 'subject_name',
            label: 'Who is this compliment about',
            field_type: 'text',
            order: 1,
            is_required: true,
            width: 'full',
            show_condition: { field: 'feedback_kind', equals: 'compliment' },
          },
          {
            id: 3,
            name: 'description',
            label: 'Details',
            field_type: 'textarea',
            order: 2,
            is_required: true,
            width: 'full',
          },
        ],
      },
    ],
  }
}

beforeEach(() => {
  localStorage.clear()
})

describe('show_condition', () => {
  it('hides the compliment subject until kind is compliment', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn().mockResolvedValue({ reference_number: 'COMP-2026-0001' })

    render(
      <DynamicFormRenderer
        template={template()}
        onSubmit={onSubmit}
        initialData={{ feedback_kind: 'complaint', description: 'The crate arrived damaged.' }}
      />,
    )

    expect(screen.queryByLabelText(/Who is this compliment about/)).not.toBeInTheDocument()
    await user.click(screen.getByTestId('submit-report-btn'))
    expect(onSubmit).toHaveBeenCalled()
  })

  it('requires the named subject when kind is compliment', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn().mockResolvedValue({ reference_number: 'CMND-2026-0001' })

    render(
      <DynamicFormRenderer
        template={template()}
        onSubmit={onSubmit}
        initialData={{ feedback_kind: 'compliment', description: 'The fitter was outstanding.' }}
      />,
    )

    expect(screen.getByLabelText(/Who is this compliment about/)).toBeInTheDocument()
    await user.click(screen.getByTestId('submit-report-btn'))
    expect(onSubmit).not.toHaveBeenCalled()
    expect(screen.getByText(/Who is this compliment about is required/)).toBeInTheDocument()
  })
})
