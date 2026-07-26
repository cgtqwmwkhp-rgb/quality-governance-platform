import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { FormField } from '../FormField'
import { FormNotice } from '../FormNotice'
import { SubmitButton } from '../SubmitButton'
import { UnsavedChangesDialog } from '../UnsavedChangesDialog'
import { useFormController } from '../useFormController'
import { useUnsavedChangesGuard } from '../useUnsavedChangesGuard'
import type { FieldSpecs } from '../formValidation'

describe('FormField', () => {
  it('marks a required field visually and programmatically from one prop', () => {
    render(
      <FormField id="thing" label="Thing" required>
        {(control) => <input {...control} />}
      </FormField>,
    )

    const input = screen.getByLabelText(/Thing/)
    expect(input).toBeRequired()
    expect(input).toHaveAttribute('aria-required', 'true')
    // The asterisk and the attribute come from the same prop, so they cannot disagree.
    expect(screen.getByText('*')).toBeInTheDocument()
  })

  it('omits the DOM required attribute for non-native controls but keeps aria-required', () => {
    render(
      <FormField id="thing" label="Thing" required nativeControl={false}>
        {(control) => (
          <button type="button" {...control}>
            choose
          </button>
        )}
      </FormField>,
    )

    const trigger = screen.getByRole('button', { name: /Thing/ })
    expect(trigger).not.toHaveAttribute('required')
    expect(trigger).toHaveAttribute('aria-required', 'true')
  })

  it('renders the error next to the control, announced and wired to the input', () => {
    render(
      <FormField id="thing" label="Thing" required error="Thing is required">
        {(control) => <input {...control} />}
      </FormField>,
    )

    const input = screen.getByLabelText(/Thing/)
    const error = screen.getByRole('alert')
    expect(error).toHaveTextContent('Thing is required')
    expect(input).toHaveAttribute('aria-invalid', 'true')
    expect(input.getAttribute('aria-describedby')).toContain('thing-error')
    expect(error).toHaveAttribute('id', 'thing-error')
  })

  it('describes the control by both hint and error when both are present', () => {
    render(
      <FormField id="thing" label="Thing" hint="Some guidance" error="Bad">
        {(control) => <input {...control} />}
      </FormField>,
    )
    expect(screen.getByLabelText('Thing')).toHaveAttribute(
      'aria-describedby',
      'thing-hint thing-error',
    )
  })

  it('leaves an optional field free of required signalling', () => {
    render(
      <FormField id="thing" label="Thing">
        {(control) => <input {...control} />}
      </FormField>,
    )
    const input = screen.getByLabelText('Thing')
    expect(input).not.toBeRequired()
    expect(input).not.toHaveAttribute('aria-required')
    expect(screen.queryByText('*')).not.toBeInTheDocument()
  })
})

describe('FormNotice', () => {
  it('announces errors assertively and stays in the document', () => {
    render(<FormNotice tone="error">Save failed</FormNotice>)
    const notice = screen.getByRole('alert')
    expect(notice).toHaveTextContent('Save failed')
    expect(notice).toHaveAttribute('aria-live', 'assertive')
  })

  it('uses a polite status role for non-error tones', () => {
    render(<FormNotice tone="warning">Saved offline</FormNotice>)
    expect(screen.getByRole('status')).toHaveAttribute('aria-live', 'polite')
  })
})

describe('SubmitButton', () => {
  it('disables itself and announces progress while in flight', () => {
    render(
      <SubmitButton submitting submittingLabel="Creating…">
        Create
      </SubmitButton>,
    )
    const button = screen.getByRole('button')
    expect(button).toBeDisabled()
    expect(button).toHaveAttribute('aria-busy', 'true')
    expect(button).toHaveTextContent('Creating…')
    expect(screen.getByRole('status')).toHaveTextContent('Creating…')
  })

  it('is a submit button that stays enabled when idle', () => {
    render(
      <SubmitButton submitting={false} submittingLabel="Creating…">
        Create
      </SubmitButton>,
    )
    const button = screen.getByRole('button', { name: 'Create' })
    expect(button).toHaveAttribute('type', 'submit')
    expect(button).toBeEnabled()
    expect(button).not.toHaveAttribute('aria-busy')
  })
})

const FIELDS: FieldSpecs<'name' | 'reason'> = {
  name: { label: 'Name', required: true },
  reason: { label: 'Reason', required: true },
}

function ControllerHarness({
  onSubmit,
}: {
  onSubmit: (values: Record<string, unknown>) => void | Promise<void>
}) {
  const [values, setValues] = useState<{ name: string; reason: string }>({ name: '', reason: '' })
  const form = useFormController({
    fields: FIELDS,
    values,
    controlId: (field) => `harness-${field}`,
    onSubmit,
  })

  return (
    <form {...form.formProps}>
      <FormField {...form.fieldProps('name')}>
        {(control) => (
          <input
            {...control}
            value={values.name}
            onChange={(event) => setValues((prev) => ({ ...prev, name: event.target.value }))}
          />
        )}
      </FormField>
      <FormField {...form.fieldProps('reason')}>
        {(control) => (
          <input
            {...control}
            value={values.reason}
            onChange={(event) => setValues((prev) => ({ ...prev, reason: event.target.value }))}
          />
        )}
      </FormField>
      {form.submitError ? <FormNotice tone="error">{form.submitError}</FormNotice> : null}
      <SubmitButton submitting={form.submitting} submittingLabel="Saving…">
        Save
      </SubmitButton>
    </form>
  )
}

