/**
 * Notifications API client extracted from `client.ts` (Path-to-10 FE lane).
 * Instantiated from `client.ts` with the shared axios instance to avoid cycles.
 */
import type { AxiosInstance } from 'axios'

export interface NotificationEntry {
  id: number
  type: string
  priority: string
  title: string
  message: string
  entity_type?: string
  entity_id?: string
  action_url?: string
  sender_id?: number
  sender_name?: string
  is_read: boolean
  created_at: string
}

export interface NotificationCategoryChannels {
  email: boolean
  push: boolean
  in_app: boolean
  /** Tolerant reader for legacy FE payloads */
  inApp?: boolean
}

export interface NotificationPreferences {
  email_enabled: boolean
  sms_enabled: boolean
  push_enabled: boolean
  phone_number?: string | null
  quiet_hours_enabled?: boolean
  quiet_hours_start?: string | null
  quiet_hours_end?: string | null
  email_digest_enabled?: boolean
  email_digest_frequency?: string
  category_preferences?: Record<string, NotificationCategoryChannels>
}

export function createNotificationsApi(api: AxiosInstance) {
  return {
    list: (params?: { page?: number; page_size?: number; unread_only?: boolean }) => {
      const sp = new URLSearchParams()
      if (params?.page) sp.set('page', String(params.page))
      if (params?.page_size) sp.set('page_size', String(params.page_size))
      if (params?.unread_only) sp.set('unread_only', 'true')
      return api.get<{
        items: NotificationEntry[]
        total: number
        unread_count: number
        page?: number
        page_size?: number
      }>(`/api/v1/notifications/?${sp}`)
    },
    getUnreadCount: () => api.get<{ unread_count: number }>('/api/v1/notifications/unread-count'),
    markRead: (id: number) => api.post<{ success: boolean }>(`/api/v1/notifications/${id}/read`),
    markAllRead: () => api.post<{ success: boolean }>('/api/v1/notifications/read-all'),
    delete: (id: number) => api.delete<{ success: boolean }>(`/api/v1/notifications/${id}`),
    clearAll: () => api.delete<{ success: boolean; count: number }>('/api/v1/notifications/'),
    getPreferences: () => api.get<NotificationPreferences>('/api/v1/notifications/preferences'),
    updatePreferences: (data: Partial<NotificationPreferences>) =>
      api.put<{ success: boolean; preferences: Partial<NotificationPreferences> }>(
        '/api/v1/notifications/preferences',
        data,
      ),
  }
}
