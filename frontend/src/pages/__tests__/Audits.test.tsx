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
            id: 11,
            reference_number: 'TPL-0001',
            name: 'External Audit Intake',
            description: 'Reusable external audit template',
            category: 'Compliance',
            audit_type: 'audit',
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
  })

  it('imports an external audit and links the uploaded report', async () => {
    render(<Audits />)

    fireEvent.click(await screen.findByRole('button', { name: 'Import External Audit' }))

    const dialog = await screen.findByRole('dialog')
    fireEvent.change(within(dialog).getByLabelText(/Import Type/i), {
      target: { value: 'achilles_uvdb' },
    })

    expect(within(dialog).getByDisplayValue('third_party')).toBeInTheDocument()
    expect(within(dialog).getByLabelText(/Audit Scheme \/ Standard/i)).toHaveValue('Achilles UVDB')

    const file = new File(['audit pdf'], 'achilles-audit.pdf', { type: 'application/pdf' })
    fireEvent.change(within(dialog).getByLabelText(/Source Audit Report/i), {
      target: { files: [file] },
    })

    fireEvent.click(within(dialog).getAllByRole('button', { name: 'Import External Audit' }).at(-1)!)

    await waitFor(() => {
      expect(mockCreateRun).toHaveBeenCalledTimes(1)
    })

    expect(mockCreateRun).toHaveBeenCalledWith(
      expect.objectContaining({
        template_id: 11,
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
    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/audits/41/execute')
    })
  })

  it('requires a report before importing an external audit', async () => {
    render(<Audits />)

    fireEvent.click(await screen.findByRole('button', { name: 'Import External Audit' }))

    const dialog = await screen.findByRole('dialog')
    fireEvent.change(within(dialog).getByLabelText(/Import Type/i), {
      target: { value: 'customer' },
    })

    fireEvent.click(within(dialog).getAllByRole('button', { name: 'Import External Audit' }).at(-1)!)

    expect(await screen.findByText('Please upload the external audit report')).toBeInTheDocument()
    expect(mockCreateRun).not.toHaveBeenCalled()
  })
})
