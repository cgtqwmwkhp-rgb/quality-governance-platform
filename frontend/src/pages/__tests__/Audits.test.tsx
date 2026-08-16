import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import Audits from '../Audits'

const mockNavigate = vi.fn()
const mockListRuns = vi.fn()
const mockListFindings = vi.fn()
const mockListTemplates = vi.fn()
const mockCreateRun = vi.fn()
const mockUpdateRun = vi.fn()
const mockUpload = vi.fn()
const mockCreateImportJob = vi.fn()
const mockQueueImportJob = vi.fn()
let mockSearchParams = new URLSearchParams()

function stubFindingsApi(payload: { items?: unknown[]; total?: number } = {}) {
  const items = payload.items ?? []
  const total = payload.total ?? items.length
  mockListFindings.mockImplementation(
    (_page: number, pageSize: number, _runId?: number, status?: string) => {
      if (status === 'open') {
        const openTotal = items.filter(
          (finding) => (finding as { status?: string }).status === 'open',
        ).length
        return Promise.resolve({
          data: { items: [], total: openTotal, page: 1, page_size: 1, pages: 1 },
        })
      }
      return Promise.resolve({
        data: {
          items,
          total,
          page: 1,
          page_size: pageSize,
          pages: Math.max(1, Math.ceil(total / Math.max(pageSize, 1))),
        },
      })
    },
  )
}

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
    t: (key: string, options?: Record<string, string>) => {
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
        'audits.empty.title': 'No audits found',
        'audits.empty.subtitle': 'Schedule your first audit to get started',
        'audits.empty.filter_title': 'No audits match filters',
        'audits.empty.filter_subtitle': 'Try clearing search or KPI filters, or switch to List view.',
        'audits.stats.total': 'Total Audits',
        'status.in_progress': 'In Progress',
      }
      if (typeof options === 'string') {
        return translations[key] ?? options
      }
      const value = translations[key] ?? key
      return options?.id ? value.replace('{{id}}', options.id) : value
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
    createRun: (...args: unknown[]) => mockCreateRun(...args),
    updateRun: (...args: unknown[]) => mockUpdateRun(...args),
    updateFinding: vi.fn().mockResolvedValue({ data: { id: 501, status: 'closed' } }),
    flagFindingToRisk: vi.fn().mockResolvedValue({ data: { id: 501, risk_ids: [88] } }),
  },
  actionsApi: {
    list: vi.fn().mockResolvedValue({ data: { items: [], total: 0, page: 1, page_size: 100, pages: 0 } }),
    update: vi.fn(),
    create: vi.fn(),
  },
  evidenceAssetsApi: {
    upload: (...args: unknown[]) => mockUpload(...args),
  },
  externalAuditImportsApi: {
    createJob: (...args: unknown[]) => mockCreateImportJob(...args),
    queueJob: (...args: unknown[]) => mockQueueImportJob(...args),
  },
}))

vi.mock('../../components/ui/Toast', () => ({
  ToastContainer: () => null,
  useToast: () => ({ toasts: [], dismiss: vi.fn() }),
}))

