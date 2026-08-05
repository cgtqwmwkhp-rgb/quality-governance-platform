import { useTranslation } from 'react-i18next'
import type { Ownership } from '../complianceScheduleHelpers'

/**
 * One wording for ownership across the register and the individual record.
 *
 * The keys are spelled as literals here rather than built from the Ownership
 * value, because scripts/i18n-check.mjs only validates keys it can see as
 * literals — a computed key would pass the gate while being absent from en.json.
 */
export function useOwnershipLabel(): (ownership: Ownership) => string {
  const { t } = useTranslation()

  return (ownership: Ownership): string => {
    if (ownership === 'you') return t('compliance.schedule.owner.you', 'Owned by you')
    if (ownership === 'other') return t('compliance.schedule.owner.other', 'Owned by someone else')
    return t('compliance.schedule.owner.unassigned', 'Unassigned')
  }
}
