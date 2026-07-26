import { describe, expect, it } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'

import SystemSettings from '../SystemSettings'

describe('SystemSettings', () => {
  it('labels each setting in plain English rather than by its internal key (PX-198)', () => {
    render(<SystemSettings />)

    expect(screen.getByText('Company name')).toBeInTheDocument()
    expect(screen.getByText('Company logo URL')).toBeInTheDocument()
    expect(screen.queryByText('company_name')).not.toBeInTheDocument()
    expect(screen.queryByText('company_logo_url')).not.toBeInTheDocument()
  })

  it('keeps keys out of the other input types too', () => {
    render(<SystemSettings />)

    fireEvent.click(screen.getByRole('button', { name: /security/i }))

    expect(screen.getByText('Session timeout minutes')).toBeInTheDocument()
    expect(screen.getByText('Require MFA')).toBeInTheDocument()
    expect(screen.queryByText('session_timeout_minutes')).not.toBeInTheDocument()
    expect(screen.queryByText('require_mfa')).not.toBeInTheDocument()
  })
})
