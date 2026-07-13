import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import Audits from '../Audits'

const mockNavigate = vi.fn()
const mockListRuns = vi.fn()
const mockListFindings = vi.fn()
const mockListTemplates = vi.fn()
const mockUpdateFinding = vi.fn()
const mockListActions = vi.fn()
const mockUpdateAction = vi.fn()
const mockCreateAction = vi.fn()
const mockShowToast = vi.fn()
let mockSearchParams = new URLSearchParams('view=findings')

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
    useSearchParams: () => [mockSearchParams, vi.fn()],
  }
})

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, options?: Record<string, string | number>) => {
      const translations: Record<string, string> = {
        'audits.findings.type.positive': 'Positive practice',
        'audits.findings.type.nonconformity': 'Nonconformity',
        'audits.findings.empty.title': 'No findings recorded yet',
        'audits.findings.empty.description':
          'Complete an audit or inspection to record findings and positive practices.',
        'audits.findings.actions.view_audits': 'View audits',
        'audits.findings.actions.open_audit': 'Open audit workspace',
        'audits.findings.deep_link_miss.title': 'Finding not found',
        'audits.findings.deep_link_miss.description':
          'Finding {{id}} is unavailable or outside the loaded results.',
        'audits.findings.deep_link_miss.action': 'View all findings',
        'audits.findings.loop.title': 'Loop status',
        'audits.findings.loop.complete': 'Loop closed',
        'audits.findings.loop.finding': 'Finding',
        'audits.findings.loop.capa': 'CAPA',
        'audits.findings.loop.risk': 'Risk',
        'audits.findings.loop.capa_loading': 'Loading…',
        'audits.findings.loop.capa_unavailable': 'Status unavailable',
        'audits.findings.loop.capa_missing': 'Not linked',
        'audits.findings.loop.unassigned': 'Unassigned',
        'audits.findings.loop.risk_linked': `Linked (${options?.count ?? 0})`,
        'audits.findings.loop.risk_pending': 'Not linked',
        'audits.findings.loop.gate_hint': 'Finding close is gated',
        'audits.findings.loop.assign_capa': 'Assign CAPA',
        'audits.findings.loop.create_assign_capa': 'Create & assign CAPA',
        'audits.findings.loop.open_capa': 'Open CAPA detail',
        'audits.findings.loop.open_risk': 'Open linked risk',
        'audits.findings.loop.view_risk': 'View risk register',
        'audits.findings.loop.close_finding': 'Close finding',
        'audits.findings.loop.assign_dialog_title': 'Assign CAPA from finding',
        'audits.findings.loop.assign_dialog_body': 'Set assignee',
        'audits.findings.loop.assign_email_label': 'Assignee email',
        'audits.findings.loop.assign_email_required': 'Enter an assignee email.',
        'audits.findings.loop.assign_failed': 'Could not assign CAPA.',
        'audits.findings.loop.assign_submit': 'Save assignee',
        'audits.findings.loop.assign_success': 'CAPA assignee saved.',
        'audits.findings.loop.close_dialog_title': 'Close finding',
        'audits.findings.loop.close_dialog_body': 'Close after CAPA',
        'audits.findings.loop.close_dialog_blocked': 'CAPA still open',
        'audits.findings.loop.verification_note_placeholder': 'Optional note',
        'audits.findings.loop.override_label': 'Supervisor override',
        'audits.findings.loop.override_reason_placeholder': 'Reason…',
        'audits.findings.loop.override_reason_required': 'Override reason is required.',
        'audits.findings.loop.override_required': 'Confirm override',
        'audits.findings.loop.close_failed': 'Could not close',
        'audits.findings.loop.close_success': 'Finding closed.',
        'audits.findings.loop.close_submit': 'Close finding',
        'audits.findings.loop.close_with_override': 'Close with override',
        'common.cancel': 'Cancel',
      }
      const value = translations[key] ?? key
      return options?.id ? value.replace('{{id}}', String(options.id)) : value
    },
    i18n: { language: 'en' },
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

vi.mock('../../api/client', () => ({
  auditsApi: {
    listRuns: (...args: unknown[]) => mockListRuns(...args),
    listFindings: (...args: unknown[]) => mockListFindings(...args),
    listTemplates: (...args: unknown[]) => mockListTemplates(...args),
    updateFinding: (...args: unknown[]) => mockUpdateFinding(...args),
    flagFindingToRisk: vi.fn().mockResolvedValue({ data: { id: 501, risk_ids: [88] } }),
  },
  actionsApi: {
    list: (...args: unknown[]) => mockListActions(...args),
    update: (...args: unknown[]) => mockUpdateAction(...args),
    create: (...args: unknown[]) => mockCreateAction(...args),
  },
  evidenceAssetsApi: {
    upload: vi.fn(),
  },
  externalAuditImportsApi: {
    createJob: vi.fn(),
    queueJob: vi.fn(),
  },
}))

vi.mock('../../components/ui/Toast', () => ({
  ToastContainer: () => null,
  useToast: () => ({ toasts: [], show: mockShowToast, dismiss: vi.fn() }),
}))

vi.mock('../../components/StandardsAssessmentPanel', () => ({
  StandardsAssessmentPanel: () => <div data-testid="standards-panel" />,
}))

const openFinding = {
  id: 501,
  reference_number: 'AF-00501',
  run_id: 41,
  title: 'Missing PPE at gate',
  description: 'Operator without gloves',
  severity: 'high',
  finding_type: 'nonconformity',
  status: 'open',
  corrective_action_required: true,
  risk_ids: [88],
  created_at: '2026-07-12T10:00:00Z',
}

