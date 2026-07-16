import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import PartnerWebhooks from '../PartnerWebhooks'

const mockListSubscriptions = vi.fn()
const mockListEvents = vi.fn()
const mockCreateSubscription = vi.fn()
const mockUpdateSubscription = vi.fn()
const mockDeleteSubscription = vi.fn()
const { translate } = vi.hoisted(() => ({
  translate: (_key: string, defaultValue: string) => defaultValue,
}))

class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}

vi.stubGlobal('ResizeObserver', ResizeObserverMock)

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: translate,
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

vi.mock('../../../services/api', () => ({
  partnerWebhooksApi: {
    listSubscriptions: (...args: unknown[]) => mockListSubscriptions(...args),
    listEvents: () => mockListEvents(),
    createSubscription: (...args: unknown[]) => mockCreateSubscription(...args),
    updateSubscription: (...args: unknown[]) => mockUpdateSubscription(...args),
    deleteSubscription: (...args: unknown[]) => mockDeleteSubscription(...args),
  },
}))

describe('PartnerWebhooks', () => {
  beforeEach(() => {
    mockListSubscriptions.mockReset().mockResolvedValue({
      items: [
        {
          id: 3,
          tenant_id: 1,
          name: 'Partner A',
          url: 'https://partner.example/hooks',
          events: ['inspection.completed'],
          is_active: true,
          created_at: '2026-07-16T10:00:00Z',
          updated_at: '2026-07-16T10:00:00Z',
        },
      ],
      total: 1,
    })
    mockListEvents.mockReset().mockResolvedValue({
      events: ['inspection.completed', 'finding.created'],
    })
    mockCreateSubscription.mockReset().mockResolvedValue({})
    mockUpdateSubscription.mockReset().mockResolvedValue({})
    mockDeleteSubscription.mockReset().mockResolvedValue(undefined)
  })

  it('loads tenant-scoped subscriptions and event catalog from the API client', async () => {
    render(<PartnerWebhooks />)

    expect(await screen.findByText('Partner A')).toBeInTheDocument()
    expect(mockListSubscriptions).toHaveBeenCalledWith(0, 25)
    expect(mockListEvents).toHaveBeenCalled()
  })

  it('creates a subscription through the authenticated API client', async () => {
    render(<PartnerWebhooks />)
    await screen.findByText('Partner A')

    fireEvent.click(screen.getByRole('button', { name: 'Add webhook' }))
    fireEvent.change(screen.getByLabelText('Endpoint URL'), {
      target: { value: 'https://new-partner.example/hooks' },
    })
    fireEvent.change(screen.getByLabelText('Signing secret'), {
      target: { value: 'a-long-enough-secret' },
    })
    fireEvent.click(screen.getByLabelText('finding.created'))
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))

    await waitFor(() =>
      expect(mockCreateSubscription).toHaveBeenCalledWith({
        name: null,
        url: 'https://new-partner.example/hooks',
        secret: 'a-long-enough-secret',
        events: ['finding.created'],
        is_active: true,
      }),
    )
  })
})
