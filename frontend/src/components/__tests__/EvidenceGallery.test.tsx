import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { evidenceAssetsApi, type EvidenceAsset } from '../../api/client'
import { EvidenceGallery, isEvidenceImage } from '../EvidenceGallery'

vi.mock('../../api/client', () => ({
  evidenceAssetsApi: {
    getSignedUrl: vi.fn(),
  },
}))

const asset = (
  id: number,
  filename: string,
  contentType = 'image/jpeg',
): EvidenceAsset => ({
  id,
  storage_key: `evidence/incident/1/${filename}`,
  original_filename: filename,
  content_type: contentType,
  asset_type: contentType.startsWith('image/') ? 'photo' : 'document',
  source_module: 'incident',
  source_id: 1,
  visibility: 'internal_customer',
  contains_pii: false,
  redaction_required: false,
  retention_policy: 'standard',
  created_at: '2026-07-22T10:00:00Z',
  updated_at: '2026-07-22T10:00:00Z',
})

describe('EvidenceGallery', () => {
  it('renders image thumbnails from inline signed URLs', async () => {
    vi.mocked(evidenceAssetsApi.getSignedUrl).mockResolvedValue({
      data: { signed_url: 'https://example.test/scene.jpg' },
    } as never)

    render(<EvidenceGallery assets={[asset(1, 'scene.jpg')]} />)

    const image = await screen.findByAltText('scene.jpg')
    expect(image.getAttribute('src')).toBe('https://example.test/scene.jpg')
    expect(evidenceAssetsApi.getSignedUrl).toHaveBeenCalledWith(1, undefined, 'inline')
  })

  it('navigates previews with the next control and arrow keys', async () => {
    vi.mocked(evidenceAssetsApi.getSignedUrl).mockImplementation((id) =>
      Promise.resolve({ data: { signed_url: `https://example.test/${id}.jpg` } } as never),
    )

    render(<EvidenceGallery assets={[asset(1, 'first.jpg'), asset(2, 'second.jpg')]} />)

    await screen.findByAltText('first.jpg')
    fireEvent.click(screen.getByRole('button', { name: 'Preview first.jpg' }))

    const dialog = await screen.findByRole('dialog')
    fireEvent.click(within(dialog).getByRole('button', { name: 'Next evidence' }))
    expect(within(dialog).getByAltText('second.jpg').getAttribute('src')).toBe(
      'https://example.test/2.jpg',
    )

    fireEvent.keyDown(window, { key: 'ArrowLeft' })
    await waitFor(() => {
      expect(within(dialog).getByAltText('first.jpg')).not.toBeNull()
    })

    fireEvent.keyDown(window, { key: 'ArrowRight' })
    fireEvent.keyDown(window, { key: 'ArrowRight' })
    await waitFor(() => {
      expect(within(dialog).getByAltText('first.jpg')).not.toBeNull()
    })
  })

  it('keeps the selected evidence open when assets reorder', async () => {
    vi.mocked(evidenceAssetsApi.getSignedUrl).mockImplementation((id) =>
      Promise.resolve({ data: { signed_url: `https://example.test/${id}.jpg` } } as never),
    )

    const first = asset(1, 'first.jpg')
    const second = asset(2, 'second.jpg')
    const { rerender } = render(<EvidenceGallery assets={[first, second]} />)

    await screen.findByAltText('first.jpg')
    fireEvent.click(screen.getByRole('button', { name: 'Preview second.jpg' }))
    const dialog = await screen.findByRole('dialog')

    rerender(<EvidenceGallery assets={[second, first]} />)

    await waitFor(() => {
      expect(within(dialog).getByAltText('second.jpg')).not.toBeNull()
    })
  })

  it('previews PDFs in the lightbox instead of download-only copy', async () => {
    vi.mocked(evidenceAssetsApi.getSignedUrl).mockResolvedValue({
      data: { signed_url: 'https://example.test/report.pdf' },
    } as never)

    render(<EvidenceGallery assets={[asset(9, 'report.pdf', 'application/pdf')]} />)

    fireEvent.click(screen.getByRole('button', { name: 'Preview report.pdf' }))
    const dialog = await screen.findByRole('dialog')

    await waitFor(() => {
      expect(within(dialog).getByTestId('document-preview-pdf')).not.toBeNull()
    })
    expect(within(dialog).getByTitle('Preview of report.pdf').getAttribute('src')).toBe(
      'https://example.test/report.pdf',
    )
    expect(within(dialog).queryByText(/cannot be previewed here/i)).toBeNull()
    expect(within(dialog).getByRole('button', { name: /download/i })).toBeInTheDocument()
    expect(evidenceAssetsApi.getSignedUrl).toHaveBeenCalledWith(9, undefined, 'inline')
  })

  it('previews video in the lightbox with download as a secondary CTA', async () => {
    vi.mocked(evidenceAssetsApi.getSignedUrl).mockResolvedValue({
      data: { signed_url: 'https://example.test/clip.mp4' },
    } as never)

    render(<EvidenceGallery assets={[asset(3, 'clip.mp4', 'video/mp4')]} />)

    fireEvent.click(screen.getByRole('button', { name: 'Preview clip.mp4' }))
    const dialog = await screen.findByRole('dialog')

    await waitFor(() => {
      expect(within(dialog).getByTestId('document-preview-video')).not.toBeNull()
    })
    expect(within(dialog).queryByText(/cannot be previewed here/i)).toBeNull()
    expect(within(dialog).getByRole('button', { name: /download/i })).toBeInTheDocument()
  })

  it('treats photo assets and image filenames as images even when MIME is generic', () => {
    expect(
      isEvidenceImage({
        content_type: 'application/octet-stream',
        asset_type: 'photo',
        original_filename: 'scene.bin',
      }),
    ).toBe(true)
    expect(
      isEvidenceImage({
        content_type: 'application/octet-stream',
        asset_type: 'other',
        original_filename: 'pro-xXTDOUic.jpeg',
      }),
    ).toBe(true)
    expect(
      isEvidenceImage({
        content_type: 'application/pdf',
        asset_type: 'pdf',
        original_filename: 'report.pdf',
      }),
    ).toBe(false)
  })

  it('shows preview unavailable when the thumbnail image fails to load', async () => {
    vi.mocked(evidenceAssetsApi.getSignedUrl).mockResolvedValue({
      data: { signed_url: 'https://example.test/broken.jpg' },
    } as never)

    render(<EvidenceGallery assets={[asset(1, 'broken.jpg')]} />)

    const image = await screen.findByAltText('broken.jpg')
    fireEvent.error(image)

    expect(await screen.findByText('Preview unavailable')).toBeInTheDocument()
    expect(screen.queryByAltText('broken.jpg')).toBeNull()
  })
})
