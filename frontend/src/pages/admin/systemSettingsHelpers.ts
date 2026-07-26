/** Helpers for Admin System Settings honesty (PX-227 / PX-228 / PX-229). */

export type SettingValueType = 'string' | 'number' | 'boolean' | 'json' | 'email' | 'color' | 'select'

export interface SettingDefinition {
  key: string
  value: string
  category: string
  description: string
  value_type: SettingValueType
  is_editable: boolean
  select_options?: { value: string; label: string }[]
}

export interface ApiSystemSetting {
  key: string
  value: string
  category?: string
  description?: string
  value_type?: string
  is_editable?: boolean
}

export const REGIONAL_DATE_FORMATS = [
  { value: 'DD/MM/YYYY', label: 'DD/MM/YYYY (UK)' },
  { value: 'MM/DD/YYYY', label: 'MM/DD/YYYY (US)' },
  { value: 'YYYY-MM-DD', label: 'YYYY-MM-DD (ISO)' },
] as const

export const REGIONAL_TIMEZONES = [
  { value: 'Europe/London', label: 'Europe/London' },
  { value: 'UTC', label: 'UTC' },
  { value: 'Europe/Dublin', label: 'Europe/Dublin' },
  { value: 'Europe/Paris', label: 'Europe/Paris' },
] as const

export const REGIONAL_LANGUAGES = [
  { value: 'en-GB', label: 'English (UK)' },
  { value: 'en-US', label: 'English (US)' },
  { value: 'cy-GB', label: 'Cymraeg' },
] as const

/** Template definitions — branding colours must not default to #000000 (PX-227). */
export function buildSettingDefinitions(): SettingDefinition[] {
  return [
    {
      key: 'company_name',
      value: '',
      category: 'branding',
      description: 'Company name displayed throughout the system',
      value_type: 'string',
      is_editable: true,
    },
    {
      key: 'company_logo_url',
      value: '',
      category: 'branding',
      description: 'URL to company logo image',
      value_type: 'string',
      is_editable: true,
    },
    {
      key: 'primary_color',
      value: '',
      category: 'branding',
      description: 'Primary brand color',
      value_type: 'color',
      is_editable: true,
    },
    {
      key: 'accent_color',
      value: '',
      category: 'branding',
      description: 'Accent/hover color',
      value_type: 'color',
      is_editable: true,
    },
    {
      key: 'support_email',
      value: '',
      category: 'contact',
      description: 'Support email address',
      value_type: 'email',
      is_editable: true,
    },
    {
      key: 'support_phone',
      value: '',
      category: 'contact',
      description: 'Support phone number',
      value_type: 'string',
      is_editable: true,
    },
    {
      key: 'emergency_phone',
      value: '',
      category: 'contact',
      description: 'Emergency contact number',
      value_type: 'string',
      is_editable: true,
    },
    {
      key: 'incident_notification_emails',
      value: '',
      category: 'notifications',
      description: 'Emails notified on incident submission',
      value_type: 'string',
      is_editable: true,
    },
    {
      key: 'complaint_notification_emails',
      value: '',
      category: 'notifications',
      description: 'Emails notified on complaint submission',
      value_type: 'string',
      is_editable: true,
    },
    {
      key: 'rta_notification_emails',
      value: '',
      category: 'notifications',
      description: 'Emails notified on RTA submission',
      value_type: 'string',
      is_editable: true,
    },
    {
      key: 'enable_email_notifications',
      value: 'true',
      category: 'notifications',
      description: 'Enable email notifications',
      value_type: 'boolean',
      is_editable: true,
    },
    {
      key: 'enable_push_notifications',
      value: 'true',
      category: 'notifications',
      description: 'Enable push notifications',
      value_type: 'boolean',
      is_editable: true,
    },
    {
      key: 'auto_assign_incidents',
      value: 'true',
      category: 'workflow',
      description: 'Auto-assign incidents to safety team',
      value_type: 'boolean',
      is_editable: true,
    },
    {
      key: 'require_investigation',
      value: 'true',
      category: 'workflow',
      description: 'Require investigation for all incidents',
      value_type: 'boolean',
      is_editable: true,
    },
    {
      key: 'incident_sla_hours',
      value: '24',
      category: 'workflow',
      description: 'Hours to acknowledge an incident',
      value_type: 'number',
      is_editable: true,
    },
    {
      key: 'complaint_sla_hours',
      value: '48',
      category: 'workflow',
      description: 'Hours to respond to a complaint',
      value_type: 'number',
      is_editable: true,
    },
    {
      key: 'session_timeout_minutes',
      value: '60',
      category: 'security',
      description: 'Session timeout in minutes',
      value_type: 'number',
      is_editable: true,
    },
    {
      key: 'require_mfa',
      value: 'false',
      category: 'security',
      description: 'Require multi-factor authentication',
      value_type: 'boolean',
      is_editable: true,
    },
    {
      key: 'allow_portal_anonymous',
      value: 'false',
      category: 'security',
      description: 'Allow anonymous portal submissions',
      value_type: 'boolean',
      is_editable: true,
    },
    {
      key: 'date_format',
      value: 'DD/MM/YYYY',
      category: 'regional',
      description: 'Date display format',
      value_type: 'select',
      is_editable: true,
      select_options: [...REGIONAL_DATE_FORMATS],
    },
    {
      key: 'timezone',
      value: 'Europe/London',
      category: 'regional',
      description: 'Default timezone',
      value_type: 'select',
      is_editable: true,
      select_options: [...REGIONAL_TIMEZONES],
    },
    {
      key: 'language',
      value: 'en-GB',
      category: 'regional',
      description: 'Default language',
      value_type: 'select',
      is_editable: true,
      select_options: [...REGIONAL_LANGUAGES],
    },
  ]
}

