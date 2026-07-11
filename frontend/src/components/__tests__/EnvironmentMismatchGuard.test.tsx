import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

const validateEnvironmentMatch = vi.fn()
const getExpectedEnvironment = vi.fn(() => 'staging')
const getApiBaseUrl = vi.fn(() => 'https://qgp-staging-plantexpand.azurewebsites.net')

vi.mock('../../config/apiBase', () => ({
  validateEnvironmentMatch: () => validateEnvironmentMatch(),
  getExpectedEnvironment: () => getExpectedEnvironment(),
  getApiBaseUrl: () => getApiBaseUrl(),
}))

import EnvironmentMismatchGuard from '../EnvironmentMismatchGuard'

describe('EnvironmentMismatchGuard', () => {
  afterEach(() => {
    validateEnvironmentMatch.mockReset()
    vi.restoreAllMocks()
  })

  it('renders children when environments match', async () => {
    validateEnvironmentMatch.mockResolvedValue(null)
    render(
      <EnvironmentMismatchGuard>
        <div>App OK</div>
      </EnvironmentMismatchGuard>,
    )
    expect(await screen.findByText('App OK')).toBeInTheDocument()
  })

  it('shows mismatch UI and allows continue anyway', async () => {
    validateEnvironmentMatch.mockResolvedValue('Environment mismatch: Frontend expects staging')
    const user = userEvent.setup()
    render(
      <EnvironmentMismatchGuard>
        <div>App OK</div>
      </EnvironmentMismatchGuard>,
    )
    expect(await screen.findByText(/Environment Mismatch Detected/i)).toBeInTheDocument()
    expect(screen.getByText(/Frontend expects staging/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /Continue Anyway/i }))
    await waitFor(() => expect(screen.getByText('App OK')).toBeInTheDocument())
  })
})