describe('Audits external import flow', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockSearchParams = new URLSearchParams()
    mockListRuns.mockResolvedValue({
      data: { items: [], total: 0, page: 1, page_size: 100, pages: 0 },
    })
    stubFindingsApi()
    mockListTemplates.mockResolvedValue({
      data: {
        items: [
          {
            id: 21,
            reference_number: 'TPL-0021',
            name: 'Annual Safety Audit',
            description: 'Published schedule template',
            category: 'Safety',
            audit_type: 'audit',
            tags: [],
            version: 3,
            is_active: true,
            is_published: true,
            created_at: '2026-03-24T10:00:00Z',
            updated_at: '2026-03-24T10:00:00Z',
          },
          {
            id: 11,
            reference_number: 'TPL-0001',
            name: 'ZZZ External Audit Intake (System)',
            description: 'Reusable external audit template',
            category: 'System',
            audit_type: 'external_import',
            tags: ['external_audit_intake', 'external_audit_intake:achilles_uvdb'],
            version: 1,
            is_active: true,
            is_published: true,
            created_at: '2026-03-24T10:00:00Z',
            updated_at: '2026-03-24T10:00:00Z',
          },
        ],
        total: 2,
        page: 1,
        page_size: 100,
        pages: 1,
      },
    })
    mockCreateRun.mockResolvedValue({
      data: {
        id: 41,
        reference_number: 'AUD-00041',
        template_id: 11,
        template_version: 1,
        title: 'External Audit Intake',
        status: 'pending_review',
        source_origin: 'third_party',
        assurance_scheme: 'Achilles UVDB',
        is_external_audit_import: true,
        created_at: '2026-03-24T10:05:00Z',
      },
    })
    mockUpload.mockResolvedValue({
      data: {
        id: 55,
        original_filename: 'achilles-audit.pdf',
      },
    })
    mockUpdateRun.mockResolvedValue({
      data: {
        id: 41,
      },
    })
    mockCreateImportJob.mockResolvedValue({
      data: {
        id: 72,
      },
    })
    mockQueueImportJob.mockResolvedValue({
      data: {
        id: 72,
        status: 'queued',
      },
    })
  })

  it('imports an external audit and links the uploaded report', { timeout: 15000 }, async () => {
    render(<Audits />)

    fireEvent.click(await screen.findByRole('button', { name: 'Import External Audit' }))

    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).queryByText(/Audit Template/i)).not.toBeInTheDocument()
    fireEvent.change(within(dialog).getByLabelText(/External Audit Program/i), {
      target: { value: 'achilles_uvdb' },
    })

    expect(within(dialog).getByDisplayValue('third_party')).toBeInTheDocument()
    expect(within(dialog).getByLabelText(/Audit Scheme \/ Standard/i)).toHaveValue('Achilles UVDB')

    const file = new File(['audit pdf'], 'achilles-audit.pdf', { type: 'application/pdf' })
    fireEvent.change(within(dialog).getByLabelText(/Source Audit Report/i), {
      target: { files: [file] },
    })

    fireEvent.click(within(dialog).getByRole('button', { name: 'Create Intake' }))

    await waitFor(() => {
      expect(mockCreateRun).toHaveBeenCalledTimes(1)
    })

    expect(mockCreateRun).toHaveBeenCalledWith(
      expect.objectContaining({
        template_id: 21,
        external_audit_type: 'achilles_uvdb',
        source_origin: 'third_party',
        assurance_scheme: 'Achilles UVDB',
      }),
    )
    expect(mockUpload).toHaveBeenCalledWith(
      file,
      expect.objectContaining({
        source_module: 'audit',
        source_id: 41,
      }),
    )
    expect(mockUpdateRun).toHaveBeenCalledWith(
      41,
      expect.objectContaining({
        source_document_asset_id: 55,
        source_document_label: 'achilles-audit.pdf',
      }),
    )
    expect(mockCreateImportJob).toHaveBeenCalledWith({
      audit_run_id: 41,
      source_document_asset_id: 55,
    })
    expect(mockQueueImportJob).toHaveBeenCalledWith(72)
    await waitFor(
      () => {
        expect(mockNavigate).toHaveBeenCalledWith('/audits/41/import-review?jobId=72')
      },
      { timeout: 3000 },
    )
  })

  it('requires a report before importing an external audit', async () => {
    render(<Audits />)

    fireEvent.click(await screen.findByRole('button', { name: 'Import External Audit' }))

    const dialog = await screen.findByRole('dialog')
    fireEvent.change(within(dialog).getByLabelText(/External Audit Program/i), {
      target: { value: 'customer' },
    })

    fireEvent.click(within(dialog).getByRole('button', { name: 'Create Intake' }))

    expect(await screen.findByText('Please upload the external audit report')).toBeInTheDocument()
    expect(mockCreateRun).not.toHaveBeenCalled()
  })

  it('requires ISO standard selection before importing an ISO external audit', async () => {
    render(<Audits />)

    fireEvent.click(await screen.findByRole('button', { name: 'Import External Audit' }))

    const dialog = await screen.findByRole('dialog')
    fireEvent.change(within(dialog).getByLabelText(/External Audit Program/i), {
      target: { value: 'iso' },
    })

    const file = new File(['audit pdf'], 'iso-audit.pdf', { type: 'application/pdf' })
    fireEvent.change(within(dialog).getByLabelText(/Source Audit Report/i), {
      target: { files: [file] },
    })

    fireEvent.click(within(dialog).getByRole('button', { name: 'Create Intake' }))

    expect(await screen.findByText('Please select which ISO standard applies')).toBeInTheDocument()
    expect(mockCreateRun).not.toHaveBeenCalled()
  })

  it('imports an ISO external audit with a preset standard', { timeout: 15000 }, async () => {
    render(<Audits />)

    fireEvent.click(await screen.findByRole('button', { name: 'Import External Audit' }))

    const dialog = await screen.findByRole('dialog')
    fireEvent.change(within(dialog).getByLabelText(/External Audit Program/i), {
      target: { value: 'iso' },
    })

    fireEvent.change(within(dialog).getByLabelText(/ISO Standard/i), {
      target: { value: 'ISO 9001:2015' },
    })

    const file = new File(['audit pdf'], 'iso-audit.pdf', { type: 'application/pdf' })
    fireEvent.change(within(dialog).getByLabelText(/Source Audit Report/i), {
      target: { files: [file] },
    })

    fireEvent.click(within(dialog).getByRole('button', { name: 'Create Intake' }))

    await waitFor(() => {
      expect(mockCreateRun).toHaveBeenCalledTimes(1)
    })

    expect(mockCreateRun).toHaveBeenCalledWith(
      expect.objectContaining({
        template_id: 21,
        external_audit_type: 'iso',
        source_origin: 'certification',
        assurance_scheme: 'ISO 9001:2015',
      }),
    )
  })

  it('allows historical dates for imported audits while retaining schedule-date guardrails', async () => {
    render(<Audits />)

    fireEvent.click(await screen.findByRole('button', { name: 'Import External Audit' }))

    const importDialog = await screen.findByRole('dialog')
    const importDateInput = within(importDialog).getByLabelText(/Audit Date/i)
    expect(importDateInput).not.toHaveAttribute('min')
    expect(importDialog.className).toContain('sm:max-w-3xl')
    expect(importDialog.className).toContain('max-h-[85vh]')

    fireEvent.click(within(importDialog).getByRole('button', { name: /close/i }))

    fireEvent.click(await screen.findByRole('button', { name: 'Schedule Audit' }))

    const scheduleDialog = await screen.findByRole('dialog')
    const scheduleDateInput = within(scheduleDialog).getByLabelText(/Scheduled Date/i)
    expect(scheduleDateInput).toHaveAttribute('min', new Date().toISOString().split('T')[0])
  })

  it('shows a visible warning when the audit is created but report upload fails', async () => {
    mockUpload.mockRejectedValueOnce({
      response: {
        data: {
          detail: 'Blob storage is temporarily unavailable',
        },
      },
    })

    render(<Audits />)

    fireEvent.click(await screen.findByRole('button', { name: 'Import External Audit' }))

    const dialog = await screen.findByRole('dialog')
    fireEvent.change(within(dialog).getByLabelText(/External Audit Program/i), {
      target: { value: 'achilles_uvdb' },
    })

    const file = new File(['audit pdf'], 'achilles-audit.pdf', { type: 'application/pdf' })
    fireEvent.change(within(dialog).getByLabelText(/Source Audit Report/i), {
      target: { files: [file] },
    })

    fireEvent.click(within(dialog).getByRole('button', { name: 'Create Intake' }))

    expect(await screen.findByText('Intake created with follow-up required')).toBeInTheDocument()
    expect(screen.getByText(/Blob storage is temporarily unavailable/)).toBeInTheDocument()
    expect(mockUpdateRun).not.toHaveBeenCalled()
    expect(mockNavigate).not.toHaveBeenCalled()
  })

  it('routes to import review even when automatic queueing fails', async () => {
    mockQueueImportJob.mockRejectedValueOnce({
      response: {
        data: {
          detail: {
            message: 'Background processing could not be started. Retry queueing the import.',
          },
        },
      },
    })

    render(<Audits />)

    fireEvent.click(await screen.findByRole('button', { name: 'Import External Audit' }))

    const dialog = await screen.findByRole('dialog')
    fireEvent.change(within(dialog).getByLabelText(/External Audit Program/i), {
      target: { value: 'achilles_uvdb' },
    })

    const file = new File(['audit pdf'], 'achilles-audit.pdf', { type: 'application/pdf' })
    fireEvent.change(within(dialog).getByLabelText(/Source Audit Report/i), {
      target: { files: [file] },
    })

    fireEvent.click(within(dialog).getByRole('button', { name: 'Create Intake' }))

    await waitFor(() => {
      expect(mockQueueImportJob).toHaveBeenCalledWith(72)
    })
    await waitFor(
      () => {
        expect(mockNavigate).toHaveBeenCalledWith('/audits/41/import-review?jobId=72&queueError=1')
      },
      { timeout: 3000 },
    )
  })

  it('surfaces structured backend import errors instead of schedule fallback text', async () => {
    mockCreateRun.mockRejectedValueOnce({
      response: {
        status: 404,
        data: {
          detail: {
            message:
              "No published external audit intake template is configured for 'achilles_uvdb'",
          },
        },
      },
    })

    render(<Audits />)

    fireEvent.click(await screen.findByRole('button', { name: 'Import External Audit' }))

    const dialog = await screen.findByRole('dialog')
    fireEvent.change(within(dialog).getByLabelText(/External Audit Program/i), {
      target: { value: 'achilles_uvdb' },
    })

    const file = new File(['audit pdf'], 'achilles-audit.pdf', { type: 'application/pdf' })
    fireEvent.change(within(dialog).getByLabelText(/Source Audit Report/i), {
      target: { files: [file] },
    })

    fireEvent.click(within(dialog).getByRole('button', { name: 'Create Intake' }))

    expect(
      await screen.findByText(
        "No published external audit intake template is configured for 'achilles_uvdb'",
      ),
    ).toBeInTheDocument()
    expect(
      screen.queryByText('Failed to schedule audit. Please try again.'),
    ).not.toBeInTheDocument()
  })

  it('hides system intake templates from the schedule picker', async () => {
    render(<Audits />)

    fireEvent.click(await screen.findByRole('button', { name: 'Schedule Audit' }))

    const dialog = await screen.findByRole('dialog')
    const templateSelect = within(dialog).getAllByRole('combobox')[0]!
    const options = within(templateSelect)
      .getAllByRole('option')
      .map((option) => option.textContent)

    expect(options.join(' ')).toContain('Annual Safety Audit')
    expect(options.join(' ')).not.toContain('ZZZ External Audit Intake (System)')
  })

  it('shows imported external outcomes in the audit workspace and opens review mode', async () => {
    mockListRuns.mockResolvedValueOnce({
      data: {
        items: [
          {
            id: 41,
            reference_number: 'AUD-00041',
            template_id: 11,
            template_version: 1,
            title: 'Imported Achilles Intake',
            status: 'pending_review',
            source_origin: 'third_party',
            assurance_scheme: 'Achilles UVDB',
            is_external_audit_import: true,
            is_external_import_intake: false,
            created_at: '2026-03-24T10:05:00Z',
          },
          {
            id: 42,
            reference_number: 'AUD-00042',
            template_id: 21,
            template_version: 3,
            title: 'Visible Internal Audit',
            status: 'scheduled',
            source_origin: 'internal',
            is_external_audit_import: false,
            is_external_import_intake: false,
            created_at: '2026-03-24T10:10:00Z',
          },
        ],
        total: 2,
        page: 1,
        page_size: 100,
        pages: 1,
      },
    })

    render(<Audits />)

    expect(await screen.findByText('Imported Achilles Intake')).toBeInTheDocument()
    expect(screen.getByText('Visible Internal Audit')).toBeInTheDocument()

    fireEvent.click(screen.getAllByText('Open Review')[0]!)

    expect(mockNavigate).toHaveBeenCalledWith('/audits/41/import-review')

    fireEvent.click(screen.getByRole('button', { name: 'List' }))

    expect(await screen.findByText('Visible Internal Audit')).toBeInTheDocument()
    expect(screen.getByText('Imported Achilles Intake')).toBeInTheDocument()
  })
})

