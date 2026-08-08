/**
 * Job Lifecycle coach steps (X-2 registry).
 *
 * Registered now so JL-2 mounts the same `<GraphCoach surface="job_lifecycle" />`
 * without a second coach implementation. Not mounted until Job Lifecycle ships.
 */

import type { GraphCoachSurfaceDefinition } from './types'

export const JOB_LIFECYCLE_COACH: GraphCoachSurfaceDefinition = {
  surface: 'job_lifecycle',
  heading: 'Job lifecycle coach',
  steps: [
    {
      id: 'orient',
      title: 'Orient',
      body: 'What is a job type? Pick the vertical (Incident Management, QA, Fleet…) this pack governs.',
    },
    {
      id: 'axes',
      title: 'Axes',
      body: 'Confirm lanes and steps (or start from a template). Cells hold library document references only — never a second document store. Lanes are process axes, not departments.',
    },
    {
      id: 'attach',
      title: 'Attach / link',
      body: 'Propose cell attachments from Library drag-and-drop. You confirm every attachment; nothing auto-writes impact-driving edges.',
    },
    {
      id: 'thread',
      title: 'Walk the job',
      body: 'Walk Enquiry → Review on the swimlane. Gaps light up using the same Connections hop contract as Document Detail.',
    },
    {
      id: 'freshness',
      title: 'Check freshness',
      body: 'Turn Freshness on to read document control status onto the tray and cell references. Obsolete documents are refused on attach — the Library / Document Control record decides, not the composer. "Unknown" means no review date is recorded, not that a document is in date.',
    },
    {
      id: 'prove',
      title: 'Prove coverage',
      body: 'Walk one phase with freshness on and see where control status is missing. Orientation (Matrix · Transpose · Phase) is a view — same cells, same refs.',
    },
  ],
}
