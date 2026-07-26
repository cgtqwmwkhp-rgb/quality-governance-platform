import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

vi.mock('framer-motion', () => {
  const Passthrough = ({ children, ...props }: { children?: ReactNode; [key: string]: unknown }) => {
    const { initial: _i, animate: _a, exit: _e, transition: _t, ...rest } = props
    return <div {...rest}>{children}</div>
  }
  return {
    AnimatePresence: ({ children }: { children?: ReactNode }) => <>{children}</>,
    motion: new Proxy({}, { get: () => Passthrough }),
  }
})

vi.mock('../../../hooks/useVoiceToText', () => ({
  useVoiceToText: () => ({ isListening: false, isSupported: false, toggleListening: vi.fn() }),
}))

vi.mock('../../../hooks/useGeolocation', () => ({
  useGeolocation: () => ({ isLoading: false, getLocationString: vi.fn(), error: null }),
}))

import DynamicFormRenderer, {
  MAX_UPLOAD_BYTES,
  draftHasUserInput,
  isAllowedUploadFile,
  stripNonSerializableValues,
  validateUploadFiles,
} from '../DynamicFormRenderer'
import type { DynamicFormData } from '../DynamicFormRenderer'
import type { FormTemplate } from '../../../services/api'

// ==================== Fixtures ====================

function field(overrides: Record<string, unknown>) {
  return {
    id: 1,
    name: 'field',
    label: 'Field',
    field_type: 'text',
    order: 0,
    is_required: false,
    width: 'full',
    ...overrides,
  }
}

function threeStepTemplate(): FormTemplate {
  return {
    id: 1,
    name: 'Customer Complaint',
    slug: 'complaint',
    form_type: 'complaint',
    version: 1,
    is_active: true,
    is_published: true,
    allow_drafts: true,
    allow_attachments: true,
    require_signature: false,
    auto_assign_reference: true,
    notify_on_submit: true,
    steps: [
      {
        id: 1,
        name: 'Step One',
        order: 0,
        fields: [
          field({ id: 1, name: 'alpha', label: 'Alpha', is_required: true }),
          field({ id: 4, name: 'delta', label: 'Delta', order: 1 }),
        ],
      },
      {
        id: 2,
        name: 'Step Two',
        order: 1,
        fields: [field({ id: 2, name: 'bravo', label: 'Bravo', is_required: true })],
      },
      {
        id: 3,
        name: 'Step Three',
        order: 2,
        fields: [field({ id: 3, name: 'charlie', label: 'Charlie' })],
      },
    ],
  }
}

function uploadTemplate(fieldType: 'file' | 'image'): FormTemplate {
  return {
    ...threeStepTemplate(),
    slug: `upload-${fieldType}`,
    steps: [
      {
        id: 1,
        name: 'Evidence',
        order: 0,
        fields: [field({ id: 1, name: 'photos', label: 'Evidence', field_type: fieldType })],
      },
    ],
  }
}

function renderForm(overrides: Partial<Parameters<typeof DynamicFormRenderer>[0]> = {}) {
  const onSubmit = vi.fn().mockResolvedValue({ reference_number: 'CMP-1' })
  const props = { template: threeStepTemplate(), onSubmit, ...overrides }
  const utils = render(<DynamicFormRenderer {...props} />)
  return { ...utils, onSubmit, props }
}

/** Labels in FieldRenderer are not associated with their input, so scope by the field wrapper. */
function fieldInput(name: string): HTMLElement {
  return within(screen.getByTestId(`field-${name}`)).getByRole('textbox')
}

async function findFieldInput(name: string): Promise<HTMLElement> {
  const wrapper = await screen.findByTestId(`field-${name}`)
  return within(wrapper).getByRole('textbox')
}

function makeFile(name: string, type: string, size: number): File {
  const file = new File(['x'], name, { type })
  Object.defineProperty(file, 'size', { value: size })
  return file
}

const continueButton = () => screen.getByRole('button', { name: /continue/i })

beforeEach(() => {
  localStorage.clear()
  vi.clearAllMocks()
})

// ==================== PX-282: step navigation & validation-on-next ====================

