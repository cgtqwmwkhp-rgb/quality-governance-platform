import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, cleanup, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { BrowserRouter, MemoryRouter } from 'react-router-dom'
import { usePreferencesStore } from '../../stores/usePreferencesStore'

const hasRoleMock = vi.fn(() => true)
const isSuperuserMock = vi.fn(() => true)
const useFeatureFlagMock = vi.fn(() => true)
const isAICopilotDemoEnabledMock = vi.fn(() => false)
const isAIIntelligenceRouteEnabledMock = vi.fn(() => false)

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
  searchApi: {
    search: vi.fn().mockResolvedValue({ data: { results: [], total: 0, query: '', facets: {} } }),
    interpret: vi.fn().mockResolvedValue({
      data: { q: '', source: 'keyword' },
    }),
  },
  getApiErrorMessage: (error: unknown) => (error instanceof Error ? error.message : 'error'),
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

vi.mock('../../config/aiCopilotDemo', () => ({
  isAICopilotDemoEnabled: () => isAICopilotDemoEnabledMock(),
}))

vi.mock('../../config/aiIntelligenceRoute', () => ({
  isAIIntelligenceRouteEnabled: () => isAIIntelligenceRouteEnabledMock(),
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
    usePreferencesStore.setState({ sidebarCollapsed: false })
    hasRoleMock.mockReset()
    hasRoleMock.mockReturnValue(true)
    isSuperuserMock.mockReset()
    isSuperuserMock.mockReturnValue(true)
    useFeatureFlagMock.mockReset()
    useFeatureFlagMock.mockReturnValue(true)
    isAICopilotDemoEnabledMock.mockReset()
    isAICopilotDemoEnabledMock.mockReturnValue(false)
    isAIIntelligenceRouteEnabledMock.mockReset()
    isAIIntelligenceRouteEnabledMock.mockReturnValue(false)
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
      'nav.audits_hub',
      'nav.compliance_sustainability',
      'nav.risk_improvement',
      'nav.library',
      'nav.insights',
      'nav.admin',
    ]) {
      expect(screen.getByRole('button', { name: hub })).toHaveAttribute('aria-expanded', 'false')
    }

    expect(navLink('/documents')).not.toBeInTheDocument()
    expect(navLink('/document-control')).not.toBeInTheDocument()
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
      ['nav.my_work', ['/actions', '/my-reading', '/my-compliance']],
      [
        'nav.safety_cases',
        ['/incidents', '/near-misses', '/rtas', '/complaints', '/investigations'],
      ],
      ['nav.fleet_assets', ['/vehicle-checklists', '/safety-assets']],
      [
        'nav.workforce',
        [
          '/workforce/dashboard',
          '/workforce/assessments',
          '/workforce/training',
          '/workforce/engineers',
        ],
      ],
      [
        'nav.audits_hub',
        ['/audits', '/audit-templates', '/customer-audits'],
      ],
      [
        'nav.compliance_sustainability',
        [
          '/ims',
          '/compliance',
          '/knowledge-exceptions',
          '/compliance-schedule',
          '/compliance-automation',
        ],
      ],
      ['nav.risk_improvement', ['/risk-register', '/job-lifecycle']],
      ['nav.library', ['/documents', '/document-control']],
      [
        'nav.insights',
        ['/analytics', '/calendar', '/exports'],
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
          '/admin/hseq-inbox',
          '/admin/lookups',
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

  it('places Customer & external under Audits and keeps UVDB/Planet Mark off the sidebar (N-NAV)', async () => {
    const user = userEvent.setup()
    const Layout = (await import('../Layout')).default

    render(
      <BrowserRouter>
        <Layout onLogout={onLogout} />
      </BrowserRouter>,
    )

    await user.click(screen.getByRole('button', { name: 'nav.audits_hub' }))
    const assurancePanel = screen.getByTestId('nav-hub-assurance')
    expect(within(assurancePanel).getByRole('link', { name: 'nav.audits' })).toHaveAttribute(
      'href',
      '/audits',
    )
    expect(within(assurancePanel).getByRole('link', { name: 'nav.audit_builder' })).toHaveAttribute(
      'href',
      '/audit-templates',
    )
    expect(
      within(assurancePanel).getByRole('link', { name: 'nav.customer_external' }),
    ).toHaveAttribute('href', '/customer-audits')
    expect(within(assurancePanel).queryByRole('link', { name: 'nav.uvdb_achilles' })).not.toBeInTheDocument()
    expect(within(assurancePanel).queryByRole('link', { name: 'nav.planet_mark' })).not.toBeInTheDocument()
    expect(
      within(assurancePanel).queryByRole('link', { name: /nav\.customer_audits|nav\.customer_programme/ }),
    ).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'nav.compliance_sustainability' }))
    const compliancePanel = screen.getByTestId('nav-hub-compliance-sustainability')
    expect(within(compliancePanel).getByRole('link', { name: 'nav.standards' })).toHaveAttribute(
      'href',
      '/compliance',
    )
    expect(within(compliancePanel).queryByRole('link', { name: 'nav.uvdb_achilles' })).not.toBeInTheDocument()
    expect(within(compliancePanel).queryByRole('link', { name: 'nav.planet_mark' })).not.toBeInTheDocument()
    expect(
      within(compliancePanel).queryByRole('link', { name: 'nav.customer_programme' }),
    ).not.toBeInTheDocument()
    expect(
      within(compliancePanel).queryByRole('link', { name: 'nav.customer_external' }),
    ).not.toBeInTheDocument()
  })

  it('auto-expands Compliance and marks Standards when a scheme home is the active route (N-NAV)', async () => {
    window.history.pushState({}, '', '/uvdb')
    const Layout = (await import('../Layout')).default

    render(
      <BrowserRouter>
        <Layout onLogout={onLogout} />
      </BrowserRouter>,
    )

    expect(screen.getByRole('button', { name: 'nav.compliance_sustainability' })).toHaveAttribute(
      'aria-expanded',
      'true',
    )
    expect(screen.getByRole('button', { name: 'nav.audits_hub' })).toHaveAttribute(
      'aria-expanded',
      'false',
    )
    expect(navLink('/uvdb')).not.toBeInTheDocument()
    expect(navLink('/compliance').className).toContain('bg-primary/10')
  })

  it('auto-expands Audits when Customer & external is the active route (N-NAV)', async () => {
    window.history.pushState({}, '', '/customer-audits')
    const Layout = (await import('../Layout')).default

    render(
      <BrowserRouter>
        <Layout onLogout={onLogout} />
      </BrowserRouter>,
    )

    expect(screen.getByRole('button', { name: 'nav.audits_hub' })).toHaveAttribute(
      'aria-expanded',
      'true',
    )
    expect(screen.getByRole('button', { name: 'nav.compliance_sustainability' })).toHaveAttribute(
      'aria-expanded',
      'false',
    )
    expect(navLink('/customer-audits')).toBeInTheDocument()
  })

  it('exposes Fleet & Assets as a first-level hub (not a Safety subsection)', async () => {
    const user = userEvent.setup()
    const Layout = (await import('../Layout')).default

    render(
      <BrowserRouter>
        <Layout onLogout={onLogout} />
      </BrowserRouter>,
    )

    const fleetHub = screen.getByRole('button', { name: 'nav.fleet_assets' })
    await user.click(fleetHub)
    const fleetPanel = screen.getByTestId('nav-hub-fleet-assets')
    expect(within(fleetPanel).getByRole('link', { name: /vehicle_checklists|Van/i })).toBeTruthy()
    expect(within(fleetPanel).getByRole('link', { name: /safety_asset_register|Asset Register/i })).toBeTruthy()
    expect(screen.queryByTestId('nav-group-fleet-assets')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'nav.safety_cases' }))
    const safetyPanel = screen.getByTestId('nav-hub-safety-cases')
    expect(within(safetyPanel).queryByRole('link', { name: /vehicle_checklists/i })).not.toBeInTheDocument()
    expect(within(safetyPanel).queryByRole('link', { name: /safety_asset_register/i })).not.toBeInTheDocument()
  })

  // FR-CS-CERT-IN-SCHEDULE: the shelf is a view of the Compliance Schedule, so it
  // has no nav entry of its own in any hub — reaching it goes through the schedule.
  it('does not list the Certificate shelf as a nav item beside the schedule', async () => {
    const user = userEvent.setup()
    const Layout = (await import('../Layout')).default

    render(
      <BrowserRouter>
        <Layout onLogout={onLogout} />
      </BrowserRouter>,
    )

    await user.click(screen.getByRole('button', { name: 'nav.compliance_sustainability' }))
    const compliancePanel = screen.getByTestId('nav-hub-compliance-sustainability')
    expect(
      within(compliancePanel).queryByRole('link', { name: /assurance_cert_shelf/i }),
    ).not.toBeInTheDocument()
    expect(within(compliancePanel).getByRole('link', { name: /compliance_schedule/i })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'nav.audits_hub' }))
    const assurancePanel = screen.getByTestId('nav-hub-assurance')
    expect(
      within(assurancePanel).queryByRole('link', { name: /assurance_cert_shelf/i }),
    ).not.toBeInTheDocument()

    expect(navLink('/assurance/certificates')).not.toBeInTheDocument()
  })

  it('exposes Library as a hub with Documents and Document Control, not campaigns or policies', async () => {
    const user = userEvent.setup()
    const Layout = (await import('../Layout')).default

    render(
      <BrowserRouter>
        <Layout onLogout={onLogout} />
      </BrowserRouter>,
    )

    const libraryHub = screen.getByRole('button', { name: 'nav.library' })
    await user.click(libraryHub)

    const libraryPanel = screen.getByTestId('nav-hub-library')
    expect(within(libraryPanel).getByRole('link', { name: 'nav.documents' })).toHaveAttribute(
      'href',
      '/documents',
    )
    expect(
      within(libraryPanel).getByRole('link', { name: 'nav.document_control' }),
    ).toHaveAttribute('href', '/document-control')
    // Document campaigns and Policies live under LibraryShell tabs, not the vertical menu.
    expect(navLink('/documents/campaigns')).not.toBeInTheDocument()
    expect(screen.queryByTestId('nav-document-campaigns')).not.toBeInTheDocument()
    expect(navLink('/policies')).not.toBeInTheDocument()
    expect(screen.queryByText('nav.policies')).not.toBeInTheDocument()
  })

  it('keeps Document Control out of Compliance after the Library move', async () => {
    const user = userEvent.setup()
    const Layout = (await import('../Layout')).default

    render(
      <BrowserRouter>
        <Layout onLogout={onLogout} />
      </BrowserRouter>,
    )

    await user.click(screen.getByRole('button', { name: 'nav.compliance_sustainability' }))
    const compliancePanel = screen.getByTestId('nav-hub-compliance-sustainability')
    expect(
      within(compliancePanel).queryByRole('link', { name: 'nav.document_control' }),
    ).not.toBeInTheDocument()
  })

  it('marks Library active on Library shell routes including campaigns', async () => {
    const Layout = (await import('../Layout')).default

    for (const path of [
      '/documents',
      '/policies',
      '/documents/42',
      '/policies/7',
      '/documents/campaigns',
    ]) {
      cleanup()

      render(
        <MemoryRouter initialEntries={[path]}>
          <Layout onLogout={onLogout} />
        </MemoryRouter>,
      )

      expect(screen.getByRole('button', { name: 'nav.library' })).toHaveAttribute(
        'aria-expanded',
        'true',
      )
      expect(navLink('/documents')).toHaveClass('bg-primary/10')
      expect(navLink('/documents/campaigns')).not.toBeInTheDocument()
    }
  })

  it('auto-expands Library and marks Document Control when that route is active', async () => {
    window.history.pushState({}, '', '/document-control')
    const Layout = (await import('../Layout')).default

    render(
      <BrowserRouter>
        <Layout onLogout={onLogout} />
      </BrowserRouter>,
    )

    expect(screen.getByRole('button', { name: 'nav.library' })).toHaveAttribute(
      'aria-expanded',
      'true',
    )
    expect(navLink('/document-control')).toHaveClass('bg-primary/10')
    expect(screen.getByRole('button', { name: 'nav.compliance_sustainability' })).toHaveAttribute(
      'aria-expanded',
      'false',
    )
  })

  // docs/ops/BUTTON_REGISTRY.yml targets these hooks by name for the UX coverage
  // gate (dashboard::nav-to-incidents / nav-to-rtas). Renaming the hub id or moving
  // either route to another hub must fail here, at PR time, rather than in the gate
  // after deployment.
  it('keeps the safety-cases hub hooks the UX coverage registry depends on', async () => {
    const user = userEvent.setup()
    const Layout = (await import('../Layout')).default

    render(
      <BrowserRouter>
        <Layout onLogout={onLogout} />
      </BrowserRouter>,
    )

    const toggle = screen.getByTestId('nav-hub-btn-safety-cases')
    expect(toggle).toHaveAttribute('aria-expanded', 'false')

    const container = screen.getByTestId('nav-hub-safety-cases')
    expect(container.querySelector('a[href="/incidents"]')).not.toBeInTheDocument()
    expect(container.querySelector('a[href="/rtas"]')).not.toBeInTheDocument()

    await user.click(toggle)

    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    expect(container.querySelector('a[href="/incidents"]')).toBeInTheDocument()
    expect(container.querySelector('a[href="/rtas"]')).toBeInTheDocument()
  })

  it('exposes Insights hub links for analytics, calendar, and exports', async () => {
    const user = userEvent.setup()
    const Layout = (await import('../Layout')).default

    render(
      <BrowserRouter>
        <Layout onLogout={onLogout} />
      </BrowserRouter>,
    )

    const insightsHub = screen.getByRole('button', { name: 'nav.insights' })
    await user.click(insightsHub)

    for (const path of ['/analytics', '/calendar', '/exports']) {
      expect(navLink(path)).toBeInTheDocument()
    }
    expect(navLink('/ai-intelligence')).not.toBeInTheDocument()
  })

  it('restores the AI Intelligence alias link only when its flag is on', async () => {
    isAIIntelligenceRouteEnabledMock.mockReturnValue(true)
    const user = userEvent.setup()
    const Layout = (await import('../Layout')).default

    render(
      <BrowserRouter>
        <Layout onLogout={onLogout} />
      </BrowserRouter>,
    )

    await user.click(screen.getByRole('button', { name: 'nav.insights' }))

    expect(navLink('/ai-intelligence')).toBeInTheDocument()
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
      '/ai-intelligence',
    ]) {
      expect(navLink(path)).not.toBeInTheDocument()
    }
  })

  it('does not offer the frozen Workflow Center under My Work', async () => {
    const user = userEvent.setup()
    const Layout = (await import('../Layout')).default

    render(
      <BrowserRouter>
        <Layout onLogout={onLogout} />
      </BrowserRouter>,
    )

    await user.click(screen.getByRole('button', { name: 'nav.my_work' }))

    expect(navLink('/actions')).toBeInTheDocument()
    expect(navLink('/workflows')).not.toBeInTheDocument()
  })

  // FR-WFFORCE-CAL-01 / FR-WF-CG-01: both routes still resolve as redirects, so
  // only the absent nav entry proves the duplicate and the orphan are gone.
  it('does not offer the retired Workforce calendar or Competence gaps entries', async () => {
    const user = userEvent.setup()
    const Layout = (await import('../Layout')).default

    render(
      <BrowserRouter>
        <Layout onLogout={onLogout} />
      </BrowserRouter>,
    )

    await user.click(screen.getByRole('button', { name: 'nav.workforce' }))

    expect(navLink('/workforce/engineers')).toBeInTheDocument()
    expect(navLink('/workforce/calendar')).not.toBeInTheDocument()
    expect(navLink('/workforce/competence-gaps')).not.toBeInTheDocument()

    // The surviving calendar is the unified one under Insights.
    await user.click(screen.getByRole('button', { name: 'nav.insights' }))
    expect(navLink('/calendar')).toBeInTheDocument()
  })

  it('points the header Settings gear to Admin Console for admin-capable roles', async () => {
    hasRoleMock.mockImplementation((...roles: string[]) =>
      roles.some((role) => ['admin', 'manager', 'hsec'].includes(role)),
    )
    isSuperuserMock.mockReturnValue(false)
    const Layout = (await import('../Layout')).default

    render(
      <BrowserRouter>
        <Layout onLogout={onLogout} />
      </BrowserRouter>,
    )

    expect(screen.getByRole('link', { name: 'nav.settings' })).toHaveAttribute('href', '/admin')
  })

  it('points the header Settings gear to the dashboard when Admin is not allowed', async () => {
    hasRoleMock.mockReturnValue(false)
    isSuperuserMock.mockReturnValue(false)
    const Layout = (await import('../Layout')).default

    render(
      <BrowserRouter>
        <Layout onLogout={onLogout} />
      </BrowserRouter>,
    )

    expect(screen.getByRole('link', { name: 'nav.settings' })).toHaveAttribute('href', '/dashboard')
  })

  it('auto-expands the hub containing the active child route', async () => {
    window.history.pushState({}, '', '/my-reading/42')
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
    expect(navLink('/my-reading')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'nav.audits_hub' })).toHaveAttribute(
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
    expect(navLink('/compliance')).toBeInTheDocument()
    expect(navLink('/standards')).not.toBeInTheDocument()
    expect(navLink('/compliance-automation')).not.toBeInTheDocument()
  })

  it('shows the Admin hub for roles that can deep-link /admin', async () => {
    const user = userEvent.setup()
    // Align with App.tsx RequireRole(['admin','manager','hsec']) — not isSuperuser.
    hasRoleMock.mockImplementation((...roles: string[]) =>
      roles.some((role) => ['admin', 'manager', 'hsec'].includes(role)),
    )
    isSuperuserMock.mockReturnValue(false)
    useFeatureFlagMock.mockReturnValue(false)
    const Layout = (await import('../Layout')).default

    render(
      <BrowserRouter>
        <Layout onLogout={onLogout} />
      </BrowserRouter>,
    )

    const adminHub = screen.getByRole('button', { name: 'nav.admin' })
    await user.click(adminHub)
    expect(navLink('/admin')).toBeInTheDocument()
  })

  it('hides the Admin hub when the user cannot deep-link /admin', async () => {
    hasRoleMock.mockReturnValue(false)
    isSuperuserMock.mockReturnValue(true)
    useFeatureFlagMock.mockReturnValue(true)
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

  it('hides every PlantEx Assist entry point when the demo flag is off', async () => {
    const Layout = (await import('../Layout')).default

    render(
      <BrowserRouter>
        <Layout onLogout={onLogout} />
      </BrowserRouter>,
    )

    expect(screen.queryByRole('button', { name: /nav\.copilot/i })).not.toBeInTheDocument()
    expect(screen.queryByTestId('ai-copilot')).not.toBeInTheDocument()
    expect(navLink('/copilot')).not.toBeInTheDocument()
  })

  it('lazy-mounts PlantEx Assist only after the header control is opened', async () => {
    isAICopilotDemoEnabledMock.mockReturnValue(true)
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

  it('opens the search palette overlay from the header without routing to /search', async () => {
    const user = userEvent.setup()
    window.history.pushState({}, '', '/rtas/99')
    const Layout = (await import('../Layout')).default

    render(
      <BrowserRouter>
        <Layout onLogout={onLogout} />
      </BrowserRouter>,
    )

    expect(window.location.pathname).toBe('/rtas/99')
    await user.click(screen.getByRole('button', { name: 'search.open_palette' }))

    expect(await screen.findByRole('dialog')).toBeInTheDocument()
    expect(screen.getByText('search.palette_title')).toBeInTheDocument()
    expect(window.location.pathname).toBe('/rtas/99')
    expect(window.location.pathname).not.toBe('/search')
  })

  it('toggles the desktop sidebar width when the collapse control is clicked', async () => {
    const user = userEvent.setup()
    const Layout = (await import('../Layout')).default

    render(
      <BrowserRouter>
        <Layout onLogout={onLogout} />
      </BrowserRouter>,
    )

    const sidebar = document.getElementById('app-sidebar')
    expect(sidebar).toBeTruthy()
    expect(sidebar).not.toHaveAttribute('data-collapsed')
    expect(sidebar?.className).not.toMatch(/\blg:w-16\b/)

    await user.click(screen.getByTestId('nav-sidebar-collapse'))

    expect(sidebar).toHaveAttribute('data-collapsed', 'true')
    expect(sidebar?.className).toMatch(/\blg:w-16\b/)

    await user.click(screen.getByTestId('nav-sidebar-collapse'))

    expect(sidebar).not.toHaveAttribute('data-collapsed')
    expect(sidebar?.className).not.toMatch(/\blg:w-16\b/)
  })
})
