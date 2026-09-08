/**
 * The ICAM x HSG245 taxonomy the contributing-factors picker offers (INV-C12 / DEC-1).
 *
 * These values mirror the server enums `FishboneCategory` and `CausalDepth` in
 * `src/domain/models/rca_tools.py`, and the order mirrors `ICAM_CATEGORY_ORDER`
 * in `src/domain/services/investigation_factors_service.py`, which is also the
 * order the API returns factors in.
 *
 * They are listed here rather than fetched because they are a settled taxonomy,
 * not configuration: DEC-1 fixed four categories and three depths, and there is
 * no fifth. `icamFactors.test.ts` pins these strings, and the server rejects an
 * unrecognised category or depth with a 422 — so a drift between the two is a
 * loud failure on the next run of either suite, never a factor filed under a
 * category nothing reads back.
 *
 * The labels are plain English on purpose. This module is imported only by the
 * lazily loaded InvestigationDetail chunk; adding i18n keys for them would put
 * the copy in the app shell's `index-*.js` bundle, which is what pushed the
 * 212 kB gzip ceiling in INV-C10.
 */

export interface IcamOption {
  value: string
  label: string
  /** One line of guidance, shown under the picker so the choice is informed. */
  hint: string
}

export const ICAM_CATEGORIES: IcamOption[] = [
  {
    value: 'organisational_factors',
    label: 'Organisational factors',
    hint: 'Decisions, resourcing, culture and processes above the job itself.',
  },
  {
    value: 'task_environmental_conditions',
    label: 'Task and environmental conditions',
    hint: 'The place, the equipment and the demands of the task on the day.',
  },
  {
    value: 'individual_team_actions',
    label: 'Individual and team actions',
    hint: 'What people did or did not do at the point the harm occurred.',
  },
  {
    value: 'absent_failed_defences',
    label: 'Absent or failed defences',
    hint: 'A control that should have stopped this, and did not exist or did not hold.',
  },
]

export const CAUSAL_DEPTHS: IcamOption[] = [
  {
    value: 'immediate',
    label: 'Immediate',
    hint: 'The act or condition directly at the point of harm.',
  },
  {
    value: 'underlying',
    label: 'Underlying',
    hint: 'What allowed that act or condition to be there.',
  },
  {
    value: 'root',
    label: 'Root',
    hint: 'The failure in the management system that allowed the underlying cause.',
  },
]

export function categoryLabel(value: string): string {
  return ICAM_CATEGORIES.find((option) => option.value === value)?.label || value
}

/**
 * A depth's label, or a plain statement that none was recorded.
 *
 * A factor written through the generic RCA-tools routes before INV-C12 carries
 * no depth. Showing "Immediate" for it would be the screen making a judgement
 * the investigator never made.
 */
export function depthLabel(value: string | null | undefined): string {
  if (!value) return 'No depth recorded'
  return CAUSAL_DEPTHS.find((option) => option.value === value)?.label || value
}
