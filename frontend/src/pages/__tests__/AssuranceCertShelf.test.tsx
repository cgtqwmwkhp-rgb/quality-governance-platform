import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import AssuranceCertShelf from '../AssuranceCertShelf'

const mockGetAssuranceCertShelf = vi.fn()

vi.mock('../../api/client', () => ({
  complianceAutomationApi: {
    getAssuranceCertShelf: (...args: unknown[]) => mockGetAssuranceCertShelf(...args),
  },
  getApiErrorMessage: (_error: unknown, fallback: string) => fallback,
}))

vi.mock('../../contexts/ToastContext', () => ({
  toast: {
    error: vi.fn(),
  },
}))

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (_key: string, fallback?: string) => fallback ?? _key,
    i18n: { language: 'en' },
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

describe('AssuranceCertShelf', () => {
  beforeEach(() => {
    mockGetAssuranceCertShelf.mockReset()
    mockGetAssuranceCertShelf.mockResolvedValue({
      data: {
        items: [
          {
            shelf_key: 'planet_mark:1',
            name: 'Planet Mark YE2025',
            scheme: 'planet_mark',
            source: 'planet_mark',
            issuing_body: 'Planet Mark',
            reference_number: 'PM-001',
            expiry_date: '2026-08-01T00:00:00',
            readiness_status: 'due_soon',
            is_critical: false,
            is_external_sor: true,
            detail_path: '/planet-mark',
            library_path: null,
            external_url: null,
            metadata: {},
          },
        ],
        total: 1,
        summary: {
          valid: 0,
          due_soon: 1,
          expired: 0,
          unknown: 0,
          by_scheme: { planet_mark: 1 },
        },
        due_soon_days: 30,
      },
    })
  })

  it('renders shelf summary and certificate row', async () => {
    render(
      <MemoryRouter>
        <AssuranceCertShelf />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByTestId('assurance-cert-shelf-page')).toBeInTheDocument()
    })

    expect(screen.getByText('Planet Mark YE2025')).toBeInTheDocument()
    expect(screen.getAllByText('Due soon').length).toBeGreaterThan(0)
    expect(screen.getByTestId('assurance-cert-detail-planet_mark:1')).toHaveAttribute('href', '/planet-mark')
  })

  it('shows empty state when shelf has no items', async () => {
    mockGetAssuranceCertShelf.mockResolvedValue({
      data: {
        items: [],
        total: 0,
        summary: { valid: 0, due_soon: 0, expired: 0, unknown: 0, by_scheme: {} },
        due_soon_days: 30,
      },
    })

    render(
      <MemoryRouter>
        <AssuranceCertShelf />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByTestId('assurance-cert-shelf-empty')).toBeInTheDocument()
    })
  })
})
