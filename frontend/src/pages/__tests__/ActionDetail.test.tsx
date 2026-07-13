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
    t: (key: string) =>
      ({
        'actions.view_finding': 'View finding',
        'actions.email_unavailable.title': 'Email alerts unavailable',
        'actions.email_unavailable.body':
          'The assignee is saved, but email alerts are unavailable while outbound email is not configured.',
      } as Record<string, string>)[key] || key,
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

const renderDetail = () =>
  render(
    <MemoryRouter initialEntries={['/actions/item?key=capa%3A9']}>
      <ActionDetail />
    </MemoryRouter>,
  )

describe('ActionDetail finding deep-link', () => {
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
    expect(screen.getByRole('link', { name: 'View finding' })).toHaveAttribute(
      'href',
      '/audits?view=findings&findingId=42',
    )
  })

  it('does not link an audit finding with a non-positive source id', async () => {
    mockGetByKey.mockResolvedValue({ data: { ...auditFindingAction, source_id: 0 } })

    renderDetail()

    expect(await screen.findByRole('heading', { name: 'Correct audit finding' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'View finding' })).not.toBeInTheDocument()
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
})
