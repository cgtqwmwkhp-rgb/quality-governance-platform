import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import {
  RunningSheetPanel,
  buildRunningSheetCreateActionHref,
} from '../RunningSheetPanel'

describe('buildRunningSheetCreateActionHref', () => {
  it('prefills incident source and returnTo', () => {
    const href = buildRunningSheetCreateActionHref({
      sourceType: 'incident',
      sourceId: 7,
      referenceNumber: 'INC-7',
      entrySnippet: 'Witness statement captured',
    })
    expect(href).toContain('/actions?')
    expect(href).toContain('create=1')
    expect(href).toContain('sourceType=incident')
    expect(href).toContain('sourceId=7')
    expect(href).toContain(encodeURIComponent('/incidents/7'))
    expect(href).toContain('Witness+statement+captured')
  })

  it('prefills near_miss title/description/returnTo without invalid sourceType', () => {
    const href = buildRunningSheetCreateActionHref({
      sourceType: 'near_miss',
      sourceId: 3,
      referenceNumber: 'NM-3',
    })
    expect(href).toContain('create=1')
    expect(href).not.toContain('sourceType=near_miss')
    expect(href).toContain(encodeURIComponent('/near-misses/3'))
    expect(href).toContain('title=Follow-up+from+NM-3')
  })
})

describe('RunningSheetPanel', () => {
  it('renders empty state and enables adding a new entry', () => {
    const onChange = vi.fn()
    const onAdd = vi.fn()

    render(
      <MemoryRouter>
        <RunningSheetPanel
          entries={[]}
          newEntry=""
          addingEntry={false}
          title="Running Sheet"
          placeholder="Add to the story"
          emptyTitle="No entries yet"
          emptyDescription="Build the chronology"
          onNewEntryChange={onChange}
          onAddEntry={onAdd}
          onDeleteEntry={vi.fn()}
        />
      </MemoryRouter>,
    )

    expect(screen.getByText('No entries yet')).toBeInTheDocument()
    fireEvent.change(screen.getByPlaceholderText('Add to the story'), {
      target: { value: 'New note' },
    })
    expect(onChange).toHaveBeenCalledWith('New note')
  })

  it('renders entries and supports deletion', () => {
    const onDelete = vi.fn()

    render(
      <MemoryRouter>
        <RunningSheetPanel
          entries={[
            {
              id: 4,
              content: 'Initial chronology entry',
              entry_type: 'note',
              author_email: 'owner@example.com',
              created_at: '2026-03-24T10:00:00Z',
            },
          ]}
          newEntry=""
          addingEntry={false}
          title="Running Sheet"
          placeholder="Add to the story"
          emptyTitle="No entries yet"
          emptyDescription="Build the chronology"
          onNewEntryChange={vi.fn()}
          onAddEntry={vi.fn()}
          onDeleteEntry={onDelete}
        />
      </MemoryRouter>,
    )

    expect(screen.getByText('Initial chronology entry')).toBeInTheDocument()
    fireEvent.click(screen.getByLabelText('Delete running sheet entry'))
    expect(onDelete).toHaveBeenCalledWith(4)
  })

  it('shows Create Action bridge when href provided', () => {
    const href = buildRunningSheetCreateActionHref({
      sourceType: 'incident',
      sourceId: 9,
      referenceNumber: 'INC-9',
    })
    render(
      <MemoryRouter>
        <RunningSheetPanel
          entries={[]}
          newEntry=""
          addingEntry={false}
          title="Running Sheet"
          placeholder="Add to the story"
          emptyTitle="No entries yet"
          emptyDescription="Build the chronology"
          onNewEntryChange={vi.fn()}
          onAddEntry={vi.fn()}
          onDeleteEntry={vi.fn()}
          createActionHref={href}
        />
      </MemoryRouter>,
    )

    const link = screen.getByTestId('running-sheet-create-action')
    expect(link).toHaveAttribute('href', href)
    expect(link).toHaveTextContent('Create Action')
  })
})