describe('Audits board work lanes (AUD-W-W1)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockSearchParams = new URLSearchParams()
    stubFindingsApi()
    mockListTemplates.mockResolvedValue({
      data: { items: [], total: 0, page: 1, page_size: 100, pages: 0 },
    })
  })

  it('groups audits into Do now, Needs review, and Closed lanes', async () => {
    mockListRuns.mockResolvedValueOnce({
      data: {
        items: [
          {
            id: 1,
            reference_number: 'AUD-00001',
            template_id: 21,
            template_version: 1,
            title: 'Scheduled internal audit',
            status: 'scheduled',
            source_origin: 'internal',
            created_at: '2026-07-12T10:00:00Z',
          },
          {
            id: 2,
            reference_number: 'AUD-00002',
            template_id: 21,
            template_version: 1,
            title: 'Imported UVDB intake',
            status: 'pending_review',
            source_origin: 'third_party',
            assurance_scheme: 'Achilles UVDB',
            is_external_audit_import: true,
            created_at: '2026-07-12T10:05:00Z',
          },
          {
            id: 3,
            reference_number: 'AUD-00003',
            template_id: 21,
            template_version: 1,
            title: 'Completed safety audit',
            status: 'completed',
            score_percentage: 92,
            source_origin: 'internal',
            created_at: '2026-07-12T10:10:00Z',
            completed_at: new Date().toISOString(),
          },
        ],
        total: 3,
        page: 1,
        page_size: 100,
        pages: 1,
      },
    })

    render(<Audits />)

    expect(await screen.findByTestId('audits-board-lane-do_now')).toBeInTheDocument()
    expect(screen.getByTestId('audits-board-lane-review')).toBeInTheDocument()
    expect(screen.getByTestId('audits-board-lane-closed')).toBeInTheDocument()

    expect(
      within(screen.getByTestId('audits-board-lane-do_now')).getByText('Scheduled internal audit'),
    ).toBeInTheDocument()
    expect(
      within(screen.getByTestId('audits-board-lane-review')).getByText('Imported UVDB intake'),
    ).toBeInTheDocument()
    expect(
      within(screen.getByTestId('audits-board-lane-closed')).getByText('Completed safety audit'),
    ).toBeInTheDocument()

    expect(
      within(screen.getByTestId('audits-board-lane-do_now')).getByRole('button', { name: /^Start$/i }),
    ).toBeInTheDocument()

    const reviewLane = screen.getByTestId('audits-board-lane-review')
    const closedLane = screen.getByTestId('audits-board-lane-closed')
    expect(
      within(reviewLane).getByText('Imported UVDB intake').closest('[role="button"]'),
    ).toBeInTheDocument()
    expect(within(reviewLane).getByText('Open Review')).toBeInTheDocument()
    expect(
      within(closedLane).getByText('Completed safety audit').closest('[role="button"]'),
    ).toBeInTheDocument()
    expect(within(closedLane).getByText('View')).toBeInTheDocument()
  })

  it('shows program filter chips when data supports them and filters the board', async () => {
    mockListRuns.mockResolvedValueOnce({
      data: {
        items: [
          {
            id: 10,
            reference_number: 'AUD-00010',
            template_id: 21,
            template_version: 1,
            title: 'Internal safety walk',
            status: 'scheduled',
            source_origin: 'internal',
            created_at: '2026-07-12T10:00:00Z',
          },
          {
            id: 11,
            reference_number: 'AUD-00011',
            template_id: 11,
            template_version: 1,
            title: 'Customer site audit',
            status: 'pending_review',
            source_origin: 'customer',
            assurance_scheme: 'Customer Audit',
            is_external_audit_import: true,
            created_at: '2026-07-12T11:00:00Z',
          },
        ],
        total: 2,
        page: 1,
        page_size: 100,
        pages: 1,
      },
    })

    render(<Audits />)

    expect(await screen.findByTestId('audits-program-filters')).toBeInTheDocument()
    expect(screen.getByTestId('audits-program-chip-internal')).toBeInTheDocument()
    expect(screen.getByTestId('audits-program-chip-customer')).toBeInTheDocument()

    fireEvent.click(screen.getByTestId('audits-program-chip-customer'))

    expect(screen.getByText('Customer site audit')).toBeInTheDocument()
    expect(screen.queryByText('Internal safety walk')).not.toBeInTheDocument()

    const filterToolbar = screen.getByRole('toolbar', { name: 'Audit filters' })
    expect(within(filterToolbar).getByText('Total Audits')).toBeInTheDocument()
    expect(within(filterToolbar).getByText('1')).toBeInTheDocument()
  })
})

