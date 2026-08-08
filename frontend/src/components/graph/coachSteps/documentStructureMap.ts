/**
 * Structure map coach steps (DG-3 / X-2 registry extension).
 *
 * Mounted on the whole-library Structure map when `graph_coach` is on.
 * Copy never says “golden thread”.
 */

import type { GraphCoachSurfaceDefinition } from './types'

export const DOCUMENT_STRUCTURE_MAP_COACH: GraphCoachSurfaceDefinition = {
  surface: 'document_structure_map',
  heading: 'Structure map coach',
  steps: [
    {
      id: 'orient',
      title: 'Orient',
      body: 'Structure map explores confirmed implements relationships across the library — Policy → Procedure → SOP. Pick a focus document to place its spine on the map.',
    },
    {
      id: 'roots',
      title: 'Find roots',
      body: 'Root documents appear as implements parents that are not themselves children. Start from a root to walk the governed hierarchy down.',
    },
    {
      id: 'confirm',
      title: 'Confirmed only',
      body: 'Only confirmed implements edges draw the map. Proposed links stay in the Relationships confirm queue — Structure map never auto-confirms.',
    },
    {
      id: 'orient_view',
      title: 'Swap orientation',
      body: 'Use Horizontal hub-fan or Vertical spine to read the same edges. Orientation is a view — it does not change authored relationships.',
    },
    {
      id: 'open',
      title: 'Open and edit',
      body: 'Open any peer to Document Detail for Relationships, Thread, and Connections. Structure map is an explorer, not a second editor.',
    },
  ],
}
