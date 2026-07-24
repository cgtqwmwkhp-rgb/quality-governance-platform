import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { CaseWitnessesPanel } from '../CaseWitnessesPanel'
import type { Witness } from '../../../api/client'

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (
      key: string,
      opts?: string | { defaultValue?: string; count?: number; number?: number },
    ) => {
      if (typeof opts === 'string') return opts
      if (opts?.defaultValue) {
        return opts.defaultValue
          .replace('{{count}}', String(opts.count ?? ''))
          .replace('{{number}}', String(opts.number ?? ''))
      }
      return key
    },
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

describe('CaseWitnessesPanel', () => {
  it('renders an empty state and adds the first witness', () => {
    const onChange = vi.fn()
    render(
      <CaseWitnessesPanel value={undefined} onChange={onChange} testIdPrefix="incident" />,
    )

    expect(screen.getByText('No witnesses recorded')).toBeInTheDocument()
    expect(
      screen.getByText('Add a witness to capture their contact details and statement.'),
    ).toBeInTheDocument()

    fireEvent.click(screen.getByTestId('incident-witnesses-add'))
    expect(onChange).toHaveBeenCalledWith({ witnesses: [{}] })
  })

  it('edits witness fields and reports the updated value', () => {
    const witness: Witness = { name: 'Jane Doe', phone: '', email: '', statement: '' }
    const onChange = vi.fn()
    render(
      <CaseWitnessesPanel
        value={{ witnesses: [witness] }}
        onChange={onChange}
        testIdPrefix="incident"
      />,
    )

    expect(screen.getByText('Witness 1')).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'John Smith' } })
    expect(onChange).toHaveBeenLastCalledWith({
      witnesses: [{ ...witness, name: 'John Smith' }],
    })

    fireEvent.change(screen.getByLabelText('Statement'), {
      target: { value: 'Saw the whole thing happen.' },
    })
    expect(onChange).toHaveBeenLastCalledWith({
      witnesses: [{ ...witness, statement: 'Saw the whole thing happen.' }],
    })

    fireEvent.click(
      screen.getByRole('switch', { name: 'Willing to provide a written statement' }),
    )
    expect(onChange).toHaveBeenLastCalledWith({
      witnesses: [{ ...witness, willing_to_provide_statement: true }],
    })
  })

  it('removes a witness from the list', () => {
    const onChange = vi.fn()
    render(
      <CaseWitnessesPanel
        value={{ witnesses: [{ name: 'Jane Doe' }, { name: 'John Smith' }] }}
        onChange={onChange}
        testIdPrefix="incident"
      />,
    )

    fireEvent.click(screen.getAllByText('Remove')[0])
    expect(onChange).toHaveBeenCalledWith({ witnesses: [{ name: 'John Smith' }] })
  })

  it('renders a read-only summary with no editable controls', () => {
    render(
      <CaseWitnessesPanel
        value={{
          witnesses: [
            { name: 'Jane Doe', phone: '07700 900000', willing_to_provide_statement: true },
          ],
        }}
        onChange={vi.fn()}
        readOnly
        testIdPrefix="rta"
      />,
    )

    expect(screen.getByText('Jane Doe')).toBeInTheDocument()
    expect(screen.getByText('07700 900000')).toBeInTheDocument()
    expect(screen.getByText('Yes')).toBeInTheDocument()
    expect(screen.queryByLabelText('Name')).not.toBeInTheDocument()
    expect(screen.queryByText('Remove')).not.toBeInTheDocument()
    expect(screen.queryByTestId('rta-witnesses-add')).not.toBeInTheDocument()
  })
})