describe('Audits board AUD-W-01 Round 3 verify', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockSearchParams = new URLSearchParams()
    stubFindingsApi()
    mockListTemplates.mockResolvedValue({
      data: { items: [], total: 0, page: 1, page_size: 100, pages: 0 },
    })
  })

  it('renders exactly three work lanes and never four equal status columns', async () => {
    mockListRuns.mockResolvedValueOnce({
      data: {
        items: [
          {
            id: 1,
            reference_number: 'AUD-00001',
            template_id: 21,
            template_version: 1,
            title: 'Scheduled lane item',
            status: 'scheduled',
            source_origin: 'internal',
            created_at: '2026-07-12T10:00:00Z',
          },
          {
            id: 2,
            reference_number: 'AUD-00002',
            template_id: 21,
            template_version: 1,
            title: 'In-progress lane item',
            status: 'in_progress',
            source_origin: 'internal',
            created_at: '2026-07-12T10:05:00Z',
          },
        ],
        total: 2,
        page: 1,
        page_size: 100,
        pages: 1,
      },
    })

    render(<Audits />)

    expect(await screen.findByTestId('audits-board-lane-do_now')).toBeInTheDocument()
    expect(screen.getByTestId('audits-board-lane-review')).toBeInTheDocument()
    expect(screen.getByTestId('audits-board-lane-closed')).toBeInTheDocument()
    expect(screen.queryByTestId('audits-board-lane-scheduled')).not.toBeInTheDocument()
    expect(screen.queryByTestId('audits-board-lane-in_progress')).not.toBeInTheDocument()

    const doNow = screen.getByTestId('audits-board-lane-do_now')
    expect(within(doNow).getByText('Scheduled lane item')).toBeInTheDocument()
    expect(within(doNow).getByText('In-progress lane item')).toBeInTheDocument()
    expect(within(doNow).getByText('Do now')).toBeInTheDocument()
  })

  it('shows all program chips when mixed programs load and clear restores the board', async () => {
    mockListRuns.mockResolvedValueOnce({
      data: {
        items: [
          {
            id: 20,
            reference_number: 'AUD-00020',
            template_id: 21,
            template_version: 1,
            title: 'Internal walk',
            status: 'scheduled',
            source_origin: 'internal',
            created_at: '2026-07-12T10:00:00Z',
          },
          {
            id: 21,
            reference_number: 'AUD-00021',
            template_id: 11,
            template_version: 1,
            title: 'UVDB intake',
            status: 'pending_review',
            source_origin: 'third_party',
            assurance_scheme: 'Achilles UVDB',
            is_external_audit_import: true,
            created_at: '2026-07-12T11:00:00Z',
          },
          {
            id: 22,
            reference_number: 'AUD-00022',
            template_id: 12,
            template_version: 1,
            title: 'Planet Mark intake',
            status: 'completed',
            assurance_scheme: 'Planet Mark',
            external_audit_type: 'planet_mark',
            created_at: '2026-07-12T12:00:00Z',
            completed_at: new Date().toISOString(),
          },
          {
            id: 23,
            reference_number: 'AUD-00023',
            template_id: 13,
            template_version: 1,
            title: 'Customer site',
            status: 'in_progress',
            source_origin: 'customer',
            assurance_scheme: 'Customer Audit',
            created_at: '2026-07-12T13:00:00Z',
          },
        ],
        total: 4,
        page: 1,
        page_size: 100,
        pages: 1,
      },
    })

    render(<Audits />)

    expect(await screen.findByTestId('audits-program-filters')).toBeInTheDocument()
    expect(screen.getByTestId('audits-program-chip-internal')).toBeInTheDocument()
    expect(screen.getByTestId('audits-program-chip-uvdb')).toBeInTheDocument()
    expect(screen.getByTestId('audits-program-chip-planet_mark')).toBeInTheDocument()
    expect(screen.getByTestId('audits-program-chip-customer')).toBeInTheDocument()

    fireEvent.click(screen.getByTestId('audits-program-chip-uvdb'))
    expect(screen.getByText('UVDB intake')).toBeInTheDocument()
    expect(screen.queryByText('Internal walk')).not.toBeInTheDocument()
    expect(screen.queryByText('Customer site')).not.toBeInTheDocument()

    fireEvent.click(screen.getByTestId('audits-program-clear'))
    expect(screen.getByText('Internal walk')).toBeInTheDocument()
    expect(screen.getByText('UVDB intake')).toBeInTheDocument()
    expect(screen.getByText('Planet Mark intake')).toBeInTheDocument()
    expect(screen.getByText('Customer site')).toBeInTheDocument()
  })

  it('keeps aged-out Closed runs off the board and opens List from the more control', async () => {
    const aged = new Date(Date.now() - 40 * 24 * 60 * 60 * 1000).toISOString()
    mockListRuns.mockResolvedValueOnce({
      data: {
        items: [
          {
            id: 31,
            reference_number: 'AUD-2026-0056',
            template_id: 21,
            template_version: 2,
            title: 'Aged Wickford close',
            status: 'completed',
            source_origin: 'internal',
            created_at: aged,
            completed_at: aged,
          },
          {
            id: 32,
            reference_number: 'AUD-2026-0057',
            template_id: 21,
            template_version: 3,
            title: 'Field Engineer Internal Audit',
            status: 'in_progress',
            source_origin: 'internal',
            created_at: new Date().toISOString(),
          },
        ],
        total: 2,
        page: 1,
        page_size: 100,
        pages: 1,
      },
    })

    render(<Audits />)

    const closedLane = await screen.findByTestId('audits-board-lane-closed')
    expect(within(closedLane).queryByText('Aged Wickford close')).not.toBeInTheDocument()
    expect(screen.getByTestId('audits-board-closed-more')).toHaveTextContent(
      '1 more closed — open List',
    )

    fireEvent.click(screen.getByTestId('audits-board-closed-more'))
    expect(await screen.findByText('Aged Wickford close')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'List' })).toHaveAttribute('aria-pressed', 'true')
  })

  it('switches to List when search is used so a specific run can be located', async () => {
    mockListRuns.mockResolvedValueOnce({
      data: {
        items: [
          {
            id: 41,
            reference_number: 'AUD-2026-0057',
            template_id: 21,
            template_version: 3,
            title: 'Field Engineer Internal Audit',
            status: 'in_progress',
            source_origin: 'internal',
            created_at: new Date().toISOString(),
          },
        ],
        total: 1,
        page: 1,
        page_size: 100,
        pages: 1,
      },
    })

    render(<Audits />)
    expect(await screen.findByTestId('audits-board-lane-do_now')).toBeInTheDocument()

    fireEvent.change(screen.getByPlaceholderText('audits.search_placeholder'), {
      target: { value: 'AUD-2026-0057' },
    })

    expect(screen.getByRole('button', { name: 'List' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByText('AUD-2026-0057')).toBeInTheDocument()
    expect(screen.queryByTestId('audits-board-lane-do_now')).not.toBeInTheDocument()
  })

  it('shows a truncation banner when more runs exist than the loaded page', async () => {
    mockListRuns.mockResolvedValueOnce({
      data: {
        items: [
          {
            id: 51,
            reference_number: 'AUD-00051',
            template_id: 21,
            template_version: 1,
            title: 'Loaded run',
            status: 'scheduled',
            source_origin: 'internal',
            created_at: new Date().toISOString(),
          },
        ],
        total: 240,
        page: 1,
        page_size: 100,
        pages: 3,
      },
    })

    render(<Audits />)
    expect(await screen.findByTestId('audits-runs-truncated-banner')).toHaveTextContent(
      'Showing 1 of 240 runs loaded',
    )
  })
})

