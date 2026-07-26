/**
 * Regression cover for the shared case register (PX-147, PX-205, PX-288).
 *
 * jsdom has no layout engine, so nothing here can measure a scrollWidth. What it
 * can do is pin the structural properties the browser measurements came from:
 * the table must be fixed-layout so no cell can widen it, long text must be
 * allowed to break inside its own column, references and dates must not wrap,
 * and every column must carry a visible label in the stacked layout so nothing
 * is lost below the breakpoint. Lose any of those and the measured defects come
 * straight back.
 */
import { describe, it, expect, vi } from 'vitest'
import { fireEvent, render, screen, within } from '@testing-library/react'
import { CaseRegisterTable, type CaseRegisterColumn } from '../CaseRegisterTable'
import { expectNoA11yViolations } from '../../../test/axe-helper'

interface Row {
  id: number
  reference: string
  summary: string
  status: string
  occurred: string
}

/** The PX-147 record: 214 unbroken characters in a free-text column. */
const UNBROKEN_214 = 'A'.repeat(214)

const rows: Row[] = [
  {
    id: 1,
    reference: 'NM-2026-20033D1D',
    summary: UNBROKEN_214,
    status: 'reported',
    occurred: '23/07/2026',
  },
  { id: 2, reference: 'NM-2026-0002', summary: 'Trip hazard', status: 'closed', occurred: '11/10/2024' },
]

const columns: CaseRegisterColumn<Row>[] = [
  {
    key: 'reference',
    header: 'Reference',
    width: 'reference',
    render: (row) => <span>{row.reference}</span>,
  },
  { key: 'summary', header: 'Details', render: (row) => <span>{row.summary}</span> },
  { key: 'status', header: 'Status', width: 'badge', render: (row) => <span>{row.status}</span> },
  {
    key: 'occurred',
    header: 'Occurred',
    width: 'date',
    render: (row) => <span>{row.occurred}</span>,
  },
]

const classesOf = (el: Element) => el.className.split(/\s+/)

/** The triage view: a cell with its own controls sitting inside an activatable row. */
const withOwner: CaseRegisterColumn<Row>[] = [
  ...columns,
  {
    key: 'owner',
    header: 'Assign owner',
    width: 'action',
    isolateClicks: true,
    hideStackedLabel: true,
    cellTestId: (row) => `assign-${row.id}`,
    render: (row) => (
      <div>
        <input placeholder="Search owner" />
        <button type="button">Assign {row.id}</button>
      </div>
    ),
  },
]

function renderRegister(overrides: Partial<Parameters<typeof CaseRegisterTable<Row>>[0]> = {}) {
  return render(
    <CaseRegisterTable
      label="Near misses"
      columns={columns}
      rows={rows}
      rowKey={(row) => row.id}
      empty={<p>No near misses found</p>}
      {...overrides}
    />,
  )
}

