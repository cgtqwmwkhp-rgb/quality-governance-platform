import { useTranslation } from 'react-i18next'
import { formatOwnershipLabel, type Ownership } from '../complianceScheduleHelpers'

/**
 * One wording for ownership across the register and the individual record.
 *
 * The keys are spelled as literals here rather than built from the Ownership
 * value, because scripts/i18n-check.mjs only validates keys it can see as
 * literals — a computed key would pass the gate while being absent from en.json.
 *
 * Optional ``ownerName`` upgrades the id-only Wave-1 labels to a person's name
 * when the schedule API has resolved ``owner_name``.
 */
export function useOwnershipLabel(): (
  ownership: Ownership,
  ownerName?: string | null,
) => string {
  const { t } = useTranslation()

  return (ownership: Ownership, ownerName?: string | null): string =>
    formatOwnershipLabel(ownership, ownerName, {
      you: t('compliance.schedule.owner.you', 'Owned by you'),
      other: t('compliance.schedule.owner.other', 'Owned by someone else'),
      unassigned: t('compliance.schedule.owner.unassigned', 'Unassigned'),
      youNamed: (name) =>
        t('compliance.schedule.owner.you_named', '{{name}} (you)', { name }),
    })
}