describe('Audits board empty-state honesty', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockSearchParams = new URLSearchParams()
    stubFindingsApi()
    mockListTemplates.mockResolvedValue({
      data: { items: [], total: 0, page: 1, page_size: 100, pages: 0 },
    })
  })

  it('shows global empty copy when there are no audits', async () => {
    mockListRuns.mockResolvedValueOnce({
      data: { items: [], total: 0, page: 1, page_size: 100, pages: 0 },
    })

    render(<Audits />)

    expect(await screen.findByTestId('audits-board-empty')).toBeInTheDocument()
    expect(screen.getByText('No audits found')).toBeInTheDocument()
    expect(screen.queryByText('No audits match filters')).not.toBeInTheDocument()
  })

  it('does not show global empty copy on the board when KPI total is positive', async () => {
    mockListRuns.mockResolvedValueOnce({
      data: {
        items: [
          {
            id: 1,
            reference_number: 'AUD-00001',
            template_id: 21,
            template_version: 1,
            title: 'Scheduled safety audit',
            status: 'scheduled',
            created_at: '2026-07-12T10:00:00Z',
          },
        ],
        total: 1,
        page: 1,
        page_size: 100,
        pages: 1,
      },
    })

    render(<Audits />)

    expect(await screen.findByText('Scheduled safety audit')).toBeInTheDocument()
    const filterToolbar = screen.getByRole('toolbar', { name: 'Audit filters' })
    expect(within(filterToolbar).getByText('Total Audits')).toBeInTheDocument()
    expect(within(filterToolbar).getByText('1')).toBeInTheDocument()
    expect(screen.queryByText('No audits found')).not.toBeInTheDocument()
    expect(screen.queryByTestId('audits-board-empty')).not.toBeInTheDocument()
  })

  it('shows filter-empty copy on list when hero filter hides all rows but totals stay positive', async () => {
    mockListRuns.mockResolvedValueOnce({
      data: {
        items: [
          {
            id: 2,
            reference_number: 'AUD-00002',
            template_id: 21,
            template_version: 1,
            title: 'Completed audit',
            status: 'completed',
            created_at: '2026-07-12T10:00:00Z',
            completed_at: new Date().toISOString(),
          },
        ],
        total: 1,
        page: 1,
        page_size: 100,
        pages: 1,
      },
    })

    render(<Audits />)
    await screen.findByText('Completed audit')

    const filterToolbar = screen.getByRole('toolbar', { name: 'Audit filters' })
    fireEvent.click(within(filterToolbar).getByRole('button', { name: /In Progress/i }))

    expect(await screen.findByTestId('audits-list-filter-empty')).toBeInTheDocument()
    expect(screen.getByText('No audits match filters')).toBeInTheDocument()
    expect(screen.queryByText('No audits found')).not.toBeInTheDocument()
    expect(within(filterToolbar).getByText('Total Audits')).toBeInTheDocument()
  })

  it('shows lane-empty copy when audits exist outside board columns', async () => {
    mockListRuns.mockResolvedValueOnce({
      data: {
        items: [
          {
            id: 3,
            reference_number: 'AUD-00003',
            template_id: 21,
            template_version: 1,
            title: 'Draft audit',
            status: 'draft',
            created_at: '2026-07-12T10:00:00Z',
          },
        ],
        total: 1,
        page: 1,
        page_size: 100,
        pages: 1,
      },
    })

    render(<Audits />)

    expect(await screen.findByTestId('audits-board-lane-empty')).toBeInTheDocument()
    expect(screen.getByText('No board-visible audits')).toBeInTheDocument()
    expect(screen.queryByText('No audits found')).not.toBeInTheDocument()
    expect(screen.getByRole('toolbar', { name: 'Audit filters' })).toHaveTextContent('Total Audits')
  })
})