const openCapa = {
  id: 900,
  reference_number: 'CAPA-00900',
  title: 'Action plan: Missing PPE at gate',
  description: 'Operator without gloves',
  action_type: 'corrective',
  status: 'open',
  display_status: 'open',
  action_key: 'capa:900',
  source_type: 'audit_finding',
  source_id: 501,
  assigned_to_email: 'capa.owner@example.com',
  priority: 'high',
  created_at: '2026-07-12T10:05:00Z',
}

describe('Audits findings closure console', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockSearchParams = new URLSearchParams('view=findings')
    mockListRuns.mockResolvedValue({
      data: { items: [], total: 0, page: 1, page_size: 100, pages: 0 },
    })
    mockListTemplates.mockResolvedValue({
      data: { items: [], total: 0, page: 1, page_size: 100, pages: 0 },
    })
    mockListFindings.mockResolvedValue({
      data: { items: [openFinding], total: 1, page: 1, page_size: 100, pages: 1 },
    })
    mockListActions.mockResolvedValue({
      data: { items: [openCapa], total: 1, page: 1, page_size: 100, pages: 1 },
    })
    mockUpdateFinding.mockResolvedValue({
      data: { ...openFinding, status: 'closed' },
    })
    mockUpdateAction.mockResolvedValue({
      data: { ...openCapa, assigned_to_email: 'new.owner@example.com' },
    })
  })

  it('shows live CAPA display_status + assignee on the loop ribbon', async () => {
    render(<Audits />)

    expect(await screen.findByTestId('finding-loop-ribbon-501')).toBeInTheDocument()
    expect(screen.getByTestId('finding-loop-capa-status-501')).toHaveTextContent('open')
    expect(screen.getByTestId('finding-loop-capa-assignee-501')).toHaveTextContent(
      'capa.owner@example.com',
    )
    expect(screen.getByTestId('finding-loop-risk-status-501')).toHaveTextContent('Linked (1)')
  })

  it('assigns CAPA from the finding card', async () => {
    render(<Audits />)

    await screen.findByTestId('finding-loop-ribbon-501')
    fireEvent.click(screen.getByTestId('finding-loop-assign-501'))
    fireEvent.change(screen.getByTestId('finding-loop-assign-email-501'), {
      target: { value: 'new.owner@example.com' },
    })
    fireEvent.click(screen.getByTestId('finding-loop-assign-submit-501'))

    await waitFor(() => {
      expect(mockUpdateAction).toHaveBeenCalledWith(900, 'audit_finding', {
        assigned_to_email: 'new.owner@example.com',
      })
    })
    expect(mockShowToast).toHaveBeenCalledWith('CAPA assignee saved.', 'success')
  })

  it('closes finding via updateFinding when CAPA is completed without override', async () => {
    mockListActions.mockResolvedValue({
      data: {
        items: [{ ...openCapa, display_status: 'completed', status: 'closed' }],
        total: 1,
        page: 1,
        page_size: 100,
        pages: 1,
      },
    })

    render(<Audits />)

    await screen.findByTestId('finding-loop-ribbon-501')
    expect(screen.queryByTestId('finding-loop-gate-501')).not.toBeInTheDocument()

    fireEvent.click(screen.getByTestId('finding-loop-close-501'))
    fireEvent.click(screen.getByTestId('finding-loop-close-submit-501'))

    await waitFor(() => {
      expect(mockUpdateFinding).toHaveBeenCalledWith(501, { status: 'closed' })
    })
    expect(mockShowToast).toHaveBeenCalledWith('Finding closed.', 'success')
  })

  it('requires honest override while CAPA remains open', async () => {
    render(<Audits />)

    await screen.findByTestId('finding-loop-gate-501')
    fireEvent.click(screen.getByTestId('finding-loop-close-501'))
    expect(screen.getByTestId('finding-loop-close-submit-501')).toBeDisabled()

    fireEvent.click(screen.getByTestId('finding-loop-override-501'))
    fireEvent.change(screen.getByTestId('finding-loop-override-reason-501'), {
      target: { value: 'Accepted residual risk for this site' },
    })
    fireEvent.click(screen.getByTestId('finding-loop-close-submit-501'))

    await waitFor(() => {
      expect(mockUpdateFinding).toHaveBeenCalledWith(501, {
        status: 'closed',
        closure_override: true,
        closure_override_reason: 'Accepted residual risk for this site',
      })
    })
  })

  it('toasts when close fails (sibling bridge gate / API error)', async () => {
    mockListActions.mockResolvedValue({
      data: {
        items: [{ ...openCapa, display_status: 'completed', status: 'closed' }],
        total: 1,
        page: 1,
        page_size: 100,
        pages: 1,
      },
    })
    mockUpdateFinding.mockRejectedValue({
      response: { data: { detail: 'CAPA must be closed before finding can close' } },
    })

    render(<Audits />)

    await screen.findByTestId('finding-loop-ribbon-501')
    fireEvent.click(screen.getByTestId('finding-loop-close-501'))
    fireEvent.click(screen.getByTestId('finding-loop-close-submit-501'))

    await waitFor(() => {
      expect(mockShowToast).toHaveBeenCalledWith(
        'CAPA must be closed before finding can close',
        'error',
      )
    })
  })
})
