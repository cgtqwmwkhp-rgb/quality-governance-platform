import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'

const mockList = vi.fn()
const mockListRoles = vi.fn()

vi.mock('../../../api/client', async () => {
  const actual = await vi.importActual<typeof import('../../../api/client')>('../../../api/client')
  return {
    ...actual,
    usersApi: {
      list: (...args: unknown[]) => mockList(...args),
      listRoles: (...args: unknown[]) => mockListRoles(...args),
      create: vi.fn(),
      update: vi.fn(),
    },
  }
})

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (_key: string, fallback?: string) => fallback ?? _key,
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

import UserManagement from '../UserManagement'

describe('UserManagement soft-fail honesty', () => {
  beforeEach(() => {
    mockList.mockReset()
    mockListRoles.mockReset()
  })

  it('shows unavailable banner on load failure without throwing', async () => {
    mockList.mockRejectedValue(new Error('timeout'))
    mockListRoles.mockRejectedValue(new Error('timeout'))

    render(<UserManagement />)

    expect(await screen.findByTestId('user-management-unavailable')).toBeInTheDocument()
    expect(screen.getByText('User list unavailable')).toBeInTheDocument()
    expect(screen.queryByText('No users have been provisioned yet.')).not.toBeInTheDocument()
  })
})