describe('Audits findings CUJ deep-links', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockSearchParams = new URLSearchParams()
    mockListRuns.mockResolvedValue({
      data: { items: [], total: 0, page: 1, page_size: 100, pages: 0 },
    })
    mockListTemplates.mockResolvedValue({
      data: { items: [], total: 0, page: 1, page_size: 100, pages: 0 },
    })
    const findingFixtures = [
      {
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
      },
      {
        id: 502,
        reference_number: 'AF-00502',
        run_id: 41,
        title: 'Good housekeeping',
        description: 'Positive practice observed',
        severity: 'observation',
        finding_type: 'positive',
        status: 'open',
        corrective_action_required: false,
        risk_ids: [],
        created_at: '2026-07-12T10:01:00Z',
      },
    ]
    stubFindingsApi({ items: findingFixtures, total: 2 })
  })

  it('navigates to Actions and Risk Register from finding cards', async () => {
    render(<Audits />)

    fireEvent.click(await screen.findByRole('button', { name: 'Findings' }))

    expect(await screen.findByText('Missing PPE at gate')).toBeInTheDocument()

    fireEvent.click(screen.getByTestId('finding-open-capa-501'))
    expect(mockNavigate).toHaveBeenCalledWith('/actions?sourceType=audit_finding&sourceId=501')

    fireEvent.click(screen.getByTestId('finding-open-risk-501'))
    expect(mockNavigate).toHaveBeenCalledWith('/risk-register?auditOnly=1&auditRef=AF-00501')

    expect(screen.queryByTestId('finding-open-capa-502')).not.toBeInTheDocument()
    fireEvent.click(screen.getByTestId('finding-open-risk-502'))
    expect(mockNavigate).toHaveBeenCalledWith('/risk-register?auditOnly=1&auditRef=AF-00502')
  })

  it('visually distinguishes positive practices from nonconformities', async () => {
    render(<Audits />)

    fireEvent.click(await screen.findByRole('button', { name: 'Findings' }))

    expect(await screen.findByText('Nonconformity')).toBeInTheDocument()
    expect(screen.getByText('Positive practice')).toBeInTheDocument()
    expect(screen.getByTestId('finding-type-501')).toHaveClass('text-destructive')
    expect(screen.getByTestId('finding-type-502')).toHaveClass('text-success')
    expect(screen.getByTestId('finding-card-501')).toHaveClass('border-l-destructive')
    expect(screen.getByTestId('finding-card-502')).toHaveClass('border-l-success')
  })

  it('shows an actionable empty state for audits without findings', async () => {
    stubFindingsApi({ items: [], total: 0 })
    mockListRuns.mockResolvedValueOnce({
      data: {
        items: [
          {
            id: 41,
            reference_number: 'AUD-00041',
            template_id: 21,
            template_version: 3,
            title: 'Site inspection',
            status: 'scheduled',
            created_at: '2026-07-12T10:00:00Z',
          },
        ],
        total: 1,
        page: 1,
        page_size: 100,
        pages: 1,
      },
    })

    render(<Audits />)
    fireEvent.click(await screen.findByRole('button', { name: 'Findings' }))

    expect(await screen.findByText('No findings recorded yet')).toBeInTheDocument()
    expect(
      screen.getByText(
        'Complete an audit or inspection to record findings and positive practices.',
      ),
    ).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Open audit workspace' }))
    expect(mockNavigate).toHaveBeenCalledWith('/audits/41/execute')

    fireEvent.click(screen.getByRole('button', { name: 'View audits' }))
    expect(screen.getByRole('button', { name: 'List' })).toHaveAttribute('aria-pressed', 'true')
  })

  it('shows a clear message when a finding deep-link does not resolve', async () => {
    mockSearchParams = new URLSearchParams('view=findings&findingId=999')

    render(<Audits />)

    expect(await screen.findByText('Finding not found')).toBeInTheDocument()
    expect(
      screen.getByText('Finding 999 is unavailable or outside the loaded results.'),
    ).toBeInTheDocument()
    expect(screen.getByText('Missing PPE at gate')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'View all findings' }))
    expect(mockNavigate).toHaveBeenCalledWith('/audits?view=findings')
  })
})

describe('Audits customer assurance filter (IA-W3)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockSearchParams = new URLSearchParams('source=customer')
    mockListRuns.mockResolvedValue({
      data: {
        items: [
          {
            id: 10,
            reference_number: 'AUD-00010',
            template_id: 11,
            template_version: 1,
            title: 'Customer Site Audit',
            status: 'pending_review',
            source_origin: 'customer',
            assurance_scheme: 'Customer Audit',
            is_external_audit_import: true,
            created_at: '2026-07-12T10:00:00Z',
          },
          {
            id: 11,
            reference_number: 'AUD-00011',
            template_id: 21,
            template_version: 3,
            title: 'Internal Safety Audit',
            status: 'scheduled',
            source_origin: 'internal',
            created_at: '2026-07-12T11:00:00Z',
          },
        ],
        total: 2,
        page: 1,
        page_size: 100,
        pages: 1,
      },
    })
    stubFindingsApi()
    mockListTemplates.mockResolvedValue({
      data: { items: [], total: 0, page: 1, page_size: 100, pages: 0 },
    })
  })

  it('shows customer assurance chrome and filters audit runs', async () => {
    render(<Audits />)

    expect(await screen.findByText('Customer & External Audits')).toBeInTheDocument()
    expect(screen.getByText('Customer Site Audit')).toBeInTheDocument()
    expect(screen.queryByText('Internal Safety Audit')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'View all audits' })).toBeInTheDocument()
  })
})

