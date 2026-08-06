import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { RecordFilingControl } from '../RecordFilingControl'
import type { ComplianceRecord } from '../../../api/complianceScheduleClient'

const { mockListAssets, mockFile, mockGet, mockToast } = vi.hoisted(() => ({
  mockListAssets: vi.fn(),
  mockFile: vi.fn(),
  mockGet: vi.fn(),
  mockToast: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
}))

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, opts?: string | { defaultValue?: string; ref?: string }) => {
      if (typeof opts === 'string') return opts
      if (opts && typeof opts === 'object' && 'ref' in opts && opts.ref) {
        const base = typeof opts.defaultValue === 'string' ? opts.defaultValue : key
        return base.replace('{{ref}}', opts.ref)
      }
      if (opts?.defaultValue) return opts.defaultValue
      return key
    },
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

vi.mock('../../../contexts/ToastContext', () => ({ toast: mockToast }))

vi.mock('../../../api/client', () => ({
  default: { get: mockGet },
  evidenceAssetsApi: { list: mockListAssets },
  complianceScheduleApi: { fileRecordToLibrary: mockFile },
  getApiErrorMessage: (_e: unknown, fallback?: string) => fallback ?? 'failed',
}))

function makeRecord(overrides: Partial<ComplianceRecord> = {}): ComplianceRecord {
  return {
    id: 55,
    external_id: 'ext-55',
    tenant_id: 1,
    reference_number: 'CRC-2026-0001',
    requirement_id: 10,
    due_date: '2026-04-01',
    outcome: 'completed',
    completed_at: '2026-04-02T09:00:00Z',
    filing_status: 'not_filed',
    library_document_id: null,
    filing_error: null,
    created_at: '2026-04-02T09:00:00Z',
    ...overrides,
  }
}

function renderControl(record: ComplianceRecord, onFiled = vi.fn()) {
  render(
    <MemoryRouter>
      <RecordFilingControl record={record} onFiled={onFiled} />
    </MemoryRouter>,
  )
  return onFiled
}

async function openAndFill(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByTestId('compliance-schedule-record-filing-55-toggle'))
  const evidence = await screen.findByTestId('compliance-schedule-record-filing-55-evidence-select')
  await waitFor(() =>
    expect(
      screen.getByTestId('compliance-schedule-record-filing-55-category-select'),
    ).not.toBeDisabled(),
  )
  await user.selectOptions(evidence, '99')
  await user.selectOptions(
    screen.getByTestId('compliance-schedule-record-filing-55-category-select'),
    '4',
  )
}