describe('PX-282 stepper navigation', () => {
  it('blocks Continue while the current step has a required field empty', async () => {
    const user = userEvent.setup()
    renderForm()

    await user.click(continueButton())

    expect(await screen.findByText('Alpha is required')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Step One' })).toBeInTheDocument()
  })

  it('advances exactly one step per Continue, even when clicked twice before re-render', async () => {
    const user = userEvent.setup()
    renderForm()

    await user.type(fieldInput('alpha'), 'first answer')

    const button = continueButton()
    // Both clicks land in one batch, as a rapid double-click can. The old
    // handler applied `prev + 1` per call and jumped straight to Step Three,
    // skipping Step Two and its required field entirely.
    act(() => {
      fireEvent.click(button)
      fireEvent.click(button)
    })

    expect(await screen.findByRole('heading', { name: 'Step Two' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Step Three' })).not.toBeInTheDocument()
  })

  it('cannot advance past the final step', async () => {
    const user = userEvent.setup()
    renderForm()

    await user.type(fieldInput('alpha'), 'first answer')
    await user.click(continueButton())
    await user.type(await findFieldInput('bravo'), 'second answer')
    await user.click(continueButton())

    expect(await screen.findByRole('heading', { name: 'Step Three' })).toBeInTheDocument()
    // The final step offers Submit, never Continue.
    expect(screen.queryByRole('button', { name: /continue/i })).not.toBeInTheDocument()
    expect(screen.getByTestId('submit-report-btn')).toBeInTheDocument()
  })

  it('clears validation errors from the step being left when going Back', async () => {
    const user = userEvent.setup()
    renderForm()

    await user.type(fieldInput('alpha'), 'first answer')
    await user.click(continueButton())

    // Fail validation on step two.
    await user.click(await screen.findByRole('button', { name: /continue/i }))
    expect(await screen.findByText('Bravo is required')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /back/i }))

    expect(await screen.findByRole('heading', { name: 'Step One' })).toBeInTheDocument()
    expect(screen.queryByText('Bravo is required')).not.toBeInTheDocument()
  })

  it('does not keep showing a failed-submission banner after navigating Back', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn().mockRejectedValue(new Error('network down'))
    renderForm({ onSubmit })

    await user.type(fieldInput('alpha'), 'first answer')
    await user.click(continueButton())
    await user.type(await findFieldInput('bravo'), 'second answer')
    await user.click(continueButton())
    await screen.findByRole('heading', { name: 'Step Three' })

    await user.click(screen.getByTestId('submit-report-btn'))
    expect(await screen.findByText(/submission failed/i)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /back/i }))

    // The banner belongs to the submit attempt, not to Step Two.
    expect(await screen.findByRole('heading', { name: 'Step Two' })).toBeInTheDocument()
    expect(screen.queryByText(/submission failed/i)).not.toBeInTheDocument()
  })

  it('does not mutate the caller template when sorting steps and fields', () => {
    const template = threeStepTemplate()
    // Present the steps out of order; the renderer must sort a copy.
    template.steps = [template.steps[2], template.steps[0], template.steps[1]]
    const originalOrder = template.steps.map((s) => s.id)

    renderForm({ template })

    expect(template.steps.map((s) => s.id)).toEqual(originalOrder)
    expect(screen.getByRole('heading', { name: 'Step One' })).toBeInTheDocument()
  })

  it('renders a fallback instead of crashing when a template has no steps', () => {
    renderForm({ template: { ...threeStepTemplate(), steps: [] } })

    expect(screen.getByText(/no steps configured/i)).toBeInTheDocument()
  })
})

// ==================== PX-329: step indicator state ====================

