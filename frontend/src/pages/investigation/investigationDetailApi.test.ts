import { beforeEach, describe, expect, it, vi } from 'vitest'

const get = vi.fn()
const put = vi.fn()
const post = vi.fn()

vi.mock('../../api/client', () => ({
  default: { get, put, post },
}))

describe('investigationDetailApi RCA (INV-C10 / INV-C11)', () => {
  beforeEach(() => {
    get.mockReset()
    put.mockReset()
    post.mockReset()
  })

  it('getRca and saveRca hit the investigation-scoped analyses path', async () => {
    const { getRca, saveRca } = await import('./investigationDetailApi')
    const body = {
      problem_statement: 'Guard removed',
      whys: [{ level: 1, answer: 'Interlock bypassed', evidence: 'Photo 3' }],
      root_cause: 'No banksman',
      contributing_factors: '',
    }
    getRca(4)
    saveRca(4, body)
    expect(get).toHaveBeenCalledWith('/api/v1/investigations/4/rca')
    expect(put).toHaveBeenCalledWith('/api/v1/investigations/4/rca', body)
  })

  it('createCapaFromWhy posts to the investigation-scoped rca/capa path', async () => {
    const { createCapaFromWhy } = await import('./investigationDetailApi')
    createCapaFromWhy(4, { why_level: 2, five_whys_id: 11 })
    expect(post).toHaveBeenCalledWith('/api/v1/investigations/4/rca/capa', {
      why_level: 2,
      five_whys_id: 11,
    })
  })
})
