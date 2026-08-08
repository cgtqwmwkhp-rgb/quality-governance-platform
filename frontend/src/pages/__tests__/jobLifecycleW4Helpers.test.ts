/**
 * JL-UX-W4 helper contracts — map/trail layout, readiness copy, concurrency.
 *
 * The properties worth pinning are the honest-reading ones:
 *
 * 1. A node the server returned is always rendered somewhere, even when it is
 *    unreachable from the root — silently dropping it would understate the pack.
 * 2. `unknown` readiness never borrows the language, or the colour, of `ready`.
 * 3. A 409 is a *conflict*, distinct from a generic failure, because the two
 *    ask the operator to do different things.
 */
import { describe, expect, it } from 'vitest'
import type { JobGraphEdge, JobGraphNode } from '../../api/jobLifecycleClient'
import {
  availableJobLifecycleViewModes,
  buildGraphNodeIndex,
  buildRequirementIndex,
  cellRequiresEvidence,
  conflictBannerCopy,
  countUnreadyCells,
  edgesFromNode,
  graphEdgeKindLabel,
  graphNodeKindLabel,
  graphNodeLinkTarget,
  ifMatchToken,
  isConflictApiError,
  isJobLifecycleGraphViewMode,
  isJobLifecycleViewMode,
  jobLifecycleViewModeLabel,
  layoutJobGraph,
  readinessStateClasses,
  readinessStateLabel,
  readinessTitle,
  resolveAvailableViewMode,
  resolveJobLifecycleViewMode,
  resolveTrailPathNodes,
} from '../jobLifecycleHelpers'

function node(key: string, overrides: Partial<JobGraphNode> = {}): JobGraphNode {
  return {
    key,
    kind: 'job_type',
    ref_id: Number(key.split(':')[1] ?? 0),
    label: key,
    href: null,
    detail: null,
    ...overrides,
  }
}

function edge(source: string, target: string, overrides: Partial<JobGraphEdge> = {}): JobGraphEdge {
  return {
    key: `nests:${source}->${target}`,
    kind: 'nests',
    source,
    target,
    label: 'nests',
    href: null,
    cell_id: null,
    lane_id: null,
    step_id: null,
    ...overrides,
  }
}

describe('W4 view modes', () => {
  it('adds Map and Trail without disturbing the W1 modes', () => {
    expect(isJobLifecycleViewMode('map')).toBe(true)
    expect(isJobLifecycleViewMode('trail')).toBe(true)
    expect(isJobLifecycleViewMode('matrix')).toBe(true)
    expect(isJobLifecycleViewMode('vertical')).toBe(false)
    expect(jobLifecycleViewModeLabel('map')).toBe('Map')
    expect(jobLifecycleViewModeLabel('trail')).toBe('Trail')
    expect(jobLifecycleViewModeLabel('phase')).toBe('Phase')
  })

  it('separates the graph modes from the swimlane layouts', () => {
    expect(isJobLifecycleGraphViewMode('map')).toBe(true)
    expect(isJobLifecycleGraphViewMode('trail')).toBe(true)
    expect(isJobLifecycleGraphViewMode('matrix')).toBe(false)
  })

  it('withholds Map when job_cell_links is closed, and keeps Trail', () => {
    const closed = availableJobLifecycleViewModes(false)
    expect(closed).not.toContain('map')
    expect(closed).toContain('trail')
    expect(availableJobLifecycleViewModes(true)).toContain('map')
  })

  it('falls back to Matrix when a stored mode is no longer offered', () => {
    expect(resolveAvailableViewMode('map', false)).toBe('matrix')
    expect(resolveAvailableViewMode('map', true)).toBe('map')
    expect(resolveAvailableViewMode('trail', false)).toBe('trail')
  })

  it('still resolves a stored map mode as a known mode', () => {
    expect(resolveJobLifecycleViewMode('map')).toBe('map')
    expect(resolveJobLifecycleViewMode('nope')).toBe('matrix')
  })
})

