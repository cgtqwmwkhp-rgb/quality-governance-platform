import { describe, expect, it, vi } from 'vitest'
import { createFormConfigApi } from './formConfigClient'

function mockApi() {
  return {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  }
}

describe('createFormConfigApi', () => {
  it('lists templates with optional form_type filter', () => {
    const api = mockApi()
    api.get.mockResolvedValue({
      data: {
        items: [
          {
            id: 1,
            name: 'Incident',
            slug: 'incident',
            form_type: 'incident',
            version: 1,
            is_active: true,
            is_published: false,
            steps: [{ id: 10, fields: [{ id: 100 }, { id: 101 }] }],
            updated_at: '2026-01-01T00:00:00Z',
          },
        ],
        total: 1,
        page: 1,
        page_size: 20,
      },
    })

    return createFormConfigApi(api as never)
      .listTemplates({ form_type: 'incident' })
      .then((result) => {
        expect(api.get).toHaveBeenCalledWith('/api/v1/admin/config/templates?form_type=incident', {
          suppressErrorToast: true,
        })
        expect(result.items[0].steps_count).toBe(1)
        expect(result.items[0].fields_count).toBe(2)
      })
  })

  it('creates and publishes templates on expected paths', async () => {
    const api = mockApi()
    api.post.mockResolvedValue({ data: { id: 1 } })

    await createFormConfigApi(api as never).createTemplate({
      name: 'T',
      slug: 't',
      form_type: 'custom',
    })
    expect(api.post).toHaveBeenCalledWith('/api/v1/admin/config/templates', {
      name: 'T',
      slug: 't',
      form_type: 'custom',
    })

    await createFormConfigApi(api as never).publishTemplate(5)
    expect(api.post).toHaveBeenCalledWith('/api/v1/admin/config/templates/5/publish')
  })

  it('deletes templates and steps on expected paths', async () => {
    const api = mockApi()
    api.delete.mockResolvedValue({ data: undefined })

    await createFormConfigApi(api as never).deleteTemplate(3)
    expect(api.delete).toHaveBeenCalledWith('/api/v1/admin/config/templates/3')

    await createFormConfigApi(api as never).deleteStep(9)
    expect(api.delete).toHaveBeenCalledWith('/api/v1/admin/config/steps/9')
  })
})