/** Overlay API rows onto template definitions without inventing black branding. */
export function mergeSettingsFromApi(
  definitions: SettingDefinition[],
  apiItems: ApiSystemSetting[],
): SettingDefinition[] {
  const byKey = new Map(apiItems.map((item) => [item.key, item]))
  return definitions.map((def) => {
    const api = byKey.get(def.key)
    if (!api) return { ...def }
    return {
      ...def,
      value: api.value ?? '',
      description: api.description?.trim() ? api.description : def.description,
      is_editable: api.is_editable ?? def.is_editable,
    }
  })
}

export function brandingLooksUnset(settings: SettingDefinition[]): boolean {
  const name = settings.find((s) => s.key === 'company_name')?.value?.trim() ?? ''
  const logo = settings.find((s) => s.key === 'company_logo_url')?.value?.trim() ?? ''
  const primary = settings.find((s) => s.key === 'primary_color')?.value?.trim() ?? ''
  const accent = settings.find((s) => s.key === 'accent_color')?.value?.trim() ?? ''
  const primaryUnset = !primary || primary.toLowerCase() === '#000000'
  const accentUnset = !accent || accent.toLowerCase() === '#000000'
  return !name && !logo && primaryUnset && accentUnset
}

export function supportContactUnset(settings: SettingDefinition[]): boolean {
  const email = settings.find((s) => s.key === 'support_email')?.value?.trim() ?? ''
  const phone = settings.find((s) => s.key === 'support_phone')?.value?.trim() ?? ''
  return !email && !phone
}

/** Colour inputs require a valid hex; empty means unset — never treat black as loaded config. */
export function colorInputDisplayValue(value: string): string {
  const trimmed = value.trim()
  if (/^#[0-9A-Fa-f]{6}$/.test(trimmed) && trimmed.toLowerCase() !== '#000000') {
    return trimmed
  }
  if (/^#[0-9A-Fa-f]{6}$/.test(trimmed) && trimmed.toLowerCase() === '#000000') {
    return '#000000'
  }
  return '#ffffff'
}

export function isColorUnset(value: string): boolean {
  const trimmed = value.trim()
  return !trimmed || trimmed.toLowerCase() === '#000000'
}
