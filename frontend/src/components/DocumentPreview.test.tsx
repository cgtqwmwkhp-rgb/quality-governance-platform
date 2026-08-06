import { render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  canPreviewInApp,
  DocumentPreview,
  isTier1Preview,
  resolvePreviewKind,
} from './DocumentPreview'

describe('resolvePreviewKind', () => {
  it('routes Tier 1 mime types and extensions', () => {
    expect(resolvePreviewKind('image/jpeg', 'scene.jpg')).toBe('image')
    expect(resolvePreviewKind('application/pdf', 'report.pdf')).toBe('pdf')
    expect(resolvePreviewKind('application/octet-stream', 'report.pdf')).toBe('pdf')
    expect(resolvePreviewKind('video/mp4', 'clip.mp4')).toBe('video')
    expect(resolvePreviewKind('audio/mpeg', 'note.mp3')).toBe('audio')
  })

  it('routes Tier 2 text and csv', () => {
    expect(resolvePreviewKind('text/plain', 'notes.txt')).toBe('text')
    expect(resolvePreviewKind('text/csv', 'export.csv')).toBe('text')
    expect(resolvePreviewKind('application/octet-stream', 'export.csv')).toBe('text')
  })

  it('marks unknown types unsupported', () => {
    expect(resolvePreviewKind('application/vnd.ms-excel', 'sheet.xls')).toBe('unsupported')
    expect(resolvePreviewKind('application/zip', 'bundle.zip')).toBe('unsupported')
  })

  it('exposes Tier 1 helpers', () => {
    expect(isTier1Preview('pdf')).toBe(true)
    expect(isTier1Preview('text')).toBe(false)
    expect(canPreviewInApp('application/pdf')).toBe(true)
    expect(canPreviewInApp('application/zip')).toBe(false)
  })
})

describe('DocumentPreview', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('renders an image when given an image mime and url', () => {
    render(
      <DocumentPreview
        url="https://example.test/photo.jpg"
        contentType="image/jpeg"
        fileName="photo.jpg"
        alt="photo.jpg"
      />,
    )
    expect(screen.getByTestId('document-preview-image')).toBeInTheDocument()
    expect(screen.getByAltText('photo.jpg').getAttribute('src')).toBe(
      'https://example.test/photo.jpg',
    )
  })

  it('renders a PDF iframe for application/pdf', () => {
    render(
      <DocumentPreview
        url="https://example.test/doc.pdf"
        contentType="application/pdf"
        fileName="doc.pdf"
      />,
    )
    const frame = screen.getByTitle('Preview of doc.pdf')
    expect(frame.tagName).toBe('IFRAME')
    expect(frame.getAttribute('src')).toBe('https://example.test/doc.pdf')
    expect(screen.getByTestId('document-preview-pdf')).toBeInTheDocument()
  })

  it('renders video and audio controls for media mimes', () => {
    const { rerender } = render(
      <DocumentPreview
        url="https://example.test/clip.mp4"
        contentType="video/mp4"
        fileName="clip.mp4"
      />,
    )
    expect(screen.getByTestId('document-preview-video').querySelector('video')).not.toBeNull()

    rerender(
      <DocumentPreview
        url="https://example.test/note.mp3"
        contentType="audio/mpeg"
        fileName="note.mp3"
      />,
    )
    expect(screen.getByTestId('document-preview-audio').querySelector('audio')).not.toBeNull()
  })

  it('fetches and shows text/csv content', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        text: () => Promise.resolve('a,b\n1,2'),
      }),
    )

    render(
      <DocumentPreview
        url="https://example.test/data.csv"
        contentType="text/csv"
        fileName="data.csv"
      />,
    )

    await waitFor(() => {
      expect(screen.getByText(/a,b/)).toBeInTheDocument()
    })
    expect(screen.getByTestId('document-preview-text')).toBeInTheDocument()
  })

  it('shows loading and unavailable states from the host', () => {
    const { rerender } = render(
      <DocumentPreview url={null} contentType="application/pdf" loading />,
    )
    expect(screen.getByTestId('document-preview-loading')).toBeInTheDocument()

    rerender(<DocumentPreview url={null} contentType="application/pdf" loadFailed />)
    expect(screen.getByTestId('document-preview-failed')).toBeInTheDocument()
    expect(screen.getByText(/Preview unavailable/)).toBeInTheDocument()
  })

  it('keeps download-only copy only for unsupported types', () => {
    render(
      <DocumentPreview
        url="https://example.test/bundle.zip"
        contentType="application/zip"
        fileName="bundle.zip"
      />,
    )
    expect(screen.getByTestId('document-preview-unsupported')).toBeInTheDocument()
    expect(screen.getByText(/cannot be previewed here/)).toBeInTheDocument()
  })
})
