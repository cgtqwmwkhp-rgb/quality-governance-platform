import axios, { AxiosError } from 'axios'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import api, {
  LOGIN_ERROR_I18N_KEYS,
  LOGIN_ERROR_MESSAGES,
  ErrorClass,
  getDurationBucket,
  classifyLoginError,
  classifyError,
  createApiError,
  getApiErrorMessage,
  checkPackCapability,
  authApi,
  auditTrailApi,
  signaturesApi,
  aiApi,
  analyticsApi,
  complianceApi,
  crossStandardMappingsApi,
  complianceAutomationApi,
  imsDashboardApi,
  iso27001Api,
  searchApi,
  evidenceAssetsApi,
  workflowsApi,
  executiveDashboardApi,
  formTemplatesApi,
  contractsApi,
  lookupsApi,
  settingsApi,
  vehicleChecklistsApi,
  externalAuditImportsApi,
  externalAuditRecordsApi,
} from './client'

function axiosErr(partial: {
  code?: string
  message?: string
  status?: number
  data?: unknown
}): AxiosError {
  const err = new Error(partial.message ?? 'boom') as AxiosError
  err.isAxiosError = true
  err.code = partial.code
  err.name = 'AxiosError'
  err.toJSON = () => ({})
  if (partial.status !== undefined) {
    err.response = {
      status: partial.status,
      data: partial.data ?? {},
      statusText: 'err',
      headers: {},
      config: { headers: {} as never },
    }
  }
  return err
}

