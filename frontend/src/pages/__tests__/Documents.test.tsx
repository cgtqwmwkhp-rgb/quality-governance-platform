import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

const mockGet = vi.fn()
const mockPost = vi.fn()
const mockTrackError = vi.fn()

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

vi.mock('../../utils/errorTracker', () => ({
  trackError: (...args: unknown[]) => mockTrackError(...args),
}))

vi.mock('../../api/client', () => ({
  __esModule: true,
  default: {
    get: (...args: unknown[]) => mockGet(...args),
    post: (...args: unknown[]) => mockPost(...args),
    defaults: { baseURL: 'https://api.example.test' },
  },
  getApiErrorMessage: (error: unknown) => (error instanceof Error ? error.message : 'Request failed'),
}))

describe('Documents', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGet.mockImplementation((url: string) => {
      if (url.startsWith('/api/v1/documents/?')) {
        return Promise.resolve({
          data: {
            items: [
              {
                id: 11,
                reference_number: 'DOC-11',
                title: 'Safety Policy',
                file_name: 'policy.pdf',
                file_type: 'pdf',
                file_size: 2048,
                document_type: 'policy',
                sensitivity: 'internal',
                status: 'approved',
                version: '1.0',
                view_count: 0,
                download_count: 0,
                is_public: false,
                created_at: '2026-03-22T10:00:00Z',
              },
            ],
          },
        })
      }
      if (url === '/api/v1/documents/stats/overview') {
        return Promise.resolve({
          data: {
            total_documents: 1,
            indexed_documents: 0,
            total_chunks: 0,
            by_status: { approved: 1 },
            by_type: { policy: 1 },
          },
        })
      }
      if (url === '/api/v1/documents/11/signed-url') {
        return Promise.resolve({
          data: { signed_url: '/api/v1/evidence-assets/download?key=policy.pdf' },
        })
      }
      return Promise.resolve({ data: { results: [] } })
    })
  })

  it('loads documents and opens a signed document url from the detail modal', async () => {
    const openSpy = vi.spyOn(window, 'open').mockImplementation(() => null)
    const Documents = (await import('../Documents')).default

    render(<Documents />)

    fireEvent.click(await screen.findByText('Safety Policy'))
    fireEvent.click(screen.getByRole('button', { name: 'Open' }))

    await waitFor(() => {
      expect(mockGet).toHaveBeenCalledWith('/api/v1/documents/11/signed-url', {
        params: { download: false },
      })
      expect(openSpy).toHaveBeenCalledWith(
        'https://api.example.test/api/v1/evidence-assets/download?key=policy.pdf',
        '_blank',
        'noopener,noreferrer',
      )
    })
  })
})
