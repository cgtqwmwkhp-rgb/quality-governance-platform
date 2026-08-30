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

  it('does not link the legal register when the schedule flag is off', () => {
    useFeatureFlagMock.mockImplementation((name: string) => name === 'register_catalogue')
    render(
      <MemoryRouter>
        <RegisterOfRegisters />
      </MemoryRouter>,
    )
    expect(screen.getByTestId('register-schedule-off-PEL-HSEQ-5056')).toHaveTextContent(
      'Schedule module is off in this deployment',
    )
    const scheduleHrefs = screen
      .queryAllByRole('link')
      .map((el) => el.getAttribute('href') ?? '')
      .filter((href) => href.startsWith('/compliance-schedule'))
    expect(scheduleHrefs).toEqual([])
  })

  it('opens the legal register with statutory=true when the schedule flag is on', () => {
    useFeatureFlagMock.mockReturnValue(true)
    render(
      <MemoryRouter>
        <RegisterOfRegisters />
      </MemoryRouter>,
    )
    const row = screen.getByText('PEL-HSEQ-5056').closest('tr')
    expect(row).not.toBeNull()
    expect(row!.querySelector('a')).toHaveAttribute(
      'href',
      '/compliance-schedule?register=PEL-HSEQ-5056&statutory=true',
    )
  })

  it('groups the existing table by function clusters without a second table', () => {
    useFeatureFlagMock.mockReturnValue(true)
    render(
      <MemoryRouter>
        <RegisterOfRegisters />
      </MemoryRouter>,
    )
    expect(screen.getAllByRole('table')).toHaveLength(1)
    expect(screen.getByTestId('register-cluster-cases')).toBeInTheDocument()
    expect(screen.getByTestId('register-cluster-assets')).toBeInTheDocument()
    expect(screen.getByTestId('register-cluster-clocks')).toBeInTheDocument()
    expect(screen.getByText('PEL-HSEQ-5010').closest('tbody')).toHaveAttribute(
      'data-testid',
      'register-cluster-cases',
    )
    expect(screen.getByText('PEL-HSEQ-5031').closest('tbody')).toHaveAttribute(
      'data-testid',
      'register-cluster-assets',
    )
  })

  it('shows EMPTY from catalogue note or absent band, never a counted zero', () => {
    useFeatureFlagMock.mockReturnValue(true)
    render(
      <MemoryRouter>
        <RegisterOfRegisters />
      </MemoryRouter>,
    )
    expect(screen.getByTestId('register-empty-PEL-HSEQ-5027')).toHaveTextContent('EMPTY')
    expect(screen.getByTestId('register-empty-PEL-DP-5008')).toHaveTextContent('EMPTY')
    expect(screen.queryByTestId('register-empty-PEL-HSEQ-5062')).not.toBeInTheDocument()
    expect(screen.queryByText(/record count/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/\b0 records\b/i)).not.toBeInTheDocument()
  })

  it('shows DUAL when a second system of record is named', () => {
    useFeatureFlagMock.mockReturnValue(true)
    render(
      <MemoryRouter>
        <RegisterOfRegisters />
      </MemoryRouter>,
    )
    expect(screen.getByTestId('register-dual-PEL-HSEQ-5032')).toHaveTextContent('DUAL')
    expect(screen.getByTestId('register-dual-PEL-IT-5003')).toHaveTextContent('DUAL')
  })

  it.each([
    ['PEL-HSEQ-5026', '/admin/forms?register=PEL-HSEQ-5026'],
    ['PEL-HSEQ-5036', '/admin/forms?register=PEL-HSEQ-5036'],
    ['PEL-HSEQ-5043', '/admin/forms?register=PEL-HSEQ-5043'],
  ])('opens %s on the Form Builder, still marked EMPTY (REG-SSOT-D1)', (docRef, href) => {
    useFeatureFlagMock.mockReturnValue(true)
    render(
      <MemoryRouter>
        <RegisterOfRegisters />
      </MemoryRouter>,
    )
    const row = screen.getByText(docRef).closest('tr')
    expect(row).not.toBeNull()
    expect(row!.querySelector('a')).toHaveAttribute('href', href)
    expect(screen.getByTestId(`register-empty-${docRef}`)).toHaveTextContent('EMPTY')
    expect(row).not.toHaveTextContent('No QGP list')
  })

  it('opens PEL-HSEQ-5052 on the Form Builder, still marked EMPTY (REG-SSOT-D2)', () => {
    useFeatureFlagMock.mockReturnValue(true)
    render(
      <MemoryRouter>
        <RegisterOfRegisters />
      </MemoryRouter>,
    )
    const row = screen.getByText('PEL-HSEQ-5052').closest('tr')
    expect(row).not.toBeNull()
    expect(row!.querySelector('a')).toHaveAttribute('href', '/admin/forms?register=PEL-HSEQ-5052')
    // Caption band, not a Library-document row any more, and no invented count
    // of transfer notes behind the link.
    expect(screen.getByTestId('register-empty-PEL-HSEQ-5052')).toHaveTextContent('EMPTY')
    expect(row).not.toHaveTextContent('No QGP list')
    expect(row).not.toHaveTextContent('Library document')
  })

  it('opens PEL-PROC-5014 on the actions spine, still marked EMPTY (REG-SSOT-D3)', () => {
    useFeatureFlagMock.mockReturnValue(true)
    render(
      <MemoryRouter>
        <RegisterOfRegisters />
      </MemoryRouter>,
    )
    const row = screen.getByText('PEL-PROC-5014').closest('tr')
    expect(row).not.toBeNull()
    expect(row!.querySelector('a')).toHaveAttribute('href', '/actions?register=PEL-PROC-5014')
    // Caption over the whole action register — there is no slavery filter, so
    // the EMPTY chip has to survive the promotion out of the absent band.
    expect(screen.getByTestId('register-empty-PEL-PROC-5014')).toHaveTextContent('EMPTY')
  })

  it('leaves PEL-PROC-5011 unopenable, with no SAQ journey invented (REG-SSOT-D3)', () => {
    useFeatureFlagMock.mockReturnValue(true)
    render(
      <MemoryRouter>
        <RegisterOfRegisters />
      </MemoryRouter>,
    )
    const row = screen.getByText('PEL-PROC-5011').closest('tr')
    expect(row).not.toBeNull()
    expect(row!.querySelector('a')).toBeNull()
    expect(screen.getByTestId('register-empty-PEL-PROC-5011')).toHaveTextContent('EMPTY')
  })

  it('does not add ISO chip filters on the hub', () => {
    useFeatureFlagMock.mockReturnValue(true)
    render(
      <MemoryRouter>
        <RegisterOfRegisters />
      </MemoryRouter>,
    )
    const tabs = screen.getByRole('tablist').querySelectorAll('[role="tab"]')
    expect([...tabs].map((el) => el.textContent)).toEqual([
      'All',
      'LIVE',
      'Caption',
      'Document',
      'Not captured',
      'This hub',
    ])
  })
})
