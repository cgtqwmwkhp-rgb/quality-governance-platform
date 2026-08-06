import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { EvidenceAsset } from '../api/client'
import { EvidenceAssetPreviewDialog } from './EvidenceAssetPreviewDialog'

const mockGetSignedUrl = vi.fn()

vi.mock('../api/client', () => ({
  evidenceAssetsApi: {
    getSignedUrl: (...args: unknown[]) => mockGetSignedUrl(...args),
  },
}))

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
    mockGetSignedUrl.mockResolvedValue({ data: { signed_url: 'https://example.test/inline.pdf' } })
  })

  it('fetches an inline signed URL and renders DocumentPreview for Tier 1 PDF', async () => {
    render(
      <EvidenceAssetPreviewDialog
        asset={makeAsset()}
        open
        onOpenChange={() => undefined}
      />,
    )

    await waitFor(() => {
      expect(mockGetSignedUrl).toHaveBeenCalledWith(42, undefined, 'inline')
    })
    expect(await screen.findByTestId('document-preview-pdf')).toBeInTheDocument()
    expect(screen.getByTitle('Preview of Scene report')).toHaveAttribute(
      'src',
      'https://example.test/inline.pdf',
    )
  })

  it('shows unsupported copy for Office docs and still offers Download', async () => {
    const user = userEvent.setup()
    mockGetSignedUrl.mockResolvedValue({
      data: { signed_url: 'https://example.test/sheet.xlsx' },
    })

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
    expect(mockGetSignedUrl).not.toHaveBeenCalled()

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
    expect(mockGetSignedUrl).not.toHaveBeenCalled()
    expect(screen.getByAltText('Scene report')).toHaveAttribute(
      'src',
      'https://example.test/already-inline.jpg',
    )
  })
})
