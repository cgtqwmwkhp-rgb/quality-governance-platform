import type {
  CampaignAudienceType,
  CreateCampaignPayload,
} from '../api/documentCampaignClient'

export const CAMPAIGN_REMINDER_PRESETS = [
  { key: '24h', hours: 24 },
  { key: '7d', hours: 168 },
  { key: '14d', hours: 336 },
  { key: '1month', hours: 720 },
] as const

export type CampaignReminderPresetKey = (typeof CAMPAIGN_REMINDER_PRESETS)[number]['key']

export const ALL_REMINDER_PRESET_KEYS: CampaignReminderPresetKey[] = [
  '24h',
  '7d',
  '14d',
  '1month',
]

export function presetKeysFromReminderHours(hours: number[]): Set<CampaignReminderPresetKey> {
  const hourSet = new Set(hours)
  const matched = CAMPAIGN_REMINDER_PRESETS.filter((preset) => hourSet.has(preset.hours)).map(
    (preset) => preset.key,
  )
  return new Set(matched.length > 0 ? matched : ALL_REMINDER_PRESET_KEYS)
}

export function reminderHoursFromPresetKeys(keys: Set<CampaignReminderPresetKey>): number[] {
  return CAMPAIGN_REMINDER_PRESETS.filter((preset) => keys.has(preset.key))
    .map((preset) => preset.hours)
    .sort((a, b) => a - b)
}

export function formatCampaignReminderHours(
  hours: number[],
  labelForKey: (key: CampaignReminderPresetKey) => string,
): string {
  if (hours.length === 0) return '—'
  const byHour = new Map(CAMPAIGN_REMINDER_PRESETS.map((preset) => [preset.hours, preset.key]))
  return [...hours]
    .sort((a, b) => a - b)
    .map((hour) => {
      const key = byHour.get(hour)
      return key ? labelForKey(key) : `${hour}h`
    })
    .join(', ')
}

export interface CampaignAudienceFormState {
  audienceType: CampaignAudienceType
  department: string
  role: string
  groupId: string
  specificUserIds: string
}

export function parseSpecificUserIds(raw: string): number[] {
  const ids = raw
    .split(/[,;\s]+/)
    .map((part) => part.trim())
    .filter(Boolean)
    .map((part) => Number(part))
    .filter((id) => Number.isInteger(id) && id > 0)
  return [...new Set(ids)]
}

export function buildCampaignPayload(
  documentId: number,
  form: {
    dueWithinDays: number
    requireQuiz: boolean
    requireSign: boolean
    reminderHours: number[]
    audience: CampaignAudienceFormState
  },
): CreateCampaignPayload {
  const payload: CreateCampaignPayload = {
    document_id: documentId,
    due_within_days: form.dueWithinDays,
    require_quiz: form.requireQuiz,
    require_sign: form.requireSign,
    reminder_hours: [...form.reminderHours].sort((a, b) => a - b),
    audience_type: form.audience.audienceType,
  }

  if (form.audience.audienceType === 'department') {
    payload.audience_department = form.audience.department.trim() || null
  } else if (form.audience.audienceType === 'role') {
    payload.audience_role = form.audience.role.trim() || null
  } else if (form.audience.audienceType === 'group') {
    const groupId = Number(form.audience.groupId)
    payload.audience_group_id = Number.isInteger(groupId) && groupId > 0 ? groupId : null
  } else if (form.audience.audienceType === 'specific_users') {
    payload.audience_user_ids = parseSpecificUserIds(form.audience.specificUserIds)
  }

  return payload
}

export function canLaunchCampaign(requireQuiz: boolean, hasApprovedQuiz: boolean): boolean {
  if (!requireQuiz) return true
  return hasApprovedQuiz
}

export function defaultRequireQuiz(hasApprovedQuiz: boolean): boolean {
  return hasApprovedQuiz
}
