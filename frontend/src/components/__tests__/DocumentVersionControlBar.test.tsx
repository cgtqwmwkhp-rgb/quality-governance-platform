import { describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { DocumentVersionControlBar } from '../DocumentVersionControlBar'

describe('DocumentVersionControlBar', () => {
  it('shows tip, published, working draft, and immutable history', () => {
    render(
      <DocumentVersionControlBar
        documentLabel="PPE Procedure"
        currentVersion="1.1"
        status="under_revision"
        publishedVersion="1.0"
        workingVersion="1.1"
        versions={[
          {
            id: 2,
            version_number: '1.1',
            status: 'draft',
            change_summary: 'Add eye protection',
            is_immutable: false,
            read_only: false,
            created_at: '2026-07-13T10:00:00Z',
          },
          {
            id: 1,
            version_number: '1.0',
            status: 'published',
            change_summary: 'Initial release',
            is_immutable: true,
            read_only: true,
            created_at: '2026-07-01T10:00:00Z',
          },
        ]}
        onRevise={vi.fn()}
        onPublish={vi.fn()}
      />,
    )

    expect(screen.getByTestId('document-version-control-bar')).toBeInTheDocument()
    expect(screen.getByTestId('version-tip')).toHaveTextContent('v1.1')
    expect(screen.getByTestId('version-published')).toHaveTextContent('v1.0')
    expect(screen.getByTestId('version-working')).toHaveTextContent('v1.1')
    expect(screen.getByTestId('version-immutable-1.0')).toHaveTextContent('Read-only')
    expect(screen.getByTestId('version-revise-btn')).toBeDisabled()
    expect(screen.getByTestId('version-publish-btn')).not.toBeDisabled()
  })

  it('allows revise to bump draft before first publish', () => {
    render(
      <DocumentVersionControlBar
        currentVersion="1.0"
        status="draft"
        publishedVersion={null}
        workingVersion="1.0"
        versions={[
          {
            id: 1,
            version_number: '1.0',
            status: 'draft',
            change_summary: 'Initial',
            is_immutable: false,
            read_only: false,
            created_at: '2026-07-01T10:00:00Z',
          },
        ]}
        onRevise={vi.fn()}
      />,
    )
    expect(screen.getByTestId('version-revise-btn')).not.toBeDisabled()
  })

  it('submits revise with change summary when no open draft', async () => {
    const onRevise = vi.fn().mockResolvedValue(undefined)
    render(
      <DocumentVersionControlBar
        currentVersion="1.0"
        status="published"
        publishedVersion="1.0"
        workingVersion={null}
        versions={[
          {
            id: 1,
            version_number: '1.0',
            status: 'published',
            change_summary: 'Initial',
            is_immutable: true,
            read_only: true,
            created_at: '2026-07-01T10:00:00Z',
          },
        ]}
        onRevise={onRevise}
      />,
    )

    fireEvent.click(screen.getByTestId('version-revise-btn'))
    fireEvent.change(screen.getByTestId('version-change-summary'), {
      target: { value: 'Clarify inspection cadence after audit finding' },
    })
    fireEvent.click(screen.getByTestId('version-revise-submit'))

    await waitFor(() => {
      expect(onRevise).toHaveBeenCalledWith(
        'Clarify inspection cadence after audit finding',
        false,
      )
    })
  })
})
