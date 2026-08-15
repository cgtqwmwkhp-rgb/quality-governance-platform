/**
 * A failed lookup must degrade the portal form, not strand the employee.
 *
 * `loadConfig` used to set `error` and return without ever calling `setTemplate`
 * when the customers lookup rejected, so `template` stayed null and the
 * `error || !template` guard rendered an "Unable to Load Form" card whose only
 * exits were Go Back and Retry. Both P0 journeys — /portal/report/incident and
 * /portal/report/near-miss — mount this component, so both dead-ended.
 *
 * It also awaited the template and the three lookups one after another, making
 * the form's time-to-interactive the sum of four round trips.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import PortalDynamicForm from '../PortalDynamicForm'

const mockGetBySlug = vi.fn()
const mockLookupList = vi.fn()

vi.mock('../../api/client', () => ({
  formTemplatesApi: { getBySlug: (...args: unknown[]) => mockGetBySlug(...args) },
  lookupsApi: { list: (...args: unknown[]) => mockLookupList(...args) },
  getApiErrorMessage: (error: unknown, fallback?: string) =>
    error instanceof Error && error.message ? error.message : (fallback ?? 'Request failed'),
}))

vi.mock('../../contexts/PortalAuthContext', () => ({
  usePortalAuth: () => ({ user: { id: 'u1', name: 'Test User', email: 'test@example.com' } }),
}))

const TEMPLATE = {
  id: 1,
  name: 'Incident Report',
  slug: 'incident',
  version: 1,
  form_type: 'incident',
  steps: [
    {
      id: 'step-1',
      title: 'Customer Details',
      order: 1,
      fields: [
        {
          id: 'f-contract',
          name: 'contract',
          label: 'Select Customer',
          field_type: 'select',
          is_required: true,
          order: 1,
        },
      ],
    },
  ],
}

function lookupPayload(category: string) {
  const items: Record<string, Array<{ code: string; label: string }>> = {
    customers: [{ code: 'ukpn', label: 'UKPN' }],
    workforce_roles: [{ code: 'mobile-engineer', label: 'Mobile Engineer' }],
    medical_assistance: [{ code: 'none', label: 'No assistance needed' }],
  }
  return { items: (items[category] ?? []).map((item) => ({ ...item, category })) }
}

function renderForm() {
  return render(
    <MemoryRouter initialEntries={['/portal/report/incident']}>
      <PortalDynamicForm formType="incident" />
    </MemoryRouter>,
  )
}

describe('PortalDynamicForm form-config loading', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetBySlug.mockResolvedValue(TEMPLATE)
    mockLookupList.mockImplementation((category: string) =>
      Promise.resolve(lookupPayload(category)),
    )
  })

  it('renders the contract field when every catalog loads', async () => {
    renderForm()
    expect(await screen.findByTestId('field-contract')).toBeInTheDocument()
    expect(screen.getByTestId('portal-form-ready')).toBeInTheDocument()
    expect(screen.queryByTestId('portal-form-loading')).not.toBeInTheDocument()
  })

  it('still renders the form when the customers lookup fails', async () => {
    mockLookupList.mockImplementation((category: string) =>
      category === 'customers'
        ? Promise.reject(new Error('Network unavailable'))
        : Promise.resolve(lookupPayload(category)),
    )

    renderForm()

    // The step-1 field the P0 journey drives must exist even with no catalogue.
    expect(await screen.findByTestId('field-contract')).toBeInTheDocument()
    expect(screen.queryByText('portal.unable_load_form')).not.toBeInTheDocument()
    expect(screen.queryByText('Unable to Load Form')).not.toBeInTheDocument()
  })

  it('names the failed customers lookup in a non-fatal banner', async () => {
    mockLookupList.mockImplementation((category: string) =>
      category === 'customers'
        ? Promise.reject(new Error('Network unavailable'))
        : Promise.resolve(lookupPayload(category)),
    )

    renderForm()

    const banner = await screen.findByTestId('portal-catalog-warning')
    expect(banner).toHaveTextContent('Network unavailable')
  })

  it('renders the form when every lookup fails', async () => {
    mockLookupList.mockImplementation(() => Promise.reject(new Error('Network unavailable')))

    renderForm()

    expect(await screen.findByTestId('field-contract')).toBeInTheDocument()
  })

  it('renders the form when the template read also fails', async () => {
    mockGetBySlug.mockRejectedValue(new Error('Network unavailable'))
    mockLookupList.mockImplementation(() => Promise.reject(new Error('Network unavailable')))

    renderForm()

    expect(await screen.findByTestId('field-contract')).toBeInTheDocument()
    expect(await screen.findByTestId('portal-template-fallback-banner')).toBeInTheDocument()
  })

  it('issues the template read and the three lookups concurrently', async () => {
    const started: string[] = []
    let releaseTemplate: (() => void) | undefined
    mockGetBySlug.mockImplementation(() => {
      started.push('template')
      return new Promise((resolve) => {
        releaseTemplate = () => resolve(TEMPLATE)
      })
    })
    mockLookupList.mockImplementation((category: string) => {
      started.push(category)
      return Promise.resolve(lookupPayload(category))
    })

    renderForm()

    // All four are in flight while the template read is still unresolved. When
    // they were chained, nothing after 'template' could have started yet.
    await waitFor(() => expect(started).toHaveLength(4))
    expect(started).toEqual(
      expect.arrayContaining(['template', 'customers', 'workforce_roles', 'medical_assistance']),
    )

    releaseTemplate?.()
    expect(await screen.findByTestId('field-contract')).toBeInTheDocument()
  })
})
