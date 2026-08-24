/**
 * Doc Graph / Relationships coach steps (X-2).
 *
 * Mirrors the shared wizard sketch: Orient → Roles → Link → Thread → Prove.
 * Copy never says “golden thread”.
 */

import type { GraphCoachSurfaceDefinition } from './types'

export const DOCUMENT_RELATIONSHIPS_COACH: GraphCoachSurfaceDefinition = {
  surface: 'document_relationships',
  heading: 'Document relationships coach',
  steps: [
    {
      id: 'orient',
      title: 'Orient',
      body: 'What document is this, and what role does it play on the implements thread (policy, procedure, SOP, form, or record)?',
    },
    {
      id: 'roles',
      title: 'Expected roles',
      body: 'Review the expected implements / requires_record roles for this document type. Coverage honesty highlights missing spine roles — it does not invent ISO scores.',
    },
    {
      id: 'link',
      title: 'Link with confirm',
      body: 'Propose edges from search, heuristics, or Map drag-and-drop. Impact-driving edges stay proposed until a person confirms them — never auto-confirmed.',
    },
    {
      id: 'thread',
      title: 'Walk the thread',
      body: 'Use the ambient Document Thread strip and Map|List view to walk Policy → Procedure → SOP → Form. Confirmed edges only form the spine.',
    },
    {
      id: 'prove',
      title: 'Prove on publish',
      body: 'Publish impact preview lists dependents and clause freshness. A degraded ImpactBundle blocks publish — completing this coach does not.',
    },
  ],
}
