import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'

const getUnreadCount = vi.fn()

// Mirrors i18next closely enough to be worth asserting on: a string second
// argument is the default copy, an object carries interpolation values.
vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, options?: string | Record<string, unknown>) => {
      if (key === 'a11y.notifications_unread' && typeof options === 'object') {
        return `Notifications, ${options.count} unread`
      }
      if (typeof options === 'string') return options
      return key
    },
    i18n: { language: 'en' },
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

vi.mock('../../api/client', () => ({
  notificationsApi: { getUnreadCount: () => getUnreadCount() },
  searchApi: {
    search: vi.fn().mockResolvedValue({ data: { results: [], total: 0, query: '', facets: {} } }),
    interpret: vi.fn().mockResolvedValue({ data: { q: '', source: 'keyword' } }),
  },
  getApiErrorMessage: (error: unknown) => (error instanceof Error ? error.message : 'error'),
}))

vi.mock('../../api/safetyAssetsClient', () => ({
  safetyAssetsApi: {
    listPendingSafetyLookups: vi.fn().mockResolvedValue({ data: { items: [], total: 0 } }),
  },
}))

vi.mock('../../config/apiBase', () => ({ API_BASE_URL: 'http://localhost:3000' }))
vi.mock('../../utils/auth', () => ({ hasRole: () => true, isSuperuser: () => true }))
vi.mock('../../hooks/useFeatureFlag', () => ({ useFeatureFlag: () => true }))
vi.mock('../../config/aiCopilotDemo', () => ({ isAICopilotDemoEnabled: () => false }))
vi.mock('../../config/aiIntelligenceRoute', () => ({ isAIIntelligenceRouteEnabled: () => false }))
vi.mock('../OfflineIndicator', () => ({ default: () => null }))
vi.mock('../ui/ThemeToggle', () => ({ ThemeToggle: () => <div data-testid="theme-toggle" /> }))

async function renderLayout() {
  const Layout = (await import('../Layout')).default
  return render(
    <BrowserRouter>
      <Layout onLogout={() => {}} />
    </BrowserRouter>,
  )
}

describe('Layout accessibility', () => {
  beforeEach(() => {
    window.history.pushState({}, '', '/dashboard')
    getUnreadCount.mockReset()
    getUnreadCount.mockResolvedValue({ data: { unread_count: 0 } })
  })

  // PX-290: the shell renders on every route, so a heading here becomes a
  // second H1 on every page that has one of its own.
  it('contributes no H1 to the page, while keeping the brand visible', async () => {
    const { container } = await renderLayout()

    expect(container.querySelectorAll('h1')).toHaveLength(0)
    expect(screen.getByText('Quality Governance Platform')).toBeInTheDocument()
    expect(screen.getByText('Plantexpand Limited')).toBeInTheDocument()
  })

  // PX-162: icon-only controls in the shell.
  it('names the mobile menu button and wires it to the sidebar it controls', async () => {
    await renderLayout()

    const menuButton = screen.getByRole('button', { name: 'a11y.open_menu' })
    expect(menuButton).toHaveAttribute('aria-expanded', 'false')
    const controls = menuButton.getAttribute('aria-controls')
    expect(controls).toBe('app-sidebar')
    expect(document.getElementById(controls as string)).not.toBeNull()
  })

  it('renames the mobile menu button once the sidebar is open', async () => {
    const { default: userEvent } = await import('@testing-library/user-event')
    const user = userEvent.setup()
    await renderLayout()

    await user.click(screen.getByRole('button', { name: 'a11y.open_menu' }))

    const menuButton = screen.getByRole('button', { name: 'a11y.close_menu' })
    expect(menuButton).toHaveAttribute('aria-expanded', 'true')
  })

  it('names the notifications link and folds the unread count into that name', async () => {
    await renderLayout()

    expect(screen.getByRole('link', { name: 'nav.notifications' })).toHaveAttribute(
      'href',
      '/notifications',
    )

    getUnreadCount.mockResolvedValue({ data: { unread_count: 3 } })
    await renderLayout()

    await waitFor(() => {
      expect(screen.getByRole('link', { name: 'Notifications, 3 unread' })).toBeInTheDocument()
    })
  })

  it('names the sidebar navigation landmark', async () => {
    await renderLayout()

    expect(screen.getByRole('navigation', { name: 'a11y.navigation_menu' })).toBeInTheDocument()
  })

  // PX-182 was reported as "the header search box is a dead control". It is a
  // real button that opens the palette — asserted here so the regression is
  // caught rather than re-reported.
  it('exposes the header search as a named button', async () => {
    await renderLayout()

    expect(screen.getByRole('button', { name: 'Open search' })).toBeInTheDocument()
  })

  it('leaves no unnamed interactive control in the shell', async () => {
    const { container } = await renderLayout()

    const unnamed = Array.from(container.querySelectorAll('button, a[href]')).filter(
      (element) =>
        !(element.getAttribute('aria-label') ?? '').trim() &&
        !(element.textContent ?? '').trim() &&
        !(element.getAttribute('aria-labelledby') ?? '').trim(),
    )

    expect(unnamed.map((element) => element.outerHTML)).toEqual([])
  })
})
