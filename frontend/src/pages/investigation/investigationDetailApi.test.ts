import { beforeEach, describe, expect, it, vi } from 'vitest'

const get = vi.fn()
const put = vi.fn()

vi.mock('../../api/client', () => ({
  default: { get, put },
}))

describe('investigationDetailApi RCA (INV-C10)', () => {
  beforeEach(() => {
    get.mockReset()
    put.mockReset()
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
})
