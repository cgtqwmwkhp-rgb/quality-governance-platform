import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'

import SaveIssueBanner from '../SaveIssueBanner'
import type { SaveIssue } from '../saveErrorModel'

const issues: SaveIssue[] = [
  {
    id: 'issue-0-risk_category',
    field: 'risk_category',
    label: 'Risk level on a question',
    action: 'Open the question’s risk/criticality controls and save again',
    raw: 'body -> risk_category: Extra inputs are not permitted',
    questionId: 'q-13',
    context: 'Vehicle: Capture defect photo',
  },
]

describe('SaveIssueBanner', () => {
  it('renders summary and actionable issue text', () => {
    render(
      <SaveIssueBanner
        summary="Couldn’t save: Risk level on a question."
        issues={issues}
      />,
    )

    expect(screen.getByRole('alert')).toBeInTheDocument()
    expect(screen.getByTestId('save-issue-summary')).toHaveTextContent(/Risk level/i)
    expect(screen.getByTestId('save-issue-action-0')).toHaveTextContent(
      /Open the question’s risk\/criticality controls/i,
    )
    expect(screen.getByText(/Vehicle: Capture defect photo/)).toBeInTheDocument()
  })

  it('invokes onShowQuestion when Show question is clicked', () => {
    const onShowQuestion = vi.fn()
    render(
      <SaveIssueBanner
        summary="Couldn’t save"
        issues={issues}
        onShowQuestion={onShowQuestion}
      />,
    )
    fireEvent.click(screen.getByTestId('save-issue-show-0'))
    expect(onShowQuestion).toHaveBeenCalledWith('q-13')
  })
})
