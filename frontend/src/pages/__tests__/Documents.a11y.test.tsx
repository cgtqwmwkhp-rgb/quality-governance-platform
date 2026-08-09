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
    t: (key: string, options?: Record<string, unknown>) => {
      if (key === 'documents.table.open_aria' && options) {
        return `Open ${options.ref} — ${options.title}`
      }
      if (key === 'documents.table.caption') {
        return 'Master Document Register'
      }
      return key
    },
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
  documentCampaignApi: {
    listCompliance: vi.fn().mockResolvedValue({ data: { items: [], total: 0 } }),
  },
  documentGraphApi: {
    createEdge: vi.fn(),
  },
  getApiErrorMessage: (error: unknown) =>
    error instanceof Error ? error.message : 'Request failed',
}))

vi.mock('../../hooks/useFeatureFlag', () => ({
  useFeatureFlag: () => false,
}))

vi.mock('../../contexts/ToastContext', () => ({
  toast: { error: vi.fn(), warning: vi.fn(), success: vi.fn(), info: vi.fn() },
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

  it('keeps greyscale status and unique open link names under pathological titles (L-08)', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url.startsWith('/api/v1/documents/?')) {
        return Promise.resolve({
          data: {
            items: [
              {
                id: 11,
                reference_number: 'DOC-11',
                pel_doc_ref: 'PEL-HSEQ-0001',
                title: `${'Very long pathological title '.repeat(20)} end`,
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
                created_by_name: `${'UploaderName'.repeat(30)}`,
                href: '/documents/11',
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

    render(<Documents />, { wrapper: Wrapper })
    await waitFor(() => {
      expect(screen.getByTestId('documents-register-table')).toBeInTheDocument()
    })
    const status = screen.getByTestId('documents-register-status')
    expect(status).toHaveAttribute('data-status', 'approved')
    expect(status.className).not.toMatch(/success|destructive|purple|emerald/)
    expect(
      screen.getByRole('link', { name: /Open PEL-HSEQ-0001/i }),
    ).toBeInTheDocument()
    expect(screen.getAllByRole('columnheader').length).toBeGreaterThanOrEqual(8)
  })
})
