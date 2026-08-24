/**
 * Per-surface GraphCoach step registry (X-2 / DG-3).
 */

import { DOCUMENT_RELATIONSHIPS_COACH } from './documentRelationships'
import { DOCUMENT_STRUCTURE_MAP_COACH } from './documentStructureMap'
import { JOB_LIFECYCLE_COACH } from './jobLifecycle'
import type { GraphCoachSurface, GraphCoachSurfaceDefinition } from './types'

const REGISTRY: Record<GraphCoachSurface, GraphCoachSurfaceDefinition> = {
  document_relationships: DOCUMENT_RELATIONSHIPS_COACH,
  document_structure_map: DOCUMENT_STRUCTURE_MAP_COACH,
  job_lifecycle: JOB_LIFECYCLE_COACH,
}

export const GRAPH_COACH_SURFACES: readonly GraphCoachSurface[] = [
  'document_relationships',
  'document_structure_map',
  'job_lifecycle',
]

export function getCoachSurfaceDefinition(
  surface: GraphCoachSurface,
): GraphCoachSurfaceDefinition {
  return REGISTRY[surface]
}

export function getCoachSteps(surface: GraphCoachSurface) {
  return getCoachSurfaceDefinition(surface).steps
}

export type { GraphCoachSurface, GraphCoachSurfaceDefinition, GraphCoachStep } from './types'
