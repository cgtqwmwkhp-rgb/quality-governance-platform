import { describe, expect, it } from 'vitest'
import { serviceWorkerShouldHandleFetch } from '../swFetchPolicy'

const SWA = 'https://purple-water-03205fa03.6.azurestaticapps.net'

describe('serviceWorkerShouldHandleFetch', () => {
  it('handles same-origin API and static GETs', () => {
    expect(serviceWorkerShouldHandleFetch(`${SWA}/api/v1/healthz`, SWA)).toBe(true)
    expect(serviceWorkerShouldHandleFetch(`${SWA}/assets/index.js`, SWA)).toBe(true)
  })

  it('continues to handle cross-origin Azure API GETs', () => {
    expect(
      serviceWorkerShouldHandleFetch(
        'https://app-qgp-prod.azurewebsites.net/api/v1/assessments',
        SWA,
      ),
    ).toBe(true)
    expect(
      serviceWorkerShouldHandleFetch(
        'http://qgp-staging-plantexpand.azurewebsites.net/api/v1/healthz',
        SWA,
      ),
    ).toBe(true)
    expect(
      serviceWorkerShouldHandleFetch(
        'https://app-qgp-prod.azurewebsites.net/healthz',
        SWA,
      ),
    ).toBe(false)
  })

  it('does not intercept Azure Blob SAS evidence URLs (png/jpeg/pdf)', () => {
    const png =
      'https://stqgpprdcdd14b.blob.core.windows.net/evidence-assets/evidence/near_miss/106/shot.png?sp=r&sig=abc'
    const jpeg =
      'https://stqgpprdcdd14b.blob.core.windows.net/evidence-assets/evidence/road_traffic_collision/64/NIKOS.jpg?sp=r'
    const pdf =
      'https://stqgpprdcdd14b.blob.core.windows.net/evidence-assets/evidence/incident/137/note.pdf?sp=r'
    expect(serviceWorkerShouldHandleFetch(png, SWA)).toBe(false)
    expect(serviceWorkerShouldHandleFetch(jpeg, SWA)).toBe(false)
    expect(serviceWorkerShouldHandleFetch(pdf, SWA)).toBe(false)
  })

  it('does not intercept blob: object URLs', () => {
    expect(serviceWorkerShouldHandleFetch('blob:https://example/uuid', SWA)).toBe(false)
  })
})
