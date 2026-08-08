import { describe, expect, it, vi } from 'vitest'
import { createJobLifecycleApi } from './jobLifecycleClient'

function mockApi() {
  return {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  }
}

describe('createJobLifecycleApi', () => {
  it('lists job types and creates a type', () => {
    const api = mockApi()
    const client = createJobLifecycleApi(api as never)

    client.listJobTypes()
    expect(api.get).toHaveBeenCalledWith('/api/v1/job-lifecycle/job-types')

    client.createJobType({ code: 'im', name: 'Incident Management' })
    expect(api.post).toHaveBeenCalledWith('/api/v1/job-lifecycle/job-types', {
      code: 'im',
      name: 'Incident Management',
    })
  })

  it('lists lanes/steps/cells and puts cell document refs', () => {
    const api = mockApi()
    const client = createJobLifecycleApi(api as never)

    client.listLanes(3)
    expect(api.get).toHaveBeenCalledWith('/api/v1/job-lifecycle/job-types/3/lanes')

    client.listSteps(3)
    expect(api.get).toHaveBeenCalledWith('/api/v1/job-lifecycle/job-types/3/steps')

    client.listCells(3)
    expect(api.get).toHaveBeenCalledWith('/api/v1/job-lifecycle/job-types/3/cells')

    client.putCellDocuments(3, 10, 20, { library_document_ids: [7, 8] })
    expect(api.put).toHaveBeenCalledWith(
      '/api/v1/job-lifecycle/job-types/3/cells/10/20/documents',
      { library_document_ids: [7, 8] },
    )
  })

  it('patches and deletes axes by id', () => {
    const api = mockApi()
    const client = createJobLifecycleApi(api as never)

    client.updateLane(10, { name: 'Operate' })
    expect(api.patch).toHaveBeenCalledWith('/api/v1/job-lifecycle/lanes/10', { name: 'Operate' })

    client.updateStep(20, { name: 'Review' })
    expect(api.patch).toHaveBeenCalledWith('/api/v1/job-lifecycle/steps/20', { name: 'Review' })

    client.deleteLane(10)
    expect(api.delete).toHaveBeenCalledWith('/api/v1/job-lifecycle/lanes/10')

    client.deleteStep(20)
    expect(api.delete).toHaveBeenCalledWith('/api/v1/job-lifecycle/steps/20')
  })
})
