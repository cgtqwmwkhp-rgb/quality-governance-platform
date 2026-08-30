import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { evidenceAssetsApi } from '../../api/client'
import { EvidenceGallery } from '../EvidenceGallery'

vi.mock('../../api/client', () => ({
  evidenceAssetsApi: {
    getSignedUrl: vi.fn(),
    upload: vi.fn(),
  },
}))

describe('EvidenceGallery upload', () => {
  beforeEach(() => {
    vi.mocked(evidenceAssetsApi.upload).mockReset()
  })

  it('stays read-only by default even when a source is supplied', () => {
    render(<EvidenceGallery assets={[]} uploadSourceModule="incident" uploadSourceId={1} />)
    expect(screen.queryByText('Upload evidence')).not.toBeInTheDocument()
  })

  it('does not render the upload control without a resolvable source', () => {
    render(<EvidenceGallery assets={[]} enableUpload />)
    expect(screen.queryByText('Upload evidence')).not.toBeInTheDocument()
  })

  it('uploads a selected file and notifies the caller to refresh', async () => {
    vi.mocked(evidenceAssetsApi.upload).mockResolvedValue({ data: { id: 44 } } as never)
    const onUploadComplete = vi.fn()

    render(
      <EvidenceGallery
        assets={[]}
        enableUpload
        uploadSourceModule="incident"
        uploadSourceId={7}
        onUploadComplete={onUploadComplete}
      />,
    )

    const input = screen.getByLabelText('Upload evidence')
    const file = new File(['content'], 'scene.jpg', { type: 'image/jpeg' })
    fireEvent.change(input, { target: { files: [file] } })

    await waitFor(() =>
      expect(evidenceAssetsApi.upload).toHaveBeenCalledWith(file, {
        source_module: 'incident',
        source_id: 7,
        title: 'scene.jpg',
        visibility: 'internal_customer',
      }),
    )
    await waitFor(() =>
      expect(onUploadComplete).toHaveBeenCalledWith({ uploadedAssetIds: [44] }),
    )
  })

  it('rejects unsupported file types without calling the upload API', async () => {
    render(
      <EvidenceGallery
        assets={[]}
        enableUpload
        uploadSourceModule="incident"
        uploadSourceId={7}
      />,
    )

    const input = screen.getByLabelText('Upload evidence')
    const file = new File(['content'], 'malware.exe', { type: 'application/x-msdownload' })
    fireEvent.change(input, { target: { files: [file] } })

    await waitFor(() =>
      expect(screen.getByText(/not a supported file type/i)).toBeInTheDocument(),
    )
    expect(evidenceAssetsApi.upload).not.toHaveBeenCalled()
  })

  it('rejects a 0-byte file without calling the upload API', async () => {
    render(
      <EvidenceGallery
        assets={[]}
        enableUpload
        uploadSourceModule="incident"
        uploadSourceId={7}
      />,
    )

    const input = screen.getByLabelText('Upload evidence')
    const file = new File([], 'blank.jpg', { type: 'image/jpeg' })
    fireEvent.change(input, { target: { files: [file] } })

    await waitFor(() =>
      expect(screen.getByText(/empty \(0 bytes\)/i)).toBeInTheDocument(),
    )
    expect(evidenceAssetsApi.upload).not.toHaveBeenCalled()
  })

  it('accepts .eml evidence when the browser leaves MIME empty', async () => {
    vi.mocked(evidenceAssetsApi.upload).mockResolvedValue({ data: { id: 51 } } as never)
    const onUploadComplete = vi.fn()

    render(
      <EvidenceGallery
        assets={[]}
        enableUpload
        uploadSourceModule="incident"
        uploadSourceId={7}
        onUploadComplete={onUploadComplete}
      />,
    )

    const input = screen.getByLabelText('Upload evidence')
    const file = new File(['From: a@b.com'], 'witness.eml', { type: '' })
    fireEvent.change(input, { target: { files: [file] } })

    await waitFor(() =>
      expect(evidenceAssetsApi.upload).toHaveBeenCalledWith(file, {
        source_module: 'incident',
        source_id: 7,
        title: 'witness.eml',
        visibility: 'internal_customer',
      }),
    )
    expect(screen.getByText(/email \(\.eml, \.msg\)/i)).toBeInTheDocument()
  })
})
