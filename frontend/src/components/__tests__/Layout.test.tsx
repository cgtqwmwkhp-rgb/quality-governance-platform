import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { BrowserRouter } from 'react-router-dom'

const hasRoleMock = vi.fn(() => true)
const isSuperuserMock = vi.fn(() => true)
const useFeatureFlagMock = vi.fn(() => true)

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
  isSuperuser: () => isSuperuserMock(),
}))

vi.mock('../../hooks/useFeatureFlag', () => ({
  useFeatureFlag: (flagName: string) => useFeatureFlagMock(flagName),
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
  const navLink = (path: string) =>
    document.querySelector<HTMLAnchorElement>(`nav a[href="${path}"]`)

  beforeEach(() => {
    window.history.pushState({}, '', '/dashboard')
    onLogout.mockClear()
    hasRoleMock.mockReset()
    hasRoleMock.mockReturnValue(true)
    isSuperuserMock.mockReset()
    isSuperuserMock.mockReturnValue(true)
    useFeatureFlagMock.mockReset()
    useFeatureFlagMock.mockReturnValue(true)
  })

  it('renders the requested first-level hub structure', async () => {
    const Layout = (await import('../Layout')).default

    render(
      <BrowserRouter>
        <Layout onLogout={onLogout} />
      </BrowserRouter>,
    )

    expect(screen.getByText('QGP')).toBeInTheDocument()
    expect(navLink('/dashboard')).toHaveTextContent('nav.home')

    for (const hub of [
      'nav.my_work',
      'nav.safety_cases',
      'nav.workforce',
      'nav.assurance',
      'nav.compliance_sustainability',
      'nav.risk_improvement',
      'nav.library',
      'nav.admin',
    ]) {
      expect(screen.getByRole('button', { name: hub })).toHaveAttribute('aria-expanded', 'false')
    }

    expect(screen.queryByRole('button', { name: /nav\.more|More/i })).not.toBeInTheDocument()
  })

  it('shows each hub child as a direct link after one expansion click', async () => {
    const user = userEvent.setup()
    const Layout = (await import('../Layout')).default

    render(
      <BrowserRouter>
        <Layout onLogout={onLogout} />
      </BrowserRouter>,
    )

    const hubs = [
      ['nav.my_work', ['/actions', '/workflows']],
      [
        'nav.safety_cases',
        [
          '/incidents',
          '/near-misses',
          '/rtas',
          '/complaints',
          '/investigations',
          '/vehicle-checklists',
        ],
      ],
      [
        'nav.workforce',
        [
          '/workforce/dashboard',
          '/workforce/assessments',
          '/workforce/training',
          '/workforce/engineers',
          '/workforce/calendar',
        ],
      ],
      [
        'nav.assurance',
        ['/audits', '/audit-templates', '/uvdb', '/planet-mark', '/customer-audits'],
      ],
      [
        'nav.compliance_sustainability',
        ['/ims', '/standards', '/compliance', '/compliance-automation'],
      ],
      ['nav.risk_improvement', ['/risk-register']],
      ['nav.library', ['/documents', '/policies']],
      ['nav.admin', ['/admin/users']],
    ] as const

    for (const [hub, paths] of hubs) {
      const trigger = screen.getByRole('button', { name: hub })
      await user.click(trigger)
      expect(trigger).toHaveAttribute('aria-expanded', 'true')

      for (const path of paths) {
        expect(navLink(path)).toBeInTheDocument()
      }
    }
  })

  it('does not expose W0 dead and demo routes in the sidebar', async () => {
    const Layout = (await import('../Layout')).default

    render(
      <BrowserRouter>
        <Layout onLogout={onLogout} />
      </BrowserRouter>,
    )

    for (const path of [
      '/analytics',
      '/analytics/advanced',
      '/analytics/dashboards',
      '/analytics/reports',
      '/calendar',
      '/exports',
      '/ai-intelligence',
      '/signatures',
      '/audit-trail',
    ]) {
      expect(navLink(path)).not.toBeInTheDocument()
    }
  })

  it('auto-expands the hub containing the active child route', async () => {
    window.history.pushState({}, '', '/workflows/active')
    const Layout = (await import('../Layout')).default

    render(
      <BrowserRouter>
        <Layout onLogout={onLogout} />
      </BrowserRouter>,
    )

    expect(screen.getByRole('button', { name: 'nav.my_work' })).toHaveAttribute(
      'aria-expanded',
      'true',
    )
    expect(navLink('/workflows')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'nav.assurance' })).toHaveAttribute(
      'aria-expanded',
      'false',
    )
  })

  it('applies workforce and compliance automation role gates', async () => {
    const user = userEvent.setup()
    hasRoleMock.mockReturnValue(false)
    isSuperuserMock.mockReturnValue(false)
    const Layout = (await import('../Layout')).default

    render(
      <BrowserRouter>
        <Layout onLogout={onLogout} />
      </BrowserRouter>,
    )

    expect(screen.queryByRole('button', { name: 'nav.workforce' })).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'nav.compliance_sustainability' }))

    expect(navLink('/ims')).toBeInTheDocument()
    expect(navLink('/standards')).toBeInTheDocument()
    expect(navLink('/compliance')).toBeInTheDocument()
    expect(navLink('/compliance-automation')).not.toBeInTheDocument()
  })

  it('only shows the Admin hub when user management is enabled for a superuser', async () => {
    useFeatureFlagMock.mockReturnValue(false)
    const Layout = (await import('../Layout')).default

    render(
      <BrowserRouter>
        <Layout onLogout={onLogout} />
      </BrowserRouter>,
    )

    expect(screen.queryByRole('button', { name: 'nav.admin' })).not.toBeInTheDocument()
  })

  it('renders the persistent sidebar and header controls', async () => {
    const Layout = (await import('../Layout')).default

    render(
      <BrowserRouter>
        <Layout onLogout={onLogout} />
      </BrowserRouter>,
    )

    expect(screen.getByText('logout')).toBeInTheDocument()
    expect(screen.getByText(/search/)).toBeInTheDocument()
    expect(screen.getByTestId('theme-toggle')).toBeInTheDocument()
  })

  it('lazy-mounts AI Copilot only after the header control is opened', async () => {
    const user = userEvent.setup()
    const Layout = (await import('../Layout')).default

    render(
      <BrowserRouter>
        <Layout onLogout={onLogout} />
      </BrowserRouter>,
    )

    expect(screen.queryByTestId('ai-copilot')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /nav\.copilot/i }))

    expect(await screen.findByTestId('ai-copilot')).toBeInTheDocument()
  })
})
