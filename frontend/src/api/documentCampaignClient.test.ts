import { describe, expect, it, vi } from 'vitest'
import { createDocumentCampaignApi } from './documentCampaignClient'

function mockApi() {
  return {
    get: vi.fn(),
    post: vi.fn(),
  }
}

describe('createDocumentCampaignApi', () => {
  it('lists groups', () => {
    const api = mockApi()
    createDocumentCampaignApi(api as never).listGroups()
    expect(api.get).toHaveBeenCalledWith('/api/v1/document-campaigns/groups')
  })

  it('creates a group with member ids', () => {
    const api = mockApi()
    createDocumentCampaignApi(api as never).createGroup('HSEC team', [1, 2, 3])
    expect(api.post).toHaveBeenCalledWith('/api/v1/document-campaigns/groups', {
      name: 'HSEC team',
      member_user_ids: [1, 2, 3],
    })
  })

  it('lists campaigns for a document', () => {
    const api = mockApi()
    createDocumentCampaignApi(api as never).listCampaigns(42)
    expect(api.get).toHaveBeenCalledWith('/api/v1/document-campaigns/documents/42/campaigns')
  })

  it('creates and launches campaigns', () => {
    const api = mockApi()
    const client = createDocumentCampaignApi(api as never)
    const payload = {
      document_id: 42,
      due_within_days: 14,
      require_quiz: true,
      require_sign: true,
      reminder_hours: [24, 168],
      audience_type: 'all_users' as const,
    }
    client.createCampaign(payload)
    expect(api.post).toHaveBeenCalledWith('/api/v1/document-campaigns/campaigns', payload)

    client.launchCampaign(9)
    expect(api.post).toHaveBeenCalledWith('/api/v1/document-campaigns/campaigns/9/launch')
  })
})
