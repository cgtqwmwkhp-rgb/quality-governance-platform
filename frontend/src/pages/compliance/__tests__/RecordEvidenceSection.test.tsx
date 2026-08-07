import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { RecordEvidenceSection } from '../RecordEvidenceSection'

const { mockList } = vi.hoisted(() => ({
  mockList: vi.fn(),
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

vi.mock('../../../contexts/ToastContext', () => ({
  toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
}))

vi.mock('../../../api/client', () => ({
  evidenceAssetsApi: {
    list: mockList,
    upload: vi.fn(),
    delete: vi.fn(),
    getSignedUrl: vi.fn(),
  },
  getApiErrorMessage: (_e: unknown, f: string) => f,
}))

describe('RecordEvidenceSection', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockList.mockResolvedValue({ data: { items: [] } })
  })

  it('stays collapsed so a long history does not list every occurrence up front', () => {
    render(<RecordEvidenceSection recordId={9} referenceNumber="CRC-1" />)
    expect(screen.queryByTestId('compliance-record-9-evidence-panel')).not.toBeInTheDocument()
    expect(mockList).not.toHaveBeenCalled()
    expect(
      screen.getByTestId('compliance-schedule-record-evidence-upload-cta-9'),
    ).toHaveTextContent('Upload documents for this past occurrence')
  })

  it('opens the panel from the visible upload CTA without using the muted toggle', async () => {
    const user = userEvent.setup()
    render(<RecordEvidenceSection recordId={9} referenceNumber="CRC-1" />)
    await user.click(screen.getByTestId('compliance-schedule-record-evidence-upload-cta-9'))
    expect(await screen.findByTestId('compliance-record-9-evidence-panel')).toBeInTheDocument()
    expect(mockList).toHaveBeenCalledWith(
      expect.objectContaining({ source_module: 'compliance_record', source_id: 9 }),
    )
  })

  it('loads compliance_record evidence for that occurrence when opened', async () => {
    const user = userEvent.setup()
    render(<RecordEvidenceSection recordId={9} referenceNumber="CRC-1" />)
    await user.click(screen.getByTestId('compliance-schedule-record-evidence-toggle-9'))
    expect(await screen.findByTestId('compliance-record-9-evidence-panel')).toBeInTheDocument()
    expect(mockList).toHaveBeenCalledWith(
      expect.objectContaining({ source_module: 'compliance_record', source_id: 9 }),
    )
  })
})
