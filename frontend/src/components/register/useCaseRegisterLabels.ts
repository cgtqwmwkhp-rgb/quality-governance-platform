import { useTranslation } from 'react-i18next'

/**
 * The one place case-register column headings are worded.
 *
 * Four registers wrote their own headings and drifted: three headed the date a
 * record happened "Date" while complaints headed the equivalent column
 * "Received", and near misses folded customer and location into one column
 * called "Details". A column headed only "Date" is also the readable half of
 * PX-122 — the dashboard shows *when an incident was reported* and /incidents
 * shows *when it occurred*, and with both headed "Date" the two screens looked
 * like they disagreed about the same record. `dashboard/RecentCasesPanel` has
 * already named its dates (Reported / Occurred / Received / Logged); these are
 * the same words for the register side.
 *
 * Name the date by the event it records. Never ship a bare "Date".
 */
export function useCaseRegisterLabels() {
  const { t } = useTranslation()

  return {
    reference: t('register.column.reference', 'Reference'),
    title: t('register.column.title', 'Title'),
    type: t('register.column.type', 'Type'),
    severity: t('register.column.severity', 'Severity'),
    status: t('register.column.status', 'Status'),
    priority: t('register.column.priority', 'Priority'),
    customer: t('register.column.customer', 'Customer'),
    location: t('register.column.location', 'Location'),
    complainant: t('register.column.complainant', 'Complainant'),
    owner: t('register.column.owner', 'Assign owner'),
    /** When the event itself happened — incident, near miss or collision date. */
    occurred: t('register.column.occurred', 'Occurred'),
    /** When a complaint reached us. */
    received: t('register.column.received', 'Received'),
  }
}
