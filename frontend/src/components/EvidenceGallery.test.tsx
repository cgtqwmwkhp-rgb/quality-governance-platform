import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { evidenceAssetsApi, type EvidenceAsset } from '../api/client'
import { EvidenceGallery } from './EvidenceGallery'

vi.mock('../api/client', () => ({
  evidenceAssetsApi: {
    getSignedUrl: vi.fn(),
  },
}))

const asset = (id: number, filename: string): EvidenceAsset => ({
  id,
  storage_key: `evidence/incident/1/${filename}`,
  original_filename: filename,
  content_type: 'image/jpeg',
  asset_type: 'photo',
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
})