describe('client pure helpers', () => {
  it('getDurationBucket covers all buckets', () => {
    expect(getDurationBucket(0)).toBe('fast')
    expect(getDurationBucket(1500)).toBe('normal')
    expect(getDurationBucket(5000)).toBe('slow')
    expect(getDurationBucket(10000)).toBe('very_slow')
    expect(getDurationBucket(20000)).toBe('timeout')
  })

  it('LOGIN_ERROR maps are complete', () => {
    for (const code of Object.keys(LOGIN_ERROR_MESSAGES) as (keyof typeof LOGIN_ERROR_MESSAGES)[]) {
      expect(LOGIN_ERROR_I18N_KEYS[code]).toContain(code)
      expect(LOGIN_ERROR_MESSAGES[code].length).toBeGreaterThan(0)
    }
  })

  it('classifyLoginError covers bounded codes', () => {
    expect(classifyLoginError(new Error('x'))).toBe('UNKNOWN')
    vi.spyOn(axios, 'isAxiosError').mockReturnValue(true)
    expect(classifyLoginError(axiosErr({ code: 'ECONNABORTED' }))).toBe('TIMEOUT')
    expect(classifyLoginError(axiosErr({ message: 'timeout of 15ms exceeded' }))).toBe('TIMEOUT')
    expect(classifyLoginError(axiosErr({ message: 'Network Error' }))).toBe('NETWORK_ERROR')
    expect(classifyLoginError(axiosErr({ status: 401 }))).toBe('UNAUTHORIZED')
    expect(classifyLoginError(axiosErr({ status: 503 }))).toBe('UNAVAILABLE')
    expect(classifyLoginError(axiosErr({ status: 502 }))).toBe('UNAVAILABLE')
    expect(classifyLoginError(axiosErr({ status: 500 }))).toBe('SERVER_ERROR')
    expect(classifyLoginError(axiosErr({ status: 418 }))).toBe('UNKNOWN')
    vi.mocked(axios.isAxiosError).mockRestore()
  })

  it('classifyError and createApiError cover status classes', () => {
    expect(classifyError('nope')).toBe(ErrorClass.UNKNOWN)
    vi.spyOn(axios, 'isAxiosError').mockReturnValue(true)
    expect(classifyError(axiosErr({ code: 'ECONNABORTED' }))).toBe(ErrorClass.NETWORK_ERROR)
    expect(classifyError(axiosErr({ message: 'down' }))).toBe(ErrorClass.NETWORK_ERROR)
    expect(classifyError(axiosErr({ status: 422 }))).toBe(ErrorClass.VALIDATION_ERROR)
    expect(classifyError(axiosErr({ status: 403 }))).toBe(ErrorClass.AUTH_ERROR)
    expect(classifyError(axiosErr({ status: 404 }))).toBe(ErrorClass.NOT_FOUND)
    expect(
      classifyError(axiosErr({ status: 409, data: { error_class: 'UAT_WRITE_BLOCKED' } })),
    ).toBe(ErrorClass.WRITE_BLOCKED)
    expect(classifyError(axiosErr({ status: 409, data: {} }))).toBe(ErrorClass.UNKNOWN)
    expect(classifyError(axiosErr({ status: 500 }))).toBe(ErrorClass.SERVER_ERROR)
    expect(classifyError(axiosErr({ status: 418 }))).toBe(ErrorClass.UNKNOWN)

    const created = createApiError(axiosErr({ status: 400, data: { detail: 'bad' }, message: 'm' }))
    expect(created.error_class).toBe(ErrorClass.VALIDATION_ERROR)
    expect(created.status_code).toBe(400)
    expect(created.detail).toBe('bad')
    vi.mocked(axios.isAxiosError).mockRestore()
  })

  it('getApiErrorMessage prefers classified and response payloads', () => {
    vi.spyOn(axios, 'isAxiosError').mockReturnValue(true)
    const classified = axiosErr({ status: 400 }) as AxiosError & { classifiedMessage?: string }
    classified.classifiedMessage = 'classified'
    expect(getApiErrorMessage(classified)).toBe('classified')
    expect(getApiErrorMessage(axiosErr({ status: 400, data: { message: 'msg' } }))).toBe('msg')
    expect(getApiErrorMessage(axiosErr({ status: 400, data: { detail: 'd' } }))).toBe('d')
    expect(
      getApiErrorMessage(axiosErr({ status: 400, data: { detail: { message: 'nested' } } })),
    ).toBe('nested')
    expect(getApiErrorMessage(axiosErr({ status: 400, data: { detail: { a: 1 } } }))).toBe(
      JSON.stringify({ a: 1 }),
    )
    const bare = axiosErr({ message: 'axios-msg' })
    bare.response = undefined
    expect(getApiErrorMessage(bare)).toBe('axios-msg')
    vi.mocked(axios.isAxiosError).mockRestore()

    expect(getApiErrorMessage(new Error('plain'))).toBe('plain')
    expect(getApiErrorMessage('x')).toBe('An unexpected error occurred')
    expect(getApiErrorMessage('x', 'fallback')).toBe('fallback')
  })
})

