/**
 * Admin → Competence binds: map published QGP templates onto PAMS
 * characteristics (CB-UI-2).
 *
 * CB-UI-1 put the Plant board on the LIVE API and it correctly reads "issued in
 * PAMS, not demonstrated in QGP" in every square, because `competence_assessment_binds`
 * is empty. This is the screen that fills it. One published template per PAMS
 * characteristic per mode: the field assessment and the induction are separate
 * demonstrations of the same characteristic, so both may be bound, and a second
 * template either way is refused by the server.
 *
 * Two things this screen must not do:
 *  - **Write PAMS.** It cannot: the only endpoints it calls write QGP's own
 *    bind table, and no PAMS write path exists server-side.
 *  - **Grey out an unmapped characteristic.** Every characteristic the snapshot
 *    holds is listed whether or not anyone has bound it. Unbound is a gap in
 *    QGP's mapping, not a competence finding, and painting it like one is the
 *    exact defect CB-UI-1 removed from the board.
 *
 * Copy is plain English rather than i18n keys, for the same measured reason as
 * CB-UI-1: a key pair is shell-resident and would be charged to the app shell's
 * gzip budget for text only this lazy chunk renders.
 */
import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { AlertTriangle, Loader2, Trash2 } from 'lucide-react'
import {
  auditsApi,
  competenceBindApi,
  getApiErrorMessage,
  type AuditTemplate,
  type CompetenceAssessmentBind,
  type CompetenceBindListResponse,
  type CompetenceBindMode,
} from '../../api/client'
import { toast } from '../../contexts/ToastContext'
import { Button } from '../../components/ui/Button'
import { Card, CardContent, CardHeader } from '../../components/ui/Card'
import { Badge } from '../../components/ui/Badge'
import { cn } from '../../helpers/utils'
import { parseInstrument } from '../auditInstrument'
import {
  BIND_CELL_TONE,
  MODE_LABEL,
  apiErrorStatus,
  bindCellState,
  bindCellSummary,
  buildBindRows,
  intervalSummary,
  type CharacteristicBindRow,
} from './competenceBinds/competenceBindRows'

const DISABLED_FALLBACK =
  'The competence board is not enabled in this environment, so there is nothing to bind against. Nothing is being hidden.'

const LOAD_FAILED_FALLBACK = 'The assessment binds could not be loaded.'

/** The picker offers published templates only; the server refuses the rest. */
const TEMPLATE_PAGE_SIZE = 200

const MODES: CompetenceBindMode[] = ['field', 'induction']

type PageState =
  | { status: 'loading' }
  | { status: 'ready'; data: CompetenceBindListResponse }
  | { status: 'unavailable'; message: string }
  | { status: 'error'; message: string }

function normalise(data: CompetenceBindListResponse): CompetenceBindListResponse {
  return {
    items: Array.isArray(data?.items) ? data.items : [],
    characteristics: Array.isArray(data?.characteristics) ? data.characteristics : [],
    banner: data?.banner ?? null,
  }
}

function BindCell({
  row,
  mode,
  templateName,
  onRemove,
  removing,
}: {
  row: CharacteristicBindRow
  mode: CompetenceBindMode
  templateName: (templateId: number) => string
  onRemove: (bind: CompetenceAssessmentBind) => void
  removing: number | null
}) {
  const bind = mode === 'field' ? row.field : row.induction
  const state = bindCellState(bind)
  const summary = bindCellSummary(row, mode, templateName)

  return (
    <td className="p-2 border-b border-border align-top">
      <div
        data-testid={`bind-cell-${row.key}-${mode}`}
        data-cell-state={state}
        title={summary}
        className={cn('rounded-md px-2 py-1.5 text-xs', BIND_CELL_TONE[state])}
      >
        {bind ? (
          <div className="flex items-start justify-between gap-2">
            <span>
              <span className="block font-medium text-foreground">{templateName(bind.template_id)}</span>
              <span className="block text-muted-foreground">{intervalSummary(bind)}</span>
            </span>
            <Button
              size="sm"
              variant="ghost"
              aria-label={`Remove the ${MODE_LABEL[mode].toLowerCase()} bind on ${row.label}`}
              data-testid={`bind-remove-${row.key}-${mode}`}
              disabled={removing === bind.id}
              onClick={() => onRemove(bind)}
            >
              <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
            </Button>
          </div>
        ) : (
          <span>Not bound</span>
        )}
      </div>
      <span className="sr-only">{summary}</span>
    </td>
  )
}