describe('Audits open findings KPI honesty (PX-262)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockSearchParams = new URLSearchParams()
    mockListRuns.mockResolvedValue({
      data: { items: [], total: 0, page: 1, page_size: 100, pages: 0 },
    })
    mockListTemplates.mockResolvedValue({
      data: { items: [], total: 0, page: 1, page_size: 100, pages: 0 },
    })
  })

  it('uses the server open total when the loaded findings page is truncated', async () => {
    stubFindingsApi({
      items: [
        {
          id: 1,
          reference_number: 'AF-00001',
          run_id: 1,
          title: 'Loaded open finding',
          description: 'd',
          severity: 'medium',
          finding_type: 'nonconformity',
          status: 'open',
          corrective_action_required: true,
          created_at: '2026-07-12T10:00:00Z',
        },
        {
          id: 2,
          reference_number: 'AF-00002',
          run_id: 1,
          title: 'In progress finding',
          description: 'd',
          severity: 'medium',
          finding_type: 'nonconformity',
          status: 'in_progress',
          corrective_action_required: true,
          created_at: '2026-07-12T10:01:00Z',
        },
      ],
      total: 101,
    })
    mockListFindings.mockImplementation((_page, pageSize, _runId, status?: string) => {
      if (status === 'open') {
        return Promise.resolve({
          data: { items: [], total: 100, page: 1, page_size: 1, pages: 1 },
        })
      }
      return Promise.resolve({
        data: {
          items: [
            {
              id: 1,
              reference_number: 'AF-00001',
              run_id: 1,
              title: 'Loaded open finding',
              description: 'd',
              severity: 'medium',
              finding_type: 'nonconformity',
              status: 'open',
              corrective_action_required: true,
              created_at: '2026-07-12T10:00:00Z',
            },
            {
              id: 2,
              reference_number: 'AF-00002',
              run_id: 1,
              title: 'In progress finding',
              description: 'd',
              severity: 'medium',
              finding_type: 'nonconformity',
              status: 'in_progress',
              corrective_action_required: true,
              created_at: '2026-07-12T10:01:00Z',
            },
          ],
          total: 101,
          page: 1,
          page_size: pageSize,
          pages: 1,
        },
      })
    })

    render(<Audits />)

    const toolbar = await screen.findByRole('toolbar', { name: 'Audit filters' })
    expect(toolbar).toHaveTextContent('100')
    fireEvent.click(screen.getByRole('button', { name: 'Findings' }))
    expect(await screen.findByTestId('audits-findings-truncated-banner')).toBeInTheDocument()
  })
})

describe('Audits import modal deep-link (PX-260)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockSearchParams = new URLSearchParams('modal=import')
    mockListRuns.mockResolvedValue({
      data: { items: [], total: 0, page: 1, page_size: 100, pages: 0 },
    })
    stubFindingsApi()
    mockListTemplates.mockResolvedValue({
      data: {
        items: [
          {
            id: 11,
            reference_number: 'TPL-0001',
            name: 'External intake',
            description: 'd',
            category: 'System',
            audit_type: 'external_import',
            tags: ['external_audit_intake'],
            version: 1,
            is_active: true,
            is_published: true,
            created_at: '2026-03-24T10:00:00Z',
            updated_at: '2026-03-24T10:00:00Z',
          },
        ],
        total: 1,
        page: 1,
        page_size: 100,
        pages: 1,
      },
    })
  })

  it('opens the external import dialog when modal=import is present', async () => {
    render(<Audits />)

    expect(await screen.findByRole('dialog')).toBeInTheDocument()
    expect(screen.getByText('Create External Audit Intake')).toBeInTheDocument()
  })
})

describe('A2 honest KPIs', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockSearchParams = new URLSearchParams()
    stubFindingsApi()
    mockListTemplates.mockResolvedValue({
      data: { items: [], total: 0, page: 1, page_size: 100, pages: 0 },
    })
  })

  it('shows em dash for Average Score when closed runs only have a fake 0%', async () => {
    mockListRuns.mockResolvedValueOnce({
      data: {
        items: [
          {
            id: 56,
            reference_number: 'AUD-2026-0056',
            template_id: 21,
            template_version: 2,
            title: 'Wickford close',
            status: 'completed',
            source_origin: 'internal',
            score_percentage: 0,
            max_score: 0,
            created_at: new Date().toISOString(),
            completed_at: new Date().toISOString(),
          },
          {
            id: 54,
            reference_number: 'AUD-2026-0054',
            template_id: 21,
            template_version: 1,
            title: 'Unscored close',
            status: 'completed',
            source_origin: 'internal',
            score_percentage: 0,
            created_at: new Date().toISOString(),
            completed_at: new Date().toISOString(),
          },
        ],
        total: 2,
        page: 1,
        page_size: 100,
        pages: 1,
      },
    })

    render(<Audits />)

    const kpi = await screen.findByTestId('audits-kpi-avg-score')
    expect(kpi).toHaveTextContent('—')
    expect(screen.getByTestId('audits-kpi-avg-score-caption')).toHaveTextContent(
      'Not scored in this view',
    )
    const closed = screen.getByTestId('audits-board-lane-closed')
    expect(within(closed).queryByText('0%')).not.toBeInTheDocument()
    expect(screen.queryByTestId('audits-board-score-56')).not.toBeInTheDocument()
  })

  it('keeps a real 0% when the run has a positive max_score', async () => {
    mockListRuns.mockResolvedValueOnce({
      data: {
        items: [
          {
            id: 90,
            reference_number: 'AUD-2026-0090',
            template_id: 21,
            template_version: 1,
            title: 'Failed scored close',
            status: 'completed',
            source_origin: 'internal',
            score_percentage: 0,
            max_score: 10,
            created_at: new Date().toISOString(),
            completed_at: new Date().toISOString(),
          },
        ],
        total: 1,
        page: 1,
        page_size: 100,
        pages: 1,
      },
    })

    render(<Audits />)

    expect(await screen.findByTestId('audits-board-score-90')).toHaveTextContent('0%')
    expect(screen.getByTestId('audits-kpi-avg-score')).toHaveTextContent('0%')
    expect(screen.queryByTestId('audits-kpi-avg-score-caption')).not.toBeInTheDocument()
  })
})

function a3Run(
  partial: Record<string, unknown> & { id: number; title: string },
): Record<string, unknown> {
  return {
    template_id: 21,
    template_version: 1,
    status: 'in_progress',
    source_origin: 'internal',
    created_at: '2026-07-12T10:00:00Z',
    ...partial,
  }
}

