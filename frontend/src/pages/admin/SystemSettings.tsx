import { useState, useEffect, useCallback } from 'react';
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
} from 'lucide-react';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { cn } from '../../helpers/utils';
import { useToast, ToastContainer } from '../../components/ui/Toast';
import { settingsApi } from '../../services/api';

interface SettingCategory {
  id: string;
  name: string;
  icon: React.ReactNode;
  description: string;
}

interface Setting {
  key: string;
  value: string;
  category: string;
  description: string;
  value_type: 'string' | 'number' | 'boolean' | 'json' | 'email' | 'color';
  is_editable: boolean;
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
];

export default function SystemSettings() {
  const { toasts, show: _showToast, dismiss: dismissToast } = useToast();
  const [settings, setSettings] = useState<Setting[]>([]);
  const [activeCategory, setActiveCategory] = useState('branding');
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [changedKeys, setChangedKeys] = useState<Set<string>>(new Set());

  const loadSettings = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await settingsApi.list();
      const mapped: Setting[] = (data.items || []).map((s) => ({
        key: String(s.key || ''),
        value: String(s.value ?? ''),
        category: String(s.category || 'general'),
        description: String(s.description || ''),
        value_type: (s.value_type as Setting['value_type']) || 'string',
        is_editable: s.is_editable !== false,
      }));
      setSettings(mapped);
    } catch {
      setError('Failed to load settings');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadSettings(); }, [loadSettings]);

  const categorySettings = settings.filter((s) => s.category === activeCategory);

  const updateSetting = (key: string, value: string) => {
    setSettings((prev) =>
      prev.map((s) => (s.key === key ? { ...s, value } : s))
    );
    setChangedKeys((prev) => new Set(prev).add(key));
    setHasChanges(true);
  };

  const handleSave = async () => {
    setIsSaving(true);
    try {
      const promises = Array.from(changedKeys).map((key) => {
        const setting = settings.find((s) => s.key === key);
        if (setting) return settingsApi.update(key, setting.value);
        return Promise.resolve();
      });
      await Promise.all(promises);
      setChangedKeys(new Set());
      setSaveSuccess(true);
      setHasChanges(false);
      setTimeout(() => setSaveSuccess(false), 2000);
    } catch {
      setError('Failed to save settings');
    } finally {
      setIsSaving(false);
    }
  };

  const renderSettingInput = (setting: Setting) => {
    switch (setting.value_type) {
      case 'boolean':
        return (
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-foreground">{setting.description}</p>
              <p className="text-xs text-muted-foreground">{setting.key}</p>
            </div>
            <button
              onClick={() => updateSetting(setting.key, setting.value === 'true' ? 'false' : 'true')}
              className={cn(
                'w-12 h-6 rounded-full transition-colors relative',
                setting.value === 'true' ? 'bg-primary' : 'bg-muted'
              )}
            >
              <div
                className={cn(
                  'w-5 h-5 bg-white rounded-full absolute top-0.5 transition-transform shadow-sm',
                  setting.value === 'true' ? 'translate-x-6' : 'translate-x-0.5'
                )}
              />
            </button>
          </div>
        );

      case 'number':
        return (
          <div>
            <label className="block text-sm font-medium text-foreground mb-1">
              {setting.description}
            </label>
            <Input
              type="number"
              value={setting.value}
              onChange={(e) => updateSetting(setting.key, e.target.value)}
              className="max-w-[150px]"
            />
            <p className="text-xs text-muted-foreground mt-1">{setting.key}</p>
          </div>
        );

      case 'color':
        return (
          <div>
            <label className="block text-sm font-medium text-foreground mb-1">
              {setting.description}
            </label>
            <div className="flex items-center gap-3">
              <input
                type="color"
                value={setting.value}
                onChange={(e) => updateSetting(setting.key, e.target.value)}
                className="w-10 h-10 rounded-lg border border-border cursor-pointer"
              />
              <Input
                value={setting.value}
                onChange={(e) => updateSetting(setting.key, e.target.value)}
                placeholder="#000000"
                className="max-w-[150px] font-mono"
              />
            </div>
            <p className="text-xs text-muted-foreground mt-1">{setting.key}</p>
          </div>
        );

      case 'email':
        return (
          <div>
            <label className="block text-sm font-medium text-foreground mb-1">
              {setting.description}
            </label>
            <Input
              type="email"
              value={setting.value}
              onChange={(e) => updateSetting(setting.key, e.target.value)}
              placeholder="email@example.com"
            />
            <p className="text-xs text-muted-foreground mt-1">{setting.key}</p>
          </div>
        );

      default:
        return (
          <div>
            <label className="block text-sm font-medium text-foreground mb-1">
              {setting.description}
            </label>
            <Input
              value={setting.value}
              onChange={(e) => updateSetting(setting.key, e.target.value)}
            />
            <p className="text-xs text-muted-foreground mt-1">{setting.key}</p>
          </div>
        );
    }
  };

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
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 sm:px-6 py-8">
        {loading && (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="w-8 h-8 animate-spin text-primary" />
          </div>
        )}
        {error && !loading && (
          <Card className="p-6 text-center">
            <AlertCircle className="w-8 h-8 mx-auto text-destructive mb-2" />
            <p className="text-destructive">{error}</p>
            <Button variant="outline" onClick={loadSettings} className="mt-4">Retry</Button>
          </Card>
        )}
        {!loading && !error && <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
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
                      : 'hover:bg-muted text-foreground'
                  )}
                >
                  <div
                    className={cn(
                      'p-2 rounded-lg',
                      activeCategory === category.id
                        ? 'bg-white/20'
                        : 'bg-primary/10 text-primary'
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
                          : 'text-muted-foreground'
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
                        : 'text-muted-foreground'
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
        </div>}
      </main>
      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}
