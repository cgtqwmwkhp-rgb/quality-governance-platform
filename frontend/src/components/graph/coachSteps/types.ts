/**
 * GraphCoach step registry types (X-2).
 *
 * One shared wizard family; surfaces supply copy only. Never call Doc Graph
 * the Golden Thread. Never auto-confirm edges or invent ISO coverage %.
 */

export type GraphCoachSurface =
  | 'document_relationships'
  | 'document_structure_map'
  | 'job_lifecycle'

export interface GraphCoachStep {
  id: string
  title: string
  body: string
}

export interface GraphCoachSurfaceDefinition {
  surface: GraphCoachSurface
  heading: string
  steps: readonly GraphCoachStep[]
}
