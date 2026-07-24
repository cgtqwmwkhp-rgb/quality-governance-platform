import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Brain, Loader2 } from 'lucide-react'
import { Button } from '../components/ui/Button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/Card'
import { safetyInsightsApi, type SafetyInsightRun, type SafetyInsightTheme } from '../api/client'

const MODULES = [
  { id: 'incident', label: 'Incidents' },
  { id: 'near_miss', label: 'Near misses' },
  { id: 'rta', label: 'RTAs' },
  { id: 'complaint', label: 'Complaints' },
] as const

function caseDetailPath(module: string, id: number): string {
  switch (module) {
    case 'near_miss':
      return `/near-misses/${id}`
    case 'rta':
      return `/rtas/${id}`
    case 'complaint':
      return `/complaints/${id}`
    default:
      return `/incidents/${id}`
  }
}

function moduleListPath(module: string, ids: number[]): string {
  const q = ids.length ? `?ids=${ids.join(',')}` : ''
  switch (module) {
    case 'near_miss':
      return `/near-misses${q}`
    case 'rta':
      return `/rtas${q}`
    case 'complaint':
      return `/complaints${q}`
    default:
      return `/incidents${q}`
  }
}

function themeListLinks(theme: SafetyInsightTheme) {
  const byModule = new Map<string, number[]>()
  for (const ref of theme.case_refs || []) {
    const list = byModule.get(ref.module) || []
    list.push(ref.id)
    byModule.set(ref.module, list)
  }
  return Array.from(byModule.entries()).map(([module, ids]) => ({
    module,
    href: moduleListPath(module, ids),
    count: ids.length,
  }))
}

