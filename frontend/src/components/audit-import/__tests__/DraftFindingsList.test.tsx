import type { ComponentProps } from 'react'
import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import type { ExternalAuditImportDraft } from '../../../api/client'
import { DraftFindingsList } from '../DraftFindingsList'

function baseDraft(
  overrides: Partial<ExternalAuditImportDraft> = {},
): ExternalAuditImportDraft {
  return {
    id: 101,
    import_job_id: 7,
    audit_run_id: 42,
    status: 'draft',
    title: 'Missing calibration records',
    description: 'Calibration evidence was not available for equipment set A.',
    severity: 'high',
    finding_type: 'nonconformity',
    confidence_score: 0.72,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

function renderList(
  props: Partial<ComponentProps<typeof DraftFindingsList>> = {},
) {
  const onDecision = props.onDecision ?? vi.fn()
  const onLoad = props.onLoad ?? vi.fn()
  const result = render(
    <MemoryRouter>
      <DraftFindingsList
        drafts={props.drafts ?? []}
        job={props.job ?? null}
        error={props.error ?? null}
        busyDraftId={props.busyDraftId ?? null}
        isBulkReviewing={props.isBulkReviewing ?? false}
        specialistHome={
          props.specialistHome ?? { path: '/uvdb', label: 'UVDB home' }
        }
        onDecision={onDecision}
        onLoad={onLoad}
      />
    </MemoryRouter>,
  )
  return { ...result, onDecision, onLoad }
}

describe('DraftFindingsList', () => {
  it('renders empty-state guidance when there are no draft findings', () => {
    renderList({
      drafts: [],
      job: { id: 1, status: 'review_required' } as never,
    })

    expect(
      screen.getByText(
        /No draft findings were produced for this import\. Review the source document/,
      ),
    ).toBeInTheDocument()
  })

  it('shows processing copy when job is still running with no drafts', () => {
    renderList({
      drafts: [],
      job: { id: 2, status: 'processing' } as never,
    })

    expect(
      screen.getByText(/Processing is still running\. This workspace refreshes automatically/),
    ).toBeInTheDocument()
  })

  it('renders finding cards and invokes accept / reject decisions', () => {
    const drafts = [
      baseDraft(),
      baseDraft({
        id: 102,
        title: 'Positive PPE observation',
        finding_type: 'positive_practice',
        severity: 'low',
        confidence_score: 0.91,
      }),
    ]
    const { onDecision, onLoad } = renderList({ drafts })

    expect(screen.getByText('2 of 2 finding(s)')).toBeInTheDocument()
    expect(screen.getByText('Missing calibration records')).toBeInTheDocument()
    expect(screen.getByText('Positive PPE observation')).toBeInTheDocument()
    expect(screen.getByText('Non-Conformity')).toBeInTheDocument()
    expect(screen.getByText('Good Practice')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Refresh' }))
    expect(onLoad).toHaveBeenCalledTimes(1)

    fireEvent.click(
      screen.getByRole('button', { name: 'Accept finding: Missing calibration records' }),
    )
    expect(onDecision).toHaveBeenCalledWith(101, 'accepted')

    fireEvent.click(
      screen.getByRole('button', { name: 'Reject finding: Positive PPE observation' }),
    )
    expect(onDecision).toHaveBeenCalledWith(102, 'rejected')
  })

  it('opens edit mode and saves accept with edited fields', () => {
    const { onDecision } = renderList({ drafts: [baseDraft()] })

    fireEvent.click(screen.getByRole('button', { name: 'Edit' }))
    expect(screen.getByLabelText('Title')).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Title'), {
      target: { value: 'Updated calibration finding' },
    })
    fireEvent.change(screen.getByLabelText('Review notes'), {
      target: { value: 'Verified against site log' },
    })

    fireEvent.click(screen.getByRole('button', { name: /Save & Accept/i }))
    expect(onDecision).toHaveBeenCalledWith(
      101,
      'accepted',
      expect.objectContaining({
        title: 'Updated calibration finding',
        review_notes: 'Verified against site log',
      }),
    )
  })

  it('shows clear-filter CTA when status filter hides all drafts', () => {
    renderList({
      drafts: [baseDraft({ status: 'draft' })],
      job: { id: 7, status: 'review_required' } as never,
    })

    fireEvent.change(screen.getByLabelText('Filter draft findings by status'), {
      target: { value: 'accepted' },
    })
    expect(screen.getByText(/No findings match the current status filter/i)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Clear status filter/i }))
    expect(screen.getByText('Missing calibration records')).toBeInTheDocument()
  })

})
