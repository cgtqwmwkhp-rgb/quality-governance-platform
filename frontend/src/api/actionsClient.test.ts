import { describe, expect, it, vi } from 'vitest'
import { actionsAreComplete, createActionsApi, describeUnavailableSources } from './actionsClient'

function mockApi() {
  return {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  }
}

describe('createActionsApi', () => {
  it('list builds optional status/source filters', () => {
    const api = mockApi()
    createActionsApi(api as never).list(2, 25, 'open', 'audit_finding', 9)
    expect(api.get).toHaveBeenCalledWith(
      '/api/v1/actions/?page=2&page_size=25&status=open&source_type=audit_finding&source_id=9',
    )
  })

  it('list appends assigned_to and overdue scope params', () => {
    const api = mockApi()
    createActionsApi(api as never).list(1, 50, undefined, undefined, undefined, {
      assigned_to: 'me',
      overdue: true,
    })
    expect(api.get).toHaveBeenCalledWith(
      '/api/v1/actions/?page=1&page_size=50&assigned_to=me&overdue=true',
    )
  })

  it('summary and create hit collection paths', () => {
    const api = mockApi()
    const actions = createActionsApi(api as never)
    actions.summary()
    actions.create({ title: 't', description: 'd', source_type: 'capa' })
    expect(api.get).toHaveBeenCalledWith('/api/v1/actions/summary')
    expect(api.post).toHaveBeenCalledWith('/api/v1/actions/', {
      title: 't',
      description: 'd',
      source_type: 'capa',
    })
  })

  it('get/update encode source_type; by-key + notes match OpenAPI', () => {
    const api = mockApi()
    const actions = createActionsApi(api as never)
    actions.get(3, 'capa')
    actions.getByKey('capa:3')
    actions.update(3, 'capa', { status: 'completed' })
    actions.listOwnerNotes('capa:3', 50)
    actions.appendOwnerNote('capa:3', 'done')
    expect(api.get).toHaveBeenCalledWith('/api/v1/actions/3?source_type=capa')
    expect(api.get).toHaveBeenCalledWith('/api/v1/actions/by-key?key=capa%3A3')
    expect(api.patch).toHaveBeenCalledWith('/api/v1/actions/3?source_type=capa', {
      status: 'completed',
    })
    expect(api.get).toHaveBeenCalledWith('/api/v1/actions/by-key/notes?key=capa%3A3&limit=50')
    expect(api.post).toHaveBeenCalledWith('/api/v1/actions/by-key/notes', {
      key: 'capa:3',
      body: 'done',
    })
  })
})

/**
 * The client half of C-53. A server that reports partial failure is only useful if
 * the client stops rendering "no actions" for it, and the register's empty state is
 * the single most misleading surface in the product when it is wrong: it says the
 * work is done.
 */
describe('actionsAreComplete', () => {
  it('treats an explicit false as incomplete', () => {
    expect(actionsAreComplete({ sources_complete: false })).toBe(false)
  })

  it('treats an explicit true as complete', () => {
    expect(actionsAreComplete({ sources_complete: true })).toBe(true)
  })

  it('treats an absent field as complete', () => {
    // A server that does not publish completeness predates the field. Defaulting
    // the other way would put a permanent "this register is incomplete" warning on
    // every page during a rolling deploy, and a warning that is always on is a
    // warning nobody reads.
    expect(actionsAreComplete({})).toBe(true)
  })
})

describe('describeUnavailableSources', () => {
  it('names sources in language an operator can act on', () => {
    expect(describeUnavailableSources(['capa', 'incident'])).toBe('CAPA actions, incident actions')
  })

  it('passes an unrecognised source through rather than dropping it', () => {
    // A new action store added server-side must still be reported, even before
    // this map learns its name. Silence is the failure mode being fixed.
    expect(describeUnavailableSources(['brand_new_store'])).toBe('brand_new_store')
  })

  it('returns an empty string for nothing unavailable', () => {
    expect(describeUnavailableSources([])).toBe('')
    expect(describeUnavailableSources(undefined)).toBe('')
  })
})
