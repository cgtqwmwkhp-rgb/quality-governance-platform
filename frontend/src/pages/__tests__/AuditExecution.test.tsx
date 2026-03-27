import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import AuditExecution from '../AuditExecution'

const mockNavigate = vi.fn()
const mockGetRunDetail = vi.fn()
const mockGetTemplate = vi.fn()
const mockStartRun = vi.fn()

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: () => mockNavigate }
})

vi.mock('../../api/client', () => ({
  auditsApi: {
    getRunDetail: (...args: unknown[]) => mockGetRunDetail(...args),
    getTemplate: (...args: unknown[]) => mockGetTemplate(...args),
    startRun: (...args: unknown[]) => mockStartRun(...args),
  },
  getApiErrorMessage: (error: unknown) => (error instanceof Error ? error.message : 'Request failed'),
}))

function renderPage() {
  render(
    <MemoryRouter initialEntries={['/audits/41/execute']}>
      <Routes>
        <Route path="/audits/:auditId/execute" element={<AuditExecution />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('AuditExecution', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockStartRun.mockResolvedValue({ data: {} })
  })

  it('fails safely for imported external intake runs instead of crashing on missing questions', async () => {
    mockGetRunDetail.mockResolvedValue({
      data: {
        id: 41,
        reference_number: 'AUD-00041',
        template_id: 11,
        template_version: 1,
        title: 'Imported Achilles Intake',
        status: 'scheduled',
        is_external_import_intake: true,
        responses: [],
        findings: [],
        completion_percentage: 0,
        created_at: '2026-03-24T10:05:00Z',
      },
    })
    mockGetTemplate.mockResolvedValue({
      data: {
        id: 11,
        name: 'ZZZ External Audit Intake (System)',
        audit_type: 'external_import',
        version: 1,
        scoring_method: 'percentage',
        allow_offline: false,
        require_gps: false,
        require_signature: false,
        require_approval: false,
        auto_create_findings: true,
        is_active: true,
        is_published: true,
        sections: [],
      },
    })

    renderPage()

    expect(await screen.findByText('Audit Not Executable Here')).toBeInTheDocument()
    expect(
      screen.getByText(
        'This imported external audit is reviewed through the import workspace and cannot be executed here.',
      ),
    ).toBeInTheDocument()

    await waitFor(() => {
      expect(mockStartRun).not.toHaveBeenCalled()
    })
  })
})
