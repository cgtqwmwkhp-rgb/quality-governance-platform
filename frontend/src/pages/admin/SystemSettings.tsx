import { useCallback, useEffect, useMemo, useState } from 'react'
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
import { formatFieldName } from '../../helpers/displayLabels'
import { settingsApi, getApiErrorMessage } from '../../api/client'
import {
  brandingLooksUnset,
  buildSettingDefinitions,
  colorInputDisplayValue,
  isColorUnset,
  mergeSettingsFromApi,
  supportContactUnset,
  type SettingDefinition,
} from './systemSettingsHelpers'

interface SettingCategory {
  id: string
  name: string
  icon: React.ReactNode
  description: string
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

type LoadState = 'loading' | 'ready' | 'error'

export default function SystemSettings() {
  const [settings, setSettings] = useState<SettingDefinition[]>(() => buildSettingDefinitions())
  const [activeCategory, setActiveCategory] = useState('branding')
  const [isSaving, setIsSaving] = useState(false)
  const [saveSuccess, setSaveSuccess] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [hasChanges, setHasChanges] = useState(false)
  const [loadState, setLoadState] = useState<LoadState>('loading')
  const [loadError, setLoadError] = useState<string | null>(null)
  const [baselineJson, setBaselineJson] = useState('')

  const loadSettings = useCallback(async () => {
    setLoadState('loading')
    setLoadError(null)
    try {
      const data = await settingsApi.list()
      const merged = mergeSettingsFromApi(buildSettingDefinitions(), data.items ?? [])
      setSettings(merged)
      setBaselineJson(JSON.stringify(merged.map((s) => ({ key: s.key, value: s.value }))))
      setHasChanges(false)
      setLoadState('ready')
    } catch (err) {
      setLoadError(
        getApiErrorMessage(
          err,
          'System settings could not be loaded. Values shown are templates only — not live configuration.',
        ),
      )
      setLoadState('error')
    }
  }, [])

  useEffect(() => {
    void loadSettings()
  }, [loadSettings])

  const categorySettings = settings.filter((s) => s.category === activeCategory)

  const showBrandingHonesty =
    loadState === 'ready' && activeCategory === 'branding' && brandingLooksUnset(settings)
  const showContactHonesty =
    loadState === 'ready' && activeCategory === 'contact' && supportContactUnset(settings)

  const updateSetting = (key: string, value: string) => {
    setSettings((prev) => prev.map((s) => (s.key === key ? { ...s, value } : s)))
    setHasChanges(true)
  }

  const dirtyKeys = useMemo(() => {
    if (!baselineJson) return [] as string[]
    try {
      const baseline = new Map(
        (JSON.parse(baselineJson) as { key: string; value: string }[]).map((row) => [
          row.key,
          row.value,
        ]),
      )
      return settings.filter((s) => baseline.get(s.key) !== s.value).map((s) => s.key)
    } catch {
      return settings.map((s) => s.key)
    }
  }, [baselineJson, settings])

  const handleSave = async () => {
    if (loadState !== 'ready') {
      setSaveError('Settings have not finished loading — save is blocked to protect live branding.')
      return
    }
    setIsSaving(true)
    setSaveError(null)
    try {
      for (const key of dirtyKeys) {
        const setting = settings.find((s) => s.key === key)
        if (!setting || !setting.is_editable) continue
        await settingsApi.update(key, setting.value)
      }
      setBaselineJson(JSON.stringify(settings.map((s) => ({ key: s.key, value: s.value }))))
      setSaveSuccess(true)
      setHasChanges(false)
      setTimeout(() => setSaveSuccess(false), 3000)
    } catch (err) {
      setSaveError(getApiErrorMessage(err, 'Failed to save settings. Please try again.'))
    } finally {
      setIsSaving(false)
    }
  }

  const settingFieldId = (setting: SettingDefinition) => `setting-${setting.key}`

  const fieldNameHelper = (setting: SettingDefinition) => {
    const label = formatFieldName(setting.key)
    if (label.trim().toLowerCase() === setting.description.trim().toLowerCase()) {
      return null
    }
    return <p className="text-xs text-muted-foreground mt-1">{label}</p>
  }

  const renderSettingInput = (setting: SettingDefinition) => {
    const fieldId = settingFieldId(setting)

    switch (setting.value_type) {
      case 'boolean':
        return (
          <div className="flex items-center justify-between gap-4">
            <div>
              <Label htmlFor={fieldId} className="text-foreground">
                {setting.description}
              </Label>
              {fieldNameHelper(setting)}
            </div>
            <Switch
              id={fieldId}
              checked={setting.value === 'true'}
              onCheckedChange={(checked) => updateSetting(setting.key, checked ? 'true' : 'false')}
              disabled={loadState !== 'ready' || !setting.is_editable}
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
              disabled={loadState !== 'ready' || !setting.is_editable}
            />
            {fieldNameHelper(setting)}
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
                value={colorInputDisplayValue(setting.value)}
                onChange={(e) => updateSetting(setting.key, e.target.value)}
                className="w-10 h-10 rounded-lg border border-border cursor-pointer"
                disabled={loadState !== 'ready' || !setting.is_editable}
              />
              <Input
                value={setting.value}
                onChange={(e) => updateSetting(setting.key, e.target.value)}
                placeholder="Unset"
                aria-label={`${setting.description} (hex value)`}
                className="max-w-[150px] font-mono"
                disabled={loadState !== 'ready' || !setting.is_editable}
              />
            </div>
            {isColorUnset(setting.value) && (
              <p className="text-xs text-warning mt-1" data-testid={`setting-${setting.key}-unset`}>
                Unset in system settings — the live chrome theme is not shown here.
              </p>
            )}
            {fieldNameHelper(setting)}
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
              disabled={loadState !== 'ready' || !setting.is_editable}
            />
            {fieldNameHelper(setting)}
          </div>
        )

      case 'select':
        return (
          <div>
            <Label htmlFor={fieldId} className="block mb-1 text-foreground">
              {setting.description}
            </Label>
            <select
              id={fieldId}
              value={setting.value}
              onChange={(e) => updateSetting(setting.key, e.target.value)}
              className="flex h-10 w-full max-w-md rounded-md border border-input bg-background px-3 py-2 text-sm"
              disabled={loadState !== 'ready' || !setting.is_editable}
              data-testid={`setting-select-${setting.key}`}
            >
              {(setting.select_options ?? []).map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
            {fieldNameHelper(setting)}
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
              disabled={loadState !== 'ready' || !setting.is_editable}
            />
            {fieldNameHelper(setting)}
          </div>
        )
    }
  }

  return (
    <div className="min-h-screen bg-surface">
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
              <Button
                onClick={() => void handleSave()}
                disabled={isSaving || !hasChanges || loadState !== 'ready'}
              >
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
        {loadState === 'loading' && (
          <div
            className="mb-6 flex items-center gap-2 text-sm text-muted-foreground"
            data-testid="system-settings-loading"
          >
            <Loader2 className="w-4 h-4 animate-spin" />
            Loading live system settings…
          </div>
        )}
        {loadState === 'error' && loadError && (
          <Card className="mb-6 p-4 border-warning/40 bg-warning/5" data-testid="system-settings-load-error">
            <div className="flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-warning shrink-0 mt-0.5" />
              <div className="space-y-2">
                <p className="text-sm text-foreground">{loadError}</p>
                <Button variant="outline" size="sm" onClick={() => void loadSettings()}>
                  Retry
                </Button>
              </div>
            </div>
          </Card>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
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

              {showBrandingHonesty && (
                <div
                  className="mb-6 rounded-lg border border-warning/40 bg-warning/5 p-4 text-sm"
                  data-testid="branding-unset-honesty"
                >
                  Branding fields are empty in system settings. The live application chrome may still
                  show deployed theme branding — these blanks are not the colours currently in force.
                  Saving empty values will not update the deployed theme.
                </div>
              )}

              {showContactHonesty && (
                <div
                  className="mb-6 rounded-lg border border-warning/40 bg-warning/5 p-4 text-sm"
                  data-testid="support-contact-unset-honesty"
                >
                  No support email or phone is configured. Staff and engineers have no platform
                  contact details to use.
                </div>
              )}

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
