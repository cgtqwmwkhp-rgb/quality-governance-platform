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
      if (
        category === 'departments' ||
        category === 'locations' ||
        category === 'workforce_roles' ||
        category === 'tools' ||
        category === 'assets'
      ) {
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

  it('shows workforce_roles catalog card with documented code hints', async () => {
    render(<LookupTables />)

    expect(await screen.findByTestId('lookup-card-workforce_roles')).toBeInTheDocument()
    expect(screen.getByTestId('lookup-count-workforce_roles')).toHaveTextContent('Not configured')
    expect(screen.getByTestId('lookup-workforce-roles-hints')).toHaveTextContent(
      'engineer, field_engineer, supervisor, process_scheduler',
    )
  })

  it('exposes tools and assets lookup categories on the hub', async () => {
    render(<LookupTables />)

    expect(await screen.findByTestId('lookup-card-tools')).toBeInTheDocument()
    expect(screen.getByTestId('lookup-card-assets')).toBeInTheDocument()
    expect(screen.getByTestId('lookup-count-tools')).toHaveTextContent('Not configured')
    expect(screen.getByTestId('lookup-count-assets')).toHaveTextContent('Not configured')
    expect(screen.getByTestId('lookup-hub-category-filter')).toBeInTheDocument()
  })

  it('opens workforce_roles editor and shows standard code hints when empty', async () => {
    const user = userEvent.setup()
    render(<LookupTables />)

    await screen.findByTestId('lookup-configure-workforce_roles')
    await user.click(screen.getByTestId('lookup-configure-workforce_roles'))

    expect(await screen.findByTestId('lookup-editor-dialog')).toBeInTheDocument()
    await waitFor(() => {
      expect(mockList).toHaveBeenCalledWith('workforce_roles', false)
    })
    expect(screen.getByTestId('lookup-editor-workforce-role-hints')).toHaveTextContent(
      'field_engineer',
    )
    expect(screen.getByTestId('lookup-editor-workforce-role-hints')).toHaveTextContent(
      'process_scheduler',
    )
  })
})
