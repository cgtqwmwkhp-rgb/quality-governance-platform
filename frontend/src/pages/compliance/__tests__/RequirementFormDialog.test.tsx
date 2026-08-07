import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import type { ComplianceRequirement } from '../../../api/complianceScheduleClient'

const {
  mockCreate,
  mockUpdate,
  mockComplete,
  mockUpload,
  mockDelete,
  mockGet,
  mockCurrentUserId,
  mockSuggest,
  flagValues,
} = vi.hoisted(() => ({
  mockCreate: vi.fn(),
  mockUpdate: vi.fn(),
  mockComplete: vi.fn(),
  mockUpload: vi.fn(),
  mockDelete: vi.fn(),
  mockGet: vi.fn(),
  mockCurrentUserId: vi.fn(),
  mockSuggest: vi.fn(),
  flagValues: {
    compliance_schedule: true,
    compliance_schedule_regulatory_ai: true,
  } as Record<string, boolean>,
}))

vi.mock('../../../api/client', () => ({
  default: { get: mockGet },
  complianceScheduleApi: {
    createRequirement: mockCreate,
    updateRequirement: mockUpdate,
    completeRequirement: mockComplete,
    suggestRegulatoryBasis: mockSuggest,
    clarifyRegulatoryBasis: vi.fn(),
  },
  evidenceAssetsApi: {
    upload: mockUpload,
    delete: mockDelete,
  },
  getApiErrorMessage: (err: unknown) =>
    err instanceof Error ? err.message : 'Something went wrong',
}))

vi.mock('../../../hooks/useFeatureFlag', () => ({
  useFeatureFlag: (name: string) => flagValues[name] ?? false,
}))

vi.mock('../../../utils/auth', () => ({
  getCurrentUserId: mockCurrentUserId,
}))

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (_key: string, fallback?: unknown) => (typeof fallback === 'string' ? fallback : _key),
    i18n: { language: 'en' },
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

/**
 * Stub picker with the two behaviours that matter: typing (an address, nobody
 * selected) and choosing (a real user). The real component debounces a network
 * search, which is not what these tests are about.
 */
vi.mock('../../../components/UserEmailSearch', () => ({
  UserEmailSearch: ({
    onChange,
  }: {
    onChange: (email: string, user?: { id: number; email: string; full_name: string }) => void
  }) => (
    <div>
      <input
        data-testid="owner-typed"
        aria-label="Owner"
        onChange={(e) => onChange(e.target.value, undefined)}
      />
      <button
        type="button"
        data-testid="owner-pick"
        onClick={() =>
          onChange('picked@example.com', {
            id: 42,
            email: 'picked@example.com',
            full_name: 'Picked Person',
          })
        }
      >
        pick
      </button>
    </div>
  ),
}))

import { RequirementFormDialog } from '../RequirementFormDialog'

