/**
 * Honesty copy for portal dynamic forms when the published template is missing.
 * Kept in this lazy page module (not en.json/cy.json) so the eager index chunk
 * stays under the Performance Budget — same pattern as #1347 register honesty.
 */

/** Shown when GET templates/by-slug returns 404 / unpublished (PX-306). */
export const PORTAL_TEMPLATE_FALLBACK_BANNER =
  'No published form template is configured for this report type yet. ' +
  'You are using the built-in fallback form. An admin can publish a template ' +
  'under Admin → Form Builder; until then this built-in layout is what employees see.'
