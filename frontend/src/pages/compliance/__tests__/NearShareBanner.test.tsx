import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import '../../../i18n/i18n'
import { NearShareBanner } from '../workspace/NearShareBanner'
import type { StandardsCellNearShare } from '../../../api/standardsCellAggregateTypes'

const applyNearShare = vi.fn()
const undoNearShare = vi.fn()

vi.mock('../../../api/client', () => ({
  standardsCellAggregateApi: {
    applyNearShare: (...args: unknown[]) => applyNearShare(...args),
    undoNearShare: (...args: unknown[]) => undoNearShare(...args),
  },
  getApiErrorMessage: (err: unknown) => (err instanceof Error ? err.message : 'failed'),
}))

const nearShare: StandardsCellNearShare = {
  available: true,
  matrix_version: '1.1',
  matrix_version_id: 17,
  source: {
    framework: '9001',
    clause_number: '4.1',
    clause_key: '9001-4.1',
    cover_blocked: false,
  },
  candidates: [
    {
      framework: '14001',
      clause_key: '14001-4.1',
      clause_number: '4.1',
      verdict: 'NEAR',
      eligible: true,
      blocked_reasons: [],
      open_nc_count: 0,
      open_action_count: 0,
      addition_text:
        'ISO 14001 ADDS environmental conditions being affected by, or capable of affecting, the organisation.',
    },
    {
      framework: '45001',
      clause_key: '45001-4.1',
      clause_number: '4.1',
      verdict: 'NEAR',
      eligible: false,
      blocked_reasons: ['target_open_nc'],
      open_nc_count: 2,
      open_action_count: 0,
      addition_text:
        'ISO 14001 ADDS environmental conditions being affected by, or capable of affecting, the organisation.',
    },
  ],
  shareable_links: [
    {
      link_id: 9,
      entity_type: 'document',
      entity_id: '12',
      title: 'Context statement',
      cover_kind: 'covers',
      already_shared_frameworks: [],
    },
  ],
}

describe('NearShareBanner (AP-07)', () => {
  it('names the addition and does not pretend NEAR is EXACT', () => {
    render(
      <NearShareBanner
        frameworkId="9001"
        clauseNumber="4.1"
        nearShare={nearShare}
        onShared={() => undefined}
      />,
    )

    expect(screen.getByTestId('near-share-banner')).toBeInTheDocument()
    expect(screen.queryByTestId('exact-share-banner')).not.toBeInTheDocument()
    expect(screen.getByTestId('near-share-addition')).toHaveTextContent(/ISO 14001 ADDS/)
    expect(screen.getByTestId('near-share-confirm-note')).toHaveTextContent(/NEAR is not EXACT/)
    expect(screen.getByTestId('near-share-apply')).toHaveTextContent(/Propose share/)
    expect(screen.getByTestId('near-share-target-14001')).toBeInTheDocument()
    expect(screen.getByTestId('near-share-blocked-45001')).toHaveTextContent('target_open_nc')
  })

  it('renders nothing when NEAR share is unavailable', () => {
    const { container } = render(
      <NearShareBanner
        frameworkId="ce"
        clauseNumber="firewalls"
        nearShare={{ ...nearShare, available: false, unavailable_reason: 'no_iso_near_peers' }}
        onShared={() => undefined}
      />,
    )
    expect(container).toBeEmptyDOMElement()
  })
})
