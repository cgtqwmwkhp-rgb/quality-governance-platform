import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Download, Loader2, Megaphone, Rocket, Save } from 'lucide-react'
import {
  documentCampaignApi,
  getApiErrorMessage,
  type CampaignGroup,
  type DocumentCampaign,
} from '../api/client'
import { toast } from '../contexts/ToastContext'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { Input } from '../components/ui/Input'
import { Badge } from '../components/ui/Badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/Select'
import {
  buildCampaignPayload,
  CAMPAIGN_REMINDER_PRESETS,
  canLaunchCampaign,
  defaultRequireQuiz,
  formatCampaignReminderHours,
  presetKeysFromReminderHours,
  type CampaignAudienceFormState,
  type CampaignReminderPresetKey,
} from './documentCampaignHelpers'

interface DocumentCampaignPanelProps {
  documentId: number
  hasApprovedQuiz: boolean
}

const DEFAULT_REMINDERS: CampaignReminderPresetKey[] = ['24h', '7d', '14d', '1month']

export function DocumentCampaignPanel({ documentId, hasApprovedQuiz }: DocumentCampaignPanelProps) {
  const { t } = useTranslation()

  const [dueWithinDays, setDueWithinDays] = useState(14)
  const [requireQuiz, setRequireQuiz] = useState(() => defaultRequireQuiz(hasApprovedQuiz))
  const [requireSign, setRequireSign] = useState(true)
  const [reminderPresets, setReminderPresets] = useState<Set<CampaignReminderPresetKey>>(
    () => new Set(DEFAULT_REMINDERS),
  )
  const [audience, setAudience] = useState<CampaignAudienceFormState>({
    audienceType: 'all_users',
    department: '',
    role: '',
    groupId: '',
    specificUserIds: '',
  })

  const [groups, setGroups] = useState<CampaignGroup[]>([])
  const [groupsLoading, setGroupsLoading] = useState(false)
  const [campaigns, setCampaigns] = useState<DocumentCampaign[]>([])
  const [campaignsLoading, setCampaignsLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [launching, setLaunching] = useState(false)
  const [exportingCampaignId, setExportingCampaignId] = useState<number | null>(null)

  useEffect(() => {
    setRequireQuiz(defaultRequireQuiz(hasApprovedQuiz))
  }, [hasApprovedQuiz])

  const loadReminderDefaults = useCallback(async () => {
    try {
      const response = await documentCampaignApi.getReminderDefaults()
      setReminderPresets(presetKeysFromReminderHours(response.data.reminder_hours ?? []))
    } catch {
      setReminderPresets(new Set(DEFAULT_REMINDERS))
    }
  }, [])

  const reminderHours = useMemo(
    () =>
      CAMPAIGN_REMINDER_PRESETS.filter((preset) => reminderPresets.has(preset.key)).map(
        (preset) => preset.hours,
      ),
    [reminderPresets],
  )

  const launchAllowed = canLaunchCampaign(requireQuiz, hasApprovedQuiz)

  const loadGroups = useCallback(async () => {
    setGroupsLoading(true)
    try {
      const response = await documentCampaignApi.listGroups()
      setGroups(response.data)
    } catch (err) {
      toast.error(getApiErrorMessage(err, t('documents.detail.campaign_groups_load_error')))
    } finally {
      setGroupsLoading(false)
    }
  }, [t])

  const loadCampaigns = useCallback(async () => {
    if (!documentId || Number.isNaN(documentId)) return
    setCampaignsLoading(true)
    try {
      const response = await documentCampaignApi.listCampaigns(documentId)
      setCampaigns(response.data)
    } catch (err) {
      toast.error(getApiErrorMessage(err, t('documents.detail.campaign_list_error')))
    } finally {
      setCampaignsLoading(false)
    }
  }, [documentId, t])

  useEffect(() => {
    void loadGroups()
    void loadCampaigns()
    void loadReminderDefaults()
  }, [loadGroups, loadCampaigns, loadReminderDefaults])

  const ensureRemindersSelected = () => {
    if (reminderHours.length === 0) {
      toast.error(t('documents.detail.campaign_reminder_required'))
      return false
    }
    return true
  }

  const handleExportEvidence = async (campaignId: number) => {
    setExportingCampaignId(campaignId)
    try {
      await documentCampaignApi.downloadEvidencePack(campaignId)
      toast.success(t('documents.detail.campaign_evidence_exported'))
    } catch (err) {
      toast.error(getApiErrorMessage(err, t('documents.detail.campaign_evidence_export_error')))
    } finally {
      setExportingCampaignId(null)
    }
  }

  const toggleReminder = (key: CampaignReminderPresetKey) => {
    setReminderPresets((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  const buildPayload = () =>
    buildCampaignPayload(documentId, {
      dueWithinDays,
      requireQuiz,
      requireSign,
      reminderHours,
      audience,
    })

  const handleSaveDraft = async () => {
    if (!launchAllowed) {
      toast.error(t('documents.detail.campaign_quiz_required'))
      return
    }
    if (!ensureRemindersSelected()) return
    setSaving(true)
    try {
      await documentCampaignApi.createCampaign(buildPayload())
      toast.success(t('documents.detail.campaign_draft_saved'))
      await loadCampaigns()
    } catch (err) {
      toast.error(getApiErrorMessage(err, t('documents.detail.campaign_save_error')))
    } finally {
      setSaving(false)
    }
  }

  const handleLaunch = async () => {
    if (!launchAllowed) {
      toast.error(t('documents.detail.campaign_quiz_required'))
      return
    }
    if (!ensureRemindersSelected()) return
    setLaunching(true)
    try {
      const createResponse = await documentCampaignApi.createCampaign(buildPayload())
      await documentCampaignApi.launchCampaign(createResponse.data.id)
      toast.success(t('documents.detail.campaign_launched'))
      await loadCampaigns()
    } catch (err) {
      toast.error(getApiErrorMessage(err, t('documents.detail.campaign_launch_error')))
    } finally {
      setLaunching(false)
    }
  }

  const audienceOptions: Array<{ value: CampaignAudienceFormState['audienceType']; label: string }> =
    [
      { value: 'all_users', label: t('documents.detail.campaign_audience_all') },
      { value: 'department', label: t('documents.detail.campaign_audience_department') },
      { value: 'role', label: t('documents.detail.campaign_audience_role') },
      { value: 'group', label: t('documents.detail.campaign_audience_group') },
      { value: 'specific_users', label: t('documents.detail.campaign_audience_users') },
    ]

  return (
    <Card className="p-4 space-y-4" data-testid="document-campaign-panel">
      <div className="flex items-center gap-2">
        <Megaphone className="w-4 h-4 text-primary" />
        <h3 className="font-medium text-foreground">{t('documents.detail.campaign_title')}</h3>
      </div>

      {!launchAllowed ? (
        <div
          className="rounded-lg border border-warning/40 bg-warning/10 px-4 py-3 text-sm text-foreground"
          role="alert"
          data-testid="campaign-quiz-required-banner"
        >
          {t('documents.detail.campaign_quiz_required')}
        </div>
      ) : null}

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label htmlFor="campaign-due-days" className="text-sm text-muted-foreground">
            {t('documents.detail.campaign_due_days')}
          </label>
          <Input
            id="campaign-due-days"
            type="number"
            min={1}
            max={365}
            value={dueWithinDays}
            onChange={(e) => setDueWithinDays(Math.max(1, Number(e.target.value) || 14))}
          />
        </div>
      </div>

      <div className="flex flex-wrap gap-4 text-sm">
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={requireQuiz}
            onChange={(e) => setRequireQuiz(e.target.checked)}
          />
          {t('documents.detail.campaign_require_quiz')}
        </label>
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={requireSign}
            onChange={(e) => setRequireSign(e.target.checked)}
          />
          {t('documents.detail.campaign_require_sign')}
        </label>
      </div>

      <div className="space-y-2">
        <p className="text-sm text-muted-foreground">{t('documents.detail.campaign_reminders')}</p>
        <p className="text-xs text-muted-foreground">{t('documents.detail.campaign_reminders_help')}</p>
        <div className="flex flex-wrap gap-4 text-sm">
          {CAMPAIGN_REMINDER_PRESETS.map((preset) => (
            <label key={preset.key} className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={reminderPresets.has(preset.key)}
                onChange={() => toggleReminder(preset.key)}
              />
              {t(`documents.detail.campaign_reminder_${preset.key}`)}
            </label>
          ))}
        </div>
      </div>

      <div className="space-y-3">
        <p className="text-sm text-muted-foreground">{t('documents.detail.campaign_audience')}</p>
        <div className="flex flex-wrap gap-4 text-sm">
          {audienceOptions.map((option) => (
            <label key={option.value} className="flex items-center gap-2">
              <input
                type="radio"
                name="campaign-audience"
                checked={audience.audienceType === option.value}
                onChange={() =>
                  setAudience((prev) => ({
                    ...prev,
                    audienceType: option.value,
                  }))
                }
              />
              {option.label}
            </label>
          ))}
        </div>

        {audience.audienceType === 'department' ? (
          <Input
            placeholder={t('documents.detail.campaign_department_placeholder')}
            value={audience.department}
            onChange={(e) => setAudience((prev) => ({ ...prev, department: e.target.value }))}
          />
        ) : null}

        {audience.audienceType === 'role' ? (
          <Input
            placeholder={t('documents.detail.campaign_role_placeholder')}
            value={audience.role}
            onChange={(e) => setAudience((prev) => ({ ...prev, role: e.target.value }))}
          />
        ) : null}

        {audience.audienceType === 'group' ? (
          <Select
            value={audience.groupId || undefined}
            onValueChange={(value) => setAudience((prev) => ({ ...prev, groupId: value }))}
          >
            <SelectTrigger aria-label={t('documents.detail.campaign_audience_group')}>
              <SelectValue placeholder={t('documents.detail.campaign_group_placeholder')} />
            </SelectTrigger>
            <SelectContent>
              {groupsLoading ? (
                <SelectItem value="__loading" disabled>
                  {t('documents.detail.campaign_groups_loading')}
                </SelectItem>
              ) : groups.length === 0 ? (
                <SelectItem value="__empty" disabled>
                  {t('documents.detail.campaign_groups_empty')}
                </SelectItem>
              ) : (
                groups.map((group) => (
                  <SelectItem key={group.id} value={String(group.id)}>
                    {group.name}
                  </SelectItem>
                ))
              )}
            </SelectContent>
          </Select>
        ) : null}

        {audience.audienceType === 'specific_users' ? (
          <Input
            placeholder={t('documents.detail.campaign_users_placeholder')}
            value={audience.specificUserIds}
            onChange={(e) =>
              setAudience((prev) => ({ ...prev, specificUserIds: e.target.value }))
            }
          />
        ) : null}
      </div>

      <div className="flex flex-wrap gap-2">
        <Button onClick={() => void handleSaveDraft()} disabled={saving || launching || !launchAllowed}>
          {saving ? (
            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
          ) : (
            <Save className="w-4 h-4 mr-2" />
          )}
          {t('documents.detail.campaign_save_draft')}
        </Button>
        <Button onClick={() => void handleLaunch()} disabled={launching || saving || !launchAllowed}>
          {launching ? (
            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
          ) : (
            <Rocket className="w-4 h-4 mr-2" />
          )}
          {t('documents.detail.campaign_launch')}
        </Button>
      </div>

      <div className="space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h4 className="text-sm font-medium text-foreground">
            {t('documents.detail.campaign_existing_title')}
          </h4>
          <Link
            to="/admin/campaign-compliance"
            className="text-sm text-primary hover:underline"
          >
            {t('documents.detail.campaign_compliance_link')}
          </Link>
        </div>
        {campaignsLoading ? (
          <div className="flex justify-center py-4">
            <Loader2 className="w-5 h-5 animate-spin text-primary" />
          </div>
        ) : campaigns.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t('documents.detail.campaign_none')}</p>
        ) : (
          <div className="space-y-2">
            {campaigns.map((campaign) => (
              <div
                key={campaign.id}
                className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border px-3 py-2 text-sm"
              >
                <div className="flex flex-col gap-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-foreground">
                      {t('documents.detail.campaign_row_label', { id: campaign.id })}
                    </span>
                    <Badge variant="secondary">{campaign.status}</Badge>
                  </div>
                  {campaign.reminder_hours.length > 0 ? (
                    <span className="text-xs text-muted-foreground">
                      {t('documents.detail.campaign_reminders_selected', {
                        reminders: formatCampaignReminderHours(campaign.reminder_hours, (key) =>
                          t(`documents.detail.campaign_reminder_${key}`),
                        ),
                      })}
                    </span>
                  ) : null}
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  {campaign.assigned_count != null ? (
                    <span className="text-muted-foreground">
                      {t('documents.detail.campaign_assigned_count', {
                        count: campaign.assigned_count,
                      })}
                    </span>
                  ) : null}
                  {campaign.launched_at ? (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => void handleExportEvidence(campaign.id)}
                      disabled={exportingCampaignId === campaign.id}
                    >
                      {exportingCampaignId === campaign.id ? (
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      ) : (
                        <Download className="w-4 h-4 mr-2" />
                      )}
                      {t('documents.detail.campaign_export_evidence')}
                    </Button>
                  ) : null}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </Card>
  )
}
