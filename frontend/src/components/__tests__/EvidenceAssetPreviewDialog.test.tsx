import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { EvidenceAsset } from '../../api/client'
import { EvidenceAssetPreviewDialog } from '../EvidenceAssetPreviewDialog'

const mockGetSignedUrl = vi.fn()
const mockGetContent = vi.fn()

vi.mock('../../api/client', () => ({
  evidenceAssetsApi: {
    getSignedUrl: (...args: unknown[]) => mockGetSignedUrl(...args),
    getContent: (...args: unknown[]) => mockGetContent(...args),
  },
}))

const OBJECT_URL = 'blob:mock/preview'
let revoked: string[] = []

function makeAsset(overrides: Partial<EvidenceAsset> = {}): EvidenceAsset {
  return {
    id: 42,
    storage_key: 'k',
    content_type: 'application/pdf',
    asset_type: 'pdf',
    source_module: 'investigation',
    source_id: 1,
    visibility: 'internal_only',
    contains_pii: false,
    redaction_required: false,
    retention_policy: 'standard',
    created_at: '2026-08-01T00:00:00Z',
    updated_at: '2026-08-01T00:00:00Z',
    original_filename: 'report.pdf',
    title: 'Scene report',
    ...overrides,
  }
}

describe('EvidenceAssetPreviewDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    revoked = []
    mockGetContent.mockResolvedValue({ data: new Blob(['pdf-bytes']) })
    mockGetSignedUrl.mockResolvedValue({ data: { signed_url: 'https://storage.test/inline.pdf' } })
    vi.spyOn(URL, 'createObjectURL').mockReturnValue(OBJECT_URL)
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation((url: string) => {
      revoked.push(url)
    })
  })

  it('renders Tier 1 PDF from bytes fetched through the API, not from a signed URL', async () => {
    render(
      <EvidenceAssetPreviewDialog
        asset={makeAsset()}
        open
        onOpenChange={() => undefined}
      />,
    )

    await waitFor(() => {
      expect(mockGetContent).toHaveBeenCalledWith(42, 'inline')
    })
    expect(await screen.findByTestId('document-preview-pdf')).toBeInTheDocument()
    expect(screen.getByTitle('Preview of Scene report')).toHaveAttribute('src', OBJECT_URL)
    expect(mockGetSignedUrl).not.toHaveBeenCalled()
  })

  it('revokes the object URL when the dialog goes away', async () => {
    const { unmount } = render(
      <EvidenceAssetPreviewDialog
        asset={makeAsset()}
        open
        onOpenChange={() => undefined}
      />,
    )

    await screen.findByTestId('document-preview-pdf')
    expect(revoked).toEqual([])

    unmount()

    expect(revoked).toEqual([OBJECT_URL])
  })

  it('shows preview-unavailable copy when the bytes cannot be fetched', async () => {
    mockGetContent.mockRejectedValue(new Error('404'))

    render(
      <EvidenceAssetPreviewDialog
        asset={makeAsset()}
        open
        onOpenChange={() => undefined}
      />,
    )

    expect(await screen.findByTestId('document-preview-failed')).toBeInTheDocument()
    expect(URL.createObjectURL).not.toHaveBeenCalled()
  })

  it('shows unsupported copy for Office docs and still downloads via a signed URL', async () => {
    const user = userEvent.setup()

    render(
      <EvidenceAssetPreviewDialog
        asset={makeAsset({
          content_type:
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
          original_filename: 'sheet.xlsx',
          title: 'Sheet',
          asset_type: 'document',
        })}
        open
        onOpenChange={() => undefined}
      />,
    )

    expect(await screen.findByTestId('evidence-asset-preview-unsupported')).toBeInTheDocument()
    expect(mockGetContent).not.toHaveBeenCalled()

    await user.click(screen.getByTestId('evidence-asset-preview-download'))
    await waitFor(() => {
      expect(mockGetSignedUrl).toHaveBeenCalledWith(42, undefined, 'attachment')
    })
  })

  it('uses a host-supplied preview URL without refetching', async () => {
    render(
      <EvidenceAssetPreviewDialog
        asset={makeAsset({ content_type: 'image/jpeg', original_filename: 'photo.jpg' })}
        open
        onOpenChange={() => undefined}
        previewUrl="https://example.test/already-inline.jpg"
      />,
    )

    expect(await screen.findByTestId('document-preview-image')).toBeInTheDocument()
    expect(mockGetContent).not.toHaveBeenCalled()
    expect(mockGetSignedUrl).not.toHaveBeenCalled()
    expect(screen.getByAltText('Scene report')).toHaveAttribute(
      'src',
      'https://example.test/already-inline.jpg',
    )
  })
})
