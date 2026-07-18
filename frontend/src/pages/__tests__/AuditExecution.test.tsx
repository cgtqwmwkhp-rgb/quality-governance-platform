import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import AuditExecution from '../AuditExecution'

const mockNavigate = vi.fn()
const mockGetRunDetail = vi.fn()
const mockGetTemplate = vi.fn()
const mockStartRun = vi.fn()
const mockCompleteRun = vi.fn()

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: () => mockNavigate }
})

vi.mock('../../api/client', () => ({
  auditsApi: {
    getRunDetail: (...args: unknown[]) => mockGetRunDetail(...args),
    getTemplate: (...args: unknown[]) => mockGetTemplate(...args),
    startRun: (...args: unknown[]) => mockStartRun(...args),
    completeRun: (...args: unknown[]) => mockCompleteRun(...args),
    createResponse: vi.fn(),
    updateResponse: vi.fn(),
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
        status: 'completed',
        is_external_audit_import: true,
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

  it('opens already-completed runs on the completion proof screen (not editable execute)', async () => {
    mockGetRunDetail.mockResolvedValue({
      data: {
        id: 41,
        reference_number: 'AUD-00041',
        template_id: 11,
        template_version: 1,
        title: 'Warehouse inspection',
        location: 'London',
        status: 'completed',
        responses: [
          {
            id: 1,
            question_id: 8,
            response_value: 'ok',
          },
        ],
        findings: [
          {
            id: 1,
            corrective_action_required: true,
            risk_ids: [9],
          },
        ],
        completion_percentage: 100,
        created_at: '2026-03-24T10:05:00Z',
      },
    })
    mockGetTemplate.mockResolvedValue({
      data: {
        id: 11,
        name: 'Warehouse inspection',
        audit_type: 'internal',
        version: 1,
        scoring_method: 'percentage',
        allow_offline: false,
        require_gps: false,
        require_signature: false,
        require_approval: false,
        auto_create_findings: true,
        is_active: true,
        is_published: true,
        sections: [
          {
            id: 5,
            title: 'Safety',
            is_active: true,
            sort_order: 1,
            questions: [
              {
                id: 8,
                question_text: 'Inspection notes',
                question_type: 'text',
                is_required: false,
                is_active: true,
                sort_order: 1,
                weight: 1,
                failure_triggers_action: false,
              },
            ],
          },
        ],
      },
    })

    renderPage()

    expect(await screen.findByText('Inspection completed')).toBeInTheDocument()
    expect(screen.getByText('1 finding / 1 action created')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'YES' })).not.toBeInTheDocument()
    expect(mockStartRun).not.toHaveBeenCalled()
    expect(mockCompleteRun).not.toHaveBeenCalled()
  })

  it('shows live downstream counts then redirects to audit-sourced actions', async () => {
    const initialRun = {
      id: 41,
      reference_number: 'AUD-00041',
      template_id: 11,
      template_version: 1,
      title: 'Warehouse inspection',
      location: 'London',
      status: 'in_progress',
      responses: [],
      findings: [],
      completion_percentage: 0,
      created_at: '2026-03-24T10:05:00Z',
    }
    mockGetRunDetail
      .mockResolvedValueOnce({ data: initialRun })
      .mockResolvedValueOnce({
        data: {
          ...initialRun,
          status: 'completed',
          findings: [
            {
              id: 1,
              corrective_action_required: true,
              risk_ids: [9],
            },
          ],
        },
      })
    mockGetTemplate.mockResolvedValue({
      data: {
        id: 11,
        name: 'Warehouse inspection',
        audit_type: 'internal',
        version: 1,
        scoring_method: 'percentage',
        allow_offline: false,
        require_gps: false,
        require_signature: false,
        require_approval: false,
        auto_create_findings: true,
        is_active: true,
        is_published: true,
        sections: [
          {
            id: 5,
            title: 'Safety',
            is_active: true,
            sort_order: 1,
            questions: [
              {
                id: 8,
                question_text: 'Inspection notes',
                question_type: 'text',
                is_required: false,
                is_active: true,
                sort_order: 1,
                weight: 1,
                failure_triggers_action: false,
              },
            ],
          },
        ],
      },
    })
    mockCompleteRun.mockResolvedValue({
      data: {
        ...initialRun,
        status: 'completed',
        findings_count: 4,
        actions_count: 2,
        risks_count: 1,
      },
    })

    renderPage()

    fireEvent.click(await screen.findByRole('button', { name: 'Finish' }))
    fireEvent.click(screen.getByRole('button', { name: 'Submit Audit' }))

    expect(await screen.findByText('Inspection completed')).toBeInTheDocument()
    expect(screen.getByText('4 findings / 2 actions created')).toBeInTheDocument()
    expect(screen.getByText('Downstream Workflow Proof')).toBeInTheDocument()
    expect(mockCompleteRun).toHaveBeenCalledWith(41)

    await waitFor(
      () => {
        expect(mockNavigate).toHaveBeenCalledWith('/actions?sourceType=audit_finding')
      },
      { timeout: 2500 },
    )
  })
})
