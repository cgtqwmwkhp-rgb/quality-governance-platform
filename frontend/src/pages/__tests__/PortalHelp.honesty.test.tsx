import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import PortalHelp from '../PortalHelp'

const mockNavigate = vi.fn()

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: () => mockNavigate }
})

vi.mock('react-i18next', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-i18next')>()
  return {
    ...actual,
    useTranslation: () => ({
      t: (key: string, opts?: { count?: number }) => {
        if (key === 'portal.faq_count') return `${opts?.count ?? 0} FAQs`
        return key
      },
      i18n: { language: 'en', changeLanguage: vi.fn() },
    }),
  }
})

vi.mock('../../config/portalHelpContacts', () => ({
  getPortalHelpContacts: () => ({
    chatHref: null,
    emailHref: 'mailto:safety@example.com',
    phoneHref: null,
  }),
}))

describe('PortalHelp honesty', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('does not promise anonymous reporting (PX-312)', async () => {
    const user = userEvent.setup()
    render(
      <MemoryRouter>
        <PortalHelp />
      </MemoryRouter>,
    )

    await user.click(screen.getByRole('button', { name: /Privacy/i }))
    await user.click(screen.getByText('Can I submit a report anonymously?'))
    expect(screen.getByText(/No\. Reports submitted through the portal are attributable/i)).toBeInTheDocument()
    expect(screen.queryByText(/anonymous toggle/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/secret tracking code/i)).not.toBeInTheDocument()
  })

  it('shows FAQ counts derived from content, not article inflation (PX-313)', () => {
    render(
      <MemoryRouter>
        <PortalHelp />
      </MemoryRouter>,
    )
    expect(screen.getAllByText('2 FAQs').length).toBeGreaterThanOrEqual(2)
    expect(screen.getByText('3 FAQs')).toBeInTheDocument()
    expect(screen.queryByText(/articles/i)).not.toBeInTheDocument()
  })

  it('does not render a dead Was this helpful control (PX-314)', async () => {
    const user = userEvent.setup()
    render(
      <MemoryRouter>
        <PortalHelp />
      </MemoryRouter>,
    )
    await user.click(screen.getByRole('button', { name: /Reporting Issues/i }))
    await user.click(screen.getByText('How do I submit a report?'))
    expect(screen.queryByText(/Was this helpful/i)).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /thumbs/i })).not.toBeInTheDocument()
  })
})
