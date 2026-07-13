/**
 * Real axe coverage for the Documents CUJ page, not a route stub.
 * Complements Documents.test.tsx and Playwright a11y-audit.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { MemoryRouter } from 'react-router-dom'
import Documents from '../Documents'
import { expectNoA11yViolations } from '../../test/axe-helper'

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    i18n: { language: 'en' },
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

vi.mock('../../utils/errorTracker', () => ({
  trackError: vi.fn(),
}))

const mockGet = vi.fn()
const mockPost = vi.fn()

vi.mock('../../api/client', () => ({
  __esModule: true,
  default: {
    get: (...args: unknown[]) => mockGet(...args),
    post: (...args: unknown[]) => mockPost(...args),
    defaults: { baseURL: 'https://api.example.test' },
  },
  getApiErrorMessage: (error: unknown) =>
    error instanceof Error ? error.message : 'Request failed',
}))

function Wrapper({ children }: { children: ReactNode }) {
  return <MemoryRouter initialEntries={['/documents']}>{children}</MemoryRouter>
}

describe('Documents page accessibility (real page)', () => {
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
      return Promise.resolve({ data: { results: [] } })
    })
  })

  it('renders the real Documents page without critical axe violations', async () => {
    const { container } = render(<Documents />, { wrapper: Wrapper })
    await waitFor(() => {
      expect(screen.getByText('Safety Policy')).toBeInTheDocument()
    })
    await expectNoA11yViolations(container)
  })
})
