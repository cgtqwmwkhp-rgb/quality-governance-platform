/**
 * PX-282: stepper chrome must stay in sync with the visible step body.
 *
 * Production used AnimatePresence mode="wait", which advanced the step index,
 * progress bar and Continue/Submit label while the exiting panel still showed
 * the previous step — requiring two clicks and surfacing early validation (PX-283).
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

function field(overrides: Record<string, unknown>) {
  return {
    id: 1,
    name: 'field',
    label: 'Field',
    field_type: 'text',
    order: 0,
    is_required: false,
    width: 'full',
    ...overrides,
  }
}

function complaintStepTemplate(): FormTemplate {
  return {
    id: 3,
    name: 'Customer Complaint',
    slug: 'complaint-step-sync',
    form_type: 'complaint',
    version: 1,
    is_active: true,
    is_published: true,
    allow_drafts: false,
    allow_attachments: true,
    require_signature: false,
    auto_assign_reference: true,
    notify_on_submit: true,
    steps: [
      {
        id: 1,
        name: 'Customer Details',
        order: 0,
        fields: [
          field({
            id: 1,
            name: 'contract',
            label: 'Select Customer',
            field_type: 'select',
            is_required: true,
          }),
        ],
      },
      {
        id: 2,
        name: 'Complainant Details',
        order: 1,
        fields: [
          field({ id: 2, name: 'complainant_name', label: 'Complainant Name', is_required: true }),
          field({
            id: 3,
            name: 'complainant_contact',
            label: 'Contact Details',
            is_required: true,
            order: 1,
          }),
        ],
      },
      {
        id: 3,
        name: 'Complaint Details',
        order: 2,
        fields: [
          field({
            id: 4,
            name: 'description',
            label: 'Complaint Description',
            field_type: 'textarea',
            is_required: true,
          }),
        ],
      },
    ],
  }
}

beforeEach(() => {
  localStorage.clear()
})

describe('PX-282 AnimatePresence step sync', () => {
  it('keeps step heading, indicator and button aligned after one Continue click', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn().mockResolvedValue({ reference_number: 'CMP-99' })

    render(
      <DynamicFormRenderer
        template={complaintStepTemplate()}
        onSubmit={onSubmit}
        contractOptions={[{ value: 'acme', label: 'Acme Corp' }]}
        initialData={{ contract: 'acme' }}
      />,
    )

    expect(screen.getByRole('heading', { name: 'Customer Details' })).toBeInTheDocument()
    expect(screen.getByTestId('step-indicator-0')).toHaveAttribute('aria-current', 'step')
    expect(screen.getByRole('button', { name: /continue/i })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /continue/i }))

    // With mode="wait" removed, body and chrome advance together.
    expect(await screen.findByRole('heading', { name: 'Complainant Details' })).toBeInTheDocument()
    expect(screen.getByTestId('step-indicator-1')).toHaveAttribute('aria-current', 'step')
    expect(screen.getByRole('button', { name: /continue/i })).toBeInTheDocument()
    expect(screen.queryByTestId('submit-report-btn')).not.toBeInTheDocument()
    expect(screen.queryByText('Complainant Name is required')).not.toBeInTheDocument()
  })

  it('does not show Submit while complainant fields are still visible', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn().mockResolvedValue({ reference_number: 'CMP-99' })

    render(
      <DynamicFormRenderer
        template={complaintStepTemplate()}
        onSubmit={onSubmit}
        contractOptions={[{ value: 'acme', label: 'Acme Corp' }]}
        initialData={{ contract: 'acme' }}
      />,
    )

    await user.click(screen.getByRole('button', { name: /continue/i }))
    await screen.findByRole('heading', { name: 'Complainant Details' })

    await user.type(screen.getByLabelText(/Complainant Name/), 'Sam')
    await user.type(screen.getByLabelText(/Contact Details/), 'sam@example.com')
    await user.click(screen.getByRole('button', { name: /continue/i }))

    expect(await screen.findByRole('heading', { name: 'Complaint Details' })).toBeInTheDocument()
    expect(screen.getByTestId('submit-report-btn')).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Complainant Details' })).not.toBeInTheDocument()
  })
})
