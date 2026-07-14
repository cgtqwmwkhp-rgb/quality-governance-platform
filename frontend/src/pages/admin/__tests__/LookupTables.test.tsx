import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

const mockList = vi.fn()
const mockCreate = vi.fn()

vi.mock('../../../api/client', () => ({
  lookupsApi: {
    list: (...args: unknown[]) => mockList(...args),
    create: (...args: unknown[]) => mockCreate(...args),
  },
}))

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string | Record<string, unknown>) =>
      typeof fallback === 'string' ? fallback : key,
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

vi.mock('../../../contexts/ToastContext', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

import LookupTables from '../LookupTables'

describe('LookupTables configure CTA', () => {
  beforeEach(() => {
    mockList.mockReset()
    mockCreate.mockReset()
    mockList.mockImplementation(async (category: string) => {
      if (category === 'departments' || category === 'locations') {
        return { items: [], total: 0 }
      }
      return {
        items: [{ id: 1, category, code: 'a', label: 'A', is_active: true, display_order: 0 }],
        total: 1,
      }
    })
  })

  it('shows Not configured honesty and primary Configure CTA for empty categories', async () => {
    render(<LookupTables />)

    expect(await screen.findByTestId('lookup-count-departments')).toHaveTextContent('Not configured')
    expect(screen.getByTestId('lookup-empty-departments')).toBeInTheDocument()
    expect(screen.getByTestId('lookup-configure-departments')).toHaveTextContent('Configure')
  })

  it('opens editor from Configure CTA and loads real options', async () => {
    const user = userEvent.setup()
    render(<LookupTables />)

    await screen.findByTestId('lookup-configure-incident_types')
    await user.click(screen.getByTestId('lookup-configure-incident_types'))

    expect(await screen.findByTestId('lookup-editor-dialog')).toBeInTheDocument()
    await waitFor(() => {
      expect(mockList).toHaveBeenCalledWith('incident_types', false)
    })
    expect(await screen.findByTestId('lookup-editor-list')).toHaveTextContent('A')
  })

  it('does not fabricate zero when list fails', async () => {
    mockList.mockRejectedValue(new Error('network'))
    render(<LookupTables />)

    expect(await screen.findByTestId('lookup-count-departments')).toHaveTextContent(
      'Count unavailable',
    )
    expect(screen.queryByTestId('lookup-empty-departments')).not.toBeInTheDocument()
  })
})
