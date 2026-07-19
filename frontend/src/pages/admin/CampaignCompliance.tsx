import { Fragment, useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { ChevronDown, ChevronRight, Download, Loader2, Megaphone, Save } from 'lucide-react'
import {
  documentCampaignApi,
  getApiErrorMessage,
  type CampaignComplianceRow,
  type GroupComplianceRow,
} from '../../api/client'
import { toast } from '../../contexts/ToastContext'
import { Button } from '../../components/ui/Button'
import { Card, CardContent, CardHeader } from '../../components/ui/Card'
import {
  ALL_REMINDER_PRESET_KEYS,
  CAMPAIGN_REMINDER_PRESETS,
  presetKeysFromReminderHours,
  reminderHoursFromPresetKeys,
  type CampaignReminderPresetKey,
} from '../documentCampaignHelpers'
import { CampaignRosterPanel } from '../CampaignRosterPanel'
import { CampaignCommandKpis } from '../CampaignCommandKpis'
import { CampaignAnalyticsPanel } from '../CampaignAnalyticsPanel'
import { CampaignPeopleChase } from '../CampaignPeopleChase'

export default function CampaignCompliance() {
  const { t } = useTranslation()
  const [reminderPresets, setReminderPresets] = useState<Set<CampaignReminderPresetKey>>(
    () => new Set(ALL_REMINDER_PRESET_KEYS),
  )
  const [defaultsLoading, setDefaultsLoading] = useState(true)
  const [savingDefaults, setSavingDefaults] = useState(false)
  const [complianceRows, setComplianceRows] = useState<CampaignComplianceRow[]>([])
  const [complianceLoading, setComplianceLoading] = useState(true)
  const [exportingId, setExportingId] = useState<number | null>(null)
  const [exportingFormat, setExportingFormat] = useState<'json' | 'csv' | 'pdf' | null>(null)
  const [expandedCampaignId, setExpandedCampaignId] = useState<number | null>(null)
  const [groupRowsByCampaign, setGroupRowsByCampaign] = useState<Record<number, GroupComplianceRow[]>>({})
  const [groupLoadingId, setGroupLoadingId] = useState<number | null>(null)

  const reminderHours = useMemo(
    () => reminderHoursFromPresetKeys(reminderPresets),
    [reminderPresets],
  )

  const loadDefaults = useCallback(async () => {
    setDefaultsLoading(true)
    try {
      const response = await documentCampaignApi.getReminderDefaults()
      setReminderPresets(presetKeysFromReminderHours(response.data.reminder_hours ?? []))
    } catch {
      setReminderPresets(new Set(ALL_REMINDER_PRESET_KEYS))
    } finally {
      setDefaultsLoading(false)
    }
  }, [])

  const loadCompliance = useCallback(async () => {
    setComplianceLoading(true)
    try {
      const response = await documentCampaignApi.listCompliance()
      setComplianceRows(response.data.items ?? [])
    } catch (err) {
      toast.error(getApiErrorMessage(err, t('admin.campaign_compliance.load_error')))
      setComplianceRows([])
    } finally {
      setComplianceLoading(false)
    }
  }, [t])

  useEffect(() => {
    void loadDefaults()
    void loadCompliance()
  }, [loadDefaults, loadCompliance])

  const toggleReminder = (key: CampaignReminderPresetKey) => {
    setReminderPresets((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  const handleSaveDefaults = async () => {
    if (reminderHours.length === 0) {
      toast.error(t('admin.campaign_compliance.reminder_required'))
      return
    }
    setSavingDefaults(true)
    try {
      await documentCampaignApi.setReminderDefaults(reminderHours)
      toast.success(t('admin.campaign_compliance.defaults_saved'))
    } catch (err) {
      toast.error(getApiErrorMessage(err, t('admin.campaign_compliance.defaults_save_error')))
    } finally {
      setSavingDefaults(false)
    }
  }


  const handleToggleCampaignDetail = async (row: CampaignComplianceRow) => {
    if (expandedCampaignId === row.campaign_id) {
      setExpandedCampaignId(null)
      return
    }

    setExpandedCampaignId(row.campaign_id)
    const hasGroups = (row.audience_group_ids?.length ?? 0) > 0
    if (!hasGroups || groupRowsByCampaign[row.campaign_id]) return

    setGroupLoadingId(row.campaign_id)
    try {
      const response = await documentCampaignApi.getComplianceByGroup(row.campaign_id)
      setGroupRowsByCampaign((prev) => ({
        ...prev,
        [row.campaign_id]: response.data.items ?? [],
      }))
    } catch (err) {
      toast.error(getApiErrorMessage(err, t('admin.campaign_compliance.group_load_error')))
    } finally {
      setGroupLoadingId(null)
    }
  }

  const handleExportEvidence = async (campaignId: number, format: 'json' | 'csv' | 'pdf') => {
    setExportingId(campaignId)
    setExportingFormat(format)
    try {
      if (format === 'csv') {
        await documentCampaignApi.downloadEvidencePackCsv(campaignId)
      } else if (format === 'pdf') {
        await documentCampaignApi.downloadEvidencePackPdf(campaignId)
      } else {
        await documentCampaignApi.downloadEvidencePack(campaignId)
      }
      toast.success(t('admin.campaign_compliance.evidence_exported'))
    } catch (err) {
      toast.error(getApiErrorMessage(err, t('admin.campaign_compliance.evidence_export_error')))
    } finally {
      setExportingId(null)
      setExportingFormat(null)
    }
  }

  return (
    <div className="space-y-6" data-testid="campaign-compliance-page">
      <div>
        <h1 className="text-2xl font-bold">{t('admin.campaign_compliance.title')}</h1>
        <p className="text-muted-foreground mt-1">{t('admin.campaign_compliance.subtitle')}</p>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Megaphone className="w-5 h-5 text-primary" />
            <h2 className="text-lg font-semibold">{t('admin.campaign_compliance.defaults_title')}</h2>
          </div>
          <p className="text-sm text-muted-foreground">{t('admin.campaign_compliance.defaults_help')}</p>
        </CardHeader>
        <CardContent className="space-y-4">
          {defaultsLoading ? (
            <Loader2 className="w-5 h-5 animate-spin text-primary" />
          ) : (
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
          )}
          <Button onClick={() => void handleSaveDefaults()} disabled={savingDefaults || defaultsLoading}>
            {savingDefaults ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <Save className="w-4 h-4 mr-2" />
            )}
            {t('admin.campaign_compliance.save_defaults')}
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <h2 className="text-lg font-semibold">{t('campaigns.command.title', 'Campaign command')}</h2>
          <p className="text-sm text-muted-foreground">
            {t('campaigns.command.subtitle', 'Portfolio KPIs and recent completion activity.')}
          </p>
        </CardHeader>
        <CardContent>
          <CampaignCommandKpis />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <h2 className="text-lg font-semibold">{t('admin.campaign_compliance.table_title')}</h2>
        </CardHeader>
        <CardContent>
          {complianceLoading ? (
            <div className="flex justify-center py-8">
              <Loader2 className="w-6 h-6 animate-spin text-primary" />
            </div>
          ) : complianceRows.length === 0 ? (
            <p className="text-sm text-muted-foreground">{t('admin.campaign_compliance.empty')}</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-muted-foreground">
                    <th className="py-2 pr-2 font-medium w-8" />
                    <th className="py-2 pr-4 font-medium">{t('admin.campaign_compliance.col_document')}</th>
                    <th className="py-2 pr-4 font-medium">{t('admin.campaign_compliance.col_status')}</th>
                    <th className="py-2 pr-4 font-medium">{t('admin.campaign_compliance.col_completion')}</th>
                    <th className="py-2 pr-4 font-medium">{t('admin.campaign_compliance.col_pending')}</th>
                    <th className="py-2 pr-4 font-medium">{t('admin.campaign_compliance.col_overdue')}</th>
                    <th className="py-2 pr-4 font-medium">{t('admin.campaign_compliance.col_quiz_pass')}</th>
                    <th className="py-2 font-medium">{t('admin.campaign_compliance.col_actions')}</th>
                  </tr>
                </thead>
                <tbody>
                  {complianceRows.map((row) => {
                    const hasGroups = (row.audience_group_ids?.length ?? 0) > 0
                    const expanded = expandedCampaignId === row.campaign_id
                    const groupRows = groupRowsByCampaign[row.campaign_id] ?? []

                    return (
                      <Fragment key={row.campaign_id}>
                        <tr className="border-b border-border last:border-0">
                          <td className="py-3 pr-2">
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-8 w-8 p-0"
                              aria-expanded={expanded}
                              aria-label={t(
                                'admin.campaign_compliance.toggle_roster',
                                'Show assignee roster',
                              )}
                              onClick={() => void handleToggleCampaignDetail(row)}
                              data-testid={`campaign-compliance-expand-${row.campaign_id}`}
                            >
                              {expanded ? (
                                <ChevronDown className="w-4 h-4" />
                              ) : (
                                <ChevronRight className="w-4 h-4" />
                              )}
                            </Button>
                          </td>
                          <td className="py-3 pr-4">
                            <p className="font-medium text-foreground">
                              {row.title || row.document_title || `#${row.document_id}`}
                            </p>
                            <p className="text-xs text-muted-foreground">
                              {t('admin.campaign_compliance.campaign_id', { id: row.campaign_id })}
                            </p>
                          </td>
                          <td className="py-3 pr-4 capitalize">{row.status}</td>
                          <td className="py-3 pr-4">{Math.round(row.completion_rate)}%</td>
                          <td className="py-3 pr-4">{row.pending}</td>
                          <td className="py-3 pr-4">{row.overdue}</td>
                          <td className="py-3 pr-4">{row.quiz_pass_count ?? 0}</td>
                          <td className="py-3">
                            <div className="flex flex-wrap gap-2">
                              <Button variant="outline" size="sm" asChild>
                                <Link
                                  to={`/documents/${row.document_id}?tab=campaign-results&campaignId=${row.campaign_id}`}
                                >
                                  {t('admin.campaign_compliance.open_document', 'Document results')}
                                </Link>
                              </Button>
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => void handleExportEvidence(row.campaign_id, 'json')}
                                disabled={exportingId === row.campaign_id}
                              >
                                {exportingId === row.campaign_id && exportingFormat === 'json' ? (
                                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                                ) : (
                                  <Download className="w-4 h-4 mr-2" />
                                )}
                                {t('admin.campaign_compliance.export_evidence')}
                              </Button>
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => void handleExportEvidence(row.campaign_id, 'csv')}
                                disabled={exportingId === row.campaign_id}
                              >
                                {exportingId === row.campaign_id && exportingFormat === 'csv' ? (
                                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                                ) : (
                                  <Download className="w-4 h-4 mr-2" />
                                )}
                                {t('admin.campaign_compliance.export_csv', 'Export CSV')}
                              </Button>
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => void handleExportEvidence(row.campaign_id, 'pdf')}
                                disabled={exportingId === row.campaign_id}
                              >
                                {exportingId === row.campaign_id && exportingFormat === 'pdf' ? (
                                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                                ) : (
                                  <Download className="w-4 h-4 mr-2" />
                                )}
                                {t('admin.campaign_compliance.export_pdf', 'Export PDF')}
                              </Button>
                            </div>
                          </td>
                        </tr>
                        {expanded && (
                          <tr className="border-b border-border bg-muted/30">
                            <td colSpan={8} className="space-y-4 px-4 py-3">
                              {hasGroups ? (
                                <div>
                                  <p className="mb-2 text-sm font-medium text-foreground">
                                    {t('admin.campaign_compliance.group_breakdown', 'By group')}
                                  </p>
                                  {groupLoadingId === row.campaign_id ? (
                                    <Loader2 className="w-5 h-5 animate-spin text-primary" />
                                  ) : groupRows.length === 0 ? (
                                    <p className="text-sm text-muted-foreground">
                                      {t('admin.campaign_compliance.no_group_data')}
                                    </p>
                                  ) : (
                                    <table className="mb-4 w-full text-sm">
                                      <thead>
                                        <tr className="text-left text-muted-foreground">
                                          <th className="py-1 pr-4 font-medium">
                                            {t('admin.campaign_compliance.col_group')}
                                          </th>
                                          <th className="py-1 pr-4 font-medium">
                                            {t('admin.campaign_compliance.col_assigned')}
                                          </th>
                                          <th className="py-1 pr-4 font-medium">
                                            {t('admin.campaign_compliance.col_completion')}
                                          </th>
                                          <th className="py-1 pr-4 font-medium">
                                            {t('admin.campaign_compliance.col_pending')}
                                          </th>
                                          <th className="py-1 pr-4 font-medium">
                                            {t('admin.campaign_compliance.col_overdue')}
                                          </th>
                                          <th className="py-1 font-medium">
                                            {t('admin.campaign_compliance.col_quiz_pass')}
                                          </th>
                                        </tr>
                                      </thead>
                                      <tbody>
                                        {groupRows.map((groupRow) => (
                                          <tr
                                            key={`${row.campaign_id}-${groupRow.group_id ?? 'ungrouped'}`}
                                          >
                                            <td className="py-2 pr-4 font-medium">
                                              {groupRow.group_name}
                                            </td>
                                            <td className="py-2 pr-4">{groupRow.assigned}</td>
                                            <td className="py-2 pr-4">
                                              {Math.round(groupRow.completion_rate)}%
                                            </td>
                                            <td className="py-2 pr-4">{groupRow.pending}</td>
                                            <td className="py-2 pr-4">{groupRow.overdue}</td>
                                            <td className="py-2">{groupRow.quiz_pass_count}</td>
                                          </tr>
                                        ))}
                                      </tbody>
                                    </table>
                                  )}
                                </div>
                              ) : null}
                              <div>
                                <p className="mb-2 text-sm font-medium text-foreground">
                                  {t('campaigns.analytics.panel_title', 'Campaign analytics')}
                                </p>
                                <CampaignAnalyticsPanel campaignId={row.campaign_id} compact />
                              </div>
                              <div>
                                <p className="mb-2 text-sm font-medium text-foreground">
                                  {t(
                                    'admin.campaign_compliance.roster_title',
                                    'Who has read / scored',
                                  )}
                                </p>
                                <CampaignRosterPanel campaignId={row.campaign_id} compact />
                              </div>
                            </td>
                          </tr>
                        )}
                      </Fragment>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardContent className="pt-6">
          <CampaignPeopleChase />
        </CardContent>
      </Card>
    </div>
  )
}
