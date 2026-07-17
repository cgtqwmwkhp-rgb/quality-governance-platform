import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
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

const translations: Record<string, string> = {
  'compliance.automation.title': 'Monitoring',
  'compliance.automation.subtitle':
    'Regulatory watch, certificate expiry, compliance scoring, and RIDDOR readiness',
  'compliance.automation.empty.regulatory.title': 'No regulatory updates yet',
  'compliance.automation.empty.regulatory.description':
    'Regulatory feed items appear here when ingested. Empty means no pending updates — not fabricated alerts.',
  'compliance.automation.empty.certificates.title': 'No certificates tracked yet',
  'compliance.automation.empty.certificates.description':
    'Track training, equipment, and site certificates here once added. Empty means none on record — not sample data.',
  'compliance.automation.empty.audits.title': 'No upcoming audit runs',
  'compliance.automation.empty.audits.description':
    'Scheduled and in-progress audit runs from the Audits module appear here. Schedule new runs in Audits — empty means none queued, not demo data.',
  'compliance.automation.empty.score.breakdown.title': 'No live standard scores yet',
  'compliance.automation.empty.score.breakdown.description':
    'Scores come from evidence coverage in your standards library — not demo placeholders.',
  'compliance.automation.empty.score.gaps.description':
    'No automated gap list yet. Run gap analysis or link evidence to standards to populate this view.',
  'compliance.automation.certificates': 'Certificates',
  'compliance.automation.scheduled_audits': 'Scheduled Audits',
  'compliance.automation.compliance_score': 'Compliance Score',
  'compliance.automation.cert_expiry_tracking': 'Certificate Expiry Tracking',
  'compliance.automation.scheduled_inspections': 'Scheduled Audits & Inspections',
  'compliance.automation.audits.handoff_note':
    'Reads scheduled and in-progress runs from Audits — not the legacy compliance schedule feed.',
  'compliance.automation.open_audits': 'Open Audits',
  'compliance.automation.schedule_in_audits': 'Schedule in Audits',
  'compliance.automation.audits.open': 'Open',
  'compliance.automation.audits.continue': 'Continue',
  'compliance.automation.audits.due': 'Due',
  'compliance.automation.add_certificate': 'Add Certificate',
  'compliance.automation.score_breakdown': 'Score Breakdown by Standard',
  'compliance.automation.key_gaps': 'Key Gaps',
}

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, defaultValue?: string) => translations[key] ?? defaultValue ?? key,
    i18n: { language: 'en' },
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

vi.mock('../../contexts/ToastContext', () => ({
  toast: {
    error: vi.fn(),
    success: vi.fn(),
  },
}))

vi.mock('../../api/client', () => ({
  complianceAutomationApi: {
    listRegulatoryUpdates: (...args: unknown[]) => mockListRegulatoryUpdates(...args),
    listCertificates: (...args: unknown[]) => mockListCertificates(...args),
    getComplianceScore: (...args: unknown[]) => mockGetComplianceScore(...args),
    getComplianceTrend: (...args: unknown[]) => mockGetComplianceTrend(...args),
    listRiddorSubmissions: (...args: unknown[]) => mockListRiddorSubmissions(...args),
  },
  auditsApi: {
    listRuns: (...args: unknown[]) => mockListRuns(...args),
  },
  knowledgeBankApi: {
    listImpacts: (...args: unknown[]) => mockListImpacts(...args),
    runRegulatoryWatch: vi.fn(),
    createImpactAction: vi.fn(),
    resolveImpact: vi.fn(),
  },
  getApiErrorMessage: (err: unknown) =>
    err instanceof Error ? err.message : 'Something went wrong',
}))

function Wrapper({ children }: { children: ReactNode }) {
  return <BrowserRouter>{children}</BrowserRouter>
}

function mockEmptyLoadData() {
  mockListRegulatoryUpdates.mockResolvedValue({ data: { updates: [], total: 0, unreviewed: 0 } })
  mockListCertificates.mockResolvedValue({ data: { certificates: [], total: 0 } })
  mockListRuns.mockResolvedValue({ data: { items: [], total: 0 } })
  mockGetComplianceScore.mockResolvedValue({
    data: { overall_score: 0, categories: {}, key_gaps: [] },
  })
  mockGetComplianceTrend.mockResolvedValue({ data: { trend: [], period_months: 12 } })
  mockListImpacts.mockResolvedValue({ data: [] })
  mockListRiddorSubmissions.mockResolvedValue({ data: { submissions: [] } })
}