beforeAll(() => {
  const proto = Element.prototype as unknown as Record<string, unknown>
  if (!proto.hasPointerCapture) proto.hasPointerCapture = () => false
  if (!proto.setPointerCapture) proto.setPointerCapture = () => undefined
  if (!proto.releasePointerCapture) proto.releasePointerCapture = () => undefined
  if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => undefined
  if (!('ResizeObserver' in globalThis)) {
    ;(globalThis as unknown as Record<string, unknown>).ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

const CATEGORIES = {
  data: {
    sections: [
      {
        taxonomy_id: '03',
        name: 'Fire Safety',
        children: [{ taxonomy_id: '03.01', name: 'Fire Risk Assessment', active: true }],
      },
    ],
  },
}

const EXISTING: ComplianceRequirement = {
  id: 7,
  external_id: 'ext-7',
  tenant_id: 1,
  reference_number: 'CSR-2026-0001',
  title: 'Fire Risk Assessment',
  taxonomy_id: '03.01',
  description: 'Annual review',
  regulatory_basis: 'Fire Safety Order 2005',
  frequency_months: 12,
  frequency_days: null,
  anchor: 'schedule',
  statutory: true,
  next_due_date: '2026-09-06',
  last_completed_at: null,
  owner_id: null,
  is_active: true,
  status: 'due_soon',
  created_at: '2026-01-01T00:00:00Z',
  fra_ocr_eligible: true,
}

function renderForm(props: Partial<React.ComponentProps<typeof RequirementFormDialog>> = {}) {
  return render(
    <MemoryRouter>
      <RequirementFormDialog
        open
        onOpenChange={props.onOpenChange ?? vi.fn()}
        requirement={props.requirement}
        onSaved={props.onSaved ?? vi.fn()}
      />
    </MemoryRouter>,
  )
}

async function fillRequiredCreateFields(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByTestId('requirement-form-title-input'), 'Sprinkler service')
  await user.click(await screen.findByTestId('requirement-form-taxonomy-trigger'))
  await user.click(await screen.findByRole('option', { name: /Fire Risk Assessment/ }))
  const due = screen.getByTestId('requirement-form-next-due-input')
  await user.clear(due)
  await user.type(due, '2027-03-01')
}

beforeEach(() => {
  vi.clearAllMocks()
  mockGet.mockResolvedValue(CATEGORIES)
  mockCurrentUserId.mockReturnValue(9)
  mockCreate.mockResolvedValue({ data: { ...EXISTING, id: 11 } })
  mockUpdate.mockResolvedValue({ data: EXISTING })
  mockComplete.mockResolvedValue({ data: { id: 99 } })
  mockUpload.mockImplementation(async (_file: File) => ({
    data: { id: mockUpload.mock.calls.length + 200 },
  }))
  mockDelete.mockResolvedValue({})
})

describe('RequirementFormDialog — create', () => {
  it('creates the obligation with the fields entered', async () => {
    const user = userEvent.setup()
    renderForm()
    await fillRequiredCreateFields(user)
    await user.click(screen.getByTestId('requirement-form-submit'))

    await waitFor(() => expect(mockCreate).toHaveBeenCalledTimes(1))
    expect(mockCreate.mock.calls[0][0]).toMatchObject({
      title: 'Sprinkler service',
      taxonomy_id: '03.01',
      next_due_date: '2027-03-01',
      anchor: 'schedule',
      statutory: false,
    })
  })

  it('assigns the creator as owner, so a new obligation is never unowned', async () => {
    const user = userEvent.setup()
    renderForm()
    await fillRequiredCreateFields(user)
    await user.click(screen.getByTestId('requirement-form-submit'))

    await waitFor(() => expect(mockCreate).toHaveBeenCalled())
    expect(mockCreate.mock.calls[0][0].owner_id).toBe(9)
  })

  it('uses the picked person over the creator when one is chosen', async () => {
    const user = userEvent.setup()
    renderForm()
    await fillRequiredCreateFields(user)
    await user.click(screen.getByTestId('owner-pick'))
    await user.click(screen.getByTestId('requirement-form-submit'))

    await waitFor(() => expect(mockCreate).toHaveBeenCalled())
    expect(mockCreate.mock.calls[0][0].owner_id).toBe(42)
  })

  it('refuses to submit when an address was typed but nobody was chosen', async () => {
    const user = userEvent.setup()
    renderForm()
    await fillRequiredCreateFields(user)
    await user.type(screen.getByTestId('owner-typed'), 'someone@example.com')
    await user.click(screen.getByTestId('requirement-form-submit'))

    expect(await screen.findByTestId('requirement-form-owner-error')).toBeInTheDocument()
    expect(mockCreate).not.toHaveBeenCalled()
  })

  it('blocks submit until the required fields are present', async () => {
    const user = userEvent.setup()
    renderForm()
    await user.click(screen.getByTestId('requirement-form-submit'))

    await waitFor(() => expect(mockCreate).not.toHaveBeenCalled())
    expect(screen.getByTestId('requirement-form-title-error')).toBeInTheDocument()
  })

  it('rejects a fractional interval rather than dropping it', async () => {
    const user = userEvent.setup()
    renderForm()
    await fillRequiredCreateFields(user)
    await user.type(screen.getByTestId('requirement-form-months-input'), '1.5')
    await user.click(screen.getByTestId('requirement-form-submit'))

    await waitFor(() => expect(mockCreate).not.toHaveBeenCalled())
  })

  it('shows the API failure in the form instead of losing the typed work', async () => {
    mockCreate.mockRejectedValue(new Error('Owner is not in this tenant'))
    const user = userEvent.setup()
    renderForm()
    await fillRequiredCreateFields(user)
    await user.click(screen.getByTestId('requirement-form-submit'))

    expect(await screen.findByTestId('requirement-form-error')).toHaveTextContent(
      'Owner is not in this tenant',
    )
    expect(screen.getByTestId('requirement-form-title-input')).toHaveValue('Sprinkler service')
  })

  it('offers historical evidence on create and withholds it on edit', () => {
    const { unmount } = renderForm()
    expect(screen.getByTestId('requirement-form-historical-evidence')).toBeInTheDocument()
    unmount()

    renderForm({ requirement: EXISTING })
    expect(screen.queryByTestId('requirement-form-historical-evidence')).not.toBeInTheDocument()
  })

  it('creates then completes with staged evidence when historical proof is attached', async () => {
    const user = userEvent.setup()
    const onSaved = vi.fn()
    const onOpenChange = vi.fn()
    renderForm({ onSaved, onOpenChange })
    await fillRequiredCreateFields(user)

    await user.click(screen.getByTestId('requirement-form-historical-toggle'))
    expect(screen.getByTestId('requirement-form-historical-completed-at')).toBeInTheDocument()

    const input = screen.getByTestId('requirement-form-historical-files-input')
    const file = new File(['proof'], 'past-cert.pdf', { type: 'application/pdf' })
    await user.upload(input, file)
    expect(screen.getByTestId('requirement-form-historical-files-list')).toHaveTextContent(
      'past-cert.pdf',
    )

    await user.click(screen.getByTestId('requirement-form-submit'))

    await waitFor(() => expect(mockCreate).toHaveBeenCalledTimes(1))
    await waitFor(() => {
      expect(mockUpload).toHaveBeenCalledWith(
        file,
        expect.objectContaining({
          source_module: 'induction',
          source_id: 11,
          title: 'past-cert.pdf',
        }),
      )
      expect(mockComplete).toHaveBeenCalledWith(
        11,
        expect.objectContaining({
          check_passed: true,
          evidence_asset_ids: [201],
          completed_at: expect.any(String),
        }),
      )
    })
    expect(onSaved).toHaveBeenCalled()
    expect(onOpenChange).toHaveBeenCalledWith(false)
    expect(mockDelete).not.toHaveBeenCalled()
  })

  it('keeps the obligation and shows a retry path when historical complete fails', async () => {
    mockComplete.mockRejectedValueOnce(new Error('complete failed'))
    mockUpload.mockResolvedValueOnce({ data: { id: 55 } })
    const user = userEvent.setup()
    const onSaved = vi.fn()
    const onOpenChange = vi.fn()
    renderForm({ onSaved, onOpenChange })
    await fillRequiredCreateFields(user)
    await user.click(screen.getByTestId('requirement-form-historical-toggle'))
    await user.upload(
      screen.getByTestId('requirement-form-historical-files-input'),
      new File(['x'], 'photo.jpg', { type: 'image/jpeg' }),
    )
    await user.click(screen.getByTestId('requirement-form-submit'))

    expect(await screen.findByTestId('requirement-form-historical-error')).toBeInTheDocument()
    expect(screen.getByTestId('requirement-form-historical-retry-link')).toHaveAttribute(
      'href',
      '/compliance-schedule/11',
    )
    expect(mockDelete).toHaveBeenCalledWith(55)
    expect(onSaved).toHaveBeenCalled()
    expect(onOpenChange).not.toHaveBeenCalledWith(false)
    expect(screen.queryByTestId('requirement-form-submit')).not.toBeInTheDocument()

    // Closing must not trip the unsaved-changes guard — obligation already exists.
    await user.click(screen.getByTestId('requirement-form-cancel'))
    expect(onOpenChange).toHaveBeenCalledWith(false)
    expect(screen.queryByTestId('requirement-form-unsaved')).not.toBeInTheDocument()
  })
})

describe('RequirementFormDialog — edit', () => {
  it('prefills from the requirement being edited', async () => {
    renderForm({ requirement: EXISTING })

    expect(screen.getByTestId('requirement-form-title-input')).toHaveValue('Fire Risk Assessment')
    expect(screen.getByTestId('requirement-form-next-due-input')).toHaveValue('2026-09-06')
    expect(screen.getByTestId('requirement-form-months-input')).toHaveValue(12)
    expect(screen.getByTestId('requirement-form-basis-input')).toHaveValue(
      'Fire Safety Order 2005',
    )
  })

  it('leaves the owner alone when the picker was not touched', async () => {
    const user = userEvent.setup()
    renderForm({ requirement: { ...EXISTING, owner_id: 3 } })
    await user.clear(screen.getByTestId('requirement-form-title-input'))
    await user.type(screen.getByTestId('requirement-form-title-input'), 'Renamed')
    await user.click(screen.getByTestId('requirement-form-submit'))

    await waitFor(() => expect(mockUpdate).toHaveBeenCalled())
    const payload = mockUpdate.mock.calls[0][1]
    expect(payload.title).toBe('Renamed')
    expect('owner_id' in payload).toBe(false)
  })

  it('sets the owner on an unowned obligation when one is chosen', async () => {
    const user = userEvent.setup()
    renderForm({ requirement: EXISTING })
    await user.click(screen.getByTestId('owner-pick'))
    await user.click(screen.getByTestId('requirement-form-submit'))

    await waitFor(() => expect(mockUpdate).toHaveBeenCalled())
    expect(mockUpdate.mock.calls[0][0]).toBe(7)
    expect(mockUpdate.mock.calls[0][1].owner_id).toBe(42)
  })

  it('does not fall back to the editor as owner, which would silently reassign', async () => {
    const user = userEvent.setup()
    renderForm({ requirement: { ...EXISTING, owner_id: 3 } })
    await user.click(screen.getByTestId('requirement-form-submit'))

    await waitFor(() => expect(mockUpdate).toHaveBeenCalled())
    expect(mockUpdate.mock.calls[0][1].owner_id).toBeUndefined()
  })
})

describe('RequirementFormDialog — category is not lost on edit', () => {
  it('keeps the existing category when the list has not arrived yet', async () => {
    // The dialog renders before this resolves, which is exactly when Radix
    // reports the unmatched controlled value back as an empty string.
    let resolve: (v: unknown) => void = () => {}
    mockGet.mockReturnValue(new Promise((r) => (resolve = r)))

    const user = userEvent.setup()
    renderForm({ requirement: EXISTING })
    await user.click(screen.getByTestId('requirement-form-submit'))

    await waitFor(() => expect(mockUpdate).toHaveBeenCalled())
    expect(mockUpdate.mock.calls[0][1].taxonomy_id).toBe('03.01')
    resolve(CATEGORIES)
  })

  it('keeps a category that has since been removed from the list', async () => {
    mockGet.mockResolvedValue({
      data: {
        sections: [
          {
            taxonomy_id: '09',
            name: 'Other',
            children: [{ taxonomy_id: '09.01', name: 'Something else', active: true }],
          },
        ],
      },
    })

    const user = userEvent.setup()
    renderForm({ requirement: EXISTING })
    await waitFor(() => expect(mockGet).toHaveBeenCalled())
    await user.click(screen.getByTestId('requirement-form-submit'))

    await waitFor(() => expect(mockUpdate).toHaveBeenCalled())
    expect(mockUpdate.mock.calls[0][1].taxonomy_id).toBe('03.01')
  })

  it('still shows the retired code on the trigger rather than the placeholder', async () => {
    mockGet.mockResolvedValue({ data: { sections: [] } })
    renderForm({ requirement: EXISTING })

    await waitFor(() =>
      expect(screen.getByTestId('requirement-form-taxonomy-trigger')).toHaveTextContent('03.01'),
    )
  })
})

describe('RequirementFormDialog — category list', () => {
  it('stops submission when the category list could not be read', async () => {
    mockGet.mockRejectedValue(new Error('boom'))
    renderForm()

    await waitFor(() =>
      expect(screen.getByTestId('requirement-form-submit')).toBeDisabled(),
    )
    expect(
      screen.getByText(/category list could not be loaded/i),
    ).toBeInTheDocument()
  })

  it('does not claim a failure when the list is merely still loading', async () => {
    let resolve: (v: unknown) => void = () => {}
    mockGet.mockReturnValue(new Promise((r) => (resolve = r)))
    renderForm()

    expect(screen.queryByText(/category list could not be loaded/i)).not.toBeInTheDocument()
    resolve(CATEGORIES)
    await waitFor(() => expect(screen.getByTestId('requirement-form-submit')).toBeEnabled())
  })
})

describe('RequirementFormDialog — regulatory basis AI accept', () => {
  it('sends regulatory_standard_id after Accept then submit', async () => {
    mockSuggest.mockResolvedValue({
      data: {
        candidates: [
          {
            label: 'Regulatory Reform (Fire Safety) Order 2005',
            regulation_or_standard_code: 'FSO2005',
            standard_id: 55,
            clause_ids: [9],
            confidence: 0.94,
            rationale: 'Matched curated UK regulation map',
            source: 'curated_uk_map',
          },
        ],
        needs_clarification: false,
        clarifying_questions: [],
        confidence_threshold: 0.7,
        ai_available: false,
        notice: null,
      },
    })

    const user = userEvent.setup()
    renderForm()
    await fillRequiredCreateFields(user)

    await user.click(screen.getByTestId('regulatory-basis-suggest-button'))
    await waitFor(() => {
      expect(screen.getByTestId('regulatory-basis-accept')).toBeInTheDocument()
    })
    await user.click(screen.getByTestId('regulatory-basis-accept'))

    expect(screen.getByTestId('requirement-form-basis-input')).toHaveValue(
      'Regulatory Reform (Fire Safety) Order 2005',
    )
    expect(screen.getByTestId('requirement-form-basis-link-chip')).toBeInTheDocument()

    await user.click(screen.getByTestId('requirement-form-submit'))
    await waitFor(() => expect(mockCreate).toHaveBeenCalled())
    expect(mockCreate.mock.calls[0][0]).toMatchObject({
      regulatory_basis: 'Regulatory Reform (Fire Safety) Order 2005',
      regulatory_standard_id: 55,
      regulatory_clause_id: 9,
    })
  })

  it('clears the structured link when the basis text is hand-edited', async () => {
    mockSuggest.mockResolvedValue({
      data: {
        candidates: [
          {
            label: 'Regulatory Reform (Fire Safety) Order 2005',
            regulation_or_standard_code: 'FSO2005',
            standard_id: 55,
            clause_ids: [],
            confidence: 0.94,
            rationale: 'Matched',
            source: 'curated_uk_map',
          },
        ],
        needs_clarification: false,
        clarifying_questions: [],
        confidence_threshold: 0.7,
        ai_available: false,
        notice: null,
      },
    })

    const user = userEvent.setup()
    renderForm()
    await fillRequiredCreateFields(user)
    await user.click(screen.getByTestId('regulatory-basis-suggest-button'))
    await waitFor(() => screen.getByTestId('regulatory-basis-accept'))
    await user.click(screen.getByTestId('regulatory-basis-accept'))

    const basis = screen.getByTestId('requirement-form-basis-input')
    await user.clear(basis)
    await user.type(basis, 'Something typed by hand')
    await user.click(screen.getByTestId('requirement-form-submit'))

    await waitFor(() => expect(mockCreate).toHaveBeenCalled())
    expect(mockCreate.mock.calls[0][0]).toMatchObject({
      regulatory_basis: 'Something typed by hand',
      regulatory_standard_id: null,
      regulatory_clause_id: null,
    })
  })
})
