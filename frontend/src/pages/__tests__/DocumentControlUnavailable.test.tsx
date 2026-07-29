import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import DocumentControl from '../DocumentControl'

/**
 * The Document Control page must not read an unread distribution list as "none".
 *
 * The server sends `distributions: []` even when the table could not be read,
 * because this page does `detail.distributions.length` and a missing key would
 * crash it. That makes the empty array on its own byte-identical to "no
 * controlled copies were issued" — an ISO-relevant claim. The `unavailable`
 * block travelling beside it is the only thing that distinguishes the two, so
 * these tests pin that the page consults it.
 *
 * Every test here fails before the change: the page rendered the same thing for
 * an empty list and an unread one.
 */

const mockList = vi.fn()
const mockGet = vi.fn()
const mockToastError = vi.fn()

vi.mock('../../api/client', () => ({
  default: { post: vi.fn() },
  documentControlApi: {
    list: (...args: unknown[]) => mockList(...args),
    get: (...args: unknown[]) => mockGet(...args),
    goldenThread: vi.fn(),
    create: vi.fn(),
    submitForApproval: vi.fn(),
    createVersion: vi.fn(),
    publish: vi.fn(),
    distribute: vi.fn(),
  },
  getApiErrorMessage: (err: unknown) => (err instanceof Error ? err.message : 'Request failed'),
  isUnprovisionedError: (err: unknown) =>
    Boolean((err as { unprovisioned?: boolean } | null)?.unprovisioned),
}))

vi.mock('../../contexts/ToastContext', () => ({
  toast: {
    success: vi.fn(),
    error: (...args: unknown[]) => mockToastError(...args),
  },
}))

const DOCUMENT = {
  id: 42,
  document_number: 'DOC-2026-0042',
  title: 'Lifting operations procedure',
  document_type: 'procedure',
  category: 'safety',
  current_version: '1.0',
  status: 'draft',
  department: null,
  owner_name: null,
  effective_date: null,
  next_review_date: null,
  is_overdue: false,
}

function detailPayload(overrides: Record<string, unknown> = {}) {
  return {
    ...DOCUMENT,
    description: null,
    subcategory: null,
    author_name: null,
    approver_name: null,
    approved_date: null,
    expiry_date: null,
    review_frequency_months: 12,
    last_review_date: null,
    file_name: null,
    file_path: null,
    file_size: null,
    file_type: null,
    relevant_standards: null,
    relevant_clauses: null,
    access_level: 'internal',
    is_confidential: false,
    training_required: false,
    view_count: 1,
    download_count: 0,
    versions: [],
    distributions: [],
    ...overrides,
  }
}

async function openTheDocument() {
  render(
    <MemoryRouter>
      <DocumentControl />
    </MemoryRouter>,
  )
  await screen.findByText('Lifting operations procedure')
  await userEvent.click(screen.getByText('Lifting operations procedure'))
}

describe('Document Control distribution list', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockList.mockResolvedValue({ data: { total: 1, documents: [DOCUMENT], library_document_count: 0 } })
  })

  it('says nothing about distributions when the list was read and was empty', async () => {
    mockGet.mockResolvedValue({ data: detailPayload() })

    await openTheDocument()

    await waitFor(() => expect(mockGet).toHaveBeenCalled())
    expect(screen.queryByTestId('document-control-distributions-unavailable')).toBeNull()
  })

  it('discloses that an empty list was never read', async () => {
    mockGet.mockResolvedValue({
      data: detailPayload({
        unavailable: {
          fields: ['access_log', 'distributions'],
          missing_tables: ['document_distributions', 'document_access_logs'],
          provisioning_state: 'migration_pending',
        },
      }),
    })

    await openTheDocument()

    const notice = await screen.findByTestId('document-control-distributions-unavailable')
    expect(notice.textContent).toMatch(/could not be read/i)
    expect(notice.textContent).toContain('document_distributions')
    // The point of the whole change: the page must not say there are none.
    expect(notice.textContent).not.toMatch(/no controlled copies/i)
    expect(notice.textContent).toMatch(/needs a migration/i)
  })

  it('discloses that the view was not written to the access log', async () => {
    mockGet.mockResolvedValue({
      data: detailPayload({
        unavailable: {
          fields: ['access_log'],
          missing_tables: ['document_access_logs'],
        },
      }),
    })

    await openTheDocument()

    const notice = await screen.findByTestId('document-control-access-log-unavailable')
    expect(notice.textContent).toMatch(/not recorded/i)
    expect(notice.textContent).toMatch(/audit trail/i)
  })

  it('still lists the copies that were actually read', async () => {
    mockGet.mockResolvedValue({
      data: detailPayload({
        distributions: [
          {
            id: 7,
            recipient_name: 'Site Manager',
            recipient_type: 'user',
            distribution_type: 'controlled',
            copy_number: 'C-01',
            acknowledged: false,
            acknowledged_date: null,
          },
        ],
      }),
    })

    await openTheDocument()

    expect(await screen.findByTestId('document-control-distribution-7')).toBeTruthy()
    expect(screen.queryByTestId('document-control-distributions-unavailable')).toBeNull()
  })
})

describe('Document Control detail failure copy', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockList.mockResolvedValue({ data: { total: 1, documents: [DOCUMENT], library_document_count: 0 } })
  })

  it('offers a retry for a failure that might clear', async () => {
    mockGet.mockRejectedValue(new Error('Network error'))

    await openTheDocument()

    const panel = await screen.findByTestId('document-control-detail-failed')
    expect(panel.textContent).toMatch(/Retry by selecting the document again/i)
  })

  it('does not invite a retry that can never succeed', async () => {
    const err = Object.assign(new Error('document_distributions is absent'), { unprovisioned: true })
    mockGet.mockRejectedValue(err)

    await openTheDocument()

    const panel = await screen.findByTestId('document-control-detail-unprovisioned')
    expect(panel.textContent).toMatch(/retrying will not help/i)
    expect(panel.textContent).not.toMatch(/Retry by selecting/i)
  })
})
