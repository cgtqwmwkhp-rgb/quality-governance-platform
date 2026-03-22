import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { trackError } from '../../utils/errorTracker'
import {
  workforceApi,
  getApiErrorMessage,
  type EngineerProfile as EngineerProfileType,
  type CompetencyRecord,
} from '../../api/client'

const stateColors: Record<string, string> = {
  active: 'bg-success/10 text-success',
  due: 'bg-warning/10 text-warning',
  expired: 'bg-destructive/10 text-destructive',
  failed: 'bg-destructive/10 text-destructive',
  not_assessed: 'bg-muted text-muted-foreground',
}

export default function EngineerProfile() {
  const { t } = useTranslation()
  const { id } = useParams<{ id: string }>()
  const [engineer, setEngineer] = useState<EngineerProfileType | null>(null)
  const [competencies, setCompetencies] = useState<CompetencyRecord[]>([])
  const [assetTypeMap, setAssetTypeMap] = useState<Record<number, string>>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    workforceApi
      .listAssetTypes()
      .then((res) => {
        const map: Record<number, string> = {}
        for (const at of res.data?.items || []) map[at.id] = at.name
        setAssetTypeMap(map)
      })
      .catch(() => {})
  }, [])

  useEffect(() => {
    if (!id) {
      setLoading(false)
      setError(t('workforce.engineers.not_found'))
      return
    }
    const numId = parseInt(id, 10)
    if (isNaN(numId)) {
      setLoading(false)
      setError(t('workforce.engineers.not_found'))
      return
    }

    const load = async () => {
      setLoading(true)
      setError(null)
      try {
        const [engRes, compRes] = await Promise.all([
          workforceApi.getEngineer(numId),
          workforceApi.getCompetencies(numId),
        ])
        setEngineer(engRes.data)
        setCompetencies(compRes.data || [])
      } catch (err) {
        trackError(err, { component: 'EngineerProfile', action: 'load' })
        setError(getApiErrorMessage(err))
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [id, t])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    )
  }

  if (!engineer) {
    return (
      <div className="p-6">
        <p className="text-muted-foreground">{error || t('workforce.engineers.not_found')}</p>
        <Link to="/workforce/engineers" className="text-primary hover:underline mt-2 inline-block">
          {t('workforce.engineers.back')}
        </Link>
      </div>
    )
  }

  const activeCount = competencies.filter((c) => c.state === 'active').length
  const dueCount = competencies.filter((c) => c.state === 'due').length
  const expiredCount = competencies.filter((c) => c.state === 'expired').length

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center gap-3">
        <Link to="/workforce/engineers" className="text-muted-foreground hover:text-foreground">
          &larr; {t('workforce.engineers.title')}
        </Link>
      </div>

      {/* Profile Header */}
      <div className="bg-card border border-border rounded-xl p-6">
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center">
                <span className="text-primary font-bold text-lg">
                  {(engineer.job_title || 'E')[0].toUpperCase()}
                </span>
              </div>
              <div>
                <h1 className="text-2xl font-bold text-foreground">
                  {engineer.employee_number || engineer.job_title || `Engineer #${engineer.id}`}
                </h1>
                <p className="text-muted-foreground">{engineer.job_title || 'Field Engineer'}</p>
              </div>
            </div>
          </div>
          <span
            className={`px-3 py-1 rounded-full text-xs font-medium ${engineer.is_active ? 'bg-success/10 text-success' : 'bg-destructive/10 text-destructive'}`}
          >
            {engineer.is_active ? t('common.active') : t('common.inactive')}
          </span>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-6">
          <div>
            <p className="text-xs text-muted-foreground uppercase tracking-wide">
              {t('workforce.engineers.employee_no')}
            </p>
            <p className="text-foreground font-medium mt-1">{engineer.employee_number || '—'}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground uppercase tracking-wide">
              {t('workforce.common.department')}
            </p>
            <p className="text-foreground font-medium mt-1">{engineer.department || '—'}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground uppercase tracking-wide">
              {t('workforce.common.site')}
            </p>
            <p className="text-foreground font-medium mt-1">{engineer.site || '—'}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground uppercase tracking-wide">
              {t('workforce.engineers.external_id')}
            </p>
            <p className="text-foreground font-mono text-sm mt-1">
              {engineer.external_id?.slice(0, 8)}...
            </p>
          </div>
        </div>
      </div>

      {/* Competency Summary KPIs */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-card border border-border rounded-xl p-5">
          <p className="text-sm text-muted-foreground">
            {t('workforce.competency.active_competencies')}
          </p>
          <p className="text-3xl font-bold text-success mt-1">{activeCount}</p>
        </div>
        <div className="bg-card border border-border rounded-xl p-5">
          <p className="text-sm text-muted-foreground">
            {t('workforce.competency.due_reassessment')}
          </p>
          <p className="text-3xl font-bold text-warning mt-1">{dueCount}</p>
        </div>
        <div className="bg-card border border-border rounded-xl p-5">
          <p className="text-sm text-muted-foreground">{t('workforce.competency.expired')}</p>
          <p className="text-3xl font-bold text-destructive mt-1">{expiredCount}</p>
        </div>
      </div>

      {/* Competency Records Table */}
      <div className="bg-card border border-border rounded-xl overflow-hidden">
        <div className="px-6 py-4 border-b border-border">
          <h2 className="text-lg font-semibold text-foreground">
            {t('workforce.competency.records')}
          </h2>
        </div>
        {competencies.length === 0 ? (
          <div className="px-6 py-12 text-center text-muted-foreground">
            {t('workforce.competency.records_empty')}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/30">
                  <th className="px-4 py-3 text-left font-medium text-muted-foreground">
                    {t('workforce.common.asset_type')}
                  </th>
                  <th className="px-4 py-3 text-left font-medium text-muted-foreground">
                    {t('workforce.competency.source')}
                  </th>
                  <th className="px-4 py-3 text-left font-medium text-muted-foreground">
                    {t('workforce.assessments.outcome')}
                  </th>
                  <th className="px-4 py-3 text-left font-medium text-muted-foreground">
                    {t('workforce.competency.state')}
                  </th>
                  <th className="px-4 py-3 text-left font-medium text-muted-foreground">
                    {t('workforce.competency.assessed')}
                  </th>
                  <th className="px-4 py-3 text-left font-medium text-muted-foreground">
                    {t('workforce.competency.expires')}
                  </th>
                </tr>
              </thead>
              <tbody>
                {competencies.map((rec) => (
                  <tr
                    key={rec.id}
                    className="border-b border-border hover:bg-muted/20 transition-colors"
                  >
                    <td className="px-4 py-3 text-foreground">
                      {assetTypeMap[rec.asset_type_id] ?? `Asset Type #${rec.asset_type_id}`}
                    </td>
                    <td className="px-4 py-3">
                      <span className="capitalize text-foreground">{rec.source_type}</span>
                    </td>
                    <td className="px-4 py-3">
                      <span className="capitalize text-foreground">{rec.outcome || '—'}</span>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`px-2 py-0.5 rounded-full text-xs font-medium ${stateColors[rec.state] || stateColors.not_assessed}`}
                      >
                        {rec.state.replace(/_/g, ' ')}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {rec.assessed_at ? new Date(rec.assessed_at).toLocaleDateString() : '—'}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {rec.expires_at ? new Date(rec.expires_at).toLocaleDateString() : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Skills Matrix */}
      <div className="bg-card border border-border rounded-xl overflow-hidden">
        <div className="px-6 py-4 border-b border-border">
          <h2 className="text-lg font-semibold text-foreground">
            {t('workforce.competency.skills_matrix')}
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            {t('workforce.competency.skills_matrix_subtitle')}
          </p>
        </div>
        <div className="p-6">
          {competencies.length === 0 ? (
            <p className="text-center text-muted-foreground py-8">
              {t('workforce.competency.skills_matrix_empty')}
            </p>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
              {competencies.map((rec) => (
                <div
                  key={rec.id}
                  className={`rounded-lg p-3 text-center border ${
                    rec.state === 'active'
                      ? 'border-success/50 bg-success/10'
                      : rec.state === 'due'
                        ? 'border-warning/50 bg-warning/10'
                        : rec.state === 'expired' || rec.state === 'failed'
                          ? 'border-destructive/50 bg-destructive/10'
                          : 'border-border bg-muted/30'
                  }`}
                >
                  <p className="text-xs text-muted-foreground">
                    {assetTypeMap[rec.asset_type_id] ?? `#${rec.asset_type_id}`}
                  </p>
                  <p className="text-xs font-medium mt-1 capitalize">
                    {rec.state.replace(/_/g, ' ')}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
