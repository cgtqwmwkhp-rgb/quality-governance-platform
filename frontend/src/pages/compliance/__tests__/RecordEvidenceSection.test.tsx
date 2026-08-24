import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { RecordEvidenceSection } from '../RecordEvidenceSection'
import { toast } from '../../../contexts/ToastContext'

const {
  mockList,
  mockCreateDraftFromEvidence,
  mockUseFeatureFlag,
} = vi.hoisted(() => ({
  mockList: vi.fn(),
  mockCreateDraftFromEvidence: vi.fn(),
  mockUseFeatureFlag: vi.fn(),
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

vi.mock('../../../hooks/useFeatureFlag', () => ({
  useFeatureFlag: mockUseFeatureFlag,
}))

vi.mock('../../../api/client', () => ({
  evidenceAssetsApi: {
    list: mockList,
    upload: vi.fn(),
    delete: vi.fn(),
    getSignedUrl: vi.fn(),
  },
  complianceScheduleFraOcrApi: {
    createDraftFromEvidence: mockCreateDraftFromEvidence,
  },
  getApiErrorMessage: (_e: unknown, f: string) => f,
}))

vi.mock('../../../components/case/CaseEvidencePanel', () => ({
  CaseEvidencePanel: ({
    sourceId,
    testIdPrefix,
    onUploadComplete,
  }: {
    sourceId: number
    testIdPrefix?: string
    onUploadComplete?: (result?: { uploadedAssetIds: number[] }) => void | Promise<void>
  }) => (
    <div data-testid={`${testIdPrefix || 'case'}-evidence-panel`}>
      <button
        type="button"
        data-testid="mock-case-evidence-upload-complete"
        onClick={() => void onUploadComplete?.({ uploadedAssetIds: [101, 102] })}
      >
        simulate upload complete
      </button>
      <span data-testid="mock-case-evidence-source">{sourceId}</span>
    </div>
  ),
}))

describe('RecordEvidenceSection', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockList.mockResolvedValue({ data: { items: [] } })
    mockUseFeatureFlag.mockReturnValue(false)
    mockCreateDraftFromEvidence.mockResolvedValue({
      data: { id: 7, evidence_asset_id: 101 },
    })
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
  })

  it('loads compliance_record evidence for that occurrence when opened', async () => {
    const user = userEvent.setup()
    render(<RecordEvidenceSection recordId={9} referenceNumber="CRC-1" />)
    await user.click(screen.getByTestId('compliance-schedule-record-evidence-toggle-9'))
    expect(await screen.findByTestId('compliance-record-9-evidence-panel')).toBeInTheDocument()
    expect(screen.getByTestId('mock-case-evidence-source')).toHaveTextContent('9')
  })

  it('auto-triggers FRA OCR from-evidence for eligible PDF uploads when flag is on', async () => {
    const user = userEvent.setup()
    mockUseFeatureFlag.mockReturnValue(true)
    mockList.mockResolvedValue({
      data: {
        items: [
          {
            id: 101,
            content_type: 'application/pdf',
            original_filename: 'fra.pdf',
          },
          {
            id: 102,
            content_type: 'image/jpeg',
            original_filename: 'photo.jpg',
          },
        ],
      },
    })
    const onFraOcrDraftCreated = vi.fn()

    render(
      <RecordEvidenceSection
        recordId={9}
        referenceNumber="CRC-1"
        fraOcrEligible
        onFraOcrDraftCreated={onFraOcrDraftCreated}
      />,
    )
    await user.click(screen.getByTestId('compliance-schedule-record-evidence-upload-cta-9'))
    await user.click(screen.getByTestId('mock-case-evidence-upload-complete'))

    await waitFor(() =>
      expect(mockCreateDraftFromEvidence).toHaveBeenCalledWith(9, { evidence_asset_id: 101 }),
    )
    expect(mockCreateDraftFromEvidence).toHaveBeenCalledTimes(1)
    expect(toast.success).toHaveBeenCalled()
    expect(onFraOcrDraftCreated).toHaveBeenCalledWith(
      expect.objectContaining({ id: 7, evidence_asset_id: 101 }),
    )
  })

  it('does not auto-trigger FRA OCR when obligation is not eligible', async () => {
    const user = userEvent.setup()
    mockUseFeatureFlag.mockReturnValue(true)

    render(<RecordEvidenceSection recordId={9} referenceNumber="CRC-1" fraOcrEligible={false} />)
    await user.click(screen.getByTestId('compliance-schedule-record-evidence-upload-cta-9'))
    await user.click(screen.getByTestId('mock-case-evidence-upload-complete'))

    await waitFor(() => expect(mockCreateDraftFromEvidence).not.toHaveBeenCalled())
  })
})
