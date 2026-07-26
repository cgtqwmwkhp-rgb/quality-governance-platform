import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

const mockList = vi.fn()
const mockUpdate = vi.fn()

vi.mock('../../../api/client', async () => {
  const actual = await vi.importActual<typeof import('../../../api/client')>('../../../api/client')
  return {
    ...actual,
    settingsApi: {
      list: (...args: unknown[]) => mockList(...args),
      update: (...args: unknown[]) => mockUpdate(...args),
      get: vi.fn(),
    },
  }
})

import SystemSettings from '../SystemSettings'

describe('SystemSettings', () => {
  beforeEach(() => {
    mockList.mockReset()
    mockUpdate.mockReset()
    mockList.mockResolvedValue({
      items: [
        {
          key: 'company_name',
          value: 'Plantexpand Limited',
          category: 'branding',
          description: 'Company name displayed throughout the system',
          value_type: 'string',
          is_editable: true,
        },
        {
          key: 'primary_color',
          value: '#0B6E4F',
          category: 'branding',
          value_type: 'color',
          is_editable: true,
        },
        {
          key: 'support_email',
          value: 'support@plantexpand.com',
          category: 'contact',
          value_type: 'email',
          is_editable: true,
        },
      ],
      total: 3,
    })
  })

  it('labels each setting in plain English rather than by its internal key (PX-198)', async () => {
    render(<SystemSettings />)

    expect(await screen.findByDisplayValue('Plantexpand Limited')).toBeInTheDocument()
    expect(screen.getByText('Company name')).toBeInTheDocument()
    expect(screen.getByText('Company logo URL')).toBeInTheDocument()
    expect(screen.queryByText('company_name')).not.toBeInTheDocument()
    expect(screen.queryByText('company_logo_url')).not.toBeInTheDocument()
  })

  it('keeps keys out of the other input types too', async () => {
    render(<SystemSettings />)
    await screen.findByDisplayValue('Plantexpand Limited')

    fireEvent.click(screen.getByRole('button', { name: /security/i }))

    expect(screen.getByText('Session timeout minutes')).toBeInTheDocument()
    expect(screen.getByText('Require MFA')).toBeInTheDocument()
    expect(screen.queryByText('session_timeout_minutes')).not.toBeInTheDocument()
    expect(screen.queryByText('require_mfa')).not.toBeInTheDocument()
  })

  it('loads live branding from the settings API instead of black defaults (PX-227)', async () => {
    render(<SystemSettings />)

    expect(await screen.findByDisplayValue('Plantexpand Limited')).toBeInTheDocument()
    expect(screen.getByDisplayValue('#0B6E4F')).toBeInTheDocument()
    expect(screen.queryByTestId('branding-unset-honesty')).not.toBeInTheDocument()
    expect(mockList).toHaveBeenCalled()
  })

  it('shows support-contact honesty when contact fields are empty (PX-228)', async () => {
    mockList.mockResolvedValue({
      items: [{ key: 'company_name', value: 'Acme', category: 'branding', value_type: 'string' }],
      total: 1,
    })
    render(<SystemSettings />)
    await screen.findByDisplayValue('Acme')

    fireEvent.click(screen.getByRole('button', { name: /contact details/i }))
    expect(await screen.findByTestId('support-contact-unset-honesty')).toBeInTheDocument()
  })

  it('constrains regional settings to selects (PX-229)', async () => {
    render(<SystemSettings />)
    await screen.findByDisplayValue('Plantexpand Limited')

    fireEvent.click(screen.getByRole('button', { name: /regional/i }))
    expect(await screen.findByTestId('setting-select-date_format')).toBeInTheDocument()
    expect(screen.getByTestId('setting-select-timezone')).toBeInTheDocument()
    expect(screen.getByTestId('setting-select-language')).toBeInTheDocument()
  })

  it('blocks save until settings have loaded', async () => {
    let resolveList: (value: unknown) => void = () => {}
    mockList.mockReturnValue(
      new Promise((resolve) => {
        resolveList = resolve
      }),
    )
    render(<SystemSettings />)

    expect(screen.getByTestId('system-settings-loading')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /save changes/i })).toBeDisabled()

    resolveList({ items: [], total: 0 })
    await waitFor(() => {
      expect(screen.queryByTestId('system-settings-loading')).not.toBeInTheDocument()
    })
  })
})