export default function CompetenceBinds() {
  const [state, setState] = useState<PageState>({ status: 'loading' })
  const [templates, setTemplates] = useState<AuditTemplate[]>([])
  const [templatesFailed, setTemplatesFailed] = useState(false)
  const [characteristicKey, setCharacteristicKey] = useState('')
  const [templateId, setTemplateId] = useState('')
  const [mode, setMode] = useState<CompetenceBindMode>('field')
  const [intervalDays, setIntervalDays] = useState('')
  const [saving, setSaving] = useState(false)
  const [removing, setRemoving] = useState<number | null>(null)

  const load = useCallback(async () => {
    setState({ status: 'loading' })
    try {
      const response = await competenceBindApi.list()
      setState({ status: 'ready', data: normalise(response.data) })
    } catch (error) {
      const status = apiErrorStatus(error)
      setState(
        status === 404
          ? { status: 'unavailable', message: getApiErrorMessage(error, DISABLED_FALLBACK) }
          : { status: 'error', message: getApiErrorMessage(error, LOAD_FAILED_FALLBACK) },
      )
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    let cancelled = false
    const loadTemplates = async () => {
      try {
        const response = await auditsApi.listTemplates(1, TEMPLATE_PAGE_SIZE, { is_published: true })
        if (cancelled) return
        setTemplates(Array.isArray(response.data?.items) ? response.data.items : [])
        setTemplatesFailed(false)
      } catch {
        if (cancelled) return
        setTemplates([])
        setTemplatesFailed(true)
      }
    }
    void loadTemplates()
    return () => {
      cancelled = true
    }
  }, [])

  const templateName = useCallback(
    (id: number) => templates.find((template) => template.id === id)?.name ?? `Template #${id}`,
    [templates],
  )

  const rows = useMemo(() => {
    if (state.status !== 'ready') return []
    return buildBindRows(state.data.characteristics, state.data.items)
  }, [state])

  const boundTemplateIds = useMemo(
    () => new Set(state.status === 'ready' ? state.data.items.map((bind) => bind.template_id) : []),
    [state],
  )

  const submit = async () => {
    if (!characteristicKey || !templateId) {
      toast.error('Choose a characteristic and a published template.')
      return
    }
    const parsedInterval = intervalDays.trim() === '' ? null : Number(intervalDays)
    if (parsedInterval !== null && (!Number.isInteger(parsedInterval) || parsedInterval < 1)) {
      toast.error('The interval must be a whole number of days, or left blank.')
      return
    }
    setSaving(true)
    try {
      await competenceBindApi.create({
        template_id: Number(templateId),
        characteristic_key: characteristicKey,
        mode,
        interval_days: parsedInterval,
      })
      toast.success(`Bound ${characteristicKey} — ${MODE_LABEL[mode].toLowerCase()}`)
      setTemplateId('')
      setIntervalDays('')
      await load()
    } catch (error) {
      // The server owns the 1:1 rule; show its sentence rather than guessing one.
      toast.error(getApiErrorMessage(error, 'The bind was refused.'))
    } finally {
      setSaving(false)
    }
  }

  const remove = async (bind: CompetenceAssessmentBind) => {
    setRemoving(bind.id)
    try {
      await competenceBindApi.remove(bind.id)
      toast.success(`Removed the bind on ${bind.characteristic_key}`)
      await load()
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'The bind could not be removed.'))
    } finally {
      setRemoving(null)
    }
  }

  const header = (
    <div>
      <h1 className="text-2xl font-bold text-foreground">Competence binds</h1>
      <p className="text-muted-foreground mt-1">
        Point a published QGP template at a PAMS characteristic so that completing it records a
        demonstration on the{' '}
        <Link className="underline" to="/workforce/dashboard">
          Plant board
        </Link>
        . Binding changes nothing in PAMS: issuance stays there, and QGP never writes to it.
      </p>
    </div>
  )

  if (state.status === 'loading') {
    return (
      <div className="space-y-6" data-testid="competence-binds-page">
        {header}
        <div className="flex items-center justify-center h-48" data-testid="competence-binds-loading">
          <Loader2 className="w-8 h-8 text-primary animate-spin" aria-label="Loading" />
        </div>
      </div>
    )
  }

  if (state.status !== 'ready') {
    const unavailable = state.status === 'unavailable'
    return (
      <div className="space-y-6" data-testid="competence-binds-page">
        {header}
        <div
          role="status"
          data-testid={unavailable ? 'competence-binds-unavailable' : 'competence-binds-error'}
          className={cn(
            'rounded-lg border px-4 py-3 text-sm',
            unavailable
              ? 'border-warning/40 bg-warning/10 text-foreground'
              : 'border-destructive/40 bg-destructive/10 text-destructive',
          )}
        >
          <p className="font-medium">
            {unavailable ? 'Competence board not enabled here' : 'The assessment binds did not load'}
          </p>
          <p className="mt-1">{state.message}</p>
          {unavailable ? null : (
            <Button
              size="sm"
              variant="secondary"
              className="mt-3"
              data-testid="competence-binds-retry"
              onClick={() => void load()}
            >
              Retry
            </Button>
          )}
        </div>
      </div>
    )
  }

  const { data } = state
  const noCharacteristics = data.characteristics.length === 0

  return (
    <div className="space-y-6" data-testid="competence-binds-page">
      {header}

      {data.banner ? (
        <div
          role="status"
          data-testid="competence-binds-banner"
          className="flex items-start gap-2 rounded-lg border border-warning/40 bg-warning/10 px-4 py-3 text-sm text-foreground"
        >
          <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0 text-warning" aria-hidden="true" />
          <span>{data.banner}</span>
        </div>
      ) : null}

      <Card>
        <CardHeader>
          <h2 className="text-lg font-semibold text-foreground">Add a bind</h2>
          <p className="text-sm text-muted-foreground">
            One published template per characteristic per mode. A characteristic can carry both a
            field assessment and an induction; a second template for the same mode is refused.
          </p>
        </CardHeader>
        <CardContent>
          {templatesFailed ? (
            <p className="text-sm text-destructive" data-testid="competence-binds-templates-failed">
              Published templates could not be loaded, so a bind cannot be added right now. Reload
              the page before trying again.
            </p>
          ) : null}
          <div className="grid gap-4 md:grid-cols-4">
            <div>
              <label className="block text-sm font-medium mb-1" htmlFor="bind-characteristic">
                PAMS characteristic
              </label>
              <select
                id="bind-characteristic"
                className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
                value={characteristicKey}
                onChange={(event) => setCharacteristicKey(event.target.value)}
                disabled={noCharacteristics}
              >
                <option value="">Choose a characteristic…</option>
                {data.characteristics.map((entry) => (
                  <option key={entry.key} value={entry.key}>
                    {entry.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-1" htmlFor="bind-template">
                Published template
              </label>
              <select
                id="bind-template"
                className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
                value={templateId}
                onChange={(event) => setTemplateId(event.target.value)}
              >
                <option value="">Choose a template…</option>
                {templates.map((template) => (
                  <option key={template.id} value={String(template.id)}>
                    {template.name} — {parseInstrument(template.tags)}
                    {boundTemplateIds.has(template.id) ? ' (already bound)' : ''}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-1" htmlFor="bind-mode">
                Mode
              </label>
              <select
                id="bind-mode"
                className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
                value={mode}
                onChange={(event) => setMode(event.target.value as CompetenceBindMode)}
              >
                {MODES.map((value) => (
                  <option key={value} value={value}>
                    {MODE_LABEL[value]}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-1" htmlFor="bind-interval">
                Reassessment interval (days)
              </label>
              <input
                id="bind-interval"
                type="number"
                min={1}
                max={3650}
                className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
                value={intervalDays}
                onChange={(event) => setIntervalDays(event.target.value)}
                placeholder="Optional"
              />
            </div>
          </div>
          <p className="mt-2 text-xs text-muted-foreground">
            Leave the interval blank to keep the existing competency-requirement expiry. Blank is
            not "never expires".
          </p>
          <Button
            type="button"
            className="mt-4"
            data-testid="competence-binds-submit"
            disabled={saving || noCharacteristics}
            onClick={() => void submit()}
          >
            {saving ? 'Binding…' : 'Add bind'}
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <h2 className="text-lg font-semibold text-foreground">PAMS characteristics</h2>
          <p className="text-sm text-muted-foreground">
            Every characteristic in the current PAMS snapshot, bound or not. An unbound
            characteristic means QGP has not mapped an assessment to it yet — it is not a finding
            against anyone, and the Plant board keeps reading it as issued in PAMS.
          </p>
        </CardHeader>
        <CardContent>
          {noCharacteristics ? (
            <p className="text-sm text-muted-foreground" data-testid="competence-binds-empty">
              There is no PAMS characteristic to bind against yet. That is the snapshot being
              absent, not a count of zero.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-sm" data-testid="competence-binds-table">
                <caption className="sr-only">
                  PAMS characteristics and the QGP templates bound to them
                </caption>
                <thead>
                  <tr>
                    <th
                      scope="col"
                      className="text-left p-2 font-medium text-muted-foreground border-b border-border"
                    >
                      Characteristic
                    </th>
                    {MODES.map((value) => (
                      <th
                        key={value}
                        scope="col"
                        className="text-left p-2 font-medium text-muted-foreground border-b border-border"
                      >
                        {MODE_LABEL[value]}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.key} data-testid={`bind-row-${row.key}`}>
                      <th
                        scope="row"
                        className="text-left p-2 font-medium text-foreground border-b border-border align-top whitespace-nowrap"
                      >
                        {row.label}
                        {row.inSnapshot ? null : (
                          <Badge
                            variant="outline"
                            className="ml-2"
                            data-testid={`bind-orphan-${row.key}`}
                          >
                            Not in the current snapshot
                          </Badge>
                        )}
                      </th>
                      {MODES.map((value) => (
                        <BindCell
                          key={value}
                          row={row}
                          mode={value}
                          templateName={templateName}
                          onRemove={(bind) => void remove(bind)}
                          removing={removing}
                        />
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <p className="mt-4 text-xs text-muted-foreground">
            Removing a bind empties the demonstration overlay for that column on the Plant board and
            the cell falls back to what PAMS holds. The assessment history is kept and nothing is
            un-issued: revoking issuance is a PAMS action QGP only ever raises as a change request.
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
