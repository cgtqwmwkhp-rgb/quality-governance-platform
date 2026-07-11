import { describe, expect, it, vi } from 'vitest'
import { createNotificationsApi } from './notificationsClient'

function mockApi() {
  return {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  }
}

describe('createNotificationsApi', () => {
  it('list builds unread_only and pagination query', () => {
    const api = mockApi()
    createNotificationsApi(api as never).list({ page: 2, page_size: 20, unread_only: true })
    expect(api.get).toHaveBeenCalledWith('/api/v1/notifications/?page=2&page_size=20&unread_only=true')
  })

  it('read/delete/preferences paths match OpenAPI', () => {
    const api = mockApi()
    const n = createNotificationsApi(api as never)
    n.getUnreadCount()
    n.markRead(8)
    n.markAllRead()
    n.delete(8)
    n.clearAll()
    n.getPreferences()
    n.updatePreferences({ email_enabled: true })
    expect(api.get).toHaveBeenCalledWith('/api/v1/notifications/unread-count')
    expect(api.post).toHaveBeenCalledWith('/api/v1/notifications/8/read')
    expect(api.post).toHaveBeenCalledWith('/api/v1/notifications/read-all')
    expect(api.delete).toHaveBeenCalledWith('/api/v1/notifications/8')
    expect(api.delete).toHaveBeenCalledWith('/api/v1/notifications/')
    expect(api.get).toHaveBeenCalledWith('/api/v1/notifications/preferences')
    expect(api.put).toHaveBeenCalledWith('/api/v1/notifications/preferences', {
      email_enabled: true,
    })
  })
})
