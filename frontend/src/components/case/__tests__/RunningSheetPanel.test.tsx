import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { RunningSheetPanel } from '../RunningSheetPanel'

describe('RunningSheetPanel', () => {
  it('renders empty state and enables adding a new entry', () => {
    const onChange = vi.fn()
    const onAdd = vi.fn()

    render(
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
      />,
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
      />,
    )

    expect(screen.getByText('Initial chronology entry')).toBeInTheDocument()
    fireEvent.click(screen.getByLabelText('Delete running sheet entry'))
    expect(onDelete).toHaveBeenCalledWith(4)
  })
})
