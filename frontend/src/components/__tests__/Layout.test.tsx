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

  beforeEach(() => {
    onLogout.mockClear()
    hasRoleMock.mockReset()
    hasRoleMock.mockReturnValue(true)
    isSuperuserMock.mockReset()
    isSuperuserMock.mockReturnValue(true)
    useFeatureFlagMock.mockReset()
    useFeatureFlagMock.mockReturnValue(true)
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
    expect(screen.getByRole('button', { name: /nav\.more|More/i })).toBeInTheDocument()
  })

  it('keeps library and analytics items under collapsed More until expanded', async () => {
    const user = userEvent.setup()
    const Layout = (await import('../Layout')).default

    render(
      <BrowserRouter>
        <Layout onLogout={onLogout} />
      </BrowserRouter>,
    )

    expect(screen.queryByText('nav.documents')).not.toBeInTheDocument()
    expect(screen.queryByText('nav.overview')).not.toBeInTheDocument()
    expect(screen.queryByText('nav.planet_mark')).not.toBeInTheDocument()
    expect(screen.queryByText('nav.ai_intelligence')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /nav\.more|More/i }))

    expect(screen.getByText('nav.documents')).toBeInTheDocument()
    expect(screen.getByText('nav.overview')).toBeInTheDocument()
    expect(screen.getByText('nav.workflow_center')).toBeInTheDocument()
    expect(screen.getByText('nav.planet_mark')).toBeInTheDocument()
    expect(screen.getByText('nav.ai_intelligence')).toBeInTheDocument()
  })

  it('hides analytics and automation More groups for non-privileged roles', async () => {
    const user = userEvent.setup()
    hasRoleMock.mockReturnValue(false)
    isSuperuserMock.mockReturnValue(false)
    const Layout = (await import('../Layout')).default

    render(
      <BrowserRouter>
        <Layout onLogout={onLogout} />
      </BrowserRouter>,
    )

    await user.click(screen.getByRole('button', { name: /nav\.more|More/i }))

    expect(screen.getByText('nav.documents')).toBeInTheDocument()
    expect(screen.getByText('nav.planet_mark')).toBeInTheDocument()
    expect(screen.queryByText('nav.overview')).not.toBeInTheDocument()
    expect(screen.queryByText('nav.workflow_center')).not.toBeInTheDocument()
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
    isSuperuserMock.mockReturnValue(false)
    const Layout = (await import('../Layout')).default

    render(
      <BrowserRouter>
        <Layout onLogout={onLogout} />
      </BrowserRouter>,
    )

    expect(screen.queryByText('nav.workforce')).not.toBeInTheDocument()
    expect(screen.queryByText('nav.assessments')).not.toBeInTheDocument()
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
