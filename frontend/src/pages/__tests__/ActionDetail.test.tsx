import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import ActionDetail from '../ActionDetail'

const mockGetByKey = vi.fn()
const mockListOwnerNotes = vi.fn()
const mockListEvidence = vi.fn()
const mockGetDeliveryStatus = vi.fn()

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string) =>
      ({
        'actions.view_finding': 'View finding',
        'actions.view_incident': 'View incident',
        'actions.view_investigation': 'View investigation',
        'actions.email_unavailable.title': 'Email alerts unavailable',
        'actions.email_unavailable.body':
          'The assignee is saved, but email alerts are unavailable while outbound email is not configured.',
        'actions.finding_loop_cta.title': 'Close the finding loop',
        'actions.finding_loop_cta.body':
          'CAPA is complete. Close the linked finding on the Audits findings console to finish the inspection loop.',
        'actions.finding_loop_cta.action': 'Return to finding loop',
      } as Record<string, string>)[key] || fallback || key,
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

vi.mock('../../api/client', () => ({
  actionsApi: {
    getByKey: (...args: unknown[]) => mockGetByKey(...args),
    listOwnerNotes: (...args: unknown[]) => mockListOwnerNotes(...args),
    appendOwnerNote: vi.fn(),
    update: vi.fn(),
  },
  notificationsApi: {
    getDeliveryStatus: (...args: unknown[]) => mockGetDeliveryStatus(...args),
  },
  evidenceAssetsApi: {
    list: (...args: unknown[]) => mockListEvidence(...args),
    upload: vi.fn(),
    getSignedUrl: vi.fn(),
    delete: vi.fn(),
  },
  getApiErrorMessage: (error: unknown, fallback: string) =>
    error instanceof Error ? error.message : fallback,
}))

const auditFindingAction = {
  id: 9,
  reference_number: 'ACT-0009',
  title: 'Correct audit finding',
  description: 'Resolve the finding',
  action_type: 'corrective',
  priority: 'high',
  status: 'open',
  display_status: 'open',
  action_key: 'capa:9',
  source_type: 'audit_finding',
  source_id: 42,
  created_at: '2026-07-12T10:00:00Z',
}

const renderDetail = (key = 'capa%3A9') =>
  render(
    <MemoryRouter initialEntries={[`/actions/item?key=${key}`]}>
      <ActionDetail />
    </MemoryRouter>,
  )

describe('ActionDetail source deep-links', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetByKey.mockResolvedValue({ data: auditFindingAction })
    mockListOwnerNotes.mockResolvedValue({ data: { items: [] } })
    mockListEvidence.mockResolvedValue({ data: { items: [] } })
    mockGetDeliveryStatus.mockResolvedValue({ data: { email_configured: true } })
  })

  it('links audit-finding actions to their finding', async () => {
    renderDetail()

    expect(await screen.findByRole('heading', { name: 'Correct audit finding' })).toBeInTheDocument()
    const link = screen.getByTestId('action-source-deeplink')
    expect(link).toHaveAttribute('href', '/audits?view=findings&findingId=42')
    expect(link).toHaveTextContent('View finding')
  })

  it('does not link an audit finding with a non-positive source id', async () => {
    mockGetByKey.mockResolvedValue({ data: { ...auditFindingAction, source_id: 0 } })

    renderDetail()

    expect(await screen.findByRole('heading', { name: 'Correct audit finding' })).toBeInTheDocument()
    expect(screen.queryByTestId('action-source-deeplink')).not.toBeInTheDocument()
  })

  it('links incident-backed actions back to the incident', async () => {
    mockGetByKey.mockResolvedValue({
      data: {
        ...auditFindingAction,
        id: 3,
        title: 'Cordon north gate',
        action_key: 'incident_action:3',
        source_type: 'incident',
        source_id: 11,
      },
    })

    renderDetail('incident_action%3A3')

    expect(await screen.findByRole('heading', { name: 'Cordon north gate' })).toBeInTheDocument()
    const link = screen.getByTestId('action-source-deeplink')
    expect(link).toHaveAttribute('href', '/incidents/11')
    expect(link).toHaveTextContent('View incident')
  })

  it('links capa_incident actions back to the incident', async () => {
    mockGetByKey.mockResolvedValue({
      data: {
        ...auditFindingAction,
        id: 14,
        title: 'CAPA from incident',
        action_key: 'capa:14',
        source_type: 'capa_incident',
        source_id: 11,
      },
    })

    renderDetail('capa%3A14')

    expect(await screen.findByRole('heading', { name: 'CAPA from incident' })).toBeInTheDocument()
    expect(screen.getByTestId('action-source-deeplink')).toHaveAttribute('href', '/incidents/11')
  })

  it('links investigation-backed actions back to the investigation', async () => {
    mockGetByKey.mockResolvedValue({
      data: {
        ...auditFindingAction,
        id: 5,
        title: 'Install anti-slip matting',
        action_key: 'investigation_action:5',
        source_type: 'investigation',
        source_id: 21,
      },
    })

    renderDetail('investigation_action%3A5')

    expect(
      await screen.findByRole('heading', { name: 'Install anti-slip matting' }),
    ).toBeInTheDocument()
    const link = screen.getByTestId('action-source-deeplink')
    expect(link).toHaveAttribute('href', '/investigations/21')
    expect(link).toHaveTextContent('View investigation')
  })

  it('shows SMTP honesty beside CAPA assignment when email is unconfigured', async () => {
    mockGetDeliveryStatus.mockResolvedValue({ data: { email_configured: false } })

    renderDetail()

    expect(await screen.findByText('Email alerts unavailable')).toBeInTheDocument()
    expect(
      screen.getByText(
        'The assignee is saved, but email alerts are unavailable while outbound email is not configured.',
      ),
    ).toBeInTheDocument()
  })

  it('prompts return to finding loop when CAPA is completed', async () => {
    mockGetByKey.mockResolvedValue({
      data: { ...auditFindingAction, display_status: 'completed', status: 'closed' },
    })

    renderDetail()

    expect(await screen.findByTestId('action-detail-finding-loop-cta')).toBeInTheDocument()
    expect(screen.getByTestId('action-detail-return-to-finding')).toHaveAttribute(
      'href',
      '/audits?view=findings&findingId=42',
    )
  })
})
