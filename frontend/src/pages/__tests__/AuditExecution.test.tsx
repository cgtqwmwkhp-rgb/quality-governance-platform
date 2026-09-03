import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { AxiosError } from 'axios'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { evidenceAssetsApi } from '../../api/client'
import AuditExecution from '../AuditExecution'

const mockNavigate = vi.fn()
const mockGetRunDetail = vi.fn()
const mockGetTemplate = vi.fn()
const mockStartRun = vi.fn()
const mockAcknowledgeRun = vi.fn()
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
    acknowledgeRun: (...args: unknown[]) => mockAcknowledgeRun(...args),
    createResponse: vi.fn(),
    updateResponse: vi.fn(),
    uploadQuestionEvidence: vi
      .fn()
      .mockResolvedValue({ data: { evidence_asset_id: 99, response_id: 7, evidence_asset_ids: [99] } }),
  },
  evidenceAssetsApi: {
    upload: vi.fn().mockResolvedValue({ data: { id: 99 } }),
    list: vi.fn().mockResolvedValue({ data: { items: [], total: 0 } }),
    getSignedUrl: vi.fn().mockResolvedValue({ data: { signed_url: 'https://example.com/photo.jpg' } }),
    getContent: vi.fn().mockResolvedValue({ data: new Blob(['photo-bytes']) }),
    delete: vi.fn().mockResolvedValue({}),
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
    mockAcknowledgeRun.mockResolvedValue({ data: {} })
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
    expect(mockCompleteRun).toHaveBeenCalledWith(41, null)

    await waitFor(
      () => {
        expect(mockNavigate).toHaveBeenCalledWith('/actions?sourceType=audit_finding')
      },
      { timeout: 2500 },
    )
  })

  it('shows an AUD-F4 completion refusal honestly and does not retry the completion', async () => {
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
    mockGetRunDetail.mockResolvedValue({ data: initialRun })
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

    const refusal = new AxiosError('Request failed', 'ERR_BAD_REQUEST')
    refusal.response = {
      status: 400,
      statusText: 'Bad Request',
      headers: {},
      config: {} as never,
      data: {
        error: {
          code: 'AUDIT_COMPLETE_NO_APPLICABLE_ANSWERS',
          message: 'This audit has no answers recorded against it, so it cannot be completed',
          details: { applicable_answer_count: 0, stored_response_count: 0 },
        },
      },
    }
    mockCompleteRun.mockRejectedValue(refusal)

    renderPage()

    fireEvent.click(await screen.findByRole('button', { name: 'Finish' }))
    fireEvent.click(screen.getByRole('button', { name: 'Submit Audit' }))

    expect(await screen.findByText(/no answers recorded on the server/)).toBeInTheDocument()
    expect(screen.queryByText('Inspection completed')).not.toBeInTheDocument()
    await waitFor(() => {
      expect(mockCompleteRun).toHaveBeenCalledTimes(1)
    })
  })

  describe('conditional-logic navigation visibility', () => {
    const conditionalRun = {
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
    const conditionalTemplate = {
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
          title: 'Section A',
          is_active: true,
          sort_order: 1,
          questions: [
            {
              id: 1,
              question_text: 'Any issues?',
              question_type: 'yes_no',
              is_required: true,
              is_active: true,
              sort_order: 1,
              weight: 1,
              failure_triggers_action: false,
            },
          ],
        },
        {
          id: 6,
          title: 'Section B',
          is_active: true,
          sort_order: 2,
          questions: [
            {
              id: 2,
              question_text: 'Describe the issue',
              question_type: 'text',
              is_required: false,
              is_active: true,
              sort_order: 1,
              weight: 1,
              failure_triggers_action: false,
              conditional_logic: [{ source_question_id: 1, operator: 'equals', value: 'never-matches', action: 'show' }],
            },
            {
              id: 3,
              question_text: 'Any other comments?',
              question_type: 'text',
              is_required: false,
              is_active: true,
              sort_order: 2,
              weight: 1,
              failure_triggers_action: false,
            },
          ],
        },
      ],
    }

    it('goNext skips a question hidden by conditional logic instead of landing on it', async () => {
      mockGetRunDetail.mockResolvedValue({ data: conditionalRun })
      mockGetTemplate.mockResolvedValue({ data: conditionalTemplate })

      renderPage()

      fireEvent.click(await screen.findByRole('button', { name: 'YES' }))

      // Auto-advance (600ms) fires goNext, which must skip "Describe the
      // issue" (always hidden — its show-rule can never match) and land on
      // "Any other comments?" instead.
      expect(await screen.findByText('Any other comments?', {}, { timeout: 2000 })).toBeInTheDocument()
      expect(screen.queryByText('Describe the issue')).not.toBeInTheDocument()
    })

    it('snaps the current question forward when navigation lands on a hidden question', async () => {
      mockGetRunDetail.mockResolvedValue({ data: conditionalRun })
      mockGetTemplate.mockResolvedValue({ data: conditionalTemplate })

      renderPage()

      // Land on Section A / Q1 first.
      await screen.findByText('Any issues?')

      // Section-nav always jumps to raw index 0 of the target section
      // ("Describe the issue"), which is permanently hidden by conditional
      // logic — the snap-effect must move forward to the next visible
      // question instead of ever rendering the hidden one.
      const sectionBButton = screen.getByText('Section B').closest('button')
      expect(sectionBButton).toBeTruthy()
      fireEvent.click(sectionBButton!)

      expect(await screen.findByText('Any other comments?')).toBeInTheDocument()
      expect(screen.queryByText('Describe the issue')).not.toBeInTheDocument()
    })
  })

  describe('AUD-F1 GET-only open', () => {
    const scheduledRun = {
      id: 41,
      reference_number: 'AUD-2026-0087',
      template_id: 11,
      template_version: 1,
      title: 'Field Technician Audit',
      location: 'ME14 3DA',
      status: 'scheduled',
      acknowledged_at: null,
      responses: [],
      findings: [],
      completion_percentage: 0,
      created_at: '2026-09-02T11:15:00Z',
    }
    const fieldTemplate = {
      id: 11,
      name: 'Field Technician Audit',
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
          title: 'Site',
          is_active: true,
          sort_order: 1,
          questions: [
            {
              id: 151,
              question_text: 'Van condition acceptable?',
              question_type: 'yes_no',
              is_required: true,
              is_active: true,
              sort_order: 1,
              weight: 1,
              failure_triggers_action: false,
            },
          ],
        },
      ],
    }

    it('opens a scheduled run from GET without acknowledge or start', async () => {
      mockGetRunDetail.mockResolvedValue({ data: scheduledRun })
      mockGetTemplate.mockResolvedValue({ data: fieldTemplate })

      renderPage()

      expect(await screen.findByText('Van condition acceptable?')).toBeInTheDocument()
      expect(screen.getByTestId('planned-not-started')).toBeInTheDocument()
      expect(screen.getByTestId('start-fieldwork')).toBeInTheDocument()
      expect(mockAcknowledgeRun).not.toHaveBeenCalled()
      expect(mockStartRun).not.toHaveBeenCalled()
    })

    it('Start fieldwork posts acknowledge then start', async () => {
      mockGetRunDetail.mockResolvedValue({ data: scheduledRun })
      mockGetTemplate.mockResolvedValue({ data: fieldTemplate })

      renderPage()
      fireEvent.click(await screen.findByTestId('start-fieldwork'))

      await waitFor(() => {
        expect(mockAcknowledgeRun).toHaveBeenCalledWith(41, null)
        expect(mockStartRun).toHaveBeenCalledWith(41, null)
      })
      await waitFor(() => {
        expect(screen.queryByTestId('start-fieldwork')).not.toBeInTheDocument()
      })
    })

    it('keeps the loaded run when Start fieldwork fails', async () => {
      mockGetRunDetail.mockResolvedValue({ data: scheduledRun })
      mockGetTemplate.mockResolvedValue({ data: fieldTemplate })
      mockAcknowledgeRun.mockRejectedValue(new Error('Network error. Please check your connection and try again.'))

      renderPage()
      expect(await screen.findByText('Van condition acceptable?')).toBeInTheDocument()
      fireEvent.click(screen.getByTestId('start-fieldwork'))

      expect(
        await screen.findByText(/Could not start fieldwork|Network error/i),
      ).toBeInTheDocument()
      expect(screen.getByText('Van condition acceptable?')).toBeInTheDocument()
      expect(screen.queryByText('Error Loading Audit')).not.toBeInTheDocument()
    })
  })

  describe('AUD-F2 hydrate orphan evidence', () => {
    const emptyRun = {
      id: 41,
      reference_number: 'AUD-2026-0087',
      template_id: 11,
      template_version: 1,
      title: 'Field Technician Audit',
      location: 'ME14 3DA',
      status: 'scheduled',
      acknowledged_at: null,
      responses: [],
      findings: [],
      completion_percentage: 0,
      created_at: '2026-09-02T11:15:00Z',
    }
    const photoTemplate = {
      id: 11,
      name: 'Field Technician Audit',
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
          title: 'Site',
          is_active: true,
          sort_order: 1,
          questions: [
            {
              id: 151,
              question_text: 'Van photo',
              question_type: 'photo',
              is_required: true,
              is_active: true,
              sort_order: 1,
              weight: 1,
              failure_triggers_action: false,
            },
            {
              id: 152,
              question_text: 'Meter photo',
              question_type: 'photo',
              is_required: true,
              is_active: true,
              sort_order: 2,
              weight: 1,
              failure_triggers_action: false,
            },
          ],
        },
      ],
    }

    it('lists run evidence with zero response rows and lazy-loads the current question only', async () => {
      mockGetRunDetail.mockResolvedValue({ data: emptyRun })
      mockGetTemplate.mockResolvedValue({ data: photoTemplate })
      vi.mocked(evidenceAssetsApi.list).mockResolvedValue({
        data: {
          items: [
            { id: 501, description: 'audit_question:151' },
            { id: 502, description: 'audit_question:152' },
          ],
          total: 2,
          page: 1,
          page_size: 100,
          total_pages: 1,
        },
      } as Awaited<ReturnType<typeof evidenceAssetsApi.list>>)

      renderPage()

      expect(await screen.findByText('Van photo')).toBeInTheDocument()
      await waitFor(() => {
        expect(evidenceAssetsApi.list).toHaveBeenCalledWith({
          source_module: 'audit',
          source_id: 41,
          page_size: 100,
        })
      })
      await waitFor(() => {
        expect(evidenceAssetsApi.getContent).toHaveBeenCalledWith(501, 'inline')
      })
      expect(evidenceAssetsApi.getContent).not.toHaveBeenCalledWith(502, 'inline')
      expect(await screen.findByTestId('audit-photo-preview-0')).toBeInTheDocument()

      fireEvent.click(screen.getByRole('button', { name: 'Next' }))

      expect(await screen.findByText('Meter photo')).toBeInTheDocument()
      await waitFor(() => {
        expect(evidenceAssetsApi.getContent).toHaveBeenCalledWith(502, 'inline')
      })
      expect(await screen.findByTestId('audit-photo-preview-0')).toBeInTheDocument()
    })
  })
})
