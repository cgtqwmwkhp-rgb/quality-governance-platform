import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import type { ReactNode } from 'react'
import ComplianceAutomation from '../ComplianceAutomation'

const mockListRegulatoryUpdates = vi.fn()
const mockListCertificates = vi.fn()
const mockListRuns = vi.fn()
const mockGetComplianceScore = vi.fn()
const mockGetComplianceTrend = vi.fn()
const mockListImpacts = vi.fn()
const mockListRiddorSubmissions = vi.fn()
const mockGetStandardsDigests = vi.fn()

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string | Record<string, unknown>) => {
      if (typeof fallback === 'string') return fallback
      if (fallback && typeof fallback === 'object' && 'defaultValue' in fallback) {
        let text = String(fallback.defaultValue)
        for (const [k, v] of Object.entries(fallback)) {
          if (k === 'defaultValue') continue
          text = text.replace(`{{${k}}}`, String(v))
        }
        return text
      }
      return key
    },
    i18n: { language: 'en' },
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

vi.mock('../../contexts/ToastContext', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

vi.mock('../../api/client', () => ({
  getApiErrorMessage: (err: unknown) => (err instanceof Error ? err.message : 'error'),
  auditsApi: {
    listRuns: (...args: unknown[]) => mockListRuns(...args),
  },
  knowledgeBankApi: {
    listImpacts: (...args: unknown[]) => mockListImpacts(...args),
  },
  complianceAutomationApi: {
    listRegulatoryUpdates: (...args: unknown[]) => mockListRegulatoryUpdates(...args),
    listCertificates: (...args: unknown[]) => mockListCertificates(...args),
    getComplianceScore: (...args: unknown[]) => mockGetComplianceScore(...args),
    getComplianceTrend: (...args: unknown[]) => mockGetComplianceTrend(...args),
    listRiddorSubmissions: (...args: unknown[]) => mockListRiddorSubmissions(...args),
    getStandardsDigests: (...args: unknown[]) => mockGetStandardsDigests(...args),
  },
}))

function wrap(ui: ReactNode) {
  return <BrowserRouter>{ui}</BrowserRouter>
}

describe('ComplianceAutomation standards digests', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockListRegulatoryUpdates.mockResolvedValue({ data: { updates: [], total: 0, unreviewed: 0 } })
    mockListCertificates.mockResolvedValue({ data: { certificates: [], total: 0 } })
    mockListRuns.mockResolvedValue({ data: { items: [], total: 0 } })
    mockGetComplianceScore.mockResolvedValue({ data: { overall_score: 0, categories: {} } })
    mockGetComplianceTrend.mockResolvedValue({ data: { trend: [] } })
    mockListImpacts.mockResolvedValue({ data: [] })
    mockListRiddorSubmissions.mockResolvedValue({ data: { submissions: [], total: 0 } })
    mockGetStandardsDigests.mockResolvedValue({
      data: {
        freshness: {
          tracked_document_links: 0,
          current: 0,
          stale: 0,
          unpinned: 0,
          unknown: 0,
          stale_rate: null,
          stale_items: [],
          scan_truncated: false,
        },
        ingest_backlog: {
          total: 2,
          by_status: { proposed: 2 },
          by_link_method: { ai: 2 },
          operational_signals: 0,
          conformance_candidates: 2,
          oldest_age_days: 3,
          by_clause: [
            {
              clause_id: '9001-7.5',
              framework: '9001',
              clause_number: '7.5',
              count: 2,
              inbox_path: '/knowledge-exceptions?clause=9001-7.5',
            },
          ],
          auto_confirm_threshold: 0.98,
          auto_confirm_rule: 'Machine confirm requires confidence ≥ 0.98',
          inbox_path: '/knowledge-exceptions',
          scan_truncated: false,
        },
        nonconformity: {
          open_nc_total: 1,
          open_nc_without_clause_token: 0,
          clauses_with_open_nc: 1,
          unattributed_open_nc: 0,
          recurring_clauses: 0,
          clauses_with_nc_history: 1,
          recurrence_rate: null,
          by_clause: [
            {
              framework: '9001',
              clause_number: '8.7',
              clause_key: '9001-8.7',
              open_nc_count: 1,
              closed_nc_count: 0,
              recurrence: false,
              latest_nc_at: null,
              clause_path: '/compliance?code=9001&clause=8.7',
              findings_path: '/audits?view=findings',
            },
          ],
          scan_truncated: false,
        },
        cert_expiry: {
          tracked: 1,
          valid: 0,
          due_soon: 1,
          expired: 0,
          unknown: 0,
          by_scheme: [{ scheme: '9001', tracked: 1, due_soon: 1, expired: 0, kind: 'framework_certificate' }],
          soonest: [
            {
              shelf_key: 'register:1',
              name: 'ISO 9001 certificate',
              scheme: '9001',
              kind: 'framework_certificate',
              expiry_date: '2026-09-01',
              readiness_status: 'due_soon',
              days_remaining: 20,
              is_critical: true,
              detail_path: '/compliance-schedule?view=certificates',
            },
          ],
          shelf_path: '/compliance-schedule?view=certificates',
        },
        sor_note: 'Read-model only',
      },
    })
  })

  it('does not fetch digests until Standards health tab is opened', async () => {
    render(wrap(<ComplianceAutomation />))
    await waitFor(() => expect(screen.getByText('Monitoring')).toBeInTheDocument())
    expect(mockGetStandardsDigests).not.toHaveBeenCalled()

    fireEvent.click(screen.getByRole('button', { name: /Standards health/i }))
    await waitFor(() => expect(mockGetStandardsDigests).toHaveBeenCalledTimes(1))
    expect(screen.getByTestId('monitoring-digest-stale-tile')).toHaveTextContent('—')
    expect(screen.getByTestId('monitoring-digest-recurrence-tile')).toHaveTextContent('—')
    expect(screen.getByTestId('monitoring-digest-nc-table')).toHaveTextContent('8.7')
    expect(screen.getByRole('link', { name: /Matrix/i })).toHaveAttribute(
      'href',
      '/compliance?code=9001&clause=8.7',
    )
    expect(screen.getByRole('link', { name: /Open Exceptions inbox/i })).toHaveAttribute(
      'href',
      '/knowledge-exceptions',
    )
    expect(screen.getByRole('link', { name: /^Exceptions$/i })).toHaveAttribute(
      'href',
      '/knowledge-exceptions?clause=9001-7.5',
    )
    expect(screen.getByText(/Machine confirm requires confidence/i)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Open certificate shelf/i })).toHaveAttribute(
      'href',
      '/compliance-schedule?view=certificates',
    )
  })

  it('shows an alert when digests fail without inventing zeros', async () => {
    mockGetStandardsDigests.mockRejectedValueOnce(new Error('digest unavailable'))
    render(wrap(<ComplianceAutomation />))
    await waitFor(() => expect(screen.getByText('Monitoring')).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: /Standards health/i }))
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('digest unavailable'))
    expect(screen.queryByTestId('monitoring-digest-nc-table')).not.toBeInTheDocument()
  })
})
