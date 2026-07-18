import { describe, expect, it, vi } from 'vitest'
import { createDocumentCampaignApi } from './documentCampaignClient'

function mockApi() {
  return {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
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

  it('loads and saves reminder defaults', () => {
    const api = mockApi()
    const client = createDocumentCampaignApi(api as never)
    client.getReminderDefaults()
    expect(api.get).toHaveBeenCalledWith('/api/v1/document-campaigns/reminder-defaults')

    client.setReminderDefaults([24, 168])
    expect(api.put).toHaveBeenCalledWith('/api/v1/document-campaigns/reminder-defaults', {
      reminder_hours: [24, 168],
    })
  })

  it('lists compliance and question inbox', () => {
    const api = mockApi()
    const client = createDocumentCampaignApi(api as never)
    client.listCompliance()
    expect(api.get).toHaveBeenCalledWith('/api/v1/document-campaigns/compliance')

    client.listQuestionInbox()
    expect(api.get).toHaveBeenCalledWith('/api/v1/document-campaigns/question-inbox')
  })

  it('handles evidence export and question actions', async () => {
    const api = mockApi()
    api.get.mockResolvedValue({ data: { campaign_id: 3 } })
    const appendChild = vi.spyOn(document.body, 'appendChild').mockImplementation(() => document.body)
    const removeChild = vi.spyOn(document.body, 'removeChild').mockImplementation(() => document.body)
    const click = vi.fn()
    vi.spyOn(document, 'createElement').mockImplementation(() => ({ click } as HTMLAnchorElement))

    const client = createDocumentCampaignApi(api as never)
    await client.downloadEvidencePack(3)
    expect(api.get).toHaveBeenCalledWith('/api/v1/document-campaigns/campaigns/3/evidence-pack', {
      responseType: 'json',
    })
    expect(click).toHaveBeenCalled()

    client.askAssignmentQuestion(5, { title: 'Clarification', body: 'What does section 2 mean?' })
    expect(api.post).toHaveBeenCalledWith('/api/v1/document-campaigns/assignments/5/questions', {
      title: 'Clarification',
      body: 'What does section 2 mean?',
    })

    client.replyQuestion(7, { body: 'See page 4.' })
    expect(api.post).toHaveBeenCalledWith('/api/v1/document-campaigns/questions/7/reply', {
      body: 'See page 4.',
    })

    client.resolveQuestion(7)
    expect(api.post).toHaveBeenCalledWith('/api/v1/document-campaigns/questions/7/resolve')

    appendChild.mockRestore()
    removeChild.mockRestore()
  })
})