export default function SafetyInsightsAnalyst() {
  const { t } = useTranslation()
  const [modules, setModules] = useState<string[]>(['incident', 'near_miss', 'rta', 'complaint'])
  const [scope, setScope] = useState<'org' | 'topic'>('org')
  const [topicQuery, setTopicQuery] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [minCluster, setMinCluster] = useState(2)
  const [includeSynthesis, setIncludeSynthesis] = useState(true)
  const [includeBenchmark, setIncludeBenchmark] = useState(false)
  const [run, setRun] = useState<SafetyInsightRun | null>(null)
  const [history, setHistory] = useState<SafetyInsightRun[]>([])
  const [error, setError] = useState('')
  const [starting, setStarting] = useState(false)
  const [exporting, setExporting] = useState(false)

  const loadHistory = useCallback(() => {
    void safetyInsightsApi
      .listRuns(10)
      .then((res) => setHistory(res.data.items || []))
      .catch(() => undefined)
  }, [])

  useEffect(() => {
    loadHistory()
  }, [loadHistory])

  useEffect(() => {
    if (!run || !['queued', 'running'].includes(run.status)) return
    const runId = run.id
    const timer = window.setInterval(() => {
      void safetyInsightsApi
        .getRun(runId)
        .then((res) => setRun(res.data))
        .catch(() => undefined)
    }, 2000)
    return () => window.clearInterval(timer)
    // Depend on id/status only — progress payload updates must not reset the timer.
  }, [run?.id, run?.status])

  const corpusRatios = useMemo(() => {
    const corpus = (run?.ratios as { corpus?: Record<string, unknown> } | null)?.corpus
    return corpus || null
  }, [run])

  const trainingSignals = useMemo(() => {
    const block = (run?.ratios as { training_signals?: Record<string, unknown> } | null)?.training_signals
    return block || null
  }, [run])

  const downloadPdf = async () => {
    if (!run) return
    setExporting(true)
    try {
      const res = await safetyInsightsApi.exportRun(run.id, 'pdf')
      const blob = res.data as unknown as Blob
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `safety-insights-run-${run.id}.pdf`
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      setError('Could not export board-pack PDF.')
    } finally {
      setExporting(false)
    }
  }

  const startRun = async () => {
    setError('')
    setStarting(true)
    try {
      const res = await safetyInsightsApi.startRun({
        modules,
        scope,
        topic_query: scope === 'topic' ? topicQuery : undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
        min_cluster_size: minCluster,
        include_synthesis: includeSynthesis,
        include_benchmark: includeBenchmark,
      })
      setRun(res.data)
      loadHistory()
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        t('safetyInsights.startFailed', { defaultValue: 'Could not start deep analysis.' })
      setError(String(detail))
    } finally {
      setStarting(false)
    }
  }

  const toggleModule = (id: string) => {
    setModules((prev) => (prev.includes(id) ? prev.filter((m) => m !== id) : [...prev, id]))
  }

  return (
    <div className="space-y-8 p-6 max-w-6xl mx-auto">
      <header className="space-y-2">
        <h1 className="text-3xl font-semibold tracking-tight flex items-center gap-3">
          <Brain className="h-8 w-8 text-primary" />
          {t('safetyInsights.title', { defaultValue: 'Safety Insights Analyst' })}
        </h1>
        <p className="text-muted-foreground max-w-3xl">
          {t('safetyInsights.subtitle', {
            defaultValue:
              'Research-grade micro-themes, repeat dimensions, and near-miss ratios — every finding cited to real cases.',
          })}
        </p>
      </header>

      <section className="space-y-4 border-b border-border pb-8">
        <h2 className="text-lg font-medium">
          {t('safetyInsights.scope', { defaultValue: 'Analysis scope' })}
        </h2>
        <div className="flex flex-wrap gap-3">
          {MODULES.map((m) => (
            <label key={m.id} className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={modules.includes(m.id)}
                onChange={() => toggleModule(m.id)}
              />
              {m.label}
            </label>
          ))}
        </div>
        <div className="flex flex-wrap gap-4 items-end">
          <label className="text-sm space-y-1">
            <span className="block text-muted-foreground">From</span>
            <input
              type="date"
              className="border border-border rounded-md px-2 py-1 bg-background"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
            />
          </label>
          <label className="text-sm space-y-1">
            <span className="block text-muted-foreground">To</span>
            <input
              type="date"
              className="border border-border rounded-md px-2 py-1 bg-background"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
            />
          </label>
          <label className="text-sm space-y-1">
            <span className="block text-muted-foreground">Min cluster</span>
            <input
              type="number"
              min={2}
              max={20}
              className="border border-border rounded-md px-2 py-1 w-20 bg-background"
              value={minCluster}
              onChange={(e) => setMinCluster(Number(e.target.value) || 2)}
            />
          </label>
          <label className="text-sm space-y-1">
            <span className="block text-muted-foreground">Mode</span>
            <select
              className="border border-border rounded-md px-2 py-1 bg-background"
              value={scope}
              onChange={(e) => setScope(e.target.value as 'org' | 'topic')}
            >
              <option value="org">Org-wide</option>
              <option value="topic">Topic</option>
            </select>
          </label>
          {scope === 'topic' && (
            <label className="text-sm space-y-1 grow min-w-[200px]">
              <span className="block text-muted-foreground">Topic</span>
              <input
                className="border border-border rounded-md px-2 py-1 w-full bg-background"
                placeholder="e.g. reversing"
                value={topicQuery}
                onChange={(e) => setTopicQuery(e.target.value)}
              />
            </label>
          )}
        </div>
        <div className="flex flex-wrap gap-4 text-sm">
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={includeSynthesis}
              onChange={(e) => setIncludeSynthesis(e.target.checked)}
            />
            Claude synthesis
          </label>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={includeBenchmark}
              onChange={(e) => setIncludeBenchmark(e.target.checked)}
            />
            Public HSE research
          </label>
        </div>
        <Button onClick={() => void startRun()} disabled={starting || modules.length === 0}>
          {starting ? (
            <>
              <Loader2 className="h-4 w-4 mr-2 animate-spin" /> Running…
            </>
          ) : (
            t('safetyInsights.run', { defaultValue: 'Run deep analysis' })
          )}
        </Button>
        {error && <p className="text-sm text-destructive">{error}</p>}
      </section>

      {run && (
        <section className="space-y-2">
          <div className="flex items-center gap-3 text-sm text-muted-foreground">
            {(run.status === 'queued' || run.status === 'running') && (
              <Loader2 className="h-4 w-4 animate-spin" />
            )}
            <span>
              Run #{run.id}: {run.status}
              {run.progress_message ? ` — ${run.progress_message}` : ''} ({run.progress_pct}%)
            </span>
          </div>
          {run.error_detail && (
            <p className="text-sm text-destructive">
              {run.error_code}: {run.error_detail}
            </p>
          )}
        </section>
      )}

      {run?.status === 'succeeded' && (
        <>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" disabled={exporting} onClick={() => void downloadPdf()}>
              {exporting ? 'Exporting…' : 'Download board-pack PDF'}
            </Button>
          </div>

          <section className="space-y-4">
            <h2 className="text-lg font-medium">
              {t('safetyInsights.microThemes', { defaultValue: 'Micro-themes' })}
            </h2>
            {(run.micro_themes || []).length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No clusters met the minimum size with validated case citations.
              </p>
            ) : (
              <div className="space-y-4">
                {(run.micro_themes || []).map((theme) => (
                  <div key={theme.id} className="border-b border-border pb-4 space-y-2">
                    <div className="flex flex-wrap items-baseline gap-3">
                      <h3 className="text-base font-medium">{theme.label}</h3>
                      <span className="text-sm text-muted-foreground">
                        n={theme.case_count}
                        {theme.share != null ? ` · ${theme.share}%` : ''}
                        {theme.velocity ? ` · ${theme.velocity}` : ''}
                      </span>
                    </div>
                    {theme.rationale && (
                      <p className="text-sm text-muted-foreground">{theme.rationale}</p>
                    )}
                    <div className="flex flex-wrap gap-2">
                      {(theme.case_refs || []).map((ref) => (
                        <Link
                          key={`${ref.module}-${ref.id}`}
                          to={caseDetailPath(ref.module, ref.id)}
                          className="text-sm underline underline-offset-2"
                        >
                          {ref.reference_number}
                        </Link>
                      ))}
                    </div>
                    <div className="flex flex-wrap gap-3 text-sm">
                      {themeListLinks(theme).map((link) => (
                        <Link key={link.module} to={link.href} className="underline underline-offset-2">
                          View {link.count} {link.module.replace('_', ' ')} cases
                        </Link>
                      ))}
                      <Link
                        to={`/audit-templates/new?ai=1&themeId=${theme.id}`}
                        className="underline underline-offset-2"
                      >
                        Audit this theme
                      </Link>
                      {(theme.case_refs || [])[0] && (
                        <Link
                          to={`/actions?sourceType=${theme.case_refs[0].module === 'near_miss' ? 'near_miss' : theme.case_refs[0].module}&sourceId=${theme.case_refs[0].id}&create=1`}
                          className="underline underline-offset-2"
                        >
                          Open CAPA from cited case
                        </Link>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>

          <section className="space-y-3">
            <h2 className="text-lg font-medium">Repeat dimensions</h2>
            {(run.dimensions || []).length === 0 ? (
              <p className="text-sm text-muted-foreground">No repeat person/location/vehicle/asset/contract patterns.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-muted-foreground border-b">
                      <th className="py-2 pr-4">Type</th>
                      <th className="py-2 pr-4">Key</th>
                      <th className="py-2 pr-4">Count</th>
                      <th className="py-2">Cases</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(run.dimensions || []).map((dim) => (
                      <tr key={dim.id} className="border-b border-border/60">
                        <td className="py-2 pr-4">{dim.dimension_type}</td>
                        <td className="py-2 pr-4">{dim.dimension_key}</td>
                        <td className="py-2 pr-4">{dim.case_count}</td>
                        <td className="py-2">
                          <div className="flex flex-wrap gap-2">
                            {(dim.case_refs || []).slice(0, 8).map((ref) => (
                              <Link
                                key={`${ref.module}-${ref.id}`}
                                to={caseDetailPath(ref.module, ref.id)}
                                className="underline underline-offset-2"
                              >
                                {ref.reference_number}
                              </Link>
                            ))}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section className="space-y-3">
            <h2 className="text-lg font-medium">Internal benchmarks</h2>
            {corpusRatios ? (
              <div className="grid gap-3 grid-cols-2 md:grid-cols-4">
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-xs text-muted-foreground">NM : Incident</CardTitle>
                  </CardHeader>
                  <CardContent className="text-2xl font-semibold">
                    {String(corpusRatios.near_miss_to_incident_ratio ?? '—')}
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-xs text-muted-foreground">HiPo NM : Incident</CardTitle>
                  </CardHeader>
                  <CardContent className="text-2xl font-semibold">
                    {String(corpusRatios.hipo_near_miss_to_incident_ratio ?? '—')}
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-xs text-muted-foreground">Near misses</CardTitle>
                  </CardHeader>
                  <CardContent className="text-2xl font-semibold">
                    {String(corpusRatios.near_misses ?? '—')}
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-xs text-muted-foreground">Incidents</CardTitle>
                  </CardHeader>
                  <CardContent className="text-2xl font-semibold">
                    {String(corpusRatios.incidents ?? '—')}
                  </CardContent>
                </Card>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">Ratios unavailable for this run.</p>
            )}
          </section>

          <section className="space-y-3">
            <h2 className="text-lg font-medium">Training / competence signals</h2>
            {trainingSignals?.available && Array.isArray(trainingSignals.signals) && trainingSignals.signals.length > 0 ? (
              <ul className="space-y-2 text-sm">
                {(trainingSignals.signals as Array<Record<string, unknown>>).map((sig, idx) => (
                  <li key={idx} className="border-b border-border/60 pb-2">
                    <div className="font-medium">{String(sig.summary || sig.kind || 'Signal')}</div>
                    {sig.theme_label != null && (
                      <p className="text-muted-foreground">Theme: {String(sig.theme_label)}</p>
                    )}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-muted-foreground">
                {trainingSignals?.reason
                  ? `No training correlation available (${String(trainingSignals.reason)}).`
                  : 'No training correlation signals for this run.'}
              </p>
            )}
          </section>

          <section className="space-y-3">
            <h2 className="text-lg font-medium">Analyst synthesis</h2>
            {run.synthesis_available && run.synthesis_text ? (
              <div className="prose prose-sm dark:prose-invert max-w-none whitespace-pre-wrap">
                {run.synthesis_text}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                Synthesis unavailable (Claude not configured or disabled for this run).
              </p>
            )}
          </section>

          <section className="space-y-3">
            <h2 className="text-lg font-medium">External HSE research</h2>
            {run.research_available && (run.benchmarks || []).length > 0 ? (
              <ul className="space-y-3">
                {(run.benchmarks || []).map((b, idx) => (
                  <li key={idx} className="text-sm space-y-1">
                    <div className="font-medium">{b.title}</div>
                    <p className="text-muted-foreground">{b.summary}</p>
                    {b.source_url && (
                      <a
                        href={b.source_url}
                        target="_blank"
                        rel="noreferrer"
                        className="underline underline-offset-2"
                      >
                        {b.source_url}
                      </a>
                    )}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-muted-foreground">
                Public research unavailable (Perplexity not configured or not requested).
              </p>
            )}
          </section>

          {run.quality_scorecard && (
            <section className="space-y-2">
              <h2 className="text-lg font-medium">Capture quality</h2>
              <pre className="text-xs bg-muted/40 p-3 rounded-md overflow-x-auto">
                {JSON.stringify(run.quality_scorecard, null, 2)}
              </pre>
            </section>
          )}
        </>
      )}

      <section className="space-y-3">
        <h2 className="text-lg font-medium">Run history</h2>
        {history.length === 0 ? (
          <p className="text-sm text-muted-foreground">No previous runs.</p>
        ) : (
          <ul className="space-y-2 text-sm">
            {history.map((item) => (
              <li key={item.id}>
                <button
                  type="button"
                  className="underline underline-offset-2"
                  onClick={() => {
                    void safetyInsightsApi.getRun(item.id).then((res) => setRun(res.data))
                  }}
                >
                  #{item.id} · {item.status} · {item.completed_at || item.created_at || ''}
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">How this works</CardTitle>
          <CardDescription>
            Deterministic dimensions → Gemini micro-themes with citation validation → Claude synthesis
            → optional Perplexity HSE/gov research. Themes also feed Audit Builder and executive
            surfaces.
          </CardDescription>
        </CardHeader>
      </Card>
    </div>
  )
}
