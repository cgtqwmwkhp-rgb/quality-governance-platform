import { describe, expect, it } from 'vitest'
import type { DocumentEdge } from '../../api/documentGraphClient'
import {
  buildDocumentRelationshipCoverageHonesty,
  expectedRelationshipRolesForType,
  measureRelationshipRoleCoverage,
} from '../documentRelationshipCoverage'

function edge(overrides: Partial<DocumentEdge> & { id: number }): DocumentEdge {
  return {
    tenant_id: 1,
    src_document_id: 10,
    dst_document_id: 20,
    edge_type: 'implements',
    is_primary_parent: false,
    status: 'confirmed',
    created_method: 'manual',
    created_at: '2026-08-01T10:00:00Z',
    updated_at: '2026-08-01T10:00:00Z',
    ...overrides,
  }
}

describe('expectedRelationshipRolesForType', () => {
  it('returns the policy spine roles for Incident Management policies', () => {
    const roles = expectedRelationshipRolesForType('policy')
    expect(roles).toHaveLength(4)
    expect(roles.map((r) => r.id)).toEqual([
      'policy_implements_procedure',
      'policy_requires_form',
      'policy_requires_register',
      'policy_related_peer',
    ])
  })

  it('returns empty for unknown types rather than inventing a hierarchy', () => {
    expect(expectedRelationshipRolesForType('faq')).toEqual([])
    expect(expectedRelationshipRolesForType(null)).toEqual([])
  })
})

describe('measureRelationshipRoleCoverage', () => {
  it('reports 0 of N when the graph is empty for a typed document', () => {
    const coverage = measureRelationshipRoleCoverage(10, 'policy', [])
    expect(coverage.expectedRoles).toHaveLength(4)
    expect(coverage.recordedRoles).toBe(0)
    expect(coverage.confirmedEdgeCount).toBe(0)
    expect(coverage.missingRoles).toHaveLength(4)
  })

  it('counts distinct expected roles, not raw edge volume', () => {
    const coverage = measureRelationshipRoleCoverage(10, 'policy', [
      edge({ id: 1, edge_type: 'implements', dst_document_id: 20 }),
      edge({ id: 2, edge_type: 'implements', dst_document_id: 21 }),
      edge({ id: 3, edge_type: 'requires_record', dst_document_id: 30 }),
      edge({ id: 4, edge_type: 'related_to', dst_document_id: 40 }),
    ])
    // Two implements edges still fill only one implements role.
    expect(coverage.recordedRoles).toBe(3)
    expect(coverage.confirmedEdgeCount).toBe(4)
    expect(coverage.missingRoles.map((r) => r.id)).toEqual(['policy_requires_register'])
  })

  it('ignores proposed edges when measuring recorded roles', () => {
    const coverage = measureRelationshipRoleCoverage(10, 'sop', [
      edge({
        id: 1,
        src_document_id: 5,
        dst_document_id: 10,
        edge_type: 'implements',
        status: 'proposed',
      }),
    ])
    expect(coverage.recordedRoles).toBe(0)
    expect(coverage.confirmedEdgeCount).toBe(0)
  })
})

describe('buildDocumentRelationshipCoverageHonesty', () => {
  it('surfaces quantitative honesty when the spine is empty or sparse', () => {
    const honesty = buildDocumentRelationshipCoverageHonesty(
      measureRelationshipRoleCoverage(10, 'policy', []),
    )
    expect(honesty.hasGap).toBe(true)
    expect(honesty.headline).toBe('0 of 4 expected relationship roles recorded')
    expect(honesty.detail).toContain('Empty or thin coverage')
    expect(honesty.detail).toContain('Missing:')
    expect(honesty.detail).not.toMatch(/%/)
    expect(honesty.detail.toLowerCase()).not.toContain('golden thread')
    expect(honesty.detail.toLowerCase()).not.toContain('iso coverage')
  })

  it('stays quiet when the type spine is fully recorded', () => {
    const honesty = buildDocumentRelationshipCoverageHonesty(
      measureRelationshipRoleCoverage(10, 'form', [
        edge({
          id: 1,
          src_document_id: 1,
          dst_document_id: 10,
          edge_type: 'requires_record',
        }),
      ]),
    )
    expect(honesty.hasGap).toBe(false)
    expect(honesty.headline).toBe('')
  })

  it('stays quiet when the document type has no expected spine', () => {
    const honesty = buildDocumentRelationshipCoverageHonesty(
      measureRelationshipRoleCoverage(10, 'faq', []),
    )
    expect(honesty.hasGap).toBe(false)
  })
})
