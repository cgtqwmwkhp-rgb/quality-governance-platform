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

  it('lists/creates/deletes cell links via JL-3 endpoints', () => {
    const api = mockApi()
    const client = createJobLifecycleApi(api as never)

    client.listCellLinks(3, 10, 20)
    expect(api.get).toHaveBeenCalledWith('/api/v1/job-lifecycle/job-types/3/cells/10/20/links')

    client.createCellLink(3, 10, 20, {
      kind: 'app',
      label: 'RAMS',
      entity_type: 'document',
      entity_id: 7,
    })
    expect(api.post).toHaveBeenCalledWith('/api/v1/job-lifecycle/job-types/3/cells/10/20/links', {
      kind: 'app',
      label: 'RAMS',
      entity_type: 'document',
      entity_id: 7,
    })

    client.deleteCellLink(99)
    expect(api.delete).toHaveBeenCalledWith('/api/v1/job-lifecycle/links/99')
  })

  it('requests document freshness with one repeated id param per document', () => {
    const api = mockApi()
    const client = createJobLifecycleApi(api as never)

    client.listDocumentFreshness([7, 8])
    expect(api.get).toHaveBeenCalledWith(
      '/api/v1/job-lifecycle/document-freshness?library_document_ids=7&library_document_ids=8',
    )
  })

  it('sends no id params for an empty request rather than a bare comma list', () => {
    const api = mockApi()
    const client = createJobLifecycleApi(api as never)

    client.listDocumentFreshness([])
    expect(api.get).toHaveBeenCalledWith('/api/v1/job-lifecycle/document-freshness?')
  })

  it('sends If-Match on an axis PATCH only when a token was read (JL-UX-W4)', () => {
    const api = mockApi()
    const client = createJobLifecycleApi(api as never)

    client.updateLane(10, { name: 'Operate' }, { ifMatch: '2026-08-08T00:00:00Z' })
    expect(api.patch).toHaveBeenCalledWith(
      '/api/v1/job-lifecycle/lanes/10',
      { name: 'Operate' },
      { headers: { 'If-Match': '2026-08-08T00:00:00Z' } },
    )

    // No token means no precondition, which is the pre-W4 behaviour exactly —
    // an empty `If-Match` header would be a malformed request, not a no-op.
    client.updateStep(20, { name: 'Review' }, { ifMatch: '' })
    expect(api.patch).toHaveBeenCalledWith('/api/v1/job-lifecycle/steps/20', { name: 'Review' })

    client.updateJobType(3, { name: 'Ops' }, { ifMatch: null })
    expect(api.patch).toHaveBeenCalledWith('/api/v1/job-lifecycle/job-types/3', { name: 'Ops' })
  })

  it('clones a pack and patches a cell requirement (JL-UX-W4)', () => {
    const api = mockApi()
    const client = createJobLifecycleApi(api as never)

    client.cloneJobType(3, { code: 'ops_v2', name: 'Ops v2' })
    expect(api.post).toHaveBeenCalledWith('/api/v1/job-lifecycle/job-types/3/clone', {
      code: 'ops_v2',
      name: 'Ops v2',
    })

    client.patchCellRequirement(3, 10, 20, { requires_evidence: true })
    expect(api.patch).toHaveBeenCalledWith('/api/v1/job-lifecycle/job-types/3/cells/10/20', {
      requires_evidence: true,
    })
  })

  it('reads the derived W4 views with their assurance stated explicitly', () => {
    const api = mockApi()
    const client = createJobLifecycleApi(api as never)

    client.listEvidenceReadiness(3)
    expect(api.get).toHaveBeenCalledWith(
      '/api/v1/job-lifecycle/job-types/3/evidence-readiness?assure=false',
    )

    client.listEvidenceReadiness(3, true)
    expect(api.get).toHaveBeenCalledWith(
      '/api/v1/job-lifecycle/job-types/3/evidence-readiness?assure=true',
    )

    client.getAuditTrail(3, { limit: 5, assure: true })
    expect(api.get).toHaveBeenCalledWith(
      '/api/v1/job-lifecycle/job-types/3/audit-trail?limit=5&assure=true',
    )

    client.getAuditTrail(3)
    expect(api.get).toHaveBeenCalledWith('/api/v1/job-lifecycle/job-types/3/audit-trail?assure=false')

    client.getCycleGraph(3)
    expect(api.get).toHaveBeenCalledWith('/api/v1/job-lifecycle/job-types/3/cycle-graph')

    client.getCycleGraph(3, 4)
    expect(api.get).toHaveBeenCalledWith('/api/v1/job-lifecycle/job-types/3/cycle-graph?depth=4')
  })
})
