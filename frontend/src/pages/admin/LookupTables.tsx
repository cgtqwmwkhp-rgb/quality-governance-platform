import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { ClipboardList, Loader2, Plus, Settings2 } from 'lucide-react'
import { lookupsApi, type LookupOption } from '../../api/client'
import { Card, CardContent, CardHeader } from '../../components/ui/Card'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/Dialog'
import { toast } from '../../contexts/ToastContext'
import { cn } from '../../helpers/utils'

const LOOKUP_CATEGORIES = [
  { key: 'incident_types', label: 'Incident Types' },
  { key: 'risk_categories', label: 'Risk Categories' },
  { key: 'complaint_types', label: 'Complaint Types' },
  { key: 'severity_levels', label: 'Severity Levels' },
  { key: 'departments', label: 'Departments' },
  { key: 'locations', label: 'Locations' },
] as const

type CategoryKey = (typeof LOOKUP_CATEGORIES)[number]['key']

type CategoryState = {
  total: number | null
  loading: boolean
  error: boolean
}

export default function LookupTables() {
  const { t } = useTranslation()
  const [counts, setCounts] = useState<Record<string, CategoryState>>(() =>
    Object.fromEntries(
      LOOKUP_CATEGORIES.map((c) => [c.key, { total: null, loading: true, error: false }]),
    ),
  )
  const [editorCategory, setEditorCategory] = useState<(typeof LOOKUP_CATEGORIES)[number] | null>(
    null,
  )
  const [options, setOptions] = useState<LookupOption[]>([])
  const [editorLoading, setEditorLoading] = useState(false)
  const [editorError, setEditorError] = useState<string | null>(null)
  const [newCode, setNewCode] = useState('')
  const [newLabel, setNewLabel] = useState('')
  const [saving, setSaving] = useState(false)

  const refreshCounts = useCallback(async () => {
    await Promise.all(
      LOOKUP_CATEGORIES.map(async (cat) => {
        try {
          const data = await lookupsApi.list(cat.key, false)
          setCounts((prev) => ({
            ...prev,
            [cat.key]: { total: data.total ?? data.items?.length ?? 0, loading: false, error: false },
          }))
        } catch {
          setCounts((prev) => ({
            ...prev,
            [cat.key]: { total: null, loading: false, error: true },
          }))
        }
      }),
    )
  }, [])

  useEffect(() => {
    void refreshCounts()
  }, [refreshCounts])

  const openEditor = async (cat: (typeof LOOKUP_CATEGORIES)[number]) => {
    setEditorCategory(cat)
    setEditorLoading(true)
    setEditorError(null)
    setOptions([])
    setNewCode('')
    setNewLabel('')
    try {
      const data = await lookupsApi.list(cat.key, false)
      setOptions(data.items ?? [])
      setCounts((prev) => ({
        ...prev,
        [cat.key]: { total: data.total ?? data.items?.length ?? 0, loading: false, error: false },
      }))
    } catch {
      setEditorError(
        t(
          'admin.lookups.load_failed',
          'Could not load lookup options. Counts are not shown as zero.',
        ),
      )
    } finally {
      setEditorLoading(false)
    }
  }

  const handleCreate = async () => {
    if (!editorCategory || !newCode.trim() || !newLabel.trim()) return
    setSaving(true)
    try {
      const created = await lookupsApi.create(editorCategory.key, {
        code: newCode.trim(),
        label: newLabel.trim(),
        is_active: true,
        display_order: options.length,
      })
      setOptions((prev) => [...prev, created])
      setNewCode('')
      setNewLabel('')
      setCounts((prev) => ({
        ...prev,
        [editorCategory.key]: {
          total: (prev[editorCategory.key]?.total ?? options.length) + 1,
          loading: false,
          error: false,
        },
      }))
      toast.success(t('admin.lookups.option_added', 'Lookup option added'))
    } catch {
      toast.error(t('admin.lookups.save_failed', 'Failed to add lookup option'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-6" data-testid="admin-lookup-tables">
      <div>
        <h1 className="text-2xl font-bold">{t('admin.lookups.title', 'Lookup Tables')}</h1>
        <p className="text-muted-foreground mt-1">
          {t('admin.lookups.subtitle', 'Manage dropdown options and reference data')}
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {LOOKUP_CATEGORIES.map((cat) => {
          const state = counts[cat.key]
          const notConfigured = !state?.error && !state?.loading && state?.total === 0
          const countLabel = state?.loading
            ? t('admin.lookups.loading', 'Loading…')
            : state?.error
              ? t('admin.lookups.unavailable', 'Count unavailable')
              : notConfigured
                ? t('admin.lookups.not_configured', 'Not configured')
                : t('admin.lookups.item_count', '{{count}} items', { count: state?.total ?? 0 })

          return (
            <Card
              key={cat.key}
              className={cn(
                'hover:shadow-md transition-shadow',
                notConfigured && 'border-amber-300/80',
              )}
              data-testid={`lookup-card-${cat.key}`}
            >
              <CardHeader className="flex flex-row items-center gap-3 pb-2">
                <div className="w-10 h-10 rounded-lg bg-orange-100 flex items-center justify-center">
                  <ClipboardList className="w-5 h-5 text-orange-600" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="font-medium">{cat.label}</p>
                  <p
                    className={cn(
                      'text-sm',
                      notConfigured ? 'text-amber-700 font-medium' : 'text-muted-foreground',
                    )}
                    data-testid={`lookup-count-${cat.key}`}
                  >
                    {countLabel}
                  </p>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                <p className="text-sm text-muted-foreground">
                  {t(
                    `admin.lookups.${cat.key}_desc`,
                    `Configure ${cat.label.toLowerCase()} for your organisation`,
                  )}
                </p>
                {notConfigured ? (
                  <p className="text-xs text-amber-800" data-testid={`lookup-empty-${cat.key}`}>
                    {t(
                      'admin.lookups.empty_honesty',
                      'No options yet — forms using this category will show an empty dropdown until you configure it.',
                    )}
                  </p>
                ) : null}
                <Button
                  type="button"
                  className="w-full"
                  variant={notConfigured ? 'default' : 'outline'}
                  data-testid={`lookup-configure-${cat.key}`}
                  onClick={() => void openEditor(cat)}
                >
                  <Settings2 className="w-4 h-4" />
                  {t('admin.lookups.configure', 'Configure')}
                </Button>
              </CardContent>
            </Card>
          )
        })}
      </div>

      <Dialog open={editorCategory != null} onOpenChange={(open) => !open && setEditorCategory(null)}>
        <DialogContent className="max-w-lg" data-testid="lookup-editor-dialog">
          <DialogHeader>
            <DialogTitle>
              {t('admin.lookups.editor_title', 'Configure {{label}}', {
                label: editorCategory?.label ?? '',
              })}
            </DialogTitle>
          </DialogHeader>

          {editorLoading ? (
            <div className="flex items-center gap-2 py-8 text-sm text-muted-foreground justify-center">
              <Loader2 className="w-4 h-4 animate-spin" />
              {t('admin.lookups.loading', 'Loading…')}
            </div>
          ) : editorError ? (
            <p className="text-sm text-destructive py-4" data-testid="lookup-editor-error">
              {editorError}
            </p>
          ) : (
            <div className="space-y-4">
              {options.length === 0 ? (
                <p className="text-sm text-muted-foreground" data-testid="lookup-editor-empty">
                  {t(
                    'admin.lookups.editor_empty',
                    'Not configured — add the first option below. Nothing is fabricated.',
                  )}
                </p>
              ) : (
                <ul className="space-y-2 max-h-56 overflow-y-auto" data-testid="lookup-editor-list">
                  {options.map((opt) => (
                    <li
                      key={opt.id}
                      className="flex items-center justify-between rounded-md border border-border px-3 py-2 text-sm"
                    >
                      <span>
                        <span className="font-mono text-xs text-muted-foreground mr-2">
                          {opt.code}
                        </span>
                        {opt.label}
                      </span>
                      {!opt.is_active ? (
                        <span className="text-xs text-muted-foreground">inactive</span>
                      ) : null}
                    </li>
                  ))}
                </ul>
              )}

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                <Input
                  placeholder={t('admin.lookups.code_placeholder', 'Code')}
                  value={newCode}
                  onChange={(e) => setNewCode(e.target.value)}
                  data-testid="lookup-new-code"
                />
                <Input
                  placeholder={t('admin.lookups.label_placeholder', 'Label')}
                  value={newLabel}
                  onChange={(e) => setNewLabel(e.target.value)}
                  data-testid="lookup-new-label"
                />
              </div>
            </div>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setEditorCategory(null)}>
              {t('common.close', 'Close')}
            </Button>
            <Button
              type="button"
              disabled={saving || !newCode.trim() || !newLabel.trim() || !!editorError}
              onClick={() => void handleCreate()}
              data-testid="lookup-add-option"
            >
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
              {t('admin.lookups.add_option', 'Add option')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

export type { CategoryKey }
