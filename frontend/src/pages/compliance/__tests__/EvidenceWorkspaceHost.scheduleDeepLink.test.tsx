import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { EvidenceWorkspaceHost } from '../EvidenceWorkspaceHost'

vi.mock('../workspace/useStandardsCellAggregate', () => ({
  useStandardsCellAggregate: () => ({
    data: null,
    loading: false,
    error: null,
    refetch: vi.fn(),
  }),
}))

vi.mock('../workspace/ExactShareBanner', () => ({
  ExactShareBanner: () => null,
}))

describe('EvidenceWorkspaceHost schedule deep-link (SG-D-02)', () => {
  it('opens Compliance Schedule with clause and framework, not a second register', () => {
    render(
      <MemoryRouter>
        <EvidenceWorkspaceHost
          selection={{
            frameworkId: '9001',
            clauseNumber: '6.1.3',
            clauseTitle: 'Legal requirements',
          }}
          onClose={() => undefined}
        />
      </MemoryRouter>,
    )

    const link = screen.getByTestId('workspace-deep-link-schedule')
    expect(link).toHaveAttribute('href', '/compliance-schedule?clause=6.1.3&framework=9001')
  })
})
