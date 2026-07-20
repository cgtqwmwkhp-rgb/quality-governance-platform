import { useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { ExternalLink, Upload } from 'lucide-react'
import {
  ATLAS_HUB_URL,
  getApiErrorMessage,
  trainingMatrixApi,
  workforceApi,
  type TrainingMatrixComplianceRow,
  type TrainingMatrixImportQa,
  type TrainingMatrixNameMapItem,
  type TrainingMatrixRequirement,
} from '../../../api/client'
import { Badge } from '../../../components/ui/Badge'
import { Button } from '../../../components/ui/Button'
import { Card, CardContent, CardHeader } from '../../../components/ui/Card'
import { Input } from '../../../components/ui/Input'
import { TableSkeleton } from '../../../components/ui/SkeletonLoader'

const STATUS_VARIANT: Record<string, 'success' | 'warning' | 'destructive' | 'secondary' | 'info'> = {
  compliant: 'success',
  due_soon: 'warning',
  overdue: 'destructive',
  pending: 'warning',
  missing: 'secondary',
  failed: 'destructive',
}

function AtlasCta({ url = ATLAS_HUB_URL }: { url?: string }) {
  const { t } = useTranslation()
  return (
    <a
      href={url}
      target="_blank"
      rel="noreferrer"
      className="inline-flex items-center gap-1.5 text-sm text-primary hover:underline"
      data-testid="training-matrix-atlas-link"
    >
      {t('workforce.training_matrix.open_atlas', 'Complete in Atlas')}
      <ExternalLink className="w-3.5 h-3.5" />
    </a>
  )
}

function ComplianceTable({ rows, loading }: { rows: TrainingMatrixComplianceRow[]; loading: boolean }) {
  const { t } = useTranslation()
  if (loading) return <TableSkeleton rows={6} columns={6} />
  if (rows.length === 0) {
    return (
      <p className="text-sm text-muted-foreground py-8 text-center" data-testid="training-matrix-empty">
        {t(
          'workforce.training_matrix.empty_compliance',
          'No compliance rows yet. Upload an Atlas matrix and configure role/department requirements.',
        )}
      </p>
    )
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left text-muted-foreground">
            <th className="py-2 px-3">Person</th>
            <th className="py-2 px-3">Course</th>
            <th className="py-2 px-3">Status</th>
            <th className="py-2 px-3">Passed</th>
            <th className="py-2 px-3">QGP due</th>
            <th className="py-2 px-3">Atlas expiry</th>
            <th className="py-2 px-3" />
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={`${row.atlas_name}-${row.course_key}`} className="border-b border-border/50">
              <td className="py-2 px-3">
                <div className="font-medium">{row.engineer_display_name || row.atlas_name}</div>
                <div className="text-xs text-muted-foreground">{row.department || '—'}</div>
              </td>
              <td className="py-2 px-3">
                {row.course_display_name}
                <div className="text-xs text-muted-foreground">{row.frequency_years}y cycle</div>
              </td>
              <td className="py-2 px-3">
                <Badge variant={STATUS_VARIANT[row.status] || 'secondary'}>
                  {row.status.replace(/_/g, ' ')}
                </Badge>
                {row.expiry_without_passed ? (
                  <div className="text-xs text-amber-700 mt-1">expiry w/o passed</div>
                ) : null}
              </td>
              <td className="py-2 px-3 text-muted-foreground">{row.passed_on || '—'}</td>
              <td className="py-2 px-3 text-muted-foreground">{row.qgp_due_on || '—'}</td>
              <td className="py-2 px-3 text-muted-foreground">{row.expires_on || '—'}</td>
              <td className="py-2 px-3">
                {row.status === 'compliant' ? null : <AtlasCta url={row.atlas_hub_url || ATLAS_HUB_URL} />}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function TrainingMatrixGapBoard() {
  const { t } = useTranslation()
  const [rows, setRows] = useState<TrainingMatrixComplianceRow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [status, setStatus] = useState('')
  const [qa, setQa] = useState<TrainingMatrixImportQa | null>(null)

  useEffect(() => {
    setLoading(true)
    setError(null)
    Promise.all([
      trainingMatrixApi.listCompliance(status ? { status } : undefined),
      trainingMatrixApi.getLatestImportQa().catch(() => null),
    ])
      .then(([compliance, qaRes]) => {
        setRows(compliance.items || [])
        setQa(qaRes)
      })
      .catch((err) => {
        setRows([])
        setError(getApiErrorMessage(err))
      })
      .finally(() => setLoading(false))
  }, [status])

  const gapRows = useMemo(
    () => rows.filter((r) => r.status !== 'compliant'),
    [rows],
  )

  return (
    <div className="space-y-4" data-testid="training-matrix-gap-board">
      <Card>
        <CardHeader className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div>
            <p className="font-medium">
              {t('workforce.training_matrix.gap_title', 'Manager gap board')}
            </p>
            <p className="text-sm text-muted-foreground">
              {t(
                'workforce.training_matrix.gap_subtitle',
                'Due dates use Atlas Passed + your frequency rules. Complete training in Atlas.',
              )}
            </p>
          </div>
          <div className="flex items-center gap-3">
            <select
              className="h-9 rounded-md border border-border bg-card px-3 text-sm"
              value={status}
              onChange={(e) => setStatus(e.target.value)}
              aria-label="Filter status"
            >
              <option value="">All non-compliant focus</option>
              <option value="overdue">Overdue</option>
              <option value="due_soon">Due soon</option>
              <option value="pending">Pending</option>
              <option value="missing">Missing</option>
              <option value="failed">Failed</option>
              <option value="compliant">Compliant</option>
            </select>
            <AtlasCta />
          </div>
        </CardHeader>
        <CardContent>
          {qa ? (
            <div
              className="mb-4 p-3 rounded-lg bg-muted/50 text-sm space-y-1"
              data-testid="training-matrix-qa"
            >
              <p>
                Expiry without Passed: <strong>{qa.expiry_without_passed_count}</strong> (
                {qa.expiry_without_passed_before_pct}% before today /{' '}
                {qa.expiry_without_passed_after_pct}% after)
              </p>
              <p className="text-muted-foreground">
                All expiry dates: {qa.all_expiry_before_pct}% before today /{' '}
                {qa.all_expiry_after_pct}% after today
              </p>
            </div>
          ) : null}
          {error ? (
            <div className="mb-4 p-3 rounded-lg bg-destructive/10 text-destructive text-sm">{error}</div>
          ) : null}
          <ComplianceTable rows={status ? rows : gapRows} loading={loading} />
        </CardContent>
      </Card>
    </div>
  )
}

export function TrainingMatrixMyTraining() {
  const { t } = useTranslation()
  const [rows, setRows] = useState<TrainingMatrixComplianceRow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    trainingMatrixApi
      .myTraining()
      .then((res) => setRows(res.items || []))
      .catch((err) => setError(getApiErrorMessage(err)))
      .finally(() => setLoading(false))
  }, [])

  return (
    <Card data-testid="training-matrix-my-training">
      <CardHeader className="flex flex-row items-center justify-between gap-3">
        <div>
          <p className="font-medium">{t('workforce.training_matrix.my_title', 'My training')}</p>
          <p className="text-sm text-muted-foreground">
            {t(
              'workforce.training_matrix.my_subtitle',
              'Your required modules and compliance. Incomplete items open Atlas to complete.',
            )}
          </p>
        </div>
        <AtlasCta />
      </CardHeader>
      <CardContent>
        {error ? (
          <div className="mb-4 p-3 rounded-lg bg-destructive/10 text-destructive text-sm">{error}</div>
        ) : null}
        <ComplianceTable rows={rows} loading={loading} />
      </CardContent>
    </Card>
  )
}

export function TrainingMatrixAdminPanel() {
  const { t } = useTranslation()
  const fileRef = useRef<HTMLInputElement>(null)
  const [uploading, setUploading] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [nameMaps, setNameMaps] = useState<TrainingMatrixNameMapItem[]>([])
  const [requirements, setRequirements] = useState<TrainingMatrixRequirement[]>([])
  const [engineers, setEngineers] = useState<{ id: number; label: string }[]>([])
  const [courses, setCourses] = useState<{ course_key: string; display_name: string }[]>([])
  const [reqForm, setReqForm] = useState({
    match_department: 'Mobile Engineers',
    match_role_key: '',
    course_key: '',
    course_display_name: '',
    frequency_years: 1,
  })

  const reload = () => {
    trainingMatrixApi.listNameMaps().then(setNameMaps).catch(() => setNameMaps([]))
    trainingMatrixApi.listRequirements().then((r) => setRequirements(r.items)).catch(() => setRequirements([]))
    trainingMatrixApi.listCourses().then(setCourses).catch(() => setCourses([]))
    workforceApi
      .listEngineers({ page: '1', page_size: '500' })
      .then((res) => {
        setEngineers(
          (res.data?.items || []).map((e: { id: number; display_name?: string }) => ({
            id: e.id,
            label: e.display_name?.trim() || `#${e.id}`,
          })),
        )
      })
      .catch(() => setEngineers([]))
  }

  useEffect(() => {
    reload()
  }, [])

  const onUpload = async (file: File) => {
    setUploading(true)
    setError(null)
    setMessage(null)
    try {
      const imp = await trainingMatrixApi.uploadImport(file)
      setMessage(
        `Imported ${imp.person_count} people, ${imp.course_count} courses (${imp.expiry_without_passed_count} expiry without passed)`,
      )
      reload()
    } catch (err) {
      setError(getApiErrorMessage(err))
    } finally {
      setUploading(false)
    }
  }

  const unmatched = nameMaps.filter((m) => !m.mapped)

  return (
    <div className="space-y-4" data-testid="training-matrix-admin">
      <Card>
        <CardHeader>
          <p className="font-medium">
            {t('workforce.training_matrix.upload_title', 'Weekly Atlas matrix upload')}
          </p>
          <p className="text-sm text-muted-foreground">
            Admin only. CSV template from Atlas. QGP is not an LMS — completions stay in Atlas.
          </p>
        </CardHeader>
        <CardContent className="space-y-3">
          <input
            ref={fileRef}
            type="file"
            accept=".csv,text/csv"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0]
              if (f) void onUpload(f)
              e.target.value = ''
            }}
          />
          <Button
            type="button"
            disabled={uploading}
            onClick={() => fileRef.current?.click()}
            data-testid="training-matrix-upload"
          >
            <Upload className="w-4 h-4 mr-2" />
            {uploading ? 'Uploading…' : 'Upload CSV'}
          </Button>
          {message ? <p className="text-sm text-foreground">{message}</p> : null}
          {error ? <p className="text-sm text-destructive">{error}</p> : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <p className="font-medium">Name mapping (Atlas → Employee)</p>
          <p className="text-sm text-muted-foreground">
            Unmatched: {unmatched.length}. Auto-match uses display name; resolve the rest here.
          </p>
        </CardHeader>
        <CardContent className="space-y-2 max-h-64 overflow-y-auto">
          {unmatched.slice(0, 40).map((row) => (
            <div key={row.atlas_name} className="flex flex-wrap items-center gap-2 text-sm">
              <span className="min-w-[10rem] font-medium">{row.atlas_name}</span>
              <span className="text-muted-foreground">{row.department || '—'}</span>
              <select
                className="h-8 rounded-md border border-border bg-card px-2 text-sm"
                defaultValue=""
                onChange={(e) => {
                  const id = Number(e.target.value)
                  if (!id) return
                  void trainingMatrixApi.upsertNameMap(row.atlas_name, id).then(reload)
                }}
              >
                <option value="">Select employee…</option>
                {engineers.map((eng) => (
                  <option key={eng.id} value={eng.id}>
                    {eng.label}
                  </option>
                ))}
              </select>
            </div>
          ))}
          {unmatched.length === 0 ? (
            <p className="text-sm text-muted-foreground">All Atlas names are mapped.</p>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <p className="font-medium">Requirements (role/dept → course + frequency)</p>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-2">
            <Input
              placeholder="Department"
              value={reqForm.match_department}
              onChange={(e) => setReqForm((p) => ({ ...p, match_department: e.target.value }))}
            />
            <Input
              placeholder="Role key (optional)"
              value={reqForm.match_role_key}
              onChange={(e) => setReqForm((p) => ({ ...p, match_role_key: e.target.value }))}
            />
            <select
              className="h-9 rounded-md border border-border bg-card px-3 text-sm"
              value={reqForm.course_key}
              onChange={(e) => {
                const course = courses.find((c) => c.course_key === e.target.value)
                setReqForm((p) => ({
                  ...p,
                  course_key: e.target.value,
                  course_display_name: course?.display_name || p.course_display_name,
                }))
              }}
            >
              <option value="">Course…</option>
              {courses.map((c) => (
                <option key={c.course_key} value={c.course_key}>
                  {c.display_name}
                </option>
              ))}
            </select>
            <select
              className="h-9 rounded-md border border-border bg-card px-3 text-sm"
              value={reqForm.frequency_years}
              onChange={(e) =>
                setReqForm((p) => ({ ...p, frequency_years: Number(e.target.value) }))
              }
            >
              <option value={1}>1 year</option>
              <option value={2}>2 years</option>
              <option value={3}>3 years</option>
            </select>
            <Button
              type="button"
              disabled={!reqForm.course_key || (!reqForm.match_department && !reqForm.match_role_key)}
              onClick={() => {
                void trainingMatrixApi
                  .createRequirement({
                    match_department: reqForm.match_department || null,
                    match_role_key: reqForm.match_role_key || null,
                    course_key: reqForm.course_key,
                    course_display_name: reqForm.course_display_name,
                    frequency_years: reqForm.frequency_years,
                    is_active: true,
                  })
                  .then(reload)
              }}
            >
              Add rule
            </Button>
          </div>
          <ul className="text-sm space-y-1 max-h-48 overflow-y-auto">
            {requirements.map((r) => (
              <li key={r.id} className="border-b border-border/50 py-1">
                <span className="font-medium">{r.course_display_name}</span> —{' '}
                {r.match_department || r.match_role_key} — {r.frequency_years}y
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>
    </div>
  )
}
