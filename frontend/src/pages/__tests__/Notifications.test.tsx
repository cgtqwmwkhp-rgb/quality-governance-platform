import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import type { ReactNode } from 'react'
import Notifications from '../Notifications'

const mockList = vi.fn()
const mockMarkRead = vi.fn()
const mockGetPreferences = vi.fn()
const mockUpdatePreferences = vi.fn()
const mockMarkAllRead = vi.fn()
const mockDelete = vi.fn()
const mockClearAll = vi.fn()

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    i18n: { language: 'en' },
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

vi.mock('../../components/ui/Switch', () => ({
  Switch: ({
    checked,
    onCheckedChange,
  }: {
    checked?: boolean
    onCheckedChange?: (v: boolean) => void
  }) => (
    <button
      type="button"
      data-testid="switch"
      aria-pressed={checked}
      onClick={() => onCheckedChange?.(!checked)}
    >
      switch
    </button>
  ),
}))

vi.mock('../../api/client', () => ({
  notificationsApi: {
    list: (...args: unknown[]) => mockList(...args),
    markRead: (...args: unknown[]) => mockMarkRead(...args),
    markAllRead: (...args: unknown[]) => mockMarkAllRead(...args),
    delete: (...args: unknown[]) => mockDelete(...args),
    clearAll: (...args: unknown[]) => mockClearAll(...args),
    getPreferences: (...args: unknown[]) => mockGetPreferences(...args),
    updatePreferences: (...args: unknown[]) => mockUpdatePreferences(...args),
  },
  getApiErrorMessage: () => 'Something went wrong',
}))

function Wrapper({ children }: { children: ReactNode }) {
  return <BrowserRouter>{children}</BrowserRouter>
}

describe('Notifications', () => {
  beforeEach(() => {
    mockList.mockReset()
    mockMarkRead.mockReset()
    mockGetPreferences.mockReset()
    mockUpdatePreferences.mockReset()
    mockMarkAllRead.mockReset()
    mockDelete.mockReset()
    mockClearAll.mockReset()

    mockList.mockResolvedValue({
      data: {
        items: [
          {
            id: 11,
            type: 'incident_new',
            priority: 'high',
            title: 'High Priority Incident Reported',
            message: 'Requires attention.',
            entity_type: 'incident',
            action_url: '/incidents/1',
            is_read: false,
            created_at: '2026-07-09T12:00:00.000Z',
          },
        ],
        total: 1,
        unread_count: 1,
      },
    })
    mockMarkRead.mockResolvedValue({ data: { success: true } })
    mockMarkAllRead.mockResolvedValue({ data: { success: true } })
    mockDelete.mockResolvedValue({ data: { success: true } })
    mockClearAll.mockResolvedValue({ data: { success: true, count: 1 } })
    mockGetPreferences.mockResolvedValue({
      data: {
        email_enabled: true,
        sms_enabled: false,
        push_enabled: true,
        category_preferences: {},
      },
    })
    mockUpdatePreferences.mockResolvedValue({ data: { success: true, preferences: {} } })
  })

  it('loads notifications from the live API instead of mocks', async () => {
    render(
      <Wrapper>
        <Notifications />
      </Wrapper>,
    )

    expect(await screen.findByText('High Priority Incident Reported')).toBeInTheDocument()
    expect(screen.queryByText('NOT001')).not.toBeInTheDocument()
    expect(mockList).toHaveBeenCalled()
  })

  it('marks a notification as read via API', async () => {
    render(
      <Wrapper>
        <Notifications />
      </Wrapper>,
    )

    expect(await screen.findByText('High Priority Incident Reported')).toBeInTheDocument()
    fireEvent.click(screen.getByText('notifications.mark_read'))
    await waitFor(() => expect(mockMarkRead).toHaveBeenCalledWith(11))
  })

  it('loads preferences from API when opening settings', async () => {
    render(
      <Wrapper>
        <Notifications />
      </Wrapper>,
    )

    expect(await screen.findByText('High Priority Incident Reported')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /notifications.preferences/i }))
    await waitFor(() => expect(mockGetPreferences).toHaveBeenCalled())
    expect(await screen.findByText('notifications.pref.high_priority_alerts')).toBeInTheDocument()
  })
})
