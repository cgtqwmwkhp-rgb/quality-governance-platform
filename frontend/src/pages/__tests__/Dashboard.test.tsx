import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    i18n: { language: 'en' },
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

vi.mock('../../api/client', () => ({
  default: {
    get: vi.fn().mockResolvedValue({
      data: {
        total: 0,
        expiry_bands: { overdue: 0, due_30: 0, due_60: 0, due_90: 0, in_date: 0, no_expiry: 0 },
        by_type: {},
        by_status: { quarantined: 0 },
        generated_at: '2026-07-14T00:00:00Z',
      },
    }),
  },
  incidentsApi: {
    list: vi.fn().mockResolvedValue({ data: { items: [], total: 0 } }),
  },
  rtasApi: {
    list: vi.fn().mockResolvedValue({ data: { items: [], total: 0 } }),
  },
  complaintsApi: {
    list: vi.fn().mockResolvedValue({ data: { items: [], total: 0 } }),
  },
  risksApi: {
    list: vi.fn().mockResolvedValue({ data: { items: [], total: 0 } }),
  },
  riskRegisterApi: {
    getSummary: vi.fn().mockResolvedValue({
      data: { total: 0, open: 0, high: 0, medium: 0, low: 0 },
    }),
  },
  actionsApi: {
    list: vi.fn().mockResolvedValue({ data: { items: [], total: 0 } }),
  },
  auditsApi: {
    listRuns: vi.fn().mockResolvedValue({ data: { items: [], total: 0 } }),
  },
  notificationsApi: {
    getUnreadCount: vi.fn().mockResolvedValue({ data: { unread_count: 0 } }),
  },
  complianceApi: {
    listClauses: vi.fn().mockResolvedValue({ data: [] }),
    getCoverage: vi.fn().mockResolvedValue({ data: { standards: [] } }),
  },
}))

vi.mock('../../config/apiBase', () => ({
  API_BASE_URL: 'http://localhost:3000',
}))

describe('Dashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders without crashing and shows the dashboard heading', async () => {
    const Dashboard = (await import('../Dashboard')).default

    render(
      <BrowserRouter>
        <Dashboard />
      </BrowserRouter>,
    )

    const heading = await screen.findByRole('heading', { name: 'Dashboard' })
    expect(heading).toBeInTheDocument()
  })

  it('displays stat cards after loading', async () => {
    const Dashboard = (await import('../Dashboard')).default

    render(
      <BrowserRouter>
        <Dashboard />
      </BrowserRouter>,
    )

    await screen.findByRole('heading', { name: 'Dashboard' })

    expect(screen.getByText('Open Incidents')).toBeInTheDocument()
    expect(screen.getByText('Open RTAs')).toBeInTheDocument()
    expect(screen.getByText('Overdue Actions')).toBeInTheDocument()
  })
})
