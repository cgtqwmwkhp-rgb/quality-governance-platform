import { useState } from 'react'
import {
  Save,
  Settings,
  Mail,
  Bell,
  Palette,
  Shield,
  Globe,
  Check,
  Loader2,
  AlertCircle,
  ChevronRight,
} from 'lucide-react'
import { Card } from '../../components/ui/Card'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Label } from '../../components/ui/Label'
import { Switch } from '../../components/ui/Switch'
import { cn } from '../../helpers/utils'

interface SettingCategory {
  id: string
  name: string
  icon: React.ReactNode
  description: string
}

interface Setting {
  key: string
  value: string
  category: string
  description: string
  value_type: 'string' | 'number' | 'boolean' | 'json' | 'email' | 'color'
  is_editable: boolean
}

const SETTING_CATEGORIES: SettingCategory[] = [
  {
    id: 'branding',
    name: 'Branding',
    icon: <Palette className="w-5 h-5" />,
    description: 'Company name, logo, and colors',
  },
  {
    id: 'contact',
    name: 'Contact Details',
    icon: <Mail className="w-5 h-5" />,
    description: 'Support email and phone numbers',
  },
  {
    id: 'notifications',
    name: 'Notifications',
    icon: <Bell className="w-5 h-5" />,
    description: 'Email notifications and alerts',
  },
  {
    id: 'workflow',
    name: 'Workflow',
    icon: <Settings className="w-5 h-5" />,
    description: 'Automation and assignment rules',
  },
  {
    id: 'security',
    name: 'Security',
    icon: <Shield className="w-5 h-5" />,
    description: 'Authentication and access control',
  },
  {
    id: 'regional',
    name: 'Regional',
    icon: <Globe className="w-5 h-5" />,
    description: 'Date format, timezone, and language',
  },
]

const INITIAL_SETTINGS: Setting[] = [
  // Branding
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
    value: '#000000',
    category: 'branding',
    description: 'Primary brand color',
    value_type: 'color',
    is_editable: true,
  },
  {
    key: 'accent_color',
    value: '#000000',
    category: 'branding',
    description: 'Accent/hover color',
    value_type: 'color',
    is_editable: true,
  },

  // Contact
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

  // Notifications
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

  // Workflow
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

  // Security
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

  // Regional
  {
    key: 'date_format',
    value: 'DD/MM/YYYY',
    category: 'regional',
    description: 'Date display format',
    value_type: 'string',
    is_editable: true,
  },
  {
    key: 'timezone',
    value: 'Europe/London',
    category: 'regional',
    description: 'Default timezone',
    value_type: 'string',
    is_editable: true,
  },
  {
    key: 'language',
    value: 'en-GB',
    category: 'regional',
    description: 'Default language',
    value_type: 'string',
    is_editable: true,
  },
]

