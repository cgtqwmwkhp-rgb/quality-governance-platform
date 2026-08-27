import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { evidenceAssetsApi, type EvidenceAsset } from '../../api/client'
import { EvidenceGallery, isEvidenceImage } from '../EvidenceGallery'

vi.mock('../../api/client', () => ({
  evidenceAssetsApi: {
    getSignedUrl: vi.fn(),
    getContent: vi.fn(),
  },
}))

/**
 * Blobs tagged with the asset they came from, so a rendered `src` says which
 * asset produced it instead of being an opaque counter.
 */
const namedBlob = (name: string) => Object.assign(new Blob([name]), { testName: name })

let created: string[] = []
let revoked: string[] = []

/**
 * The most recent object URL created for an asset. Each creation gets its own
 * URL — a refetch replaces the previous one, and only distinct URLs can show
 * that the old one was released while the rendered one was not.
 */
const currentUrlFor = (name: string) =>
  [...created].reverse().find((url) => url.startsWith(`blob:mock/${name}/`))

beforeEach(() => {
  vi.mocked(evidenceAssetsApi.getContent).mockReset()
  created = []
  revoked = []
  vi.spyOn(URL, 'createObjectURL').mockImplementation((blob: Blob | MediaSource) => {
    const url = `blob:mock/${(blob as { testName?: string }).testName ?? 'untagged'}/${created.length + 1}`
    created.push(url)
    return url
  })
  vi.spyOn(URL, 'revokeObjectURL').mockImplementation((url: string) => {
    revoked.push(url)
  })
})

