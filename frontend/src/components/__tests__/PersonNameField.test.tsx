import { useState, type ComponentProps } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { workforceApi } from '../../api/client'
import { PersonNameField, type PersonNameValue } from '../PersonNameField'

function ControlledPersonNameField(
  props: Omit<ComponentProps<typeof PersonNameField>, 'value' | 'onChange'> & {
    initialValue?: PersonNameValue | null
    onChange?: (value: PersonNameValue | null) => void
  },
) {
  const { initialValue = null, onChange, ...rest } = props
  const [value, setValue] = useState<PersonNameValue | null>(initialValue)
  return (
    <PersonNameField
      {...rest}
      value={value}
      onChange={(next) => {
        setValue(next)
        onChange?.(next)
      }}
    />
  )
}

vi.mock('../../api/client', () => ({
  workforceApi: {
    listEngineers: vi.fn(),
  },
}))

const ROSTER_ONLY = {
  id: 31,
  display_name: 'Warwick, C',
  job_title: 'Technician',
  user_id: null,
  is_active: true,
  external_id: 'ext-31',
}

const WITH_LOGIN = {
  id: 12,
  display_name: 'Harris, D',
  job_title: 'Manager',
  user_id: 4,
  is_active: true,
  external_id: 'ext-12',
  linked_user: { id: 4, email: 'david@example.com', full_name: 'David Harris' },
}

function mockRoster(items: unknown[]) {
  vi.mocked(workforceApi.listEngineers).mockResolvedValue({
    data: { items, total: items.length },
  } as never)
}

function mockRosterError() {
  vi.mocked(workforceApi.listEngineers).mockRejectedValue(new Error('network'))
}

async function openField(placeholder = 'Search employees…') {
  const input = await screen.findByRole('combobox', { name: placeholder })
  fireEvent.focus(input)
  return input
}

describe('PersonNameField', () => {
  beforeEach(() => {
    vi.mocked(workforceApi.listEngineers).mockReset()
  })

  it('loads active employees and selects one with engineerId + displayName', async () => {
    mockRoster([WITH_LOGIN, ROSTER_ONLY])
    const onChange = vi.fn()
    render(<ControlledPersonNameField onChange={onChange} />)

    await openField()
    const listbox = await screen.findByRole('listbox')
    fireEvent.click(within(listbox).getByRole('option', { name: /Harris, D/ }))

    await waitFor(() =>
      expect(onChange).toHaveBeenCalledWith({
        displayName: 'Harris, D',
        engineerId: 12,
        userId: 4,
      }),
    )
    expect(screen.getByTestId('person-name-field-linked')).toHaveTextContent('Linked employee')
  })

  it('filters the roster by typed query', async () => {
    mockRoster([WITH_LOGIN, ROSTER_ONLY])
    render(<ControlledPersonNameField />)

    const input = await openField()
    fireEvent.change(input, { target: { value: 'Warwick' } })

    const listbox = await screen.findByRole('listbox')
    expect(within(listbox).getByRole('option', { name: /Warwick, C/ })).toBeInTheDocument()
    expect(within(listbox).queryByRole('option', { name: /Harris, D/ })).not.toBeInTheDocument()
  })

  describe('hybrid mode', () => {
    it('emits free-text while typing and offers an explicit use-as-typed action', async () => {
      mockRoster([WITH_LOGIN])
      const onChange = vi.fn()
      render(<ControlledPersonNameField mode="hybrid" onChange={onChange} />)

      const input = await openField()
      fireEvent.change(input, { target: { value: 'Jane External' } })

      await waitFor(() =>
        expect(onChange).toHaveBeenLastCalledWith({
          displayName: 'Jane External',
          engineerId: null,
          userId: null,
        }),
      )

      fireEvent.click(await screen.findByTestId('person-name-field-use-free-text'))
      await waitFor(() =>
        expect(onChange).toHaveBeenLastCalledWith({
          displayName: 'Jane External',
          engineerId: null,
          userId: null,
        }),
      )
      expect(screen.getByTestId('person-name-field-free-text')).toHaveTextContent(
        'Typed name (not linked to an employee)',
      )
    })

    it('commits free-text on Enter when the use-as-typed option is available', async () => {
      mockRoster([])
      const onChange = vi.fn()
      render(<ControlledPersonNameField mode="hybrid" onChange={onChange} />)

      const input = await openField()
      fireEvent.change(input, { target: { value: 'Walk-in witness' } })
      fireEvent.keyDown(input, { key: 'Enter' })

      await waitFor(() =>
        expect(onChange).toHaveBeenLastCalledWith({
          displayName: 'Walk-in witness',
          engineerId: null,
          userId: null,
        }),
      )
    })
  })

  describe('employeesOnly mode', () => {
    it('does not keep free-text while typing and hides the use-as-typed action', async () => {
      mockRoster([ROSTER_ONLY])
      const onChange = vi.fn()
      render(<ControlledPersonNameField mode="employeesOnly" onChange={onChange} />)

      const input = await openField()
      fireEvent.change(input, { target: { value: 'Nobody Here' } })

      await waitFor(() => expect(onChange).toHaveBeenLastCalledWith(null))
      expect(screen.queryByTestId('person-name-field-use-free-text')).not.toBeInTheDocument()
      expect(await screen.findByText('No employees found')).toBeInTheDocument()
    })

    it('still allows selecting a roster employee', async () => {
      mockRoster([ROSTER_ONLY])
      const onChange = vi.fn()
      render(<ControlledPersonNameField mode="employeesOnly" onChange={onChange} />)

      await openField()
      fireEvent.click(await screen.findByRole('option', { name: /Warwick, C/ }))

      await waitFor(() =>
        expect(onChange).toHaveBeenCalledWith({
          displayName: 'Warwick, C',
          engineerId: 31,
          userId: null,
        }),
      )
    })
  })

  it('shows an honest loading state while the roster loads', async () => {
    let resolveRoster: (value: unknown) => void = () => {}
    vi.mocked(workforceApi.listEngineers).mockReturnValue(
      new Promise((resolve) => {
        resolveRoster = resolve
      }) as never,
    )

    render(<ControlledPersonNameField />)
    await openField()
    expect(await screen.findByText('Loading employees…')).toBeInTheDocument()

    resolveRoster({ data: { items: [ROSTER_ONLY], total: 1 } })
    expect(await screen.findByRole('option', { name: /Warwick, C/ })).toBeInTheDocument()
  })

  it('shows an honest error when the roster fails to load', async () => {
    mockRosterError()
    render(<ControlledPersonNameField mode="hybrid" />)

    await openField()
    expect(
      await screen.findByText('Could not load employees. Try again, or type a name.'),
    ).toBeInTheDocument()
  })

  it('clears the value via the clear control', async () => {
    mockRoster([WITH_LOGIN])
    const onChange = vi.fn()
    render(
      <ControlledPersonNameField
        label="Witness"
        initialValue={{ displayName: 'Harris, D', engineerId: 12 }}
        onChange={onChange}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Clear Witness' }))
    await waitFor(() => expect(onChange).toHaveBeenCalledWith(null))
  })

  it('wires label to the combobox for accessibility', async () => {
    mockRoster([])
    render(<ControlledPersonNameField label="Person name" required />)

    const input = await screen.findByRole('combobox', { name: /Person name/ })
    expect(input).toBeRequired()
    expect(input).toHaveAttribute('aria-haspopup', 'listbox')
    expect(input).toHaveAttribute('aria-controls')
  })
})
