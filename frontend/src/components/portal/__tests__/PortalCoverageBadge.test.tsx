import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { PortalCoverageBadge } from '../PortalCoverageBadge'
import { resolvePortalCoverageBadge } from '../portalCoverageBadgeHelpers'

describe('resolvePortalCoverageBadge', () => {
  it('maps CURRENT / LIVE / PUBLISHED to visible CURRENT badge', () => {
    expect(resolvePortalCoverageBadge({ document_issue_state: 'CURRENT' }).state).toBe('CURRENT')
    expect(resolvePortalCoverageBadge({ document_issue_state: 'live' }).visible).toBe(true)
    expect(resolvePortalCoverageBadge({ document_issue_state: 'Published' }).variant).toBe('success')
  })

  it('maps SUPERSEDED honestly and never invents CURRENT from version alone', () => {
    expect(
      resolvePortalCoverageBadge({
        document_issue_state: 'SUPERSEDED',
        document_version: '3.0',
      }).state,
    ).toBe('SUPERSEDED')
    const versionOnly = resolvePortalCoverageBadge({ document_version: '2.1' })
    expect(versionOnly.state).toBe('UNKNOWN')
    expect(versionOnly.visible).toBe(true)
    expect(versionOnly.labelKey).toBe('portal_reading.coverage_badge.version_only')
  })

  it('hides when unknown and no version', () => {
    expect(resolvePortalCoverageBadge({}).visible).toBe(false)
    expect(resolvePortalCoverageBadge(null).visible).toBe(false)
  })
})

describe('PortalCoverageBadge', () => {
  it('renders CURRENT with optional version for 360px reading row', () => {
    render(
      <PortalCoverageBadge
        label="CURRENT"
        source={{ document_issue_state: 'CURRENT', document_version: '1.2' }}
      />,
    )
    const badge = screen.getByTestId('portal-coverage-badge')
    expect(badge).toHaveAttribute('data-issue-state', 'CURRENT')
    expect(badge).toHaveTextContent('CURRENT')
    expect(screen.getByTestId('portal-coverage-badge-version')).toHaveTextContent('v1.2')
  })

  it('renders superseded warning without editor chrome', () => {
    render(
      <PortalCoverageBadge
        label="Superseded"
        source={{ document_issue_state: 'SUPERSEDED', document_version: '0.9' }}
      />,
    )
    expect(screen.getByTestId('portal-coverage-badge')).toHaveAttribute(
      'data-issue-state',
      'SUPERSEDED',
    )
    expect(screen.getByText('Superseded')).toBeInTheDocument()
    expect(screen.queryByTestId('portal-coverage-badge-version')).not.toBeInTheDocument()
  })

  it('renders nothing when state unknown and no version', () => {
    const { container } = render(<PortalCoverageBadge label="hidden" source={{}} />)
    expect(container).toBeEmptyDOMElement()
  })
})