describe('PX-329 step indicator', () => {
  async function advanceToStepThree(user: ReturnType<typeof userEvent.setup>) {
    await user.type(fieldInput('alpha'), 'first answer')
    await user.click(continueButton())
    await user.type(await findFieldInput('bravo'), 'second answer')
    await user.click(continueButton())
    await screen.findByRole('heading', { name: 'Step Three' })
  }

  it('keeps completed steps marked and clickable after navigating back', async () => {
    const user = userEvent.setup()
    renderForm()
    await advanceToStepThree(user)

    await user.click(screen.getByTestId('step-indicator-0'))
    expect(await screen.findByRole('heading', { name: 'Step One' })).toBeInTheDocument()

    // Steps already completed must stay enabled — previously they reverted to
    // "future" state and the user had to click Continue through them again.
    expect(screen.getByTestId('step-indicator-1')).toBeEnabled()
    expect(screen.getByTestId('step-indicator-2')).toBeEnabled()
    // A completed step shows a tick rather than its number.
    expect(within(screen.getByTestId('step-indicator-1')).queryByText('2')).not.toBeInTheDocument()
  })

  it('allows jumping forward to a step already visited', async () => {
    const user = userEvent.setup()
    renderForm()
    await advanceToStepThree(user)

    await user.click(screen.getByTestId('step-indicator-0'))
    await screen.findByRole('heading', { name: 'Step One' })

    await user.click(screen.getByTestId('step-indicator-2'))

    expect(await screen.findByRole('heading', { name: 'Step Three' })).toBeInTheDocument()
  })

  it('keeps never-visited steps disabled', async () => {
    const user = userEvent.setup()
    renderForm()

    expect(screen.getByTestId('step-indicator-1')).toBeDisabled()
    expect(screen.getByTestId('step-indicator-2')).toBeDisabled()

    await user.type(fieldInput('alpha'), 'first answer')
    await user.click(continueButton())
    await screen.findByRole('heading', { name: 'Step Two' })

    expect(screen.getByTestId('step-indicator-1')).toBeEnabled()
    expect(screen.getByTestId('step-indicator-2')).toBeDisabled()
  })

  it('marks the current step with aria-current', () => {
    renderForm()

    expect(screen.getByTestId('step-indicator-0')).toHaveAttribute('aria-current', 'step')
    expect(screen.getByTestId('step-indicator-1')).not.toHaveAttribute('aria-current')
  })
})

// ==================== PX-300: draft restore ====================

describe('PX-300 draft hydration', () => {
  // Mirrors the portal page, which always prefills something.
  const PREFILL: DynamicFormData = { delta: 'prefilled delta' }

  function seedDraft(data: DynamicFormData, slug = 'complaint') {
    localStorage.setItem(
      `draft_${slug}`,
      JSON.stringify({ data, savedAt: new Date().toISOString() }),
    )
  }

  it('offers and restores a saved draft even though the form is prefilled', async () => {
    const user = userEvent.setup()
    seedDraft({ ...PREFILL, alpha: 'saved answer' })

    // Non-empty initialData used to make the hydration condition permanently
    // false, so the prompt never appeared and the draft was unreachable.
    renderForm({ initialData: PREFILL })

    expect(await screen.findByText('Draft found')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /load draft/i }))

    await waitFor(() => expect(fieldInput('alpha')).toHaveValue('saved answer'))
  })

  it('keeps prefilled values that the draft never touched', async () => {
    const user = userEvent.setup()
    seedDraft({ alpha: 'saved answer' })

    renderForm({ initialData: PREFILL })
    await user.click(await screen.findByRole('button', { name: /load draft/i }))

    await waitFor(() => expect(fieldInput('alpha')).toHaveValue('saved answer'))
    expect(fieldInput('delta')).toHaveValue('prefilled delta')
  })

  it('does not prompt for a genuinely new form whose stored draft is only the prefill', async () => {
    seedDraft({ ...PREFILL })

    renderForm({ initialData: PREFILL })

    await waitFor(() =>
      expect(screen.getByRole('heading', { name: 'Step One' })).toBeInTheDocument(),
    )
    expect(screen.queryByText('Draft found')).not.toBeInTheDocument()
  })

  it('does not prompt when no draft is stored at all', async () => {
    renderForm({ initialData: PREFILL })

    await waitFor(() =>
      expect(screen.getByRole('heading', { name: 'Step One' })).toBeInTheDocument(),
    )
    expect(screen.queryByText('Draft found')).not.toBeInTheDocument()
  })

  it('discarding a draft removes it from storage and leaves the prefilled form', async () => {
    const user = userEvent.setup()
    seedDraft({ ...PREFILL, alpha: 'saved answer' })

    renderForm({ initialData: PREFILL })
    await user.click(await screen.findByRole('button', { name: /start fresh/i }))

    expect(localStorage.getItem('draft_complaint')).toBeNull()
    expect(fieldInput('alpha')).toHaveValue('')
    expect(fieldInput('delta')).toHaveValue('prefilled delta')
  })

  it('does not offer a draft when the template disallows drafts', async () => {
    seedDraft({ ...PREFILL, alpha: 'saved answer' })

    renderForm({ template: { ...threeStepTemplate(), allow_drafts: false }, initialData: PREFILL })

    await waitFor(() =>
      expect(screen.getByRole('heading', { name: 'Step One' })).toBeInTheDocument(),
    )
    expect(screen.queryByText('Draft found')).not.toBeInTheDocument()
  })
})

