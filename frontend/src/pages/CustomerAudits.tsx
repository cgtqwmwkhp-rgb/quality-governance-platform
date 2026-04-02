import { useState, useEffect } from 'react'
import {
  ClipboardCheck,
  RefreshCw,
  ArrowUpRight,
  Users,
  AlertTriangle,
  BarChart3,
} from 'lucide-react'
import {
  externalAuditRecordsApi,
  getApiErrorMessage,
  type ExternalAuditRecordSummary,
  type ExternalAuditRecordDashboardResponse,
} from '../api/client'

export default function CustomerAudits() {
  const [records, setRecords] = useState<ExternalAuditRecordSummary[]>([])
  const [total, setTotal] = useState(0)
  const [dashboard, setDashboard] = useState<ExternalAuditRecordDashboardResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      setLoading(true)
      setError(null)
      try {
        const [listRes, dashRes] = await Promise.all([
          externalAuditRecordsApi.list({ scheme: 'customer_other,other' }),
          externalAuditRecordsApi.dashboard({ scheme: 'customer_other,other' }),
        ])
        if (!cancelled) {
          setRecords(listRes.data.records)
          setTotal(listRes.data.total)
          setDashboard(dashRes.data)
        }
      } catch (err) {
        if (!cancelled) setError(getApiErrorMessage(err))
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    void load()
    return () => { cancelled = true }
  }, [])

  return (
    <div className="min-h-screen bg-background text-foreground p-6">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-4 mb-2">
          <div className="p-3 bg-primary/10 rounded-xl">
            <Users className="w-8 h-8 text-primary" />
          </div>
          <div>
            <h1 className="text-3xl font-bold text-foreground">Customer & External Audits</h1>
            <p className="text-muted-foreground">
              Imported customer, third-party, and external audit reports
            </p>
          </div>
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {/* Dashboard KPIs */}
      {dashboard && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <div className="bg-card border border-border rounded-xl p-4">
            <div className="text-sm text-muted-foreground">Total Imports</div>
            <div className="text-2xl font-bold text-foreground mt-1">{dashboard.total_records}</div>
          </div>
          <div className="bg-card border border-border rounded-xl p-4">
            <div className="text-sm text-muted-foreground">Avg Score</div>
            <div className="text-2xl font-bold text-primary mt-1">
              {dashboard.average_score_percentage != null
                ? `${Math.round(dashboard.average_score_percentage)}%`
                : '—'}
            </div>
          </div>
          <div className="bg-card border border-border rounded-xl p-4">
            <div className="text-sm text-muted-foreground flex items-center gap-1">
              <AlertTriangle className="w-3 h-3" /> Major Findings
            </div>
            <div className="text-2xl font-bold text-destructive mt-1">{dashboard.total_major}</div>
          </div>
          <div className="bg-card border border-border rounded-xl p-4">
            <div className="text-sm text-muted-foreground flex items-center gap-1">
              <BarChart3 className="w-3 h-3" /> Total Findings
            </div>
            <div className="text-2xl font-bold text-foreground mt-1">{dashboard.total_findings}</div>
          </div>
        </div>
      )}

      {/* Records list */}
      <div className="bg-card border border-border rounded-xl">
        <div className="p-4 bg-surface border-b border-border flex items-center justify-between">
          <h2 className="font-bold text-foreground flex items-center gap-2">
            <ClipboardCheck className="w-5 h-5 text-primary" />
            Audit Records ({total})
          </h2>
        </div>
        <div className="p-4">
          {loading && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground py-8 justify-center">
              <RefreshCw className="w-4 h-4 animate-spin" /> Loading audit records...
            </div>
          )}

          {!loading && records.length === 0 && (
            <div className="text-center py-12">
              <Users className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
              <h3 className="text-lg font-semibold text-muted-foreground mb-2">
                No customer or external audits
              </h3>
              <p className="text-sm text-muted-foreground">
                Import customer or external audit reports via the Audits page to see them here.
              </p>
            </div>
          )}

          <div className="space-y-3">
            {records.map((record) => (
              <div
                key={record.id}
                className="p-4 bg-surface/50 rounded-lg border border-border hover:border-primary/40 transition-all"
              >
                <div className="flex items-start justify-between mb-2">
                  <div>
                    <h4 className="font-medium text-foreground">
                      {record.scheme_label || record.company_name || 'Customer Audit'}
                    </h4>
                    <p className="text-sm text-muted-foreground">
                      {record.issuer_name && `${record.issuer_name} · `}
                      {record.report_date
                        ? new Date(record.report_date).toLocaleDateString()
                        : 'Date not available'}
                    </p>
                  </div>
                  <div className="text-right">
                    {record.score_percentage != null && (
                      <span className="text-lg font-bold text-primary">
                        {Math.round(record.score_percentage)}%
                      </span>
                    )}
                    <div
                      className={`text-xs mt-1 px-2 py-0.5 rounded-full inline-block ${
                        record.outcome_status === 'pass' || record.outcome_status === 'approved'
                          ? 'bg-success/20 text-success'
                          : record.outcome_status === 'fail'
                            ? 'bg-destructive/20 text-destructive'
                            : 'bg-warning/20 text-warning'
                      }`}
                    >
                      {record.outcome_status || record.status}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-4 text-xs text-muted-foreground">
                  <span>{record.findings_count ?? 0} findings</span>
                  {(record.major_findings ?? 0) > 0 && (
                    <span className="text-destructive">{record.major_findings} major</span>
                  )}
                  {(record.minor_findings ?? 0) > 0 && (
                    <span className="text-warning">{record.minor_findings} minor</span>
                  )}
                  {(record.observations ?? 0) > 0 && (
                    <span>{record.observations} observations</span>
                  )}
                  {record.import_job_id && (
                    <a
                      href={`/audits/0/import-review?jobId=${record.import_job_id}`}
                      className="text-primary hover:underline flex items-center gap-1 ml-auto"
                    >
                      View Import <ArrowUpRight className="w-3 h-3" />
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
