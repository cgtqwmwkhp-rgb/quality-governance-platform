import { describe, expect, it, vi } from 'vitest'
import type { AxiosInstance } from 'axios'
import { competenceAssessmentExecutePath, createCompetenceStartApi } from '../competenceStartClient'

/**
 * The start call has one job beyond posting: making sure exactly one place
 * renders the refusal.
 *
 * The response interceptor toasts every classified error, and `CompetenceBoard`
 * toasts in its own catch so the start panel can stay open with what the
 * assessor typed. Both firing relies on a five-second identical-message dedupe
 * to hide the duplicate, which holds only while the two messages are worded
 * identically — a silent coupling that would break the first time either side
 * is reworded. Suppressing the interceptor toast makes the caller the owner.
 */
function fakeAxios() {
  const post = vi.fn().mockResolvedValue({ data: {} })
  return { post, instance: { post } as unknown as AxiosInstance }
}

describe('createCompetenceStartApi (CB-UI-3)', () => {
  it('posts to the competence assessments route with the payload it was given', async () => {
    const { post, instance } = fakeAxios()

    await createCompetenceStartApi(instance).start({
      engineer_id: 10,
      characteristic_key: 'COUNTERBALANCE_FLT',
      mode: 'field',
      plant_evidence: { serial: 'H2-9981' },
    })

    expect(post.mock.calls[0][0]).toBe('/api/v1/workforce/competence/assessments')
    expect(post.mock.calls[0][1]).toEqual({
      engineer_id: 10,
      characteristic_key: 'COUNTERBALANCE_FLT',
      mode: 'field',
      plant_evidence: { serial: 'H2-9981' },
    })
  })

  it('leaves the refusal to the caller rather than toasting it twice', async () => {
    const { post, instance } = fakeAxios()

    await createCompetenceStartApi(instance).start({
      engineer_id: 10,
      characteristic_key: 'COUNTERBALANCE_FLT',
      mode: 'field',
    })

    expect(post.mock.calls[0][2]).toMatchObject({ suppressErrorToast: true })
  })

  it('sends the assessor to the existing execution shell, inventing no second one', () => {
    // A second execute route would be a second place a demonstration could be
    // completed, and only one of them would write the CB-PR4 overlay.
    expect(competenceAssessmentExecutePath('run-abc')).toBe(
      '/workforce/assessments/run-abc/execute',
    )
  })
})
