import { describe, expect, it, vi } from 'vitest'
import { buildRiskCreateActionHref, createRiskRegisterApi } from './riskRegisterClient'

function mockApi() {
  return {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  }
}

describe('createRiskRegisterApi', () => {
  it('list builds triage and search filters', () => {
    const api = mockApi()
    createRiskRegisterApi(api as never).list({
      skip: 0,
      limit: 25,
      status: 'open',
      category: 'ops',
      search: 'fire',
      suggestion_triage: 'pending',
    })
    expect(api.get).toHaveBeenCalledWith(
      '/api/v1/risk-register/?skip=0&limit=25&status=open&category=ops&search=fire&suggestion_triage=pending',
    )
  })

  it('CRUD + assess + triage + analytics paths', () => {
    const api = mockApi()
    const rr = createRiskRegisterApi(api as never)
    rr.create({ title: 'r' })
    rr.get(2)
    rr.getProfile(2)
    rr.update(2, { title: 'r2' })
    rr.delete(2)
    rr.assess(2, {
      inherent_likelihood: 3,
      inherent_impact: 4,
      residual_likelihood: 2,
      residual_impact: 3,
    })
    rr.listNotes(2, { page_size: 25 })
    rr.createNote(2, 'hello')
    rr.listActivity(2, { event_type: 'assessed' })
    rr.listActions(2, { page_size: 25 })
    rr.createAction(2, { title: 'Follow-up', description: 'From profile' })
    rr.listUpstream(2)
    rr.updateOwner(2, { risk_owner_id: 7, risk_owner_name: 'Alex' })
    rr.resolveSuggestionTriage(2, { decision: 'accept', notes: 'ok' })
    rr.getHeatmap()
    rr.getSummary()
    rr.getTrends(30)
    expect(api.post).toHaveBeenCalledWith('/api/v1/risk-register/', { title: 'r' })
    expect(api.get).toHaveBeenCalledWith('/api/v1/risk-register/2')
    expect(api.get).toHaveBeenCalledWith('/api/v1/risk-register/2/profile')
    expect(api.put).toHaveBeenCalledWith('/api/v1/risk-register/2', { title: 'r2' })
    expect(api.delete).toHaveBeenCalledWith('/api/v1/risk-register/2')
    expect(api.post).toHaveBeenCalledWith('/api/v1/risk-register/2/assess', {
      inherent_likelihood: 3,
      inherent_impact: 4,
      residual_likelihood: 2,
      residual_impact: 3,
    })
    expect(api.get).toHaveBeenCalledWith('/api/v1/risk-register/2/notes?page_size=25')
    expect(api.post).toHaveBeenCalledWith('/api/v1/risk-register/2/notes', { body: 'hello' })
    expect(api.get).toHaveBeenCalledWith('/api/v1/risk-register/2/activity?event_type=assessed')
    expect(api.get).toHaveBeenCalledWith('/api/v1/risk-register/2/actions?page_size=25')
    expect(api.post).toHaveBeenCalledWith('/api/v1/risk-register/2/actions', {
      title: 'Follow-up',
      description: 'From profile',
    })
    expect(api.get).toHaveBeenCalledWith('/api/v1/risk-register/2/upstream')
    expect(api.put).toHaveBeenCalledWith('/api/v1/risk-register/2/owner', {
      risk_owner_id: 7,
      risk_owner_name: 'Alex',
    })
    expect(api.post).toHaveBeenCalledWith('/api/v1/risk-register/2/suggestion-triage', {
      decision: 'accept',
      notes: 'ok',
    })
    expect(api.get).toHaveBeenCalledWith('/api/v1/risk-register/heatmap')
    expect(api.get).toHaveBeenCalledWith('/api/v1/risk-register/summary')
    expect(api.get).toHaveBeenCalledWith('/api/v1/risk-register/trends?days=30')
  })

  it('getTrends supports risk_id filter', () => {
    const api = mockApi()
    createRiskRegisterApi(api as never).getTrends(90, false, 42)
    expect(api.get).toHaveBeenCalledWith('/api/v1/risk-register/trends?days=90&risk_id=42')
  })

  it('bowtie/controls/KRI/appetite helpers', () => {
    const api = mockApi()
    const rr = createRiskRegisterApi(api as never)
    rr.getBowtie(7)
    rr.addBowtieElement(7, { kind: 'threat' })
    rr.deleteBowtieElement(7, 3)
    rr.listControls()
    rr.createControl({ name: 'c' })
    rr.linkControl(7, 9)
    rr.getKRIDashboard()
    rr.createKRI({ name: 'k' })
    rr.updateKRIValue(4, 12)
    rr.getKRIHistory(4)
    rr.getAppetiteStatements()
    expect(api.get).toHaveBeenCalledWith('/api/v1/risk-register/7/bowtie')
    expect(api.post).toHaveBeenCalledWith('/api/v1/risk-register/7/bowtie/elements', {
      kind: 'threat',
    })
    expect(api.delete).toHaveBeenCalledWith('/api/v1/risk-register/7/bowtie/elements/3')
    expect(api.get).toHaveBeenCalledWith('/api/v1/risk-register/controls')
    expect(api.post).toHaveBeenCalledWith('/api/v1/risk-register/controls', { name: 'c' })
    expect(api.post).toHaveBeenCalledWith('/api/v1/risk-register/7/controls/9')
    expect(api.get).toHaveBeenCalledWith('/api/v1/risk-register/kris/dashboard')
    expect(api.post).toHaveBeenCalledWith('/api/v1/risk-register/kris', { name: 'k' })
    expect(api.put).toHaveBeenCalledWith('/api/v1/risk-register/kris/4/value', { value: 12 })
    expect(api.get).toHaveBeenCalledWith('/api/v1/risk-register/kris/4/history')
    expect(api.get).toHaveBeenCalledWith('/api/v1/risk-register/appetite/statements')
  })

  it('buildRiskCreateActionHref prefills risk source and returnTo', () => {
    const href = buildRiskCreateActionHref({
      riskId: 42,
      reference: 'RSK-00042',
      title: 'Supplier disruption',
    })
    expect(href.startsWith('/actions?')).toBe(true)
    expect(href).toContain('create=1')
    expect(href).toContain('sourceType=risk')
    expect(href).toContain('sourceId=42')
    expect(href).toContain(encodeURIComponent('/risk-register/42'))
  })
})
