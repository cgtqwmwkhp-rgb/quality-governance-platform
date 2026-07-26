/**
 * PX-261: "Please choose the external audit type" rendered at the foot of a
 * scrolling dialog while the offending control sat at the top, out of view, and
 * no control carried a `required` attribute so assistive technology got no
 * programmatic signal at all.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import Audits from '../Audits'

const mockNavigate = vi.fn()
const mockListRuns = vi.fn()
const mockListFindings = vi.fn()
const mockListTemplates = vi.fn()
const mockCreateRun = vi.fn()

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
    useSearchParams: () => [new URLSearchParams(), vi.fn()],
  }
})

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, options?: unknown) => (typeof options === 'string' ? options : key),
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
    updateRun: vi.fn(),
    updateFinding: vi.fn(),
    flagFindingToRisk: vi.fn(),
  },
  actionsApi: {
    list: vi
      .fn()
      .mockResolvedValue({ data: { items: [], total: 0, page: 1, page_size: 100, pages: 0 } }),
    update: vi.fn(),
    create: vi.fn(),
  },
  evidenceAssetsApi: { upload: vi.fn() },
  externalAuditImportsApi: { createJob: vi.fn(), queueJob: vi.fn() },
}))

vi.mock('../../components/ui/Toast', () => ({
  ToastContainer: () => null,
  useToast: () => ({ toasts: [], dismiss: vi.fn(), show: vi.fn() }),
}))

const intakeTemplate = {
  id: 11,
  reference_number: 'TPL-0001',
  name: 'External Audit Intake (System)',
  description: 'Reusable external audit template',
  category: 'System',
  audit_type: 'external_import',
  tags: ['external_audit_intake'],
  version: 1,
  is_active: true,
  is_published: true,
  created_at: '2026-03-24T10:00:00Z',
  updated_at: '2026-03-24T10:00:00Z',
}

describe('Import External Audit — shared form primitive', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockListRuns.mockResolvedValue({
      data: { items: [], total: 0, page: 1, page_size: 100, pages: 0 },
    })
    mockListFindings.mockResolvedValue({
      data: { items: [], total: 0, page: 1, page_size: 100, pages: 0 },
    })
    mockListTemplates.mockResolvedValue({
      data: { items: [intakeTemplate], total: 1, page: 1, page_size: 100, pages: 1 },
    })
  })

  async function openImportDialog() {
    render(<Audits />)
    fireEvent.click(await screen.findByRole('button', { name: 'Import External Audit' }))
    return screen.findByRole('dialog')
  }

  it('PX-261: required controls carry a programmatic signal, not just JavaScript rules', async () => {
    const dialog = await openImportDialog()

    const typeSelect = within(dialog).getByLabelText(/External Audit Program/i)
    expect(typeSelect).toBeRequired()
    expect(typeSelect).toHaveAttribute('aria-required', 'true')

    const reportInput = within(dialog).getByLabelText(/Source Audit Report/i)
    expect(reportInput).toBeRequired()
    expect(reportInput).toHaveAttribute('aria-required', 'true')

    expect(document.querySelector('label[for="audit-import-type"]')?.textContent).toContain('*')
  })

  it('PX-261: the message sits beside the offending control, which is scrolled to and focused', async () => {
    const dialog = await openImportDialog()
    const typeSelect = within(dialog).getByLabelText(/External Audit Program/i)
    const scrollIntoView = vi.fn()
    typeSelect.scrollIntoView = scrollIntoView

    fireEvent.click(within(dialog).getByRole('button', { name: 'Create Intake' }))

    const error = await screen.findByTestId('audit-import-type-error')
    expect(error).toHaveTextContent('Please choose the external audit type')
    // Adjacent to the control, not stranded at the foot of the dialog.
    expect(typeSelect.getAttribute('aria-describedby')).toContain('audit-import-type-error')
    expect(typeSelect).toHaveAttribute('aria-invalid', 'true')
    expect(scrollIntoView).toHaveBeenCalled()
    expect(document.activeElement).toBe(typeSelect)
    expect(mockCreateRun).not.toHaveBeenCalled()
  })

  it('PX-261: with several fields missing, the user lands on the first one on screen', async () => {
    const dialog = await openImportDialog()

    fireEvent.click(within(dialog).getByRole('button', { name: 'Create Intake' }))

    await screen.findByTestId('audit-import-type-error')
    // Report file is also missing, but focus goes to the topmost control.
    expect(screen.getByTestId('audit-report-file-error')).toBeInTheDocument()
    expect(document.activeElement).toBe(within(dialog).getByLabelText(/External Audit Program/i))
  })

  it('PX-172: Escape on a dirty import dialog asks before discarding', async () => {
    const dialog = await openImportDialog()
    fireEvent.change(within(dialog).getByLabelText(/External Audit Program/i), {
      target: { value: 'customer' },
    })

    fireEvent.keyDown(dialog, { key: 'Escape' })

    expect(await screen.findByTestId('audit-unsaved-changes')).toBeInTheDocument()
    // The import dialog is still mounted behind the confirmation, so nothing is lost.
    expect(screen.getByTestId('audit-create-submit')).toBeInTheDocument()
  })

  it('PX-172: Escape on an untouched import dialog closes it without a prompt', async () => {
    const dialog = await openImportDialog()

    fireEvent.keyDown(dialog, { key: 'Escape' })

    await waitFor(() =>
      expect(screen.queryByRole('button', { name: 'Create Intake' })).not.toBeInTheDocument(),
    )
    expect(screen.queryByTestId('audit-unsaved-changes')).not.toBeInTheDocument()
  })
})
