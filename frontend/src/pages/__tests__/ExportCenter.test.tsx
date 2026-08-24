import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import ExportCenter from '../ExportCenter'

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string | Record<string, unknown>, options?: Record<string, unknown>) => {
      if (typeof fallback === 'string') {
        if (options && 'count' in options) {
          return fallback.replace('{{count}}', String(options.count))
        }
        return fallback
      }
      if (fallback && typeof fallback === 'object' && 'count' in fallback) {
        return `${fallback.count} records`
      }
      return key
    },
    i18n: { language: 'en' },
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

vi.mock('../../config/apiBase', () => ({
  API_BASE_URL: 'http://api.test',
}))

vi.mock('../../utils/auth', () => ({
  getPlatformToken: () => 'test-token',
}))

vi.mock('../../contexts/ToastContext', () => ({
  toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
}))

const catalog = {
  modules: [
    {
      id: 'incidents',
      name: 'Incidents',
      description: 'Tenant incident register (CSV sync)',
      record_count: 12,
      formats: ['csv'],
      sync_available: true,
    },
    {
      id: 'risks',
      name: 'Risks',
      description: 'Operational risk register (CSV sync)',
      record_count: 0,
      formats: ['csv'],
      sync_available: true,
    },
  ],
  capabilities: {
    sync_csv: true,
    job_history: false,
    scheduled_templates: false,
    max_sync_rows: 10000,
  },
}

describe('ExportCenter', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('loads live catalog and offers sync CSV download (PX-160)', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.endsWith('/api/v1/exports/catalog')) {
        return {
          ok: true,
          json: async () => catalog,
        }
      }
      if (url.endsWith('/api/v1/exports') && init?.method === 'POST') {
        return {
          ok: true,
          blob: async () => new Blob(['id,title\n1,Spill\n'], { type: 'text/csv' }),
          headers: {
            get: (name: string) => {
              if (name === 'Content-Disposition') return 'attachment; filename="incidents_export.csv"'
              if (name === 'X-Export-Truncated') return 'false'
              return null
            },
          },
        }
      }
      throw new Error(`unexpected fetch ${url}`)
    })
    vi.stubGlobal('fetch', fetchMock)

    const createObjectURL = vi.fn(() => 'blob:export')
    const revokeObjectURL = vi.fn()
    vi.stubGlobal('URL', { createObjectURL, revokeObjectURL })
    const anchorClick = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})

    render(
      <MemoryRouter>
        <ExportCenter />
      </MemoryRouter>,
    )

    expect(await screen.findByTestId('export-center-catalog')).toBeInTheDocument()
    expect(screen.getByTestId('export-center-deferred-capabilities')).toBeInTheDocument()
    expect(screen.getByText(/job history and scheduled templates/i)).toBeInTheDocument()
    expect(screen.getByTestId('export-count-incidents')).toHaveTextContent('12 records')
    // No fabricated demo history from the pre-honesty UI.
    expect(screen.queryByText('Monthly Incident Report')).not.toBeInTheDocument()
    expect(screen.queryByText(/847 records/)).not.toBeInTheDocument()

    await user.click(screen.getByTestId('export-incidents-btn'))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        'http://api.test/api/v1/exports',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ module: 'incidents', format: 'csv' }),
        }),
      )
    })
    expect(createObjectURL).toHaveBeenCalled()
    expect(anchorClick).toHaveBeenCalled()
  })

  it('shows error state when catalog API fails', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({
        ok: false,
        status: 500,
        json: async () => ({ detail: 'catalog boom' }),
      })),
    )

    render(
      <MemoryRouter>
        <ExportCenter />
      </MemoryRouter>,
    )

    expect(await screen.findByTestId('export-center-error')).toBeInTheDocument()
    expect(screen.getByText('catalog boom')).toBeInTheDocument()
    expect(screen.queryByTestId('export-center-unavailable')).not.toBeInTheDocument()
  })
})