describe('CaseRegisterTable', () => {
  it('exposes the register as a named table with one header per column', () => {
    renderRegister()

    const table = screen.getByRole('table', { name: 'Near misses' })
    const headers = within(table).getAllByRole('columnheader')
    expect(headers.map((header) => header.textContent)).toEqual([
      'Reference',
      'Details',
      'Status',
      'Occurred',
    ])
  })

  it('renders every column of every row — no column is dropped (PX-288)', () => {
    renderRegister()

    const dataRows = screen.getAllByRole('row').slice(1)
    expect(dataRows).toHaveLength(2)
    for (const row of dataRows) {
      expect(within(row).getAllByRole('cell')).toHaveLength(columns.length)
    }
  })

  it('lays the table out fixed so no cell can widen it (PX-147, PX-205)', () => {
    renderRegister()

    const classes = classesOf(screen.getByRole('table', { name: 'Near misses' }))
    expect(classes).toContain('xl:table-fixed')
    expect(classes).toContain('w-full')
  })

  it('breaks and clamps free text instead of letting it stretch its column (PX-147)', () => {
    renderRegister()

    const longCell = screen.getByText(UNBROKEN_214).parentElement
    expect(longCell?.className).toContain('break-words')
    expect(longCell?.className).toContain('line-clamp-2')
  })

  it('keeps references and dates on one line (PX-205)', () => {
    renderRegister()

    expect(screen.getByText('NM-2026-20033D1D').parentElement?.className).toContain(
      'whitespace-nowrap',
    )
    expect(screen.getByText('23/07/2026').parentElement?.className).toContain('whitespace-nowrap')
  })

  it('labels every cell in the stacked layout so narrow viewports keep the data (PX-288)', () => {
    renderRegister()

    const firstRow = screen.getAllByRole('row')[1]
    const stackedLabels = within(firstRow)
      .getAllByRole('cell')
      .map((cell) => cell.querySelector('span.xl\\:hidden')?.textContent)

    expect(stackedLabels).toEqual(['Reference', 'Details', 'Status', 'Occurred'])
  })

  it('hides the stacked label when a column asks it to', () => {
    renderRegister({
      columns: [{ ...columns[0], hideStackedLabel: true }],
    })

    const cell = screen.getAllByRole('cell')[0]
    expect(cell.querySelector('span.xl\\:hidden')).toBeNull()
  })

  it('opens a row on click, Enter and Space', () => {
    const onOpenRow = vi.fn()
    renderRegister({ onOpenRow, rowLabel: (row) => `View ${row.reference}` })

    const row = screen.getByRole('button', { name: 'View NM-2026-20033D1D' })
    fireEvent.click(row)
    fireEvent.keyDown(row, { key: 'Enter' })
    fireEvent.keyDown(row, { key: ' ' })

    expect(onOpenRow).toHaveBeenCalledTimes(3)
    expect(onOpenRow).toHaveBeenLastCalledWith(rows[0])
  })

  it('ignores other keys so typing in a cell cannot navigate away', () => {
    const onOpenRow = vi.fn()
    renderRegister({ onOpenRow, rowLabel: (row) => `View ${row.reference}` })

    fireEvent.keyDown(screen.getByRole('button', { name: 'View NM-2026-0002' }), { key: 'a' })

    expect(onOpenRow).not.toHaveBeenCalled()
  })

  it('does not open the row when an isolated cell is clicked', () => {
    const onOpenRow = vi.fn()
    renderRegister({ onOpenRow, rowLabel: (row) => `View ${row.reference}`, columns: withOwner })

    fireEvent.click(screen.getByText('Assign 1'))

    expect(onOpenRow).not.toHaveBeenCalled()
    expect(screen.getByTestId('assign-1')).toBeInTheDocument()
  })

  it('waits for a wider viewport when a register carries an inline action column', () => {
    const { rerender } = renderRegister()
    expect(classesOf(screen.getByRole('table'))).toContain('xl:table-fixed')

    rerender(
      <CaseRegisterTable
        label="Near misses"
        columns={withOwner}
        rows={rows}
        rowKey={(row) => row.id}
        empty={null}
      />,
    )

    const classes = classesOf(screen.getByRole('table'))
    expect(classes).toContain('2xl:table-fixed')
    expect(classes).not.toContain('xl:table-fixed')
  })

  it('does not open the row when a space is typed into a control inside a cell', () => {
    const onOpenRow = vi.fn()
    renderRegister({ onOpenRow, rowLabel: (row) => `View ${row.reference}`, columns: withOwner })

    const search = screen.getAllByPlaceholderText('Search owner')[0]
    fireEvent.keyDown(search, { key: ' ' })
    fireEvent.keyDown(search, { key: 'Enter' })

    expect(onOpenRow).not.toHaveBeenCalled()
  })

  it('leaves rows inert when the register has no open action', () => {
    renderRegister()

    expect(screen.queryAllByRole('button')).toHaveLength(0)
    expect(screen.getAllByRole('row')[1]).not.toHaveAttribute('tabindex')
  })

  it('spans the empty state across every column', () => {
    renderRegister({ rows: [] })

    const cell = screen.getByRole('cell')
    expect(cell).toHaveAttribute('colspan', String(columns.length))
    expect(within(cell).getByText('No near misses found')).toBeInTheDocument()
  })

  it('tags each row with the page test id when one is given', () => {
    renderRegister({ rowTestId: 'near-miss-row-link' })

    expect(screen.getAllByTestId('near-miss-row-link')).toHaveLength(2)
  })

  it('has no axe violations when populated and activatable', async () => {
    const { container } = renderRegister({
      onOpenRow: vi.fn(),
      rowLabel: (row) => `View ${row.reference}`,
    })

    await expectNoA11yViolations(container)
  })
})
