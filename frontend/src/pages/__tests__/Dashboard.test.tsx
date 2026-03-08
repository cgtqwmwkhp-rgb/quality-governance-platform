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
  incidentsApi: {
    list: vi.fn().mockResolvedValue({ data: { items: [], total: 0 } }),
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