export default function SystemSettings() {
  const [settings, setSettings] = useState<Setting[]>(INITIAL_SETTINGS)
  const [activeCategory, setActiveCategory] = useState('branding')
  const [isSaving, setIsSaving] = useState(false)
  const [saveSuccess, setSaveSuccess] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [hasChanges, setHasChanges] = useState(false)

  const categorySettings = settings.filter((s) => s.category === activeCategory)

  const updateSetting = (key: string, value: string) => {
    setSettings((prev) => prev.map((s) => (s.key === key ? { ...s, value } : s)))
    setHasChanges(true)
  }

  const handleSave = async () => {
    setIsSaving(true)
    setSaveError(null)
    try {
      // In real implementation, save to API
      await new Promise((resolve) => setTimeout(resolve, 1000))
      setSaveSuccess(true)
      setHasChanges(false)
      setTimeout(() => setSaveSuccess(false), 3000)
    } catch {
      console.error('Failed to save settings')
      setSaveError('Failed to save settings. Please try again.')
    } finally {
      setIsSaving(false)
    }
  }

  // The storage key doubles as the control id, so every visible label is also
  // the programmatic label. It is deliberately not rendered as visible copy —
  // "company_name" is an internal field name, not something an admin needs to
  // read (PX-198).
  const settingFieldId = (setting: Setting) => `setting-${setting.key}`

  const renderSettingInput = (setting: Setting) => {
    const fieldId = settingFieldId(setting)

    switch (setting.value_type) {
      case 'boolean':
        return (
          <div className="flex items-center justify-between gap-4">
            <Label htmlFor={fieldId} className="text-foreground">
              {setting.description}
            </Label>
            <Switch
              id={fieldId}
              checked={setting.value === 'true'}
              onCheckedChange={(checked) => updateSetting(setting.key, checked ? 'true' : 'false')}
            />
          </div>
        )

      case 'number':
        return (
          <div>
            <Label htmlFor={fieldId} className="block mb-1 text-foreground">
              {setting.description}
            </Label>
            <Input
              id={fieldId}
              type="number"
              value={setting.value}
              onChange={(e) => updateSetting(setting.key, e.target.value)}
              className="max-w-[150px]"
            />
          </div>
        )

      case 'color':
        return (
          <div>
            <Label htmlFor={fieldId} className="block mb-1 text-foreground">
              {setting.description}
            </Label>
            <div className="flex items-center gap-3">
              <input
                id={fieldId}
                type="color"
                value={setting.value}
                onChange={(e) => updateSetting(setting.key, e.target.value)}
                className="w-10 h-10 rounded-lg border border-border cursor-pointer"
              />
              <Input
                value={setting.value}
                onChange={(e) => updateSetting(setting.key, e.target.value)}
                placeholder="#000000"
                aria-label={`${setting.description} (hex value)`}
                className="max-w-[150px] font-mono"
              />
            </div>
          </div>
        )

      case 'email':
        return (
          <div>
            <Label htmlFor={fieldId} className="block mb-1 text-foreground">
              {setting.description}
            </Label>
            <Input
              id={fieldId}
              type="email"
              value={setting.value}
              onChange={(e) => updateSetting(setting.key, e.target.value)}
              placeholder="email@example.com"
            />
          </div>
        )

      default:
        return (
          <div>
            <Label htmlFor={fieldId} className="block mb-1 text-foreground">
              {setting.description}
            </Label>
            <Input
              id={fieldId}
              value={setting.value}
              onChange={(e) => updateSetting(setting.key, e.target.value)}
            />
          </div>
        )
    }
  }

  return (
    <div className="min-h-screen bg-surface">
      {/* Header */}
      <header className="bg-card border-b border-border sticky top-0 z-40">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-foreground">System Settings</h1>
              <p className="text-muted-foreground mt-1">
                Configure system-wide settings and preferences
              </p>
            </div>
            <div className="flex flex-col items-end">
              <Button onClick={handleSave} disabled={isSaving || !hasChanges}>
                {isSaving ? (
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                ) : saveSuccess ? (
                  <Check className="w-4 h-4 mr-2" />
                ) : (
                  <Save className="w-4 h-4 mr-2" />
                )}
                {saveSuccess ? 'Saved!' : 'Save Changes'}
              </Button>
              {saveError && <p className="text-sm text-destructive mt-2">{saveError}</p>}
              {saveSuccess && (
                <p className="text-sm text-green-600 mt-2">Settings saved successfully</p>
              )}
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 sm:px-6 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* Category Navigation */}
          <div className="lg:col-span-1">
            <nav className="space-y-1">
              {SETTING_CATEGORIES.map((category) => (
                <button
                  key={category.id}
                  onClick={() => setActiveCategory(category.id)}
                  className={cn(
                    'w-full flex items-center gap-3 px-4 py-3 rounded-xl text-left transition-colors',
                    activeCategory === category.id
                      ? 'bg-primary text-primary-foreground'
                      : 'hover:bg-muted text-foreground',
                  )}
                >
                  <div
                    className={cn(
                      'p-2 rounded-lg',
                      activeCategory === category.id ? 'bg-white/20' : 'bg-primary/10 text-primary',
                    )}
                  >
                    {category.icon}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-medium">{category.name}</p>
                    <p
                      className={cn(
                        'text-xs truncate',
                        activeCategory === category.id
                          ? 'text-primary-foreground/70'
                          : 'text-muted-foreground',
                      )}
                    >
                      {category.description}
                    </p>
                  </div>
                  <ChevronRight
                    className={cn(
                      'w-4 h-4',
                      activeCategory === category.id
                        ? 'text-primary-foreground'
                        : 'text-muted-foreground',
                    )}
                  />
                </button>
              ))}
            </nav>
          </div>

          {/* Settings Panel */}
          <div className="lg:col-span-3">
            <Card className="p-6">
              <div className="flex items-center gap-3 mb-6">
                <div className="p-2 bg-primary/10 text-primary rounded-lg">
                  {SETTING_CATEGORIES.find((c) => c.id === activeCategory)?.icon}
                </div>
                <div>
                  <h2 className="text-lg font-semibold text-foreground">
                    {SETTING_CATEGORIES.find((c) => c.id === activeCategory)?.name}
                  </h2>
                  <p className="text-sm text-muted-foreground">
                    {SETTING_CATEGORIES.find((c) => c.id === activeCategory)?.description}
                  </p>
                </div>
              </div>

              <div className="space-y-6">
                {categorySettings.map((setting) => (
                  <div
                    key={setting.key}
                    className="pb-6 border-b border-border last:border-0 last:pb-0"
                  >
                    {renderSettingInput(setting)}
                  </div>
                ))}

                {categorySettings.length === 0 && (
                  <div className="text-center py-12 text-muted-foreground">
                    <AlertCircle className="w-12 h-12 mx-auto mb-3 opacity-50" />
                    <p>No settings in this category</p>
                  </div>
                )}
              </div>
            </Card>
          </div>
        </div>
      </main>
    </div>
  )
}