describe('client inline API surfaces', () => {
  beforeEach(() => {
    vi.spyOn(api, 'get').mockResolvedValue({ data: {} } as never)
    vi.spyOn(api, 'post').mockResolvedValue({ data: {} } as never)
    vi.spyOn(api, 'put').mockResolvedValue({ data: {} } as never)
    vi.spyOn(api, 'patch').mockResolvedValue({ data: {} } as never)
    vi.spyOn(api, 'delete').mockResolvedValue({ data: {} } as never)
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('auth + audit trail + signatures paths', async () => {
    authApi.login({ email: 'a@b.c', password: 'p' })
    authApi.logout('rt')
    authApi.logout()
    auditTrailApi.list({
      entity_type: 'incident',
      action: 'create',
      user_id: 1,
      date_from: '2026-01-01',
      date_to: '2026-12-31',
      page: 2,
      per_page: 10,
    })
    auditTrailApi.list()
    auditTrailApi.getEntry(1)
    auditTrailApi.getByEntity('incident', '9')
    auditTrailApi.getByUser(3, 14)
    auditTrailApi.verify()
    auditTrailApi.exportLog({ format: 'csv', reason: 'audit' })
    auditTrailApi.getStats(7)
    signaturesApi.list('pending', 25)
    signaturesApi.list()
    signaturesApi.get(1)
    signaturesApi.create({
      title: 't',
      document_type: 'policy',
      signers: [{ email: 'a@b.c', name: 'A' }],
    })
    signaturesApi.send(1)
    signaturesApi.void(1, 'revoked')
    signaturesApi.getPending()
    signaturesApi.getAuditLog(1)
    signaturesApi.getStats()
    signaturesApi.listTemplates()
    signaturesApi.createTemplate({ name: 'tpl' })
    expect(api.post).toHaveBeenCalled()
    expect(api.get).toHaveBeenCalled()
  })

  it('ai + analytics helpers', () => {
    aiApi.analyzeText('hello', 'risk')
    aiApi.getPredictions('incidents')
    aiApi.getPredictions()
    aiApi.getAnomalies('incidents', 7)
    aiApi.getAnomalies()
    aiApi.auditAssistant('q', { a: 1 })
    aiApi.getRecommendations('audits')
    aiApi.getRecommendations()
    aiApi.getSentiment('ok')
    aiApi.classifyRisk('slip')
    aiApi.getDashboard()
    aiApi.generateAuditQuestions('ISO9001', '4.1', 'ctx')
    aiApi.generateAuditChecklist('ISO9001', ['4.1'])
    analyticsApi.getKPIs('30d')
    analyticsApi.getKPIs()
    analyticsApi.getTrends('incidents', '30d')
    analyticsApi.getTrends('incidents')
    analyticsApi.getBenchmarks('utilities')
    analyticsApi.getBenchmarks()
    analyticsApi.getExecutiveSummary('30d')
    analyticsApi.getExecutiveSummary()
    analyticsApi.getNonComplianceCosts('30d')
    analyticsApi.getNonComplianceCosts()
    analyticsApi.getROI()
    analyticsApi.getCostBreakdown('30d')
    analyticsApi.getCostBreakdown()
    analyticsApi.getDrillDown('incidents', 'severity', 'high', '30d')
    analyticsApi.getDrillDown('incidents', 'severity', 'high')
    analyticsApi.forecast('incidents', 'count', 6)
    analyticsApi.forecast('incidents', 'count')
    analyticsApi.listDashboards()
    analyticsApi.getDashboard(1)
    analyticsApi.createDashboard({ name: 'd' })
    analyticsApi.updateDashboard(1, { name: 'd2' })
    analyticsApi.deleteDashboard(1)
    analyticsApi.getWidgetData(9, '30d')
    analyticsApi.getWidgetData(9)
    expect(api.get).toHaveBeenCalled()
    expect(api.post).toHaveBeenCalled()
  })

  it('compliance + cross-standard + automation', () => {
    complianceApi.listClauses('iso9001', 'q')
    complianceApi.listClauses()
    complianceApi.autoTag('evidence', true)
    complianceApi.linkEvidence({
      entity_type: 'incident',
      entity_id: '1',
      clause_ids: ['c1'],
    })
    complianceApi.listEvidenceLinks({
      entity_type: 'incident',
      entity_id: '1',
      clause_id: 'c1',
      page: 1,
      size: 10,
    })
    complianceApi.listEvidenceLinks()
    complianceApi.deleteEvidenceLink(3)
    complianceApi.getCoverage('iso9001')
    complianceApi.getCoverage()
    complianceApi.getGaps('iso9001')
    complianceApi.getGaps()
    complianceApi.getReport('iso9001')
    complianceApi.getReport()
    complianceApi.downloadAuditPack({ includeNonconformity: true })
    complianceApi.downloadAuditPack()
    complianceApi.listStandards()
    complianceApi.analyzeEvidence('text')
    complianceApi.getSoA('Acme')
    complianceApi.getSoA()
    expect(api.get).toHaveBeenCalledWith(
      '/api/v1/compliance/audit-pack?include_nonconformity=true',
    )
    expect(api.get).toHaveBeenCalledWith('/api/v1/compliance/audit-pack')
    crossStandardMappingsApi.list({
      source_standard: 'iso9001',
      target_standard: 'iso14001',
      clause: '4.1',
      limit: 10,
      offset: 0,
    })
    crossStandardMappingsApi.list()
    crossStandardMappingsApi.listStandards()
    complianceAutomationApi.listRegulatoryUpdates({
      source: 'hse',
      impact: 'high',
      reviewed: false,
    })
    complianceAutomationApi.listRegulatoryUpdates()
    complianceAutomationApi.reviewUpdate(1, { requires_action: true, action_notes: 'n' })
    complianceAutomationApi.reviewUpdate(1)
    complianceAutomationApi.runGapAnalysis({ regulatory_update_id: 1, standard_id: 2 })
    complianceAutomationApi.runGapAnalysis()
    complianceAutomationApi.listGapAnalyses('open')
    complianceAutomationApi.listGapAnalyses()
    complianceAutomationApi.listCertificates({
      certificate_type: 'iso',
      entity_type: 'org',
      status: 'active',
      expiring_within_days: 30,
    })
    complianceAutomationApi.listCertificates()
    complianceAutomationApi.getExpiringCertificates()
    complianceAutomationApi.addCertificate({
      name: 'c',
      certificate_type: 'iso',
      entity_type: 'org',
      entity_id: '1',
      issue_date: '2026-01-01',
      expiry_date: '2027-01-01',
    })
    complianceAutomationApi.listScheduledAudits({ upcoming_days: 14, overdue: true })
    complianceAutomationApi.listScheduledAudits()
    complianceAutomationApi.scheduleAudit({
      name: 'a',
      audit_type: 'internal',
      frequency: 'annual',
      next_due_date: '2026-12-01',
    })
    complianceAutomationApi.getComplianceScore({ scope_type: 'org', scope_id: '1' })
    complianceAutomationApi.getComplianceScore()
    complianceAutomationApi.getComplianceTrend({ scope_type: 'org', months: 6 })
    complianceAutomationApi.getComplianceTrend()
    complianceAutomationApi.listRiddorSubmissions('draft')
    complianceAutomationApi.listRiddorSubmissions()
    complianceAutomationApi.checkRiddor({ severity: 'high' })
    complianceAutomationApi.prepareRiddor(9, 'injury')
    complianceAutomationApi.submitRiddor(9)
    expect(api.get).toHaveBeenCalled()
    expect(api.post).toHaveBeenCalled()
  })

  it('ims + iso27001 + search', () => {
    imsDashboardApi.getDashboard()
    iso27001Api.getDashboard()
    iso27001Api.getAssets({ skip: 0, limit: 10, criticality: 'high', asset_type: 'data' })
    iso27001Api.getAsset(1)
    iso27001Api.createAsset({ name: 'a', asset_type: 'data' })
    iso27001Api.updateAsset(1, { name: 'b' })
    iso27001Api.getControls({ domain: 'A', implementation_status: 'implemented', is_applicable: true })
    iso27001Api.updateControl(1, { implementation_status: 'implemented' })
    iso27001Api.getSoa()
    iso27001Api.getRisks({ skip: 0, limit: 5, min_score: 10, status: 'open', include_closed: false })
    iso27001Api.getRisk(2)
    iso27001Api.createRisk({ title: 'r', description: 'd' })
    iso27001Api.updateRisk(2, { status: 'closed' })
    iso27001Api.getIncidents({ skip: 0, limit: 5, severity: 'high', status: 'open' })
    iso27001Api.getIncident(3)
    iso27001Api.createIncident({
      title: 'i',
      description: 'd',
      incident_type: 'breach',
      detected_date: '2026-01-01',
    })
    iso27001Api.updateIncident(3, { status: 'investigating' })
    iso27001Api.getSuppliers({ skip: 0, limit: 5, risk_level: 'high', rating: 'compliant' })
    iso27001Api.getSupplier(4)
    iso27001Api.createSupplier({
      supplier_name: 's',
      supplier_type: 'cloud',
      overall_rating: 'compliant',
    })
    iso27001Api.getAccessControl({ active_only: true, skip: 0, limit: 10 })
    iso27001Api.createAccessControl({
      user_id: 1,
      user_name: 'u',
      system_name: 'erp',
      access_level: 'read',
      granted_date: '2026-01-01',
    })
    iso27001Api.getBCPs({ active_only: true, skip: 0, limit: 10 })
    iso27001Api.getBCP(5)
    iso27001Api.createBCP({
      name: 'bcp',
      description: 'd',
      scope: 's',
      rto_hours: 4,
      rpo_hours: 1,
      effective_date: '2026-01-01',
    })
    iso27001Api.updateBCP(5, { is_active: false })
    searchApi.search('q', { module: 'incidents', type: 'open', status: 'open' })
    searchApi.search({
      q: 'q2',
      module: 'audits',
      type: 'finding',
      status: 'open',
      date_from: '2026-01-01',
      date_to: '2026-12-31',
      page: 2,
      page_size: 20,
    })
    expect(api.get).toHaveBeenCalled()
    expect(api.post).toHaveBeenCalled()
  })

  it('evidence assets + workflows + executive dashboard', async () => {
    evidenceAssetsApi.list({
      page: 1,
      page_size: 10,
      source_module: 'investigation',
      source_id: 4,
      action_key: 'capa:1',
      asset_type: 'photo',
      linked_investigation_id: 4,
    })
    evidenceAssetsApi.list()
    evidenceAssetsApi.get(1)
    const file = new File(['x'], 'a.txt', { type: 'text/plain' })
    evidenceAssetsApi.upload(file, {
      source_module: 'investigation',
      source_id: 4,
      title: 't',
      description: 'd',
      visibility: 'internal',
      contains_pii: false,
      redaction_required: true,
    })
    evidenceAssetsApi.upload(file, { source_module: 'action', action_key: 'capa:1' })
    expect(() =>
      evidenceAssetsApi.upload(file, { source_module: 'action' }),
    ).toThrow(/source_id or action_key/)
    evidenceAssetsApi.linkToInvestigation(1, 4)
    evidenceAssetsApi.delete(1)
    evidenceAssetsApi.getSignedUrl(1, 60)
    evidenceAssetsApi.getSignedUrl(1)
    workflowsApi.getPendingApprovals()
    workflowsApi.approveRequest('a1', { notes: 'ok' })
    workflowsApi.rejectRequest('a1', { reason: 'no' })
    workflowsApi.bulkApprove(['a1', 'a2'], { notes: 'ok' })
    workflowsApi.listInstances({ status: 'active', entity_type: 'incident' })
    workflowsApi.listInstances()
    workflowsApi.listTemplates()
    workflowsApi.getStats()
    workflowsApi.getDelegations()
    workflowsApi.setDelegation({
      delegate_id: 2,
      start_date: '2026-01-01',
      end_date: '2026-02-01',
    })
    workflowsApi.cancelDelegation('d1')
    executiveDashboardApi.getDashboard(14)
    executiveDashboardApi.getSummary()
    executiveDashboardApi.getAlerts()

    vi.mocked(api.get).mockResolvedValueOnce({ data: { items: [] } } as never)
    await expect(checkPackCapability(9)).resolves.toEqual({ canGenerate: true })
    vi.mocked(api.get).mockRejectedValueOnce({ response: { status: 404 } })
    await expect(checkPackCapability(9)).resolves.toMatchObject({ canGenerate: false })
    vi.mocked(api.get).mockRejectedValueOnce({ response: { status: 501 } })
    await expect(checkPackCapability(9)).resolves.toMatchObject({ canGenerate: false })
    vi.mocked(api.get).mockRejectedValueOnce({ response: { status: 403 } })
    await expect(checkPackCapability(9)).resolves.toMatchObject({ canGenerate: false })
    vi.mocked(api.get).mockRejectedValueOnce({ response: { status: 500 } })
    await expect(checkPackCapability(9)).resolves.toEqual({ canGenerate: true })
  })

  it('admin config APIs unwrap axios data', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: { items: [], total: 0 } } as never)
    vi.mocked(api.post).mockResolvedValue({ data: { id: 1 } } as never)
    vi.mocked(api.patch).mockResolvedValue({ data: { id: 1 } } as never)
    vi.mocked(api.delete).mockResolvedValue({ data: undefined } as never)

    await formTemplatesApi.list('incident')
    await formTemplatesApi.list()
    await formTemplatesApi.getById(1)
    await formTemplatesApi.getBySlug('incident')
    await formTemplatesApi.create({ name: 't' })
    await formTemplatesApi.update(1, { name: 't2' })
    await formTemplatesApi.publish(1)
    await formTemplatesApi.delete(1)
    await contractsApi.list(true)
    await contractsApi.list(false)
    await contractsApi.create({ name: 'c', code: 'C1' })
    await contractsApi.update(1, { name: 'c2' })
    await contractsApi.delete(1)
    await lookupsApi.list('severity', true)
    await lookupsApi.list('severity', false)
    await lookupsApi.create('severity', { code: 'h', label: 'High' })
    await lookupsApi.update('severity', 1, { label: 'High!' })
    await lookupsApi.delete('severity', 1)
    await settingsApi.list('general')
    await settingsApi.list()
    await settingsApi.get('site_name')
    await settingsApi.update('site_name', 'QGP')
    expect(api.get).toHaveBeenCalled()
  })

  it('vehicle checklists + external audit imports/records', () => {
    vehicleChecklistsApi.schema()
    vehicleChecklistsApi.listDaily(2, 10)
    vehicleChecklistsApi.listMonthly(1, 25)
    vehicleChecklistsApi.getDaily(1)
    vehicleChecklistsApi.getMonthly(2)
    vehicleChecklistsApi.listDefects(1, 25, 'P1', 'open')
    vehicleChecklistsApi.listDefects()
    vehicleChecklistsApi.createDefect({
      pams_table: 'daily',
      pams_record_id: 1,
      check_field: 'tyres',
      priority: 'P1',
    })
    vehicleChecklistsApi.getDefect(3)
    vehicleChecklistsApi.updateDefect(3, { status: 'closed' })
    vehicleChecklistsApi.createDefectAction(3, { title: 'fix', description: 'd' })
    vehicleChecklistsApi.triggerSync()
    vehicleChecklistsApi.analyticsSummary()
    vehicleChecklistsApi.analyticsTrends(14)
    vehicleChecklistsApi.analyticsHeatmap(5)
    vehicleChecklistsApi.exportDailyCsv()
    vehicleChecklistsApi.exportMonthlyCsv()
    vehicleChecklistsApi.exportDefectsCsv()
    externalAuditImportsApi.createJob({ audit_run_id: 1, source_document_asset_id: 2 })
    externalAuditImportsApi.queueJob(9)
    externalAuditImportsApi.processJob(9)
    externalAuditImportsApi.getLatestJobForRun(1)
    externalAuditImportsApi.getJob(9)
    externalAuditImportsApi.getReconciliation(9)
    externalAuditImportsApi.listDrafts(9)
    externalAuditImportsApi.reviewDraft(3, { status: 'accepted', review_notes: 'ok' })
    externalAuditImportsApi.bulkReviewJob(9, { status: 'accepted' })
    externalAuditImportsApi.promoteJob(9)
    externalAuditRecordsApi.list({ scheme: 'uvdb', status: 'active', skip: 0, limit: 10 })
    externalAuditRecordsApi.get(4)
    externalAuditRecordsApi.dashboard({ scheme: 'planet_mark' })
    expect(api.get).toHaveBeenCalled()
    expect(api.post).toHaveBeenCalled()
  })
})
