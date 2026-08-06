import type { AxiosInstance } from 'axios'
import { describe, expect, it } from 'vitest'
import { createComplianceScheduleApi } from '../complianceScheduleClient'

/**
 * Every request this client makes must carry the `/api/v1` prefix.
 *
 * The shared axios instance sets `baseURL` to the host with no version segment,
 * so each client spells the version itself. This one did not, and the result was
 * silent and total: all twelve endpoints answered 404 in every environment, so the
 * register could never load. Confirmed against live staging at the time of the fix
 * --- `/compliance-schedule/stats` returned 404 while
 * `/api/v1/compliance-schedule/stats` returned 401.
 *
 * Nothing else would have caught it. The blocking `check_api_path_drift.py` gate
 * scans Python `tests/` only, so it never reads this file; and even scoped here it
 * looks for `/api/` *without* a version rather than for a missing `/api/` segment,
 * which is the shape of this defect.
 */

const VERSIONED = '/api/v1/compliance-schedule'

function recordingApi(): { api: AxiosInstance; urls: string[] } {
  const urls: string[] = []
  const record = (url: string) => {
    urls.push(url)
    return Promise.resolve({ data: {} })
  }
  const api = {
    get: (url: string) => record(url),
    post: (url: string) => record(url),
    patch: (url: string) => record(url),
    put: (url: string) => record(url),
    delete: (url: string) => record(url),
  } as unknown as AxiosInstance
  return { api, urls }
}

/** Exercises every method the client exposes. Keyed by name so the count can be
 *  compared against the client's own surface below. */
function callEveryMethod(client: ReturnType<typeof createComplianceScheduleApi>) {
  return {
    listRequirements: () => client.listRequirements({ is_active: true }),
    getRequirement: () => client.getRequirement(7),
    createRequirement: () => client.createRequirement({}),
    updateRequirement: () => client.updateRequirement(7, {}),
    deactivateRequirement: () => client.deactivateRequirement(7),
    listRecords: () => client.listRecords(7),
    completeRequirement: () => client.completeRequirement(7, {}),
    getRecord: () => client.getRecord(11),
    attachEvidence: () => client.attachEvidence(11, [1]),
    listCatalogue: () => client.listCatalogue(),
    activateCatalogue: () => client.activateCatalogue('fire-risk-assessment'),
    getStats: () => client.getStats(),
    getLocationCoverageGaps: () => client.getLocationCoverageGaps(),
    fileRecordToLibrary: () =>
      client.fileRecordToLibrary(11, { evidence_asset_id: 5, category_id: 3 }),
  }
}

describe('complianceScheduleClient request paths', () => {
  it('sends every request to a versioned path', async () => {
    const { api, urls } = recordingApi()
    const client = createComplianceScheduleApi(api)
    await Promise.all(Object.values(callEveryMethod(client)).map((call) => call()))

    expect(urls.length).toBeGreaterThan(0)
    const unversioned = urls.filter((url) => !url.startsWith(VERSIONED))
    expect(unversioned, `these paths are not served and will 404: ${unversioned.join(', ')}`).toEqual(
      [],
    )
  })

  it('covers every method the client exposes', () => {
    const { api } = recordingApi()
    const client = createComplianceScheduleApi(api)
    const exercised = Object.keys(callEveryMethod(client))
    const exposed = Object.keys(client)

    // Without this, a method added later could reintroduce an unversioned path
    // and the assertion above would pass without ever calling it.
    expect(exposed.filter((name) => !exercised.includes(name))).toEqual([])
  })

  it('does not double up the version segment', async () => {
    const { api, urls } = recordingApi()
    const client = createComplianceScheduleApi(api)
    await client.getStats()

    expect(urls[0]).toBe(`${VERSIONED}/stats`)
    expect(urls[0]).not.toContain('/api/v1/api/v1')
  })
})
