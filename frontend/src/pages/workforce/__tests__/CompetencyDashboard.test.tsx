import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const getSummary = vi.fn()
const getEngineerMatrix = vi.fn()

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

vi.mock('../../../api/client', () => ({
  workforceApi: {
    analytics: {
      getSummary,
      getEngineerMatrix,
    },
  },
  getApiErrorMessage: () => 'API failed',
}))

describe('CompetencyDashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getSummary.mockReset()
    getEngineerMatrix.mockReset()
  })

  it('renders engineer × asset-type matrix from analytics.getEngineerMatrix', async () => {
    getSummary.mockResolvedValue({
      data: {
        engineers: { total: 2 },
        competencies: {
          active: 1,
          due: 1,
          expired: 0,
          failed: 0,
          not_assessed: 2,
        },
        assessments: { total: 0, completed: 0 },
        inductions: { total: 0, completed: 0 },
      },
    })
    getEngineerMatrix.mockResolvedValue({
      data: {
        asset_types: [
          { id: 7, name: 'Transformer', category: 'network' },
          { id: 8, name: 'Switchgear', category: 'network' },
        ],
        engineers: [
          {
            engineer_id: 10,
            user_id: 42,
            employee_number: 'E001',
            competencies: { 7: 'active', 8: 'due' },
          },
          {
            engineer_id: 11,
            user_id: 43,
            employee_number: 'E002',
            competencies: { 7: 'not_assessed', 8: 'expired' },
          },
        ],
      },
    })

    const CompetencyDashboard = (await import('../CompetencyDashboard')).default

    render(
      <MemoryRouter>
        <CompetencyDashboard />
      </MemoryRouter>,
    )

    expect(await screen.findByTestId('competency-matrix-grid')).toBeInTheDocument()
    expect(screen.getByText('Transformer')).toBeInTheDocument()
    expect(screen.getByText('Switchgear')).toBeInTheDocument()
    expect(screen.getByTestId('competency-cell-10-7')).toHaveAttribute('data-status', 'active')
    expect(screen.getByTestId('competency-cell-11-8')).toHaveAttribute('data-status', 'expired')
    expect(screen.getByTestId('competency-kpi-engineers')).toHaveTextContent('2')
    expect(screen.getByTestId('competency-kpi-active')).toHaveTextContent('1')
    expect(screen.getByTestId('competency-kpi-due')).toHaveTextContent('1')
    expect(getEngineerMatrix).toHaveBeenCalled()
  })

  it('shows failure banner and unavailable KPIs — never silent zeros on failed fetch', async () => {
    getSummary.mockRejectedValue(new Error('summary down'))
    getEngineerMatrix.mockRejectedValue(new Error('matrix down'))

    const CompetencyDashboard = (await import('../CompetencyDashboard')).default

    render(
      <MemoryRouter>
        <CompetencyDashboard />
      </MemoryRouter>,
    )

    expect(await screen.findByTestId('competency-dashboard-load-error')).toBeInTheDocument()
    expect(screen.getByText('workforce.competency.load_failed')).toBeInTheDocument()
    expect(screen.getByTestId('competency-dashboard-retry')).toBeInTheDocument()
    expect(screen.getByTestId('competency-kpi-engineers')).toHaveTextContent('—')
    expect(screen.getByTestId('competency-kpi-active')).toHaveTextContent('—')
    expect(screen.getByTestId('competency-kpi-failed')).toHaveTextContent('—')
    expect(screen.queryByTestId('competency-matrix-empty')).not.toBeInTheDocument()
    expect(screen.getByTestId('competency-matrix-unavailable')).toBeInTheDocument()
  })

  it('retries after a failed load', async () => {
    const user = userEvent.setup()
    let shouldFail = true
    const successSummary = {
      data: {
        engineers: { total: 1 },
        competencies: {
          active: 0,
          due: 0,
          expired: 0,
          failed: 0,
          not_assessed: 0,
        },
        assessments: { total: 0, completed: 0 },
        inductions: { total: 0, completed: 0 },
      },
    }
    const successMatrix = {
      data: {
        asset_types: [{ id: 1, name: 'Pole', category: 'network' }],
        engineers: [
          {
            engineer_id: 5,
            user_id: 9,
            employee_number: 'E005',
            competencies: { 1: 'active' },
          },
        ],
      },
    }

    getSummary.mockImplementation(() =>
      shouldFail ? Promise.reject(new Error('summary down')) : Promise.resolve(successSummary),
    )
    getEngineerMatrix.mockImplementation(() =>
      shouldFail ? Promise.reject(new Error('matrix down')) : Promise.resolve(successMatrix),
    )

    const CompetencyDashboard = (await import('../CompetencyDashboard')).default

    render(
      <MemoryRouter>
        <CompetencyDashboard />
      </MemoryRouter>,
    )

    expect(await screen.findByTestId('competency-dashboard-load-error')).toBeInTheDocument()
    shouldFail = false
    await user.click(screen.getByTestId('competency-dashboard-retry'))

    await waitFor(() => {
      expect(screen.getByTestId('competency-matrix-grid')).toBeInTheDocument()
    })
    expect(screen.getByTestId('competency-kpi-engineers')).toHaveTextContent('1')
    expect(screen.queryByTestId('competency-dashboard-load-error')).not.toBeInTheDocument()
  })

  it('navigates to engineer profile on cell click', async () => {
    const user = userEvent.setup()
    getSummary.mockResolvedValue({
      data: {
        engineers: { total: 1 },
        competencies: { active: 1, due: 0, expired: 0, failed: 0, not_assessed: 0 },
        assessments: { total: 0, completed: 0 },
        inductions: { total: 0, completed: 0 },
      },
    })
    getEngineerMatrix.mockResolvedValue({
      data: {
        asset_types: [{ id: 3, name: 'Cable', category: 'network' }],
        engineers: [
          {
            engineer_id: 99,
            user_id: 1,
            employee_number: 'E099',
            competencies: { 3: 'active' },
          },
        ],
      },
    })

    const CompetencyDashboard = (await import('../CompetencyDashboard')).default

    render(
      <MemoryRouter initialEntries={['/workforce/competency']}>
        <Routes>
          <Route path="/workforce/competency" element={<CompetencyDashboard />} />
          <Route path="/workforce/engineers/:id" element={<div>Profile 99</div>} />
        </Routes>
      </MemoryRouter>,
    )

    expect(await screen.findByTestId('competency-cell-99-3')).toBeInTheDocument()
    await user.click(screen.getByTestId('competency-cell-99-3'))
    expect(await screen.findByText('Profile 99')).toBeInTheDocument()
  })
})