describe('useFormController', () => {
  it('blocks submit, shows every error, and moves focus to the first invalid control', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    render(<ControllerHarness onSubmit={onSubmit} />)

    await user.click(screen.getByRole('button', { name: 'Save' }))

    expect(onSubmit).not.toHaveBeenCalled()
    expect(screen.getByTestId('harness-name-error')).toHaveTextContent('Name is required')
    expect(screen.getByTestId('harness-reason-error')).toHaveTextContent('Reason is required')
    expect(document.activeElement).toBe(screen.getByLabelText(/Name/))
  })

  it('clears a field error as soon as the user fixes that field', async () => {
    const user = userEvent.setup()
    render(<ControllerHarness onSubmit={vi.fn()} />)

    await user.click(screen.getByRole('button', { name: 'Save' }))
    expect(screen.getByTestId('harness-name-error')).toBeInTheDocument()

    await user.type(screen.getByLabelText(/Name/), 'Ada')
    expect(screen.queryByTestId('harness-name-error')).not.toBeInTheDocument()
    expect(screen.getByTestId('harness-reason-error')).toBeInTheDocument()
  })

  it('submits once when valid and cannot be double-fired while in flight', async () => {
    const user = userEvent.setup()
    let release: () => void = () => {}
    const onSubmit = vi.fn(
      () =>
        new Promise<void>((resolve) => {
          release = resolve
        }),
    )
    render(<ControllerHarness onSubmit={onSubmit} />)

    await user.type(screen.getByLabelText(/Name/), 'Ada')
    await user.type(screen.getByLabelText(/Reason/), 'Because')
    await user.click(screen.getByRole('button', { name: 'Save' }))

    const button = screen.getByRole('button')
    expect(button).toBeDisabled()
    expect(button).toHaveTextContent('Saving…')

    await user.click(button)
    expect(onSubmit).toHaveBeenCalledTimes(1)

    release()
    await waitFor(() => expect(screen.getByRole('button')).toBeEnabled())
  })

  it('keeps a failure message on the page instead of flashing it', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn().mockRejectedValue(new Error('Network unreachable'))
    render(<ControllerHarness onSubmit={onSubmit} />)

    await user.type(screen.getByLabelText(/Name/), 'Ada')
    await user.type(screen.getByLabelText(/Reason/), 'Because')
    await user.click(screen.getByRole('button', { name: 'Save' }))

    const notice = await screen.findByRole('alert')
    expect(notice).toHaveTextContent('Network unreachable')

    // Still there after any toast would have auto-dismissed.
    await new Promise((resolve) => setTimeout(resolve, 50))
    expect(screen.getByRole('alert')).toHaveTextContent('Network unreachable')
  })
})

function GuardHarness({ dirty, onDiscard }: { dirty: boolean; onDiscard: () => void }) {
  const guard = useUnsavedChangesGuard({ dirty, onDiscard })
  return (
    <div>
      <button type="button" onClick={guard.requestClose}>
        Close
      </button>
      <UnsavedChangesDialog guard={guard} />
    </div>
  )
}

describe('useUnsavedChangesGuard', () => {
  it('closes straight away when the form is untouched', async () => {
    const user = userEvent.setup()
    const onDiscard = vi.fn()
    render(<GuardHarness dirty={false} onDiscard={onDiscard} />)

    await user.click(screen.getByRole('button', { name: 'Close' }))
    expect(onDiscard).toHaveBeenCalledTimes(1)
    expect(screen.queryByTestId('unsaved-changes-dialog')).not.toBeInTheDocument()
  })

  it('asks before discarding typed work, and keeps it when the user backs out', async () => {
    const user = userEvent.setup()
    const onDiscard = vi.fn()
    render(<GuardHarness dirty onDiscard={onDiscard} />)

    await user.click(screen.getByRole('button', { name: 'Close' }))
    expect(await screen.findByTestId('unsaved-changes-dialog')).toBeInTheDocument()
    expect(onDiscard).not.toHaveBeenCalled()

    await user.click(screen.getByTestId('unsaved-changes-dialog-keep'))
    await waitFor(() =>
      expect(screen.queryByTestId('unsaved-changes-dialog')).not.toBeInTheDocument(),
    )
    expect(onDiscard).not.toHaveBeenCalled()
  })

  it('discards only after explicit confirmation', async () => {
    const user = userEvent.setup()
    const onDiscard = vi.fn()
    render(<GuardHarness dirty onDiscard={onDiscard} />)

    await user.click(screen.getByRole('button', { name: 'Close' }))
    await user.click(await screen.findByTestId('unsaved-changes-dialog-discard'))
    expect(onDiscard).toHaveBeenCalledTimes(1)
  })
})