describe('RecordFilingControl', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockListAssets.mockResolvedValue({
      data: { items: [{ id: 99, title: 'FRA 2026', original_filename: 'fra.pdf' }] },
    })
    mockGet.mockResolvedValue({
      data: {
        sections: [
          {
            id: 1,
            taxonomy_id: '03',
            name: 'Health & Safety',
            children: [{ id: 4, taxonomy_id: '03.01', name: 'Fire Safety', active: true }],
          },
        ],
      },
    })
    mockFile.mockResolvedValue({
      data: { library_document_id: 321, pel_doc_ref: 'PEL-HSE-01-004', duplicate_warning: false },
    })
  })

  it('says a completed occurrence is not filed, because completing files nothing', () => {
    renderControl(makeRecord())
    expect(screen.getByTestId('compliance-schedule-record-not-filed-55')).toBeInTheDocument()
    expect(screen.getByTestId('compliance-schedule-record-filing-55-toggle')).toBeInTheDocument()
  })

  it('loads nothing until the user asks to file', () => {
    renderControl(makeRecord())
    expect(mockListAssets).not.toHaveBeenCalled()
    expect(mockGet).not.toHaveBeenCalled()
  })

  it('files the chosen evidence under the chosen category', async () => {
    const user = userEvent.setup()
    const onFiled = renderControl(makeRecord())

    await openAndFill(user)
    await user.type(screen.getByTestId('compliance-schedule-record-filing-55-title-input'), 'FRA')
    await user.click(screen.getByTestId('compliance-schedule-record-filing-55-submit'))

    await waitFor(() =>
      expect(mockFile).toHaveBeenCalledWith(55, {
        evidence_asset_id: 99,
        category_id: 4,
        title: 'FRA',
      }),
    )
    expect(mockListAssets).toHaveBeenCalledWith(
      expect.objectContaining({ source_module: 'compliance_record', source_id: 55 }),
    )
    expect(onFiled).toHaveBeenCalled()
  })

  it('omits an empty title rather than sending a blank one', async () => {
    const user = userEvent.setup()
    renderControl(makeRecord())

    await openAndFill(user)
    await user.click(screen.getByTestId('compliance-schedule-record-filing-55-submit'))

    await waitFor(() =>
      expect(mockFile).toHaveBeenCalledWith(55, { evidence_asset_id: 99, category_id: 4 }),
    )
  })

  it('cannot submit until both an attachment and a category are chosen', async () => {
    const user = userEvent.setup()
    renderControl(makeRecord())

    await user.click(screen.getByTestId('compliance-schedule-record-filing-55-toggle'))
    const submit = await screen.findByTestId('compliance-schedule-record-filing-55-submit')
    expect(submit).toBeDisabled()

    await user.selectOptions(
      await screen.findByTestId('compliance-schedule-record-filing-55-evidence-select'),
      '99',
    )
    expect(submit).toBeDisabled()
  })

  it('warns about a Library duplicate without reporting the filing as failed', async () => {
    mockFile.mockResolvedValue({
      data: { library_document_id: 321, pel_doc_ref: null, duplicate_warning: true },
    })
    const user = userEvent.setup()
    renderControl(makeRecord())

    await openAndFill(user)
    await user.click(screen.getByTestId('compliance-schedule-record-filing-55-submit'))

    await waitFor(() => expect(mockToast.warning).toHaveBeenCalled())
    expect(mockToast.success).toHaveBeenCalled()
    expect(mockToast.error).not.toHaveBeenCalled()
  })

  it('refreshes the row when filing fails, so a server-side failure becomes visible', async () => {
    mockFile.mockRejectedValue(new Error('boom'))
    const user = userEvent.setup()
    const onFiled = renderControl(makeRecord())

    await openAndFill(user)
    await user.click(screen.getByTestId('compliance-schedule-record-filing-55-submit'))

    await waitFor(() => expect(mockToast.error).toHaveBeenCalled())
    expect(onFiled).toHaveBeenCalled()
  })

  it('tells the user nothing is attached yet rather than offering an empty picker', async () => {
    mockListAssets.mockResolvedValue({ data: { items: [] } })
    const user = userEvent.setup()
    renderControl(makeRecord())

    await user.click(screen.getByTestId('compliance-schedule-record-filing-55-toggle'))
    expect(
      await screen.findByTestId('compliance-schedule-record-filing-55-evidence-empty'),
    ).toBeInTheDocument()
  })

  it('distinguishes an unreadable attachment list from an empty one', async () => {
    mockListAssets.mockRejectedValue(new Error('nope'))
    const user = userEvent.setup()
    renderControl(makeRecord())

    await user.click(screen.getByTestId('compliance-schedule-record-filing-55-toggle'))
    expect(
      await screen.findByTestId('compliance-schedule-record-filing-55-evidence-failed'),
    ).toBeInTheDocument()
    expect(
      screen.queryByTestId('compliance-schedule-record-filing-55-evidence-empty'),
    ).not.toBeInTheDocument()
  })

  it('links to the filed document and stops offering to file again', () => {
    renderControl(makeRecord({ filing_status: 'filed', library_document_id: 321 }))
    const filed = screen.getByTestId('compliance-schedule-record-filed-55')
    expect(filed).toBeInTheDocument()
    expect(filed.querySelector('a')).toHaveAttribute('href', '/documents/321')
    expect(
      screen.queryByTestId('compliance-schedule-record-filing-55-toggle'),
    ).not.toBeInTheDocument()
  })

  it('shows why a filing failed and offers a retry', async () => {
    const user = userEvent.setup()
    renderControl(
      makeRecord({ filing_status: 'filing_failed', filing_error: 'container missing' }),
    )
    expect(screen.getByTestId('compliance-schedule-record-filing-failed-55')).toHaveTextContent(
      'container missing',
    )
    const toggle = screen.getByTestId('compliance-schedule-record-filing-55-toggle')
    expect(toggle).toHaveTextContent('Try filing again')
    await user.click(toggle)
    expect(
      await screen.findByTestId('compliance-schedule-record-filing-55-evidence-select'),
    ).toBeInTheDocument()
  })

  it('never offers a category the filing endpoint cannot address', async () => {
    mockGet.mockResolvedValue({
      data: {
        sections: [
          {
            id: 1,
            taxonomy_id: '03',
            name: 'Health & Safety',
            children: [
              { taxonomy_id: '03.01', name: 'No id', active: true },
              { id: 4, taxonomy_id: '03.02', name: 'Fire Safety', active: true },
            ],
          },
        ],
      },
    })
    const user = userEvent.setup()
    renderControl(makeRecord())

    await user.click(screen.getByTestId('compliance-schedule-record-filing-55-toggle'))
    const select = await screen.findByTestId('compliance-schedule-record-filing-55-category-select')
    await waitFor(() => expect(select).not.toBeDisabled())
    const values = Array.from(select.querySelectorAll('option')).map((o) => o.value)
    expect(values).toEqual(['', '4'])
  })
})