function a3Finding(
  partial: Record<string, unknown> & { id: number; run_id: number; title: string },
): Record<string, unknown> {
  return {
    reference_number: `AF-${String(partial.id).padStart(5, '0')}`,
    description: 'd',
    severity: 'medium',
    finding_type: 'nonconformity',
    status: 'open',
    corrective_action_required: true,
    created_at: '2026-07-12T10:00:00Z',
    ...partial,
  }
}

describe('A3 programme-scoped findings + clause', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockSearchParams = new URLSearchParams()
    mockListTemplates.mockResolvedValue({
      data: { items: [], total: 0, page: 1, page_size: 100, pages: 0 },
    })
  })

  it('scopes Open Findings KPI to the Internal chip, not the tenant server total', async () => {
    mockListRuns.mockResolvedValue({
      data: {
        items: [
          a3Run({ id: 1, reference_number: 'AUD-2026-0001', title: 'Internal one' }),
          a3Run({ id: 2, reference_number: 'AUD-2026-0002', title: 'Internal two' }),
          a3Run({ id: 3, reference_number: 'AUD-2026-0003', title: 'Internal three' }),
          a3Run({ id: 4, reference_number: 'AUD-2026-0004', title: 'Internal four' }),
          a3Run({ id: 5, reference_number: 'AUD-2026-0005', title: 'Internal five' }),
          a3Run({ id: 6, reference_number: 'AUD-2026-0006', title: 'Internal six' }),
          a3Run({
            id: 99,
            reference_number: 'AUD-2026-0099',
            title: 'Customer visit',
            source_origin: 'customer',
          }),
        ],
        total: 7,
        page: 1,
        page_size: 100,
        pages: 1,
      },
    })
    stubFindingsApi({
      items: [
        a3Finding({ id: 11, run_id: 1, title: 'Internal open A' }),
        a3Finding({ id: 12, run_id: 1, title: 'Internal open B' }),
        a3Finding({ id: 91, run_id: 99, title: 'Customer open' }),
      ],
      total: 101,
    })
    mockListFindings.mockImplementation((_page, pageSize, _runId, status?: string) => {
      if (status === 'open') {
        return Promise.resolve({
          data: { items: [], total: 100, page: 1, page_size: 1, pages: 1 },
        })
      }
      return Promise.resolve({
        data: {
          items: [
            a3Finding({ id: 11, run_id: 1, title: 'Internal open A' }),
            a3Finding({ id: 12, run_id: 1, title: 'Internal open B' }),
            a3Finding({ id: 91, run_id: 99, title: 'Customer open' }),
          ],
          total: 101,
          page: 1,
          page_size: pageSize,
          pages: 1,
        },
      })
    })

    render(<Audits />)

    expect(await screen.findByTestId('audits-kpi-open-findings')).toHaveTextContent('100')
    fireEvent.click(screen.getByTestId('audits-program-chip-internal'))
    expect(screen.getByTestId('audits-kpi-open-findings')).toHaveTextContent('2')
    expect(screen.getByTestId('audits-kpi-open-findings')).not.toHaveTextContent('100')

    fireEvent.click(screen.getByRole('button', { name: 'Findings' }))
    expect(screen.getByTestId('finding-card-11')).toBeInTheDocument()
    expect(screen.getByTestId('finding-card-12')).toBeInTheDocument()
    expect(screen.queryByTestId('finding-card-91')).not.toBeInTheDocument()
  })

  it('honours ?view=findings&clause= and does not invent unmatched findings', async () => {
    mockSearchParams = new URLSearchParams('view=findings&clause=7.2')
    mockListRuns.mockResolvedValue({
      data: {
        items: [a3Run({ id: 1, reference_number: 'AUD-2026-0001', title: 'Internal one' })],
        total: 1,
        page: 1,
        page_size: 100,
        pages: 1,
      },
    })
    stubFindingsApi({
      items: [
        a3Finding({
          id: 21,
          run_id: 1,
          title: 'Competence gap',
          clause_ids: ['7.2'],
        }),
        a3Finding({
          id: 22,
          run_id: 1,
          title: 'Documented information',
          clause_ids: ['8.1'],
        }),
      ],
    })

    render(<Audits />)

    expect(await screen.findByTestId('audits-findings-clause-filter')).toHaveTextContent('7.2')
    expect(screen.getByTestId('finding-card-21')).toBeInTheDocument()
    expect(screen.queryByTestId('finding-card-22')).not.toBeInTheDocument()
    expect(screen.getByTestId('audits-kpi-open-findings')).toHaveTextContent('1')
  })
})

describe('A5b server search q=', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockSearchParams = new URLSearchParams()
    stubFindingsApi()
    mockListTemplates.mockResolvedValue({
      data: { items: [], total: 0, page: 1, page_size: 100, pages: 0 },
    })
  })

  it('refetches listRuns with q so search is not stuck on the loaded page', async () => {
    mockListRuns.mockImplementation((_page?: number, _pageSize?: number, options?: { q?: string }) => {
      if (options?.q === 'Wickford-needle') {
        return Promise.resolve({
          data: {
            items: [
              {
                id: 240,
                reference_number: 'AUD-2026-0240',
                template_id: 21,
                template_version: 1,
                title: 'Wickford-needle close',
                status: 'completed',
                source_origin: 'internal',
                created_at: new Date().toISOString(),
              },
            ],
            total: 1,
            page: 1,
            page_size: 100,
            pages: 1,
          },
        })
      }
      return Promise.resolve({
        data: {
          items: [
            {
              id: 1,
              reference_number: 'AUD-2026-0001',
              template_id: 21,
              template_version: 1,
              title: 'Loaded page run',
              status: 'scheduled',
              source_origin: 'internal',
              created_at: new Date().toISOString(),
            },
          ],
          total: 240,
          page: 1,
          page_size: 100,
          pages: 3,
        },
      })
    })

    render(<Audits />)
    expect(await screen.findByText('Loaded page run')).toBeInTheDocument()
    fireEvent.change(screen.getByTestId('audits-search'), {
      target: { value: 'Wickford-needle' },
    })
    expect(await screen.findByText('Wickford-needle close')).toBeInTheDocument()
    expect(screen.queryByText('Loaded page run')).not.toBeInTheDocument()
    expect(mockListRuns).toHaveBeenCalledWith(1, 100, { q: 'Wickford-needle' })
  })
})