describe('draft helpers', () => {
  it('draftHasUserInput ignores prefill-equal and empty values', () => {
    const baseline = { a: '1', b: 'x' }

    expect(draftHasUserInput(null, baseline)).toBe(false)
    expect(draftHasUserInput({ a: '1', b: 'x' }, baseline)).toBe(false)
    expect(draftHasUserInput({ a: '1', c: '' }, baseline)).toBe(false)
    expect(draftHasUserInput({ a: '1', c: [] }, baseline)).toBe(false)
    expect(draftHasUserInput({ a: '2' }, baseline)).toBe(true)
    expect(draftHasUserInput({ a: '1', c: 'typed' }, baseline)).toBe(true)
  })

  it('stripNonSerializableValues drops files that would come back as empty objects', () => {
    const file = makeFile('a.png', 'image/png', 10)

    expect(
      stripNonSerializableValues({
        note: 'keep me',
        single: file,
        photos: [file],
        tags: ['a', 'b'],
      }),
    ).toEqual({ note: 'keep me', tags: ['a', 'b'] })
  })
})

// ==================== PX-325 / PX-326: upload validation ====================

describe('PX-325 / PX-326 upload validation helpers', () => {
  it('accepts images for an image field and rejects other types', () => {
    expect(isAllowedUploadFile(makeFile('a.png', 'image/png', 10), true)).toBe(true)
    expect(isAllowedUploadFile(makeFile('a.pdf', 'application/pdf', 10), true)).toBe(false)
  })

  it('accepts documents as well as images for a file field', () => {
    expect(isAllowedUploadFile(makeFile('a.pdf', 'application/pdf', 10), false)).toBe(true)
    expect(isAllowedUploadFile(makeFile('a.png', 'image/png', 10), false)).toBe(true)
    expect(isAllowedUploadFile(makeFile('a.exe', 'application/x-msdownload', 10), false)).toBe(false)
  })

  it('falls back to the file extension when the browser reports no MIME type', () => {
    expect(isAllowedUploadFile(makeFile('photo.HEIC', '', 10), true)).toBe(true)
    expect(isAllowedUploadFile(makeFile('notes.docx', '', 10), false)).toBe(true)
    expect(isAllowedUploadFile(makeFile('payload.exe', '', 10), false)).toBe(false)
  })

  it('rejects files over the size limit and reports the actual size', () => {
    const { accepted, errors } = validateUploadFiles(
      [makeFile('huge.png', 'image/png', MAX_UPLOAD_BYTES + 1)],
      { imagesOnly: true },
    )

    expect(accepted).toEqual([])
    expect(errors[0]).toContain('huge.png')
    expect(errors[0]).toContain('10.0MB')
  })

  it('keeps the valid files from a mixed selection and explains each rejection', () => {
    const good = makeFile('ok.png', 'image/png', 1024)
    const wrongType = makeFile('bad.exe', 'application/x-msdownload', 1024)
    const tooBig = makeFile('huge.png', 'image/png', MAX_UPLOAD_BYTES + 1)

    const { accepted, errors } = validateUploadFiles([good, wrongType, tooBig], {
      imagesOnly: true,
    })

    expect(accepted).toEqual([good])
    expect(errors).toHaveLength(2)
    expect(errors.join(' ')).toContain('bad.exe')
    expect(errors.join(' ')).toContain('huge.png')
  })
})

