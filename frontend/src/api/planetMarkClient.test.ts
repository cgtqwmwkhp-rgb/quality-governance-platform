import { describe, expect, it, vi } from 'vitest'
import { createPlanetMarkApi } from './planetMarkClient'

function mockApi() {
  return {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
    put: vi.fn(),
  }
}

describe('createPlanetMarkApi', () => {
  it('wires dashboard/years/setup paths', () => {
    const api = mockApi()
    const pm = createPlanetMarkApi(api as never)
    pm.getDashboard()
    pm.listYears()
    pm.getYear(42)
    pm.createReportingYear({
      year_label: '2026',
      year_number: 2026,
      period_start: '2026-01-01',
      period_end: '2026-12-31',
      average_fte: 10,
    })
    expect(api.get).toHaveBeenCalledWith('/api/v1/planet-mark/dashboard')
    expect(api.get).toHaveBeenCalledWith('/api/v1/planet-mark/years')
    expect(api.get).toHaveBeenCalledWith('/api/v1/planet-mark/years/42')
    expect(api.post).toHaveBeenCalledWith(
      '/api/v1/planet-mark/years',
      expect.objectContaining({ year_number: 2026 }),
    )
  })

  it('lists sources with and without scope filter', () => {
    const api = mockApi()
    const pm = createPlanetMarkApi(api as never)
    pm.listSources(7)
    pm.listSources(7, '1')
    expect(api.get).toHaveBeenCalledWith('/api/v1/planet-mark/years/7/sources')
    expect(api.get).toHaveBeenCalledWith('/api/v1/planet-mark/years/7/sources?scope=1')
  })

  it('covers year detail reads and mutation helpers', () => {
    const api = mockApi()
    const pm = createPlanetMarkApi(api as never)
    pm.getScope3(1)
    pm.listActions(1)
    pm.getCertification(1)
    pm.getDataQuality(1)
    pm.getActionsSummary(1)
    pm.addEmissionSource(1, {
      source_name: 'Fleet',
      source_category: 'transport',
      scope: '1',
      activity_type: 'fuel',
      activity_value: 10,
      activity_unit: 'litres',
    })
    pm.createAction(1, {
      action_title: 'Reduce fuel',
      specific: 's',
      measurable: 'm',
      achievable_owner: 'a',
      time_bound: '2026-12-31',
    })
    pm.updateAction(1, 9, { status: 'in_progress', progress_percent: 40 })
    pm.bulkUpdateActions(1, [9, 10], 'completed')
    pm.patchCertification(1, { status: 'certified', certificate_number: 'PM-1' })
    expect(api.get).toHaveBeenCalledWith('/api/v1/planet-mark/years/1/scope3')
    expect(api.get).toHaveBeenCalledWith('/api/v1/planet-mark/years/1/actions')
    expect(api.get).toHaveBeenCalledWith('/api/v1/planet-mark/years/1/certification')
    expect(api.get).toHaveBeenCalledWith('/api/v1/planet-mark/years/1/data-quality')
    expect(api.get).toHaveBeenCalledWith('/api/v1/planet-mark/years/1/actions/summary')
    expect(api.post).toHaveBeenCalled()
    expect(api.put).toHaveBeenCalled()
    expect(api.patch).toHaveBeenCalled()
  })

  it('covers evidence and import helpers', () => {
    const api = mockApi()
    const pm = createPlanetMarkApi(api as never)
    pm.listEvidence(3)
    pm.listEvidence(3, { document_type: 'invoice', linked_action_id: 8 })
    const fd = new FormData()
    pm.uploadEvidence(3, fd)
    pm.patchEvidence(3, 11, { notes: 'ok', is_verified: true })
    pm.deleteEvidence(3, 11)
    pm.getEvidenceDownloadUrl(3, 11)
    pm.extractActionPlan(3, fd)
    pm.confirmActionImport(3, 'sess-1', [0, 1])
    pm.applyImport(99, 3)
    pm.getImportSyncStatus(99)
    expect(api.get).toHaveBeenCalledWith('/api/v1/planet-mark/years/3/evidence')
    expect(api.get).toHaveBeenCalledWith(
      '/api/v1/planet-mark/years/3/evidence?document_type=invoice&linked_action_id=8',
    )
    expect(api.delete).toHaveBeenCalled()
    expect(api.post).toHaveBeenCalled()
    expect(api.patch).toHaveBeenCalled()
  })
})
