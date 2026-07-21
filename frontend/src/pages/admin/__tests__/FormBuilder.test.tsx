import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

const mockGetTemplate = vi.fn()
const mockCreateTemplate = vi.fn()
const mockUpdateTemplate = vi.fn()
const mockUpdateStep = vi.fn()
const mockCreateStep = vi.fn()
const mockDeleteStep = vi.fn()
const mockUpdateField = vi.fn()
const mockCreateField = vi.fn()
const mockDeleteField = vi.fn()
const mockNavigate = vi.fn()

vi.mock('../../../api/formConfigClient', () => ({
  formConfigApi: {
    getTemplate: (...args: unknown[]) => mockGetTemplate(...args),
    createTemplate: (...args: unknown[]) => mockCreateTemplate(...args),
    updateTemplate: (...args: unknown[]) => mockUpdateTemplate(...args),
    updateStep: (...args: unknown[]) => mockUpdateStep(...args),
    createStep: (...args: unknown[]) => mockCreateStep(...args),
    deleteStep: (...args: unknown[]) => mockDeleteStep(...args),
    updateField: (...args: unknown[]) => mockUpdateField(...args),
    createField: (...args: unknown[]) => mockCreateField(...args),
    deleteField: (...args: unknown[]) => mockDeleteField(...args),
  },
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
    useParams: () => ({}),
  }
})

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string) => (typeof fallback === 'string' ? fallback : key),
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

import FormBuilder from '../FormBuilder'

describe('FormBuilder API wiring', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockCreateTemplate.mockResolvedValue({
      id: 42,
      name: 'New Form',
      slug: 'new-form',
      form_type: 'incident',
      version: 1,
      is_active: true,
      is_published: false,
      steps: [],
      updated_at: '2026-01-01T00:00:00Z',
    })
  })

  it('creates a new template via admin config API on save', async () => {
    render(<FormBuilder />)

    fireEvent.change(screen.getByPlaceholderText('e.g. Incident Report Form'), {
      target: { value: 'New Form' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'admin.forms.save_form' }))

    await waitFor(() => {
      expect(mockCreateTemplate).toHaveBeenCalled()
    })

    const payload = mockCreateTemplate.mock.calls[0][0]
    expect(payload.name).toBe('New Form')
    expect(payload.slug).toBe('new-form')
    expect(mockNavigate).toHaveBeenCalledWith('/admin/forms/42', { replace: true })
  }, 15000)

  it('adds a field when Add Field palette is used (PX-036)', async () => {
    render(<FormBuilder />)

    fireEvent.click(screen.getByTestId('formbuilder-add-field-step-1'))

    expect(screen.getByTestId('formbuilder-field-palette')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /Text Input/i }))

    expect(screen.getByDisplayValue('Text Input')).toBeInTheDocument()
  })
})
