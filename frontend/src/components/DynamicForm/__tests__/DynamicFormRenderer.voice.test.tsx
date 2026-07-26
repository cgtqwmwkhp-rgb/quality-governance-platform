import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

vi.mock('framer-motion', () => ({
  AnimatePresence: ({ children }: { children?: React.ReactNode }) => <>{children}</>,
  motion: {
    div: ({ children, ...props }: { children?: React.ReactNode }) => <div {...props}>{children}</div>,
  },
}))

vi.mock('../../../hooks/useGeolocation', () => ({
  useGeolocation: () => ({ isLoading: false, getLocationString: vi.fn(), error: null }),
}))

const toggleListening = vi.fn()

vi.mock('../../../hooks/useVoiceToText', () => ({
  useVoiceToText: () => ({
    isListening: false,
    isSupported: true,
    toggleListening,
    error: 'Microphone access denied. Please allow microphone permissions.',
  }),
}))

import DynamicFormRenderer from '../DynamicFormRenderer'
import type { FormTemplate } from '../../../services/api'

const template: FormTemplate = {
  id: 1,
  name: 'Incident',
  slug: 'incident',
  form_type: 'incident',
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
      name: 'Details',
      order: 0,
      fields: [
        {
          id: 1,
          name: 'description',
          label: 'Description',
          field_type: 'textarea',
          order: 0,
          is_required: true,
          width: 'full',
        },
      ],
    },
  ],
}

describe('PX-328 voice input error surfacing', () => {
  it('shows the microphone permission message beneath the field', async () => {
    const user = userEvent.setup()
    render(
      <DynamicFormRenderer
        template={template}
        onSubmit={vi.fn().mockResolvedValue({ reference_number: 'INC-1' })}
      />,
    )

    await user.click(screen.getByRole('button', { name: 'Start voice input' }))

    expect(
      screen.getByText('Microphone access denied. Please allow microphone permissions.'),
    ).toBeInTheDocument()
  })
})
