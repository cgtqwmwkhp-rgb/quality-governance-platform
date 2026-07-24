import { describe, expect, it, vi } from 'vitest'
import { createAuditChallengeApi } from './auditChallengeClient'

function mockApi() {
  return {
    get: vi.fn(),
    post: vi.fn(),
  }
}

describe('createAuditChallengeApi', () => {
  it('createSession posts sections/brief/chip to the challenge sessions endpoint', () => {
    const api = mockApi()
    const client = createAuditChallengeApi(api as never)
    client.createSession({ sections: [{ id: 's1' }], chip_id: 'field_assessor' })
    expect(api.post).toHaveBeenCalledWith('/api/v1/ai-templates/challenge/sessions', {
      sections: [{ id: 's1' }],
      chip_id: 'field_assessor',
    })
  })

  it('getSession polls the session by id', () => {
    const api = mockApi()
    createAuditChallengeApi(api as never).getSession(42)
    expect(api.get).toHaveBeenCalledWith('/api/v1/ai-templates/challenge/sessions/42')
  })

  it('sendMessage posts a follow-up chat turn', () => {
    const api = mockApi()
    createAuditChallengeApi(api as never).sendMessage(42, 'tighten scoring', 'rebalance_scoring')
    expect(api.post).toHaveBeenCalledWith('/api/v1/ai-templates/challenge/sessions/42/messages', {
      message: 'tighten scoring',
      chip_id: 'rebalance_scoring',
    })
  })

  it('decideProposal posts the accept/reject/edit verb and optional edited_after', () => {
    const api = mockApi()
    const client = createAuditChallengeApi(api as never)
    client.decideProposal(42, 7, 'accept')
    expect(api.post).toHaveBeenCalledWith(
      '/api/v1/ai-templates/challenge/sessions/42/proposals/7/decide',
      { decision: 'accept', edited_after: undefined },
    )

    client.decideProposal(42, 7, 'edit', { text: 'New text' })
    expect(api.post).toHaveBeenCalledWith(
      '/api/v1/ai-templates/challenge/sessions/42/proposals/7/decide',
      { decision: 'edit', edited_after: { text: 'New text' } },
    )
  })

  it('applySession posts to the apply endpoint with no body', () => {
    const api = mockApi()
    createAuditChallengeApi(api as never).applySession(42)
    expect(api.post).toHaveBeenCalledWith('/api/v1/ai-templates/challenge/sessions/42/apply')
  })
})
