import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

const mockListTemplates = vi.fn()
const mockDeleteTemplate = vi.fn()
const mockPublishTemplate = vi.fn()
const mockUpdateTemplate = vi.fn()
const mockGetTemplate = vi.fn()
const mockCreateTemplate = vi.fn()
const mockNavigate = vi.fn()

vi.mock('../../../api/formConfigClient', () => ({
  formConfigApi: {
    listTemplates: (...args: unknown[]) => mockListTemplates(...args),
    deleteTemplate: (...args: unknown[]) => mockDeleteTemplate(...args),
    publishTemplate: (...args: unknown[]) => mockPublishTemplate(...args),
    updateTemplate: (...args: unknown[]) => mockUpdateTemplate(...args),
    getTemplate: (...args: unknown[]) => mockGetTemplate(...args),
    createTemplate: (...args: unknown[]) => mockCreateTemplate(...args),
  },
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

import FormsList from '../FormsList'

/** FormsList reads `?register=` for the PEL caption, so it needs a router. */
function renderFormsList(route = '/admin/forms') {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <FormsList />
    </MemoryRouter>,
  )
}

const sampleForm = {
  id: 1,
  name: 'Incident Report',
  slug: 'incident-report',
  form_type: 'incident',
  description: 'Main incident form',
  is_active: true,
  is_published: false,
  version: 1,
  steps_count: 2,
  fields_count: 5,
  updated_at: '2026-01-01T00:00:00Z',
}

describe('FormsList API wiring', () => {
  beforeEach(() => {
    mockListTemplates.mockReset()
    mockDeleteTemplate.mockReset()
    mockPublishTemplate.mockReset()
    mockUpdateTemplate.mockReset()
    mockGetTemplate.mockReset()
    mockCreateTemplate.mockReset()
    mockNavigate.mockReset()

    mockListTemplates.mockResolvedValue({ items: [sampleForm], total: 1, page: 1, page_size: 100 })
  })

  it('loads templates from admin config API', async () => {
    renderFormsList()

    expect(await screen.findByText('Incident Report')).toBeInTheDocument()
    expect(mockListTemplates).toHaveBeenCalledWith({ page_size: 100 })
    expect(screen.getByText('2 steps')).toBeInTheDocument()
  })

  it('shows retry when list fails', async () => {
    mockListTemplates.mockRejectedValue(new Error('network'))
    renderFormsList()

    expect(await screen.findByRole('button', { name: 'Retry' })).toBeInTheDocument()
    expect(screen.getByText('network')).toBeInTheDocument()
  })

  it('publishes draft templates via API', async () => {
    const user = userEvent.setup()
    mockPublishTemplate.mockResolvedValue({ ...sampleForm, is_published: true, version: 2 })

    renderFormsList()
    await screen.findByText('Incident Report')

    const card = screen.getByText('Incident Report').closest('div[class*="group"]')
    expect(card).toBeTruthy()
    await user.hover(card!)

    const menuButton = card!.querySelector('button')
    expect(menuButton).toBeTruthy()
    await user.click(menuButton!)

    // Portaled DropdownMenu items use role="menuitem", not button.
    await user.click(await screen.findByRole('menuitem', { name: 'Publish' }))

    await waitFor(() => {
      expect(mockPublishTemplate).toHaveBeenCalledWith(1)
    })
  })

  it('explains empty Form Builder catalogue honestly (PX-272)', async () => {
    mockListTemplates.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 100 })
    renderFormsList()

    expect(await screen.findByTestId('forms-list-empty-honesty')).toBeInTheDocument()
    expect(screen.getByText('No Form Builder templates')).toBeInTheDocument()
    expect(screen.getByText(/live portal intake forms/i)).toBeInTheDocument()
    expect(screen.queryByText(/Get started by creating your first form/i)).not.toBeInTheDocument()
  })
})

describe('FormsList register caption (REG-SSOT-D1)', () => {
  beforeEach(() => {
    mockListTemplates.mockReset()
    mockNavigate.mockReset()
    mockListTemplates.mockResolvedValue({ items: [sampleForm], total: 1, page: 1, page_size: 100 })
  })

  it.each([
    ['PEL-HSEQ-5026', 'PEL-HSEQ-5026 · Worker Consultation Record'],
    ['PEL-HSEQ-5036', 'PEL-HSEQ-5036 · Permit to Work Record'],
    ['PEL-HSEQ-5043', 'PEL-HSEQ-5043 · Remote Working Agreement and Assessment Record'],
  ])('captions the Form Builder when opened as %s', async (docRef, heading) => {
    renderFormsList(`/admin/forms?register=${docRef}`)

    const banner = await screen.findByTestId('register-caption-banner')
    expect(banner).toHaveTextContent(heading)
    expect(banner).toHaveTextContent('No dedicated')
    expect(screen.getByRole('link', { name: 'Back to Registers' })).toHaveAttribute(
      'href',
      '/registers',
    )
  })

  it('renders no caption without a register param, and ignores an unknown one', async () => {
    const plain = renderFormsList()
    await screen.findByText('Incident Report')
    expect(screen.queryByTestId('register-caption-banner')).not.toBeInTheDocument()
    plain.unmount()

    renderFormsList('/admin/forms?register=PEL-NOPE-0000')
    await screen.findByText('Incident Report')
    expect(screen.queryByTestId('register-caption-banner')).not.toBeInTheDocument()
  })

  it('does not invent a record count for the captioned register', async () => {
    renderFormsList('/admin/forms?register=PEL-HSEQ-5036')

    const banner = await screen.findByTestId('register-caption-banner')
    expect(banner).not.toHaveTextContent(/Server total/i)
    expect(banner).not.toHaveTextContent(/\b\d+ records?\b/i)
  })
})
