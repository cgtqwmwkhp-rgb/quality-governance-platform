import { describe, expect, it, vi, beforeEach } from 'vitest'
import { standardsHrefForIsoRef, suggestStandardLinks } from '../builderMapAssistApi'

vi.mock('../../api/client', () => ({
  default: {
    post: vi.fn(),
    get: vi.fn(),
  },
}))

import api from '../../api/client'

describe('standardsHrefForIsoRef', () => {
  it('maps 9001-7.2 to Standards deep-link', () => {
    expect(standardsHrefForIsoRef('9001-7.2')).toBe('/standards?code=ISO9001&clause=7.2')
  })

  it('maps bare clause to search param', () => {
    expect(standardsHrefForIsoRef('7.2')).toBe('/standards?clause=7.2')
  })
})

describe('suggestStandardLinks', () => {
  beforeEach(() => {
    vi.mocked(api.post).mockReset()
  })

  it('posts via shared axios api client (not SWA-relative fetch)', async () => {
    vi.mocked(api.post).mockResolvedValue({
      data: {
        suggestions: [
          {
            id: 'sug_1',
            questionId: 'q1',
            scheme: 'ISO',
            refId: '9001-7.2',
            label: 'Competence',
            confidence: 0.9,
          },
        ],
        library_version: 'builder-map-v1',
      },
    })

    const rows = await suggestStandardLinks([
      { question_id: 'q1', question_text: 'competence records' },
    ])

    expect(api.post).toHaveBeenCalledWith('/api/v1/ai-templates/suggest-standard-links', {
      questions: [{ question_id: 'q1', question_text: 'competence records' }],
      schemes: ['ISO', 'Planet Mark', 'UVDB'],
    })
    expect(rows[0].refId).toBe('9001-7.2')
    expect(rows[0].status).toBe('suggested')
  })

  it('surfaces honest 405 guidance when edge returns Method Not Allowed', async () => {
    vi.mocked(api.post).mockRejectedValue({
      isAxiosError: true,
      response: { status: 405, data: {} },
      message: 'Request failed with status code 405',
    })
    await expect(
      suggestStandardLinks([{ question_id: 'q1', question_text: 'x' }]),
    ).rejects.toThrow(/App Service API base/i)
  })
})
