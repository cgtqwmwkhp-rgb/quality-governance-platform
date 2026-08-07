/**
 * Doc Graph coverage honesty — expected relationship roles by document type.
 *
 * Empty / sparse Relationships lists read as "this document has no hierarchy"
 * unless we say how many expected spine roles are actually recorded. This reports
 * that gap. It never invents an ISO coverage percentage from Doc Graph edges.
 *
 * Pattern mirrors Investigations source-register honesty (PX-136).
 */
import type { DocumentEdge, DocumentEdgeType } from '../api/documentGraphClient'
import {
  isActiveDocumentEdge,
  resolveDocumentEdge,
  type DocumentEdgeDirection,
} from './documentRelationshipHelpers'

/** One expected relationship role for a document type's governance spine. */
export interface ExpectedRelationshipRole {
  /** Stable id for matching / tests. */
  id: string
  /** Operator-facing label. */
  label: string
  edgeType: DocumentEdgeType
  direction: DocumentEdgeDirection
}

/**
 * Expected authored roles by library document type.
 *
 * Drawn from the locked IM vertical (policy → procedure → SOP; requires_record;
 * related_to peers). Other types get a smaller spine so honesty stays type-honest
 * rather than inventing a universal hierarchy.
 */
export const EXPECTED_RELATIONSHIP_ROLES_BY_TYPE: Record<string, ExpectedRelationshipRole[]> = {
  policy: [
    {
      id: 'policy_implements_procedure',
      label: 'Implements a procedure or plan',
      edgeType: 'implements',
      direction: 'outbound',
    },
    {
      id: 'policy_requires_form',
      label: 'Requires a record form',
      edgeType: 'requires_record',
      direction: 'outbound',
    },
    {
      id: 'policy_requires_register',
      label: 'Requires a register',
      edgeType: 'requires_record',
      direction: 'outbound',
    },
    {
      id: 'policy_related_peer',
      label: 'Related peer policy',
      edgeType: 'related_to',
      direction: 'peer',
    },
  ],
  procedure: [
    {
      id: 'procedure_parent_policy',
      label: 'Implements a parent policy',
      edgeType: 'implements',
      direction: 'inbound',
    },
    {
      id: 'procedure_child_sop',
      label: 'Implemented by an SOP or work instruction',
      edgeType: 'implements',
      direction: 'outbound',
    },
  ],
  plan: [
    {
      id: 'plan_parent_policy',
      label: 'Implements a parent policy',
      edgeType: 'implements',
      direction: 'inbound',
    },
    {
      id: 'plan_child_sop',
      label: 'Implemented by an SOP or work instruction',
      edgeType: 'implements',
      direction: 'outbound',
    },
  ],
  sop: [
    {
      id: 'sop_parent_procedure',
      label: 'Implements a procedure or plan',
      edgeType: 'implements',
      direction: 'inbound',
    },
  ],
  work_instruction: [
    {
      id: 'wi_parent_procedure',
      label: 'Implements a procedure or plan',
      edgeType: 'implements',
      direction: 'inbound',
    },
  ],
  form: [
    {
      id: 'form_required_by_policy',
      label: 'Required by a policy',
      edgeType: 'requires_record',
      direction: 'inbound',
    },
  ],
  register: [
    {
      id: 'register_required_by_policy',
      label: 'Required by a policy',
      edgeType: 'requires_record',
      direction: 'inbound',
    },
  ],
  record: [
    {
      id: 'record_required_by_policy',
      label: 'Required by a policy',
      edgeType: 'requires_record',
      direction: 'inbound',
    },
  ],
}

export function expectedRelationshipRolesForType(
  documentType: string | null | undefined,
): ExpectedRelationshipRole[] {
  if (!documentType) return []
  return EXPECTED_RELATIONSHIP_ROLES_BY_TYPE[documentType.toLowerCase()] ?? []
}

export interface RelationshipRoleCoverage {
  expectedRoles: ExpectedRelationshipRole[]
  /** How many expected roles have at least one matching confirmed edge. */
  recordedRoles: number
  /** Confirmed active edges on this document (any type). */
  confirmedEdgeCount: number
  missingRoles: ExpectedRelationshipRole[]
}

/**
 * Greedy match: each expected role consumes at most one confirmed edge of the
 * matching type+direction. Extra edges of the same type do not inflate coverage.
 */
export function measureRelationshipRoleCoverage(
  documentId: number,
  documentType: string | null | undefined,
  edges: DocumentEdge[],
): RelationshipRoleCoverage {
  const expectedRoles = expectedRelationshipRolesForType(documentType)
  const confirmed = edges.filter(
    (edge) => isActiveDocumentEdge(edge) && edge.status === 'confirmed',
  )

  const usedEdgeIds = new Set<number>()
  const missingRoles: ExpectedRelationshipRole[] = []

  for (const role of expectedRoles) {
    const match = confirmed.find((edge) => {
      if (usedEdgeIds.has(edge.id)) return false
      if (edge.edge_type !== role.edgeType) return false
      const { direction } = resolveDocumentEdge(documentId, edge)
      return direction === role.direction
    })
    if (match) {
      usedEdgeIds.add(match.id)
    } else {
      missingRoles.push(role)
    }
  }

  return {
    expectedRoles,
    recordedRoles: expectedRoles.length - missingRoles.length,
    confirmedEdgeCount: confirmed.length,
    missingRoles,
  }
}

export interface DocumentRelationshipCoverageHonesty {
  /** True when expected roles exist and at least one is unrecorded. */
  hasGap: boolean
  recordedRoles: number
  expectedRoles: number
  confirmedEdgeCount: number
  headline: string
  detail: string
}

/**
 * Build honesty copy. Returns `hasGap: false` when there is no type spine or the
 * spine is fully recorded — so the strip stays off rather than inventing a warning.
 */
export function buildDocumentRelationshipCoverageHonesty(
  coverage: RelationshipRoleCoverage | null | undefined,
): DocumentRelationshipCoverageHonesty {
  const expected = coverage?.expectedRoles.length ?? 0
  const recorded = coverage?.recordedRoles ?? 0
  const confirmed = coverage?.confirmedEdgeCount ?? 0

  if (!coverage || expected === 0 || recorded >= expected) {
    return {
      hasGap: false,
      recordedRoles: recorded,
      expectedRoles: expected,
      confirmedEdgeCount: confirmed,
      headline: '',
      detail: '',
    }
  }

  const missingLabels = coverage.missingRoles.map((role) => role.label).join('; ')
  const relationshipWord = confirmed === 1 ? 'relationship' : 'relationships'

  return {
    hasGap: true,
    recordedRoles: recorded,
    expectedRoles: expected,
    confirmedEdgeCount: confirmed,
    headline: `${recorded} of ${expected} expected relationship roles recorded`,
    detail:
      `${confirmed} confirmed ${relationshipWord} on this document. ` +
      'Empty or thin coverage means the hierarchy has not been recorded here - not that ' +
      `none exists. Missing: ${missingLabels}.`,
  }
}
