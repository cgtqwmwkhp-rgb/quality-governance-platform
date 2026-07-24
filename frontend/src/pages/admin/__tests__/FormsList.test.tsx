import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

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
    render(<FormsList />)

    expect(await screen.findByText('Incident Report')).toBeInTheDocument()
    expect(mockListTemplates).toHaveBeenCalledWith({ page_size: 100 })
    expect(screen.getByText('2 steps')).toBeInTheDocument()
  })

  it('shows retry when list fails', async () => {
    mockListTemplates.mockRejectedValue(new Error('network'))
    render(<FormsList />)

    expect(await screen.findByRole('button', { name: 'Retry' })).toBeInTheDocument()
    expect(screen.getByText('network')).toBeInTheDocument()
  })

  it('publishes draft templates via API', async () => {
    const user = userEvent.setup()
    mockPublishTemplate.mockResolvedValue({ ...sampleForm, is_published: true, version: 2 })

    render(<FormsList />)
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
})