describe('graph layout', () => {
  it('columns nodes by their distance from the root', () => {
    const nodes = [node('job_type:1'), node('job_type:2'), node('job_type:3')]
    const edges = [edge('job_type:1', 'job_type:2'), edge('job_type:2', 'job_type:3')]

    const columns = layoutJobGraph({ nodes, edges, rootKey: 'job_type:1' })

    expect(columns.map((c) => c.depth)).toEqual([0, 1, 2])
    expect(columns[0].nodes.map((n) => n.key)).toEqual(['job_type:1'])
    expect(columns[2].nodes.map((n) => n.key)).toEqual(['job_type:3'])
  })

  it('keeps a node the root cannot reach, in a trailing column', () => {
    const nodes = [node('job_type:1'), node('job_type:2'), node('job_type:9')]
    const edges = [edge('job_type:1', 'job_type:2')]

    const columns = layoutJobGraph({ nodes, edges, rootKey: 'job_type:1' })
    const placed = columns.flatMap((c) => c.nodes.map((n) => n.key))

    expect(placed).toContain('job_type:9')
    expect(columns[columns.length - 1].nodes.map((n) => n.key)).toEqual(['job_type:9'])
  })

  it('does not loop when the graph doubles back on itself', () => {
    const nodes = [node('job_type:1'), node('job_type:2')]
    const edges = [edge('job_type:1', 'job_type:2'), edge('job_type:2', 'job_type:1')]

    const columns = layoutJobGraph({ nodes, edges, rootKey: 'job_type:1' })

    expect(columns.flatMap((c) => c.nodes.map((n) => n.key)).sort()).toEqual([
      'job_type:1',
      'job_type:2',
    ])
  })

  it('places everything in one column when the root is not in the payload', () => {
    const nodes = [node('job_type:2'), node('job_type:3')]
    const columns = layoutJobGraph({ nodes, edges: [], rootKey: 'job_type:1' })

    expect(columns).toHaveLength(1)
    expect(columns[0].nodes).toHaveLength(2)
  })

  it('reads edges out of a node in server order', () => {
    const edges = [
      edge('job_type:1', 'job_type:2', { key: 'a' }),
      edge('job_type:1', 'job_type:3', { key: 'b' }),
      edge('job_type:2', 'job_type:3', { key: 'c' }),
    ]
    expect(edgesFromNode(edges, 'job_type:1').map((e) => e.key)).toEqual(['a', 'b'])
  })

  it('names node and edge kinds in operator language', () => {
    expect(graphNodeKindLabel('job_type')).toBe('Job cycle')
    expect(graphNodeKindLabel('document')).toBe('Document')
    expect(graphEdgeKindLabel('evidences')).toBe('evidenced by')
    expect(graphEdgeKindLabel('nests')).toBe('nests')
  })

  it('routes internal hrefs through the SPA and absolute ones out of it', () => {
    expect(graphNodeLinkTarget({ href: '/documents/7', detail: null })).toBe('internal')
    expect(graphNodeLinkTarget({ href: 'https://example.test/x', detail: null })).toBe('external')
    expect(graphNodeLinkTarget({ href: null, detail: null })).toBe('none')
  })

  it('refuses to navigate to a target the server said is gone', () => {
    expect(graphNodeLinkTarget({ href: '/job-lifecycle/2', detail: 'unavailable' })).toBe('none')
  })

  it('resolves a trail path in walk order and drops keys it cannot see', () => {
    const index = buildGraphNodeIndex([node('job_type:1'), node('cell:5', { kind: 'cell' })])
    expect(
      resolveTrailPathNodes(index, ['job_type:1', 'document:99', 'cell:5']).map((n) => n.key),
    ).toEqual(['job_type:1', 'cell:5'])
  })
})

describe('evidence readiness presentation', () => {
  it('never dresses unknown up as ready', () => {
    expect(readinessStateLabel('unknown')).toBe('Unknown')
    expect(readinessStateLabel('ready')).toBe('Ready')
    expect(readinessStateClasses('unknown')).not.toEqual(readinessStateClasses('ready'))
    expect(readinessStateClasses('unknown')).toContain('amber')
  })

  it('colours a missing or obsolete mandatory cell as a failure', () => {
    expect(readinessStateClasses('missing_evidence')).toContain('destructive')
    expect(readinessStateClasses('obsolete_evidence')).toContain('destructive')
  })

  it('explains each server reason in plain language', () => {
    expect(readinessTitle({ state: 'missing_evidence', reason: 'no_evidence_attached' })).toContain(
      'no library document is attached',
    )
    expect(readinessTitle({ state: 'unknown', reason: 'evidence_status_unreadable' })).toContain(
      'unknown rather than ready',
    )
    expect(
      readinessTitle({ state: 'ready', reason: 'evidence_attached', evidence_count: 2 }),
    ).toContain('presence only')
    expect(readinessTitle(null)).toContain('not loaded')
  })

  it('counts only the mandatory cells that are not satisfied', () => {
    const items = [
      { requires_evidence: true, is_ready: false },
      { requires_evidence: true, is_ready: true },
      { requires_evidence: false, is_ready: false },
    ]
    expect(countUnreadyCells(items)).toBe(1)
  })

  it('reads the requirement off the cell, defaulting an absent flag to false', () => {
    const cells = [
      {
        id: 1,
        tenant_id: 1,
        job_type_id: 1,
        lane_id: 10,
        step_id: 20,
        requires_evidence: true,
        library_document_ids: [],
        created_at: 'x',
        updated_at: 'x',
      },
      {
        id: 2,
        tenant_id: 1,
        job_type_id: 1,
        lane_id: 11,
        step_id: 20,
        library_document_ids: [],
        created_at: 'x',
        updated_at: 'x',
      },
    ]
    expect(cellRequiresEvidence(cells, 10, 20)).toBe(true)
    expect(cellRequiresEvidence(cells, 11, 20)).toBe(false)
    expect(cellRequiresEvidence(cells, 12, 20)).toBe(false)
    expect(buildRequirementIndex(cells).get('10:20')).toBe(true)
    expect(buildRequirementIndex(cells).get('11:20')).toBe(false)
  })
})

describe('optimistic concurrency', () => {
  it('sends the updated_at that was read, and nothing when there is none', () => {
    expect(ifMatchToken({ updated_at: '2026-08-08T00:00:00Z' })).toBe('2026-08-08T00:00:00Z')
    expect(ifMatchToken({ updated_at: '' })).toBeNull()
    expect(ifMatchToken(null)).toBeNull()
    expect(ifMatchToken(undefined)).toBeNull()
  })

  it('recognises a 409 from either error shape, and nothing else', () => {
    expect(isConflictApiError({ response: { status: 409 } })).toBe(true)
    expect(isConflictApiError({ status_code: 409 })).toBe(true)
    expect(isConflictApiError({ response: { status: 403 } })).toBe(false)
    expect(isConflictApiError(new Error('boom'))).toBe(false)
    expect(isConflictApiError(null)).toBe(false)
  })

  it('names the axis and never claims the edit was applied', () => {
    const copy = conflictBannerCopy('QA')
    expect(copy).toContain('QA')
    expect(copy).toContain('was not applied')
    expect(copy).toContain('Reload')
    expect(conflictBannerCopy('  ')).toContain('this item')
  })
})