/** Resolve every getContent call with a blob named after the asset id. */
const serveContentByAssetId = () =>
  vi.mocked(evidenceAssetsApi.getContent).mockImplementation((id) =>
    Promise.resolve({ data: namedBlob(String(id)) } as never),
  )

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
  it('renders image thumbnails from object URLs, never from a signed URL', async () => {
    serveContentByAssetId()

    render(<EvidenceGallery assets={[asset(1, 'scene.jpg')]} />)

    const image = await screen.findByAltText('scene.jpg')
    expect(image.getAttribute('src')).toBe(currentUrlFor('1'))
    expect(evidenceAssetsApi.getContent).toHaveBeenCalledWith(1, 'inline')
    expect(evidenceAssetsApi.getSignedUrl).not.toHaveBeenCalled()
  })

  it('revokes every object URL it created when it unmounts', async () => {
    serveContentByAssetId()

    const { unmount } = render(
      <EvidenceGallery assets={[asset(1, 'first.jpg'), asset(2, 'second.jpg')]} />,
    )

    await screen.findByAltText('first.jpg')
    await screen.findByAltText('second.jpg')
    expect(revoked).toEqual([])

    const live = [currentUrlFor('1'), currentUrlFor('2')]
    unmount()

    expect([...revoked].sort()).toEqual([...live].sort())
  })

  it('revokes the object URL of an asset that leaves the list, and keeps the survivor live', async () => {
    serveContentByAssetId()

    const first = asset(1, 'first.jpg')
    const second = asset(2, 'second.jpg')
    const { rerender } = render(<EvidenceGallery assets={[first, second]} />)

    await screen.findByAltText('first.jpg')
    await screen.findByAltText('second.jpg')
    const departing = currentUrlFor('2')

    rerender(<EvidenceGallery assets={[first]} />)

    await waitFor(() => {
      expect(revoked).toContain(departing)
    })
    // The survivor is refetched, so its URL is a new one — what must hold is that
    // whatever the thumbnail is showing has not been revoked underneath it.
    const image = await screen.findByAltText('first.jpg')
    expect(revoked).not.toContain(image.getAttribute('src'))
    expect(screen.queryByAltText('second.jpg')).toBeNull()
  })

  it('navigates previews with the next control and arrow keys', async () => {
    serveContentByAssetId()

    render(<EvidenceGallery assets={[asset(1, 'first.jpg'), asset(2, 'second.jpg')]} />)

    await screen.findByAltText('first.jpg')
    fireEvent.click(screen.getByRole('button', { name: 'Preview first.jpg' }))

    const dialog = await screen.findByRole('dialog')
    fireEvent.click(within(dialog).getByRole('button', { name: 'Next evidence' }))
    expect(within(dialog).getByAltText('second.jpg').getAttribute('src')).toBe(currentUrlFor('2'))

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
    serveContentByAssetId()

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
    serveContentByAssetId()

    render(<EvidenceGallery assets={[asset(9, 'report.pdf', 'application/pdf')]} />)

    fireEvent.click(screen.getByRole('button', { name: 'Preview report.pdf' }))
    const dialog = await screen.findByRole('dialog')

    await waitFor(() => {
      expect(within(dialog).getByTestId('document-preview-pdf')).not.toBeNull()
    })
    expect(within(dialog).getByTitle('Preview of report.pdf').getAttribute('src')).toBe(
      currentUrlFor('9'),
    )
    expect(within(dialog).queryByText(/cannot be previewed here/i)).toBeNull()
    expect(within(dialog).getByRole('button', { name: /download/i })).toBeInTheDocument()
    expect(evidenceAssetsApi.getContent).toHaveBeenCalledWith(9, 'inline')
  })

  it('previews video in the lightbox with download as a secondary CTA', async () => {
    serveContentByAssetId()

    render(<EvidenceGallery assets={[asset(3, 'clip.mp4', 'video/mp4')]} />)

    fireEvent.click(screen.getByRole('button', { name: 'Preview clip.mp4' }))
    const dialog = await screen.findByRole('dialog')

    await waitFor(() => {
      expect(within(dialog).getByTestId('document-preview-video')).not.toBeNull()
    })
    expect(within(dialog).queryByText(/cannot be previewed here/i)).toBeNull()
    expect(within(dialog).getByRole('button', { name: /download/i })).toBeInTheDocument()
  })

  it('downloads through a signed URL, which the byte proxy does not replace', async () => {
    serveContentByAssetId()
    vi.mocked(evidenceAssetsApi.getSignedUrl).mockResolvedValue({
      data: { signed_url: 'https://storage.test/scene.jpg?sig=abc' },
    } as never)
    const openSpy = vi.spyOn(window, 'open').mockImplementation(() => null)

    render(<EvidenceGallery assets={[asset(1, 'scene.jpg')]} />)

    await screen.findByAltText('scene.jpg')
    fireEvent.click(screen.getByRole('button', { name: 'Preview scene.jpg' }))
    const dialog = await screen.findByRole('dialog')
    fireEvent.click(within(dialog).getByRole('button', { name: /download/i }))

    await waitFor(() => {
      expect(evidenceAssetsApi.getSignedUrl).toHaveBeenCalledWith(1, undefined, 'attachment')
    })
    expect(openSpy).toHaveBeenCalledWith(
      'https://storage.test/scene.jpg?sig=abc',
      '_blank',
      'noopener,noreferrer',
    )
    openSpy.mockRestore()
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

  it('previews photo assets in the lightbox when MIME and filename are generic', async () => {
    serveContentByAssetId()
    const photo = {
      ...asset(10, 'scene.bin', 'application/octet-stream'),
      asset_type: 'photo',
    }

    render(<EvidenceGallery assets={[photo]} />)

    await screen.findByAltText('scene.bin')
    fireEvent.click(screen.getByRole('button', { name: 'Preview scene.bin' }))
    const dialog = await screen.findByRole('dialog')

    expect(within(dialog).getByTestId('document-preview-image')).toBeInTheDocument()
    expect(within(dialog).getByAltText('scene.bin').getAttribute('src')).toBe(currentUrlFor('10'))
    expect(within(dialog).queryByText(/cannot be previewed here/i)).toBeNull()
  })

  it('shows preview unavailable when the thumbnail image fails to load', async () => {
    serveContentByAssetId()

    render(<EvidenceGallery assets={[asset(1, 'broken.jpg')]} />)

    const image = await screen.findByAltText('broken.jpg')
    fireEvent.error(image)

    expect(await screen.findByText('Preview unavailable')).toBeInTheDocument()
    expect(screen.queryByAltText('broken.jpg')).toBeNull()
    expect(revoked).toContain(currentUrlFor('1'))
  })

  it('shows preview unavailable when the bytes cannot be fetched', async () => {
    vi.mocked(evidenceAssetsApi.getContent).mockRejectedValue(new Error('403'))

    render(<EvidenceGallery assets={[asset(1, 'denied.jpg')]} />)

    expect(await screen.findByText('Preview unavailable')).toBeInTheDocument()
    expect(URL.createObjectURL).not.toHaveBeenCalled()
  })
})
