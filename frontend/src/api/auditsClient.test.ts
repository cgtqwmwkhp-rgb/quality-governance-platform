import { describe, expect, it, vi } from 'vitest'
import { createAuditsApi } from './auditsClient'

function mockApi() {
  return {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  }
}

describe('createAuditsApi', () => {
  it('listTemplates builds query params', () => {
    const api = mockApi()
    createAuditsApi(api as never).listTemplates(2, 25, {
      search: 'iso',
      is_published: true,
      category: 'QMS',
      audit_type: 'internal',
    })
    expect(api.get).toHaveBeenCalledWith(
      '/api/v1/audits/templates?page=2&page_size=25&is_published=true&search=iso&category=QMS&audit_type=internal',
    )
  })

  it('template CRUD + publish/clone/archive paths', () => {
    const api = mockApi()
    const audits = createAuditsApi(api as never)
    audits.listCategories()
    audits.batchImportTemplates('/tmp/xml')
    audits.getTemplate(1)
    audits.createTemplate({ name: 't', audit_type: 'internal' } as never)
    audits.updateTemplate(1, { name: 't2' } as never)
    audits.publishTemplate(1)
    audits.cloneTemplate(1)
    audits.deleteTemplate(1)
    audits.listArchivedTemplates(1, 20)
    audits.restoreTemplate(1)
    expect(api.get).toHaveBeenCalledWith('/api/v1/audit-templates/categories')
    expect(api.post).toHaveBeenCalledWith('/api/v1/xml-import/batch-import', {
      directory_path: '/tmp/xml',
    })
    expect(api.get).toHaveBeenCalledWith('/api/v1/audits/templates/1')
    expect(api.post).toHaveBeenCalledWith('/api/v1/audits/templates/1/publish')
    expect(api.post).toHaveBeenCalledWith('/api/v1/audits/templates/1/clone')
    expect(api.delete).toHaveBeenCalledWith('/api/v1/audits/templates/1')
    expect(api.get).toHaveBeenCalledWith('/api/v1/audits/templates/archived?page=1&page_size=20')
    expect(api.post).toHaveBeenCalledWith('/api/v1/audits/templates/1/restore')
  })

  it('section and question paths', () => {
    const api = mockApi()
    const audits = createAuditsApi(api as never)
    audits.createSection(1, { title: 's' } as never)
    audits.updateSection(2, { title: 's2' } as never)
    audits.deleteSection(2)
    audits.createQuestion(1, { question_text: 'q', question_type: 'yes_no' } as never)
    audits.updateQuestion(3, { question_text: 'q2' } as never)
    audits.deleteQuestion(3)
    expect(api.post).toHaveBeenCalledWith(
      '/api/v1/audits/templates/1/sections',
      { title: 's' },
      undefined,
    )
    expect(api.patch).toHaveBeenCalledWith(
      '/api/v1/audits/sections/2',
      { title: 's2' },
      undefined,
    )
    expect(api.delete).toHaveBeenCalledWith('/api/v1/audits/sections/2', undefined)
    expect(api.post).toHaveBeenCalledWith(
      '/api/v1/audits/templates/1/questions',
      {
        question_text: 'q',
        question_type: 'yes_no',
      },
      undefined,
    )
    expect(api.patch).toHaveBeenCalledWith(
      '/api/v1/audits/questions/3',
      { question_text: 'q2' },
      undefined,
    )
    expect(api.delete).toHaveBeenCalledWith('/api/v1/audits/questions/3', undefined)
  })

  it('forwards a per-request config so the builder save path can raise its timeout', () => {
    const api = mockApi()
    const audits = createAuditsApi(api as never)
    const config = { timeout: 90000 }
    audits.createTemplate({ name: 't', audit_type: 'internal' } as never, config)
    audits.updateTemplate(1, { name: 't2' } as never, config)
    audits.createSection(1, { title: 's' } as never, config)
    audits.updateSection(2, { title: 's2' } as never, config)
    audits.deleteSection(2, config)
    audits.createQuestion(1, { question_text: 'q' } as never, config)
    audits.updateQuestion(3, { question_text: 'q2' } as never, config)
    audits.deleteQuestion(3, config)

    expect(api.post).toHaveBeenCalledWith('/api/v1/audits/templates', { name: 't', audit_type: 'internal' }, config)
    expect(api.patch).toHaveBeenCalledWith('/api/v1/audits/templates/1', { name: 't2' }, config)
    expect(api.post).toHaveBeenCalledWith('/api/v1/audits/templates/1/sections', { title: 's' }, config)
    expect(api.patch).toHaveBeenCalledWith('/api/v1/audits/sections/2', { title: 's2' }, config)
    expect(api.delete).toHaveBeenCalledWith('/api/v1/audits/sections/2', config)
    expect(api.post).toHaveBeenCalledWith(
      '/api/v1/audits/templates/1/questions',
      { question_text: 'q' },
      config,
    )
    expect(api.patch).toHaveBeenCalledWith('/api/v1/audits/questions/3', { question_text: 'q2' }, config)
    expect(api.delete).toHaveBeenCalledWith('/api/v1/audits/questions/3', config)
  })

  it('run lifecycle paths match OpenAPI', () => {
    const api = mockApi()
    const audits = createAuditsApi(api as never)
    audits.listRuns(1, 10)
    audits.createRun({ template_id: 1 } as never)
    audits.getRun(4)
    audits.getRunDetail(4)
    audits.updateRun(4, { notes: 'n' } as never)
    audits.startRun(4)
    audits.completeRun(4)
    expect(api.get).toHaveBeenCalledWith('/api/v1/audits/runs?page=1&page_size=10')
    expect(api.post).toHaveBeenCalledWith('/api/v1/audits/runs', { template_id: 1 })
    expect(api.get).toHaveBeenCalledWith('/api/v1/audits/runs/4')
    expect(api.patch).toHaveBeenCalledWith('/api/v1/audits/runs/4', { notes: 'n' })
    expect(api.post).toHaveBeenCalledWith('/api/v1/audits/runs/4/start')
    expect(api.post).toHaveBeenCalledWith('/api/v1/audits/runs/4/complete')
  })

  it('findings and responses list includes optional run_id', () => {
    const api = mockApi()
    const audits = createAuditsApi(api as never)
    audits.listFindings(1, 10, 9)
    audits.listFindings(1, 10)
    audits.createResponse(9, { question_id: 1 } as never)
    audits.updateResponse(2, { notes: 'n' } as never)
    audits.createFinding(9, { title: 'f', description: 'd', severity: 'low' })
    audits.updateFinding(5, { status: 'closed' })
    expect(api.get).toHaveBeenCalledWith('/api/v1/audits/findings?page=1&page_size=10&run_id=9')
    expect(api.get).toHaveBeenCalledWith('/api/v1/audits/findings?page=1&page_size=10')
    audits.listFindings(1, 1, undefined, 'open')
    expect(api.get).toHaveBeenCalledWith('/api/v1/audits/findings?page=1&page_size=1&status=open')
    expect(api.post).toHaveBeenCalledWith('/api/v1/audits/runs/9/responses', { question_id: 1 })
    expect(api.patch).toHaveBeenCalledWith('/api/v1/audits/responses/2', { notes: 'n' })
    expect(api.post).toHaveBeenCalledWith('/api/v1/audits/runs/9/findings', {
      title: 'f',
      description: 'd',
      severity: 'low',
    })
    expect(api.patch).toHaveBeenCalledWith('/api/v1/audits/findings/5', { status: 'closed' })
  })
})