describe('PX-325 / PX-326 upload validation in the form', () => {
  // `accept` is only a hint — a user can pick "All Files" in the OS dialog, so
  // the component must still validate what actually arrives.
  const uploadUser = () => userEvent.setup({ applyAccept: false })

  it('shows an inline error and keeps a rejected file out of the form', async () => {
    const user = uploadUser()
    renderForm({ template: uploadTemplate('image') })

    await user.upload(
      screen.getByTestId('file-input-photos'),
      makeFile('report.pdf', 'application/pdf', 1024),
    )

    expect(await screen.findByTestId('upload-errors-photos')).toHaveTextContent(
      /report\.pdf.*is not an image/i,
    )
    expect(screen.queryByText('report.pdf')).not.toBeInTheDocument()
  })

  it('rejects an oversized image with a size-specific message', async () => {
    const user = uploadUser()
    renderForm({ template: uploadTemplate('image') })

    await user.upload(
      screen.getByTestId('file-input-photos'),
      makeFile('huge.png', 'image/png', MAX_UPLOAD_BYTES + 1),
    )

    expect(await screen.findByTestId('upload-errors-photos')).toHaveTextContent(
      /over the 10\.0MB limit/i,
    )
  })

  it('accepts a valid file and lists it', async () => {
    const user = uploadUser()
    renderForm({ template: uploadTemplate('image') })

    await user.upload(
      screen.getByTestId('file-input-photos'),
      makeFile('scene.png', 'image/png', 2048),
    )

    expect(await screen.findByText('scene.png')).toBeInTheDocument()
    expect(screen.queryByTestId('upload-errors-photos')).not.toBeInTheDocument()
  })

  it('states the accepted types and size limit up front', () => {
    renderForm({ template: uploadTemplate('file') })

    expect(
      screen.getByText('Images, PDF, Word, Excel, CSV or text. Up to 10.0MB per file.'),
    ).toBeInTheDocument()
  })
})

// ==================== PX-281 wiring: page-supplied validation ====================

describe('validateData integration', () => {
  it('surfaces a page validation error on Continue for a field on the current step', async () => {
    const user = userEvent.setup()
    renderForm({
      validateData: (data: DynamicFormData) =>
        String(data.alpha ?? '').length > 5 ? { alpha: 'Alpha is too long' } : {},
    })

    await user.type(fieldInput('alpha'), 'far too long')
    await user.click(continueButton())

    expect(await screen.findByText('Alpha is too long')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Step One' })).toBeInTheDocument()
  })

  it('blocks submit and returns to the offending earlier step', async () => {
    const user = userEvent.setup()
    let enforce = false
    const { onSubmit } = renderForm({
      validateData: (data: DynamicFormData) =>
        enforce && data.alpha ? { alpha: 'Alpha is not acceptable' } : {},
    })

    await user.type(fieldInput('alpha'), 'value')
    await user.click(continueButton())
    await user.type(await findFieldInput('bravo'), 'value')
    await user.click(continueButton())
    await screen.findByRole('heading', { name: 'Step Three' })

    // The rule only starts failing at submit time, standing in for a value the
    // API would reject that was captured two steps earlier.
    enforce = true
    await user.click(screen.getByTestId('submit-report-btn'))

    expect(onSubmit).not.toHaveBeenCalled()
    expect(await screen.findByRole('heading', { name: 'Step One' })).toBeInTheDocument()
    expect(screen.getByText('Alpha is not acceptable')).toBeInTheDocument()
  })

  it('submits when page validation passes', async () => {
    const user = userEvent.setup()
    const { onSubmit } = renderForm({ validateData: () => ({}) })

    await user.type(fieldInput('alpha'), 'value')
    await user.click(continueButton())
    await user.type(await findFieldInput('bravo'), 'value')
    await user.click(continueButton())
    await screen.findByRole('heading', { name: 'Step Three' })

    await user.click(screen.getByTestId('submit-report-btn'))

    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1))
    expect(await screen.findByText('CMP-1')).toBeInTheDocument()
  })
})
