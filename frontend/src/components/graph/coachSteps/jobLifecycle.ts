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
      body: 'Confirm steps and departments (or start from a template). Cells hold library document references only — never a second document store.',
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
      id: 'prove',
      title: 'Prove coverage',
      body: 'Overlay ISO / clause freshness on one phase and export coverage honesty. Orientation (Matrix · Transpose · Phase) is a view — same cells, same refs.',
    },
  ],
}
