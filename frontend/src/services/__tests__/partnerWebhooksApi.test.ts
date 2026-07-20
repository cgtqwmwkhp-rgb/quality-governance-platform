import { beforeEach, describe, expect, it, vi } from 'vitest'
import { partnerWebhooksApi } from '../api'

const mockFetch = vi.fn()

beforeEach(() => {
  mockFetch.mockReset()
  mockFetch.mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => ({}),
  })
  vi.stubGlobal('fetch', mockFetch)
})

describe('partnerWebhooksApi', () => {
  it('uses /api/v1 partner-webhooks paths (OpenAPI contract)', async () => {
    await partnerWebhooksApi.listEvents()
    await partnerWebhooksApi.listSubscriptions(10, 25)
    await partnerWebhooksApi.createSubscription({
      url: 'https://partner.example/hooks',
      secret: 'a-long-enough-secret',
      events: ['inspection.completed'],
      is_active: true,
    })
    await partnerWebhooksApi.updateSubscription(7, { url: 'https://partner.example/hooks', events: [], is_active: false })
    await partnerWebhooksApi.deleteSubscription(7)

    const urls = mockFetch.mock.calls.map((call) => String(call[0]))
    expect(urls[0]).toContain('/api/v1/partner-webhooks/events')
    expect(urls[1]).toContain('/api/v1/partner-webhooks/subscriptions?skip=10&limit=25')
    expect(urls[2]).toContain('/api/v1/partner-webhooks/subscriptions')
    expect(urls[3]).toContain('/api/v1/partner-webhooks/subscriptions/7')
    expect(urls[4]).toContain('/api/v1/partner-webhooks/subscriptions/7')
    expect(urls.some((url) => url.includes('/partner-webhooks/') && !url.includes('/api/v1/'))).toBe(false)
  })
})
