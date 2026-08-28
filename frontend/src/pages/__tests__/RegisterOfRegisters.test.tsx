import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import RegisterOfRegisters from '../RegisterOfRegisters'

const useFeatureFlagMock = vi.fn(() => true)

vi.mock('../../hooks/useFeatureFlag', () => ({
  useFeatureFlag: (name: string) => useFeatureFlagMock(name),
}))

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (_key: string, fallback?: string) => fallback ?? _key,
    i18n: { language: 'en' },
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

describe('RegisterOfRegisters', () => {
  it('renders the hub table when the flag is on', () => {
    useFeatureFlagMock.mockReturnValue(true)
    render(
      <MemoryRouter>
        <RegisterOfRegisters />
      </MemoryRouter>,
    )
    expect(screen.getByRole('heading', { level: 1, name: 'Registers' })).toBeInTheDocument()
    expect(screen.getByRole('table')).toBeInTheDocument()
    expect(screen.getByText('PEL-HSEQ-5062')).toBeInTheDocument()
    expect(screen.queryByText('Page not found')).not.toBeInTheDocument()
  })

  it('renders NotFound when the flag is off', () => {
    useFeatureFlagMock.mockReturnValue(false)
    render(
      <MemoryRouter>
        <RegisterOfRegisters />
      </MemoryRouter>,
    )
    expect(screen.getByRole('heading', { name: 'Page not found' })).toBeInTheDocument()
    expect(screen.queryByTestId('register-of-registers')).not.toBeInTheDocument()
  })

  it('filters by search without inventing a count column', async () => {
    useFeatureFlagMock.mockReturnValue(true)
    const user = userEvent.setup()
    render(
      <MemoryRouter>
        <RegisterOfRegisters />
      </MemoryRouter>,
    )
    await user.type(screen.getByLabelText('Search'), 'RIDDOR')
    expect(screen.getByText('PEL-HSEQ-5033')).toBeInTheDocument()
    expect(screen.queryByText('PEL-HSEQ-5021')).not.toBeInTheDocument()
    expect(screen.queryByText(/record count/i)).not.toBeInTheDocument()
  })
})
