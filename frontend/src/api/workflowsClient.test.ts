import { describe, expect, it, vi } from 'vitest'
import { createWorkflowsApi } from './workflowsClient'

function mockApi() {
  return {
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
  }
}

describe('createWorkflowsApi', () => {
  it('listInstances builds optional query params', () => {
    const api = mockApi()
    createWorkflowsApi(api as never).listInstances({ status: 'active', entity_type: 'incident' })
    expect(api.get).toHaveBeenCalledWith(
      '/api/v1/workflows/instances?status=active&entity_type=incident',
    )
  })

  it('listTemplates path matches OpenAPI', () => {
    const api = mockApi()
    createWorkflowsApi(api as never).listTemplates()
    expect(api.get).toHaveBeenCalledWith('/api/v1/workflows/templates')
  })

  it('offers nothing for approvals, delegations or stats', () => {
    /*
     * Those methods, and the endpoints behind them, were deleted by
     * FR-APPROVALS-01: the queue was `[]` for every user, the approve/reject
     * writes recorded nothing, and the delegation list was one invented row.
     *
     * This assertion is the point of the test. The methods were unreachable from
     * any page, so nothing failed when they stopped working — and because the api
     * is mocked here, the old tests kept passing against URLs that now 404. A
     * client method is an invitation to wire it up.
     */
    const workflows = createWorkflowsApi(mockApi() as never)

    expect(Object.keys(workflows).sort()).toEqual(['listInstances', 'listTemplates'])
  })
})