describe('ComplianceAutomation monitoring honesty', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockEmptyLoadData()
  })

  it('shows Monitoring page title from i18n', async () => {
    render(<ComplianceAutomation />, { wrapper: Wrapper })

    expect(await screen.findByRole('heading', { name: 'Monitoring' })).toBeInTheDocument()
    expect(
      screen.getByText(
        'Regulatory watch, certificate expiry, compliance scoring, and RIDDOR readiness',
      ),
    ).toBeInTheDocument()
  })

  it('shows honest regulatory empty state when API returns no updates', async () => {
    render(<ComplianceAutomation />, { wrapper: Wrapper })

    expect(await screen.findByTestId('monitoring-regulatory-empty')).toBeInTheDocument()
    expect(screen.getByText('No regulatory updates yet')).toBeInTheDocument()
    expect(screen.queryByText('ISO 9001')).not.toBeInTheDocument()
  })

  it('shows honest certificates empty state when API returns no certificates', async () => {
    render(<ComplianceAutomation />, { wrapper: Wrapper })
    await screen.findByRole('heading', { name: 'Monitoring' })

    fireEvent.click(screen.getByRole('button', { name: /Certificates/i }))

    await waitFor(() => {
      expect(screen.getByTestId('monitoring-certificates-empty')).toBeInTheDocument()
    })
    expect(screen.getByText('No certificates tracked yet')).toBeInTheDocument()
    expect(screen.queryByText('Critical')).not.toBeInTheDocument()
  })

  it('shows honest scheduled audits empty state with Audits handoff when no runs', async () => {
    render(<ComplianceAutomation />, { wrapper: Wrapper })
    await screen.findByRole('heading', { name: 'Monitoring' })

    fireEvent.click(screen.getByRole('button', { name: /Scheduled Audits/i }))

    await waitFor(() => {
      expect(screen.getByTestId('monitoring-audits-empty')).toBeInTheDocument()
    })
    expect(screen.getByText('No upcoming audit runs')).toBeInTheDocument()
    expect(
      screen.getByText(/Scheduled and in-progress audit runs from the Audits module/i),
    ).toBeInTheDocument()
    expect(screen.getByTestId('monitoring-audits-empty-cta')).toHaveAttribute(
      'href',
      '/audits?view=kanban',
    )
    expect(mockListRuns).toHaveBeenCalledWith(1, 100)
  })

  it('renders authoritative audit runs with deep links to Audits workspace', async () => {
    mockListRuns.mockResolvedValue({
      data: {
        items: [
          {
            id: 42,
            reference_number: 'AUD-042',
            template_id: 1,
            template_version: 1,
            title: 'ISO surveillance',
            status: 'scheduled',
            scheduled_date: '2026-08-15',
            created_at: '2026-01-01T00:00:00Z',
          },
          {
            id: 7,
            reference_number: 'AUD-007',
            template_id: 2,
            template_version: 1,
            title: 'Site inspection',
            status: 'in_progress',
            scheduled_date: '2026-07-10',
            created_at: '2026-01-01T00:00:00Z',
          },
        ],
        total: 2,
      },
    })

    render(<ComplianceAutomation />, { wrapper: Wrapper })
    await screen.findByRole('heading', { name: 'Monitoring' })

    fireEvent.click(screen.getByRole('button', { name: /Scheduled Audits/i }))

    await waitFor(() => {
      expect(screen.getByText('ISO surveillance')).toBeInTheDocument()
    })
    expect(screen.getByText('Site inspection')).toBeInTheDocument()
    expect(screen.getByTestId('monitoring-audit-run-42')).toHaveAttribute(
      'href',
      '/audits/42/execute',
    )
    expect(screen.getByTestId('monitoring-audit-run-7')).toHaveAttribute('href', '/audits/7/execute')
    expect(screen.getByTestId('monitoring-audits-schedule-link')).toHaveAttribute(
      'href',
      '/audits?view=kanban',
    )
  })

  it('shows honest score empty states without demo ISO placeholders', async () => {
    render(<ComplianceAutomation />, { wrapper: Wrapper })
    await screen.findByRole('heading', { name: 'Monitoring' })

    fireEvent.click(screen.getByRole('button', { name: /Compliance Score/i }))

    await waitFor(() => {
      expect(screen.getByTestId('monitoring-score-breakdown-empty')).toBeInTheDocument()
    })
    expect(screen.getByText('No live standard scores yet')).toBeInTheDocument()
    expect(screen.getByTestId('monitoring-score-gaps-empty')).toBeInTheDocument()
    expect(screen.queryByText('92%')).not.toBeInTheDocument()
    expect(screen.queryByText('First aid training gaps')).not.toBeInTheDocument()
  })

  it('renders live score breakdown from API categories', async () => {
    mockGetComplianceScore.mockResolvedValue({
      data: {
        overall_score: 72,
        categories: { ISO9001: 72 },
        key_gaps: ['Missing clause 8.2 evidence'],
      },
    })
    mockGetComplianceTrend.mockResolvedValue({
      data: { trend: [{ score: 70 }, { score: 72 }], period_months: 12 },
    })

    render(<ComplianceAutomation />, { wrapper: Wrapper })
    await screen.findByRole('heading', { name: 'Monitoring' })

    fireEvent.click(screen.getByRole('button', { name: /Compliance Score/i }))

    await waitFor(() => {
      expect(screen.getByText('ISO 9001')).toBeInTheDocument()
    })
    const scoringTab = screen.getByTestId('monitoring-scoring-tab')
    expect(within(scoringTab).getByText('72%')).toBeInTheDocument()
    expect(screen.getByText('Missing clause 8.2 evidence')).toBeInTheDocument()
    expect(screen.queryByTestId('monitoring-score-breakdown-empty')).not.toBeInTheDocument()
  })
})
