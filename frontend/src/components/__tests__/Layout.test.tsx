import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { BrowserRouter, MemoryRouter } from 'react-router-dom'

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

vi.mock('../../api/safetyAssetsClient', () => ({
  safetyAssetsApi: {
    listPendingSafetyLookups: vi.fn().mockResolvedValue({ data: { items: [], total: 0 } }),
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

    expect(screen.getByText('brand.product_name')).toBeInTheDocument()
    expect(screen.getByText('brand.company_line')).toBeInTheDocument()
    expect(screen.queryByText('QGP')).not.toBeInTheDocument()
    expect(screen.queryByText('PRO')).not.toBeInTheDocument()
    expect(navLink('/dashboard')).toHaveTextContent('nav.home')

    for (const hub of [
      'nav.my_work',
      'nav.safety_cases',
      'nav.workforce',
      'nav.assurance',
      'nav.compliance_sustainability',
      'nav.risk_improvement',
      'nav.insights',
      'nav.admin',
    ]) {
      expect(screen.getByRole('button', { name: hub })).toHaveAttribute('aria-expanded', 'false')
    }

    expect(navLink('/documents')).toHaveTextContent('nav.library')
    expect(screen.queryByRole('button', { name: 'nav.library' })).not.toBeInTheDocument()
    expect(navLink('/policies')).not.toBeInTheDocument()

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
      ['nav.my_work', ['/actions', '/my-reading', '/my-compliance', '/workflows']],
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
          '/workforce/competence-gaps',
        ],
      ],
      [
        'nav.assurance',
        ['/audits', '/audit-templates', '/uvdb', '/planet-mark', '/customer-audits'],
      ],
      [
        'nav.compliance_sustainability',
        [
          '/ims',
          '/standards',
          '/compliance',
          '/knowledge-exceptions',
          '/document-control',
          '/compliance-automation',
        ],
      ],
      ['nav.risk_improvement', ['/risk-register']],
      [
        'nav.insights',
        ['/analytics', '/calendar', '/exports', '/ai-intelligence'],
      ],
      [
        'nav.admin',
        [
          '/admin',
          '/admin/users',
          '/audit-trail',
          '/admin/forms',
          '/admin/settings',
          '/admin/notifications',
          '/admin/hsec-inbox',
          '/admin/lookups',
          '/admin/contracts',
        ],
      ],
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

  it('exposes Library and Document campaigns sidebar entries', async () => {
    const Layout = (await import('../Layout')).default

    render(
      <BrowserRouter>
        <Layout onLogout={onLogout} />
      </BrowserRouter>,
    )

    const libraryLink = navLink('/documents')
    expect(libraryLink).toBeInTheDocument()
    expect(libraryLink).toHaveTextContent('nav.library')
    expect(libraryLink).toHaveAttribute('href', '/documents')
    expect(navLink('/documents/campaigns')).toBeInTheDocument()
    expect(navLink('/policies')).not.toBeInTheDocument()
    expect(screen.queryByText('nav.documents')).not.toBeInTheDocument()
    expect(screen.queryByText('nav.policies')).not.toBeInTheDocument()
  })

  it('marks Library active on /documents and /policies routes', async () => {
    const Layout = (await import('../Layout')).default

    for (const path of ['/documents', '/policies', '/documents/42', '/policies/7']) {
      cleanup()

      render(
        <MemoryRouter initialEntries={[path]}>
          <Layout onLogout={onLogout} />
        </MemoryRouter>,
      )

      expect(screen.getByRole('link', { name: 'nav.library' })).toHaveAttribute(
        'aria-current',
        'page',
      )
    }
  })

  it('marks Document campaigns active on /documents/campaigns without Library', async () => {
    const Layout = (await import('../Layout')).default

    render(
      <MemoryRouter initialEntries={['/documents/campaigns']}>
        <Layout onLogout={onLogout} />
      </MemoryRouter>,
    )

    expect(navLink('/documents/campaigns')).toHaveAttribute('aria-current', 'page')
    expect(screen.getByRole('link', { name: 'nav.library' })).not.toHaveAttribute(
      'aria-current',
      'page',
    )
  })

  it('exposes Insights hub links for analytics, calendar, exports, and AI', async () => {
    const user = userEvent.setup()
    const Layout = (await import('../Layout')).default

    render(
      <BrowserRouter>
        <Layout onLogout={onLogout} />
      </BrowserRouter>,
    )

    const insightsHub = screen.getByRole('button', { name: 'nav.insights' })
    await user.click(insightsHub)

    for (const path of ['/analytics', '/calendar', '/exports', '/ai-intelligence']) {
      expect(navLink(path)).toBeInTheDocument()
    }
  })

  it('does not expose orphaned analytics subpaths or demo routes in the sidebar', async () => {
    const Layout = (await import('../Layout')).default

    render(
      <BrowserRouter>
        <Layout onLogout={onLogout} />
      </BrowserRouter>,
    )

    for (const path of [
      '/analytics/advanced',
      '/analytics/dashboards',
      '/analytics/reports',
      '/signatures',
    ]) {
      expect(navLink(path)).not.toBeInTheDocument()
    }
  })

  it('points the header Settings gear to Admin Console for superusers', async () => {
    const Layout = (await import('../Layout')).default

    render(
      <BrowserRouter>
        <Layout onLogout={onLogout} />
      </BrowserRouter>,
    )

    expect(screen.getByRole('link', { name: 'nav.settings' })).toHaveAttribute('href', '/admin')
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

  it('keeps Compliance & Sustainability flush with other top-level hubs', async () => {
    const Layout = (await import('../Layout')).default

    render(
      <BrowserRouter>
        <Layout onLogout={onLogout} />
      </BrowserRouter>,
    )

    const assurance = screen.getByTestId('nav-hub-btn-assurance')
    const compliance = screen.getByTestId('nav-hub-btn-compliance-sustainability')
    const risk = screen.getByTestId('nav-hub-btn-risk-improvement')

    expect(compliance.closest('[class*="ml-"]')).toBeNull()
    expect(assurance.className).toBe(compliance.className)
    expect(risk.className).toBe(compliance.className)
    expect(compliance.className).toMatch(/w-full/)
    expect(compliance.className).toMatch(/text-left/)
    expect(compliance.className).not.toMatch(/\bml-4\b/)
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
