import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'

const hasRoleMock = vi.fn(() => true)

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    i18n: { language: 'en' },
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

vi.mock('../../api/client', () => ({
  notificationsApi: {
    getUnreadCount: vi.fn().mockResolvedValue({ data: { unread_count: 0 } }),
  },
}))

vi.mock('../../config/apiBase', () => ({
  API_BASE_URL: 'http://localhost:3000',
}))

vi.mock('../../utils/auth', () => ({
  hasRole: (...roles: string[]) => hasRoleMock(...roles),
}))

vi.mock('../copilot/AICopilot', () => ({
  default: () => <div data-testid="ai-copilot" />,
}))

vi.mock('../OfflineIndicator', () => ({
  default: () => null,
}))

vi.mock('../ui/ThemeToggle', () => ({
  ThemeToggle: () => <div data-testid="theme-toggle" />,
}))

describe('Layout', () => {
  const onLogout = vi.fn()

  beforeEach(() => {
    onLogout.mockClear()
    hasRoleMock.mockReset()
    hasRoleMock.mockReturnValue(true)
  })

  it('renders navigation sidebar with nav sections', async () => {
    const Layout = (await import('../Layout')).default

    render(
      <BrowserRouter>
        <Layout onLogout={onLogout} />
      </BrowserRouter>,
    )

    expect(screen.getByText('QGP')).toBeInTheDocument()
    expect(screen.getByText('nav.dashboard')).toBeInTheDocument()
    expect(screen.getByText('nav.incidents')).toBeInTheDocument()
  })

  it('renders the logout button', async () => {
    const Layout = (await import('../Layout')).default

    render(
      <BrowserRouter>
        <Layout onLogout={onLogout} />
      </BrowserRouter>,
    )

    expect(screen.getByText('logout')).toBeInTheDocument()
  })

  it('renders the search bar and header actions', async () => {
    const Layout = (await import('../Layout')).default

    render(
      <BrowserRouter>
        <Layout onLogout={onLogout} />
      </BrowserRouter>,
    )

    expect(screen.getByText(/search/)).toBeInTheDocument()
    expect(screen.getByTestId('theme-toggle')).toBeInTheDocument()
  })

  it('hides workforce navigation for unauthorized roles', async () => {
    hasRoleMock.mockReturnValue(false)
    const Layout = (await import('../Layout')).default

    render(
      <BrowserRouter>
        <Layout onLogout={onLogout} />
      </BrowserRouter>,
    )

    expect(screen.queryByText('nav.workforce')).not.toBeInTheDocument()
    expect(screen.queryByText('nav.assessments')).not.toBeInTheDocument()
  })
})
