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

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: () => mockNavigate }
})

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
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
    mockListRuns.mockResolvedValue({
      data: { items: [], total: 0, page: 1, page_size: 100, pages: 0 },
    })
    mockListFindings.mockResolvedValue({
      data: { items: [], total: 0, page: 1, page_size: 100, pages: 0 },
    })
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
        status: 'scheduled',
        source_origin: 'third_party',
        assurance_scheme: 'Achilles UVDB',
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

  it('imports an external audit and links the uploaded report', async () => {
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
    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/audits/41/import-review?jobId=72')
    })
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
    expect(
      screen.getByText(/Blob storage is temporarily unavailable/),
    ).toBeInTheDocument()
    expect(mockUpdateRun).not.toHaveBeenCalled()
    expect(mockNavigate).not.toHaveBeenCalled()
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
    expect(screen.queryByText('Failed to schedule audit. Please try again.')).not.toBeInTheDocument()
  })

  it('hides system intake templates from the schedule picker', async () => {
    render(<Audits />)

    fireEvent.click(await screen.findByRole('button', { name: 'Schedule Audit' }))

    const dialog = await screen.findByRole('dialog')
    const templateSelect = within(dialog).getAllByRole('combobox')[0]!
    const options = within(templateSelect).getAllByRole('option').map((option) => option.textContent)

    expect(options.join(' ')).toContain('Annual Safety Audit')
    expect(options.join(' ')).not.toContain('ZZZ External Audit Intake (System)')
  })
})
