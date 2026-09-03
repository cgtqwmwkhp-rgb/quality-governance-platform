/**
 * Workforce → Competency: the Plant / People competence board (CB-UI-1).
 *
 * This page replaces the workshop asset-type matrix that used to land here.
 * That matrix was drawn from WDP analytics, which holds no competency records
 * for this tenant, so the screen a manager opened to ask "who is competent on
 * what" answered with eighty-five rows of grey. The competence board API is
 * LIVE (CB-PR1..PR6, ADR-0026) and holds the two families that actually carry
 * the answer, so the page now asks it instead.
 *
 * Two families, two different sources of truth, and QGP owns neither:
 *  - **Plant** (`family=pams`): competencies issued in PAMS. Read-only. QGP
 *    never writes to PAMS — there is no client method that could.
 *  - **People** (`family=atlas`): statutory training held in the Atlas import,
 *    office and management included. QGP creates no User from an Atlas row.
 *
 * Copy is plain English rather than i18n keys on purpose. This is a lazily
 * loaded route chunk; an `en.json`/`cy.json` key pair is shell-resident and
 * would be charged to the app shell's gzip budget for text only this chunk
 * ever renders (same call as AUD-F6's device-ledger banners).
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { AlertTriangle, Loader2, PlugZap } from 'lucide-react'
import {
  competenceAssessmentExecutePath,
  competenceBoardApi,
  competenceStartApi,
  getApiErrorMessage,
  type CompetenceBindMode,
  type CompetenceBoardColumn,
  type CompetenceBoardFamily,
  type CompetenceBoardPerson,
  type CompetenceBoardResponse,
  type CompetencePlantEvidence,
} from '../../api/client'
import { toast } from '../../contexts/ToastContext'
import { Button } from '../../components/ui/Button'
import { Card, CardContent, CardHeader } from '../../components/ui/Card'
import { Badge } from '../../components/ui/Badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/Tabs'
import { cn } from '../../helpers/utils'
import {
  PEOPLE_CELL_TONE,
  PLANT_CELL_TONE,
  apiErrorStatus,
  peopleCellState,
  peopleCellSummary,
  plantCellState,
  plantCellSummary,
  todayIso,
} from './competenceBoard/competenceBoardCells'
import {
  MODE_LABEL,
  cellStartability,
  defaultMode,
  isUnbound,
  normaliseEvidence,
  startabilitySummary,
} from './competenceBoard/competenceStart'

type TabId = 'plant' | 'people'

const FAMILY_BY_TAB: Record<TabId, CompetenceBoardFamily> = {
  plant: 'pams',
  people: 'atlas',
}

const DISABLED_FALLBACK =
  'The competence board is not enabled in this environment. Nothing is being hidden — there is no data to show, and none is being invented.'

const LOAD_FAILED_FALLBACK = 'The competence board could not be loaded.'

/** Kept reachable as the kill switch for this slice; deliberately not in the nav. */
const LEGACY_ANALYTICS_PATH = '/workforce/dashboard/analytics'

type BoardState =
  | { status: 'loading' }
  | { status: 'ready'; data: CompetenceBoardResponse }
  | { status: 'unavailable'; message: string }
  | { status: 'error'; message: string }

const PLANT_LEGEND: { state: keyof typeof PLANT_CELL_TONE; label: string }[] = [
  { state: 'demonstrated_pass', label: 'Issued in PAMS, demonstrated in QGP' },
  { state: 'issued', label: 'Issued in PAMS, not yet demonstrated' },
  { state: 'demonstrated_fail', label: 'QGP assessment recorded a fail' },
  { state: 'no_record', label: 'No PAMS record' },
]

const PEOPLE_LEGEND: { state: keyof typeof PEOPLE_CELL_TONE; label: string }[] = [
  { state: 'passed', label: 'Passed, in date' },
  { state: 'passed_expired', label: 'Passed, expiry has passed' },
  { state: 'expiry_without_pass', label: 'Expiry recorded with no pass date' },
  { state: 'no_record', label: 'No Atlas record' },
]

/**
 * Tolerant read of the one thing that would throw rather than degrade: a list
 * that is not a list. The board is a strict-writer FastAPI response, so this is
 * insurance against a proxy or a future field rename, not an expected shape.
 * Nothing here invents a value — a missing list stays empty, which the panel
 * then reports as "the source has not been loaded".
 */
function normaliseBoard(
  data: CompetenceBoardResponse,
  family: CompetenceBoardFamily,
): CompetenceBoardResponse {
  return {
    ...data,
    family: data?.family ?? family,
    snapshot: data?.snapshot ?? { row_count: 0, stale: true },
    columns: Array.isArray(data?.columns) ? data.columns : [],
    people: Array.isArray(data?.people) ? data.people : [],
    unmapped_count: typeof data?.unmapped_count === 'number' ? data.unmapped_count : 0,
    // An absent assessor block stays absent rather than becoming an empty
    // permissive one: `cellStartability` reads "cannot prove issuance" from it,
    // which is the fail-closed reading.
    assessor: data?.assessor ?? null,
  }
}

function personRowKey(
  person: CompetenceBoardPerson,
  family: CompetenceBoardFamily,
  index: number,
): string {
  if (family === 'atlas') {
    if (person.atlas_person_id != null) return `atlas-${person.atlas_person_id}`
    if (person.engineer_id != null) return `eng-${person.engineer_id}`
  } else {
    if (person.engineer_id != null) return `eng-${person.engineer_id}`
    if (person.pams_technician_id != null) return `pams-${person.pams_technician_id}`
  }
  return `row-${index}`
}

/** A cell the viewer may start a demonstration from (CB-UI-3). */
type StartTarget = {
  person: CompetenceBoardPerson
  engineerId: number
  column: CompetenceBoardColumn
  modes: CompetenceBindMode[]
}

const EVIDENCE_FIELDS: { name: keyof CompetencePlantEvidence; label: string }[] = [
  { name: 'make', label: 'Make' },
  { name: 'model', label: 'Model' },
  { name: 'serial', label: 'Serial number' },
  { name: 'pams_plant_id', label: 'PAMS plant ID' },
]

/**
 * The start form for one cell (CB-UI-3).
 *
 * Inline rather than a modal, matching the CB-UI-2 bind screen: plain labelled
 * controls, no focus trap to get wrong. It is a labelled region that receives
 * focus when it opens, so a keyboard user who activated a square lands in the
 * form rather than back at the top of an eighty-five row table.
 *
 * The plant boxes are evidence about the machine and nothing else. They grant
 * no competence, they are not board columns, and leaving them blank does not
 * make the demonstration invalid — an assessment can legitimately be carried
 * out on a machine whose plate is unreadable.
 */
function StartPanel({
  target,
  onCancel,
  onSubmit,
  submitting,
}: {
  target: StartTarget
  onCancel: () => void
  onSubmit: (mode: CompetenceBindMode, evidence: CompetencePlantEvidence) => void
  submitting: boolean
}) {
  const [mode, setMode] = useState<CompetenceBindMode>(() => defaultMode(target.modes))
  const [evidence, setEvidence] = useState<CompetencePlantEvidence>({})
  const heading = useRef<HTMLHeadingElement>(null)

  // Re-key on the cell so switching cells resets the form rather than carrying
  // the previous machine's serial onto a different person's assessment.
  useEffect(() => {
    setMode(defaultMode(target.modes))
    setEvidence({})
    heading.current?.focus()
  }, [target])

  return (
    // A named `section` is already a landmark region — naming it is what makes
    // it one — so an explicit role="region" would be redundant.
    <section
      aria-labelledby="competence-start-heading"
      data-testid="competence-start-panel"
      className="rounded-lg border border-primary/40 bg-primary/5 px-4 py-3"
    >
      <h3
        ref={heading}
        tabIndex={-1}
        id="competence-start-heading"
        className="text-sm font-semibold text-foreground focus-visible:outline-none"
      >
        Start a demonstration — {target.person.display_name}, {target.column.label}
      </h3>
      <p className="mt-1 text-xs text-muted-foreground">
        This creates a QGP assessment and opens it. A pass records the demonstration on this board;
        it does not issue anything in PAMS, because QGP never writes to PAMS.
      </p>

      <div className="mt-3 grid gap-3 md:grid-cols-5">
        <div>
          <label className="block text-sm font-medium mb-1" htmlFor="competence-start-mode">
            Mode
          </label>
          <select
            id="competence-start-mode"
            className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
            value={mode}
            onChange={(event) => setMode(event.target.value as CompetenceBindMode)}
          >
            {target.modes.map((value) => (
              <option key={value} value={value}>
                {MODE_LABEL[value]}
              </option>
            ))}
          </select>
        </div>
        {EVIDENCE_FIELDS.map((field) => (
          <div key={field.name}>
            <label className="block text-sm font-medium mb-1" htmlFor={`competence-start-${field.name}`}>
              {field.label}
            </label>
            <input
              id={`competence-start-${field.name}`}
              className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
              maxLength={120}
              placeholder="Optional"
              value={evidence[field.name] ?? ''}
              onChange={(event) =>
                setEvidence((prev) => ({ ...prev, [field.name]: event.target.value }))
              }
            />
          </div>
        ))}
      </div>
      <p className="mt-2 text-xs text-muted-foreground">
        Make, model, serial and plant ID are evidence of which machine was used. They are optional,
        they are not columns on this board, and they do not narrow what the demonstration covers.
      </p>

      <div className="mt-3 flex gap-2">
        <Button
          type="button"
          data-testid="competence-start-submit"
          disabled={submitting}
          onClick={() => onSubmit(mode, evidence)}
        >
          {submitting ? 'Starting…' : `Start ${MODE_LABEL[mode].toLowerCase()}`}
        </Button>
        <Button
          type="button"
          variant="secondary"
          data-testid="competence-start-cancel"
          disabled={submitting}
          onClick={onCancel}
        >
          Cancel
        </Button>
      </div>
    </section>
  )
}

function BoardNotice({
  testId,
  tone,
  title,
  body,
  onRetry,
}: {
  testId: string
  tone: 'warning' | 'destructive'
  title: string
  body: string
  onRetry?: () => void
}) {
  return (
    <div
      role="status"
      data-testid={testId}
      className={cn(
        'rounded-lg border px-4 py-3 text-sm',
        tone === 'warning'
          ? 'border-warning/40 bg-warning/10 text-foreground'
          : 'border-destructive/40 bg-destructive/10 text-destructive',
      )}
    >
      <p className="font-medium">{title}</p>
      <p className="mt-1">{body}</p>
      <p className="mt-2 text-xs text-muted-foreground">
        The workshop asset-type analytics this page used to show are still at{' '}
        <Link className="underline" to={LEGACY_ANALYTICS_PATH}>
          {LEGACY_ANALYTICS_PATH}
        </Link>
        . They report QGP competency records, not PAMS or Atlas.
      </p>
      {onRetry ? (
        <Button
          size="sm"
          variant="secondary"
          className="mt-3"
          onClick={onRetry}
          data-testid={`${testId}-retry`}
        >
          Retry
        </Button>
      ) : null}
    </div>
  )
}

function SnapshotLine({ data }: { data: CompetenceBoardResponse }) {
  const { snapshot } = data
  const bits: string[] = []
  if (snapshot.source_name) bits.push(snapshot.source_name)
  if (snapshot.id != null) bits.push(`import #${snapshot.id}`)
  if (snapshot.row_count) bits.push(`${snapshot.row_count} source rows`)
  if (snapshot.completed_at) bits.push(`loaded ${snapshot.completed_at.slice(0, 10)}`)
  bits.push(`${data.people.length} people`)
  bits.push(`${data.columns.length} columns`)
  if (data.unmapped_count > 0) {
    bits.push(`${data.unmapped_count} not linked to a QGP employee record`)
  }
  return (
    <p className="text-xs text-muted-foreground" data-testid={`competence-snapshot-${data.family}`}>
      {bits.join(' · ')}
    </p>
  )
}

function BoardTable({
  data,
  today,
  onStart,
}: {
  data: CompetenceBoardResponse
  today: string
  onStart: (target: StartTarget) => void
}) {
  const isPlant = data.family === 'pams'
  const tones = isPlant ? PLANT_CELL_TONE : PEOPLE_CELL_TONE
  const legend = isPlant ? PLANT_LEGEND : PEOPLE_LEGEND

  return (
    <div>
      <div className="overflow-x-auto" data-testid={`competence-board-table-${data.family}`}>
        <table className="w-full border-collapse text-sm">
          <caption className="sr-only">
            {isPlant
              ? 'Plant competencies issued in PAMS, by person and characteristic'
              : 'Statutory training held in Atlas, by person and course'}
          </caption>
          <thead>
            <tr>
              <th
                scope="col"
                className="sticky left-0 z-10 bg-card text-left p-2 font-medium text-muted-foreground border-b border-border min-w-[12rem]"
              >
                Person
              </th>
              {data.columns.map((column) => (
                <th
                  key={column.key}
                  scope="col"
                  data-testid={`competence-column-${data.family}-${column.key}`}
                  className="p-2 font-medium text-muted-foreground border-b border-border text-center whitespace-nowrap"
                >
                  {column.label}
                  {/*
                    The unbound fact belongs to the column, not to a person, so
                    it is stated once here instead of eighty-five times down the
                    rows. The squares underneath keep their PAMS colour: an
                    unmapped characteristic is a gap in QGP, and greying the
                    column would read as a finding against everyone in it.
                  */}
                  {isPlant && isUnbound(column) ? (
                    <span
                      className="mt-0.5 block text-[0.65rem] font-normal normal-case text-muted-foreground"
                      data-testid={`competence-column-unbound-${column.key}`}
                    >
                      No family template yet
                    </span>
                  ) : null}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.people.map((person, index) => {
              const rowKey = personRowKey(person, data.family, index)
              const cells = person.cells ?? {}
              return (
                <tr key={rowKey} className="hover:bg-muted/20">
                  <th
                    scope="row"
                    className="sticky left-0 z-10 bg-card text-left p-2 font-medium text-foreground border-b border-border whitespace-nowrap"
                  >
                    <div className="flex items-center gap-2">
                      {person.mapped && person.engineer_id != null ? (
                        <Link
                          className="text-primary hover:underline"
                          to={`/workforce/engineers/${person.engineer_id}`}
                          data-testid={`competence-person-${data.family}-${rowKey}`}
                        >
                          {person.display_name}
                        </Link>
                      ) : (
                        <span data-testid={`competence-person-${data.family}-${rowKey}`}>
                          {person.display_name}
                        </span>
                      )}
                      {person.mapped ? null : (
                        <Badge
                          variant="outline"
                          data-testid={`competence-unmapped-${data.family}-${rowKey}`}
                        >
                          No QGP employee record
                        </Badge>
                      )}
                    </div>
                    {person.department || person.depot ? (
                      <span className="block text-xs font-normal text-muted-foreground">
                        {person.department || person.depot}
                      </span>
                    ) : null}
                  </th>
                  {data.columns.map((column) => {
                    const cell = cells[column.key]
                    const state = isPlant
                      ? plantCellState(cell, today)
                      : peopleCellState(cell, today)
                    const summary = isPlant
                      ? plantCellSummary(column.label, cell, today)
                      : peopleCellSummary(column.label, cell, today)
                    const sentence = `${person.display_name} — ${summary}`
                    const startability = cellStartability({
                      family: data.family,
                      column,
                      person,
                      assessor: data.assessor,
                    })
                    const square = (
                      <span
                        aria-hidden="true"
                        title={sentence}
                        data-testid={`competence-cell-${data.family}-${rowKey}-${column.key}`}
                        data-cell-state={state}
                        className={cn(
                          'mx-auto block h-5 w-5 rounded-sm',
                          (tones as Record<string, string>)[state],
                        )}
                      />
                    )
                    return (
                      <td key={column.key} className="p-1.5 border-b border-border text-center">
                        {startability.status === 'startable' && person.engineer_id != null ? (
                          // The square becomes a button only where a start
                          // would be accepted. The gate is still the server's:
                          // this only avoids offering a form that ends in 403.
                          <button
                            type="button"
                            data-testid={`competence-start-${rowKey}-${column.key}`}
                            // A marker every start control shares, so a test can
                            // assert the *set* of startable cells rather than the
                            // absence of one id it may have spelled wrongly.
                            data-start-cell={`${rowKey}-${column.key}`}
                            className="mx-auto block rounded-sm p-1 hover:ring-2 hover:ring-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                            onClick={() =>
                              onStart({
                                person,
                                engineerId: person.engineer_id as number,
                                column,
                                modes: startability.modes,
                              })
                            }
                          >
                            {square}
                            <span className="sr-only">
                              {`${sentence} — ${startabilitySummary(startability)}`}
                            </span>
                          </button>
                        ) : (
                          <>
                            {square}
                            <span className="sr-only">{sentence}</span>
                          </>
                        )}
                      </td>
                    )
                  })}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <ul className="mt-4 flex flex-wrap gap-4 text-xs text-muted-foreground">
        {legend.map((entry) => (
          <li key={entry.state} className="flex items-center gap-2">
            <span
              aria-hidden="true"
              className={cn('h-3 w-3 rounded-sm', (tones as Record<string, string>)[entry.state])}
            />
            {entry.label}
          </li>
        ))}
      </ul>
    </div>
  )
}

function BoardPanel({
  family,
  state,
  today,
  onRetry,
  footnote,
  onStart,
}: {
  family: CompetenceBoardFamily
  state: BoardState | undefined
  today: string
  onRetry: () => void
  footnote: string
  onStart: (target: StartTarget) => void
}) {
  if (!state || state.status === 'loading') {
    return (
      <div
        className="flex items-center justify-center h-48"
        data-testid={`competence-board-loading-${family}`}
      >
        <Loader2 className="w-8 h-8 text-primary animate-spin" aria-label="Loading" />
      </div>
    )
  }

  if (state.status === 'unavailable') {
    return (
      <BoardNotice
        testId={`competence-board-unavailable-${family}`}
        tone="warning"
        title="Competence board not enabled here"
        body={state.message}
      />
    )
  }

  if (state.status === 'error') {
    return (
      <BoardNotice
        testId={`competence-board-error-${family}`}
        tone="destructive"
        title="The competence board did not load"
        body={state.message}
        onRetry={onRetry}
      />
    )
  }

  const { data } = state
  const empty = data.columns.length === 0 || data.people.length === 0
  // No people means the source has not been loaded. People with no columns is a
  // different fact — the import is there and nothing in it carries a date — and
  // saying "not imported yet" for it would be false.
  const emptyMessage =
    data.people.length === 0
      ? (data.banner ??
        data.snapshot.stale_reason ??
        (family === 'pams'
          ? 'No PAMS competence snapshot has been loaded yet.'
          : 'No Atlas training matrix has been imported yet.'))
      : `${data.people.length} people are in the source, but no ${
          family === 'pams' ? 'characteristic' : 'course'
        } carries a date, so there is no column to draw.`

  return (
    <div className="space-y-4">
      <SnapshotLine data={data} />
      {data.banner && !empty ? (
        <div
          role="status"
          data-testid={`competence-board-banner-${family}`}
          className="flex items-start gap-2 rounded-lg border border-warning/40 bg-warning/10 px-4 py-3 text-sm text-foreground"
        >
          <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0 text-warning" aria-hidden="true" />
          <span>{data.banner}</span>
        </div>
      ) : null}
      {/*
        Said once, above the table, so a viewer who can start nothing knows why
        rather than concluding the feature is broken. The server owns the
        sentence; the board does not guess a friendlier one.
      */}
      {family === 'pams' && !empty && data.assessor?.blocked_reason ? (
        <p
          role="status"
          className="text-xs text-muted-foreground"
          data-testid="competence-assessor-blocked"
        >
          {data.assessor.blocked_reason}
        </p>
      ) : null}
      {empty ? (
        <div
          className="flex flex-col items-center justify-center h-48 gap-2 text-center text-muted-foreground"
          data-testid={`competence-board-empty-${family}`}
        >
          <PlugZap className="w-10 h-10" aria-hidden="true" />
          <p className="text-sm text-foreground">{emptyMessage}</p>
          <p className="text-xs">
            Nothing is counted as zero here — the source has not been loaded, which is a different
            statement from nobody being competent.
          </p>
        </div>
      ) : (
        <BoardTable data={data} today={today} onStart={onStart} />
      )}
      <p className="text-xs text-muted-foreground">{footnote}</p>
    </div>
  )
}

export default function CompetenceBoard() {
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()
  const activeTab: TabId = searchParams.get('tab') === 'people' ? 'people' : 'plant'
  const activeFamily = FAMILY_BY_TAB[activeTab]
  const [startTarget, setStartTarget] = useState<StartTarget | null>(null)
  const [starting, setStarting] = useState(false)

  const [boards, setBoards] = useState<Partial<Record<CompetenceBoardFamily, BoardState>>>({})
  const requested = useRef<Set<CompetenceBoardFamily>>(new Set())
  // A retry that lands after a slower first attempt must not be overwritten by
  // it, so each family only accepts the newest request it issued.
  const sequence = useRef<Partial<Record<CompetenceBoardFamily, number>>>({})
  // The date is read once per mount: recomputing it per cell would let a board
  // rendered across midnight disagree with itself row by row.
  const [today] = useState(() => todayIso())

  const load = useCallback(async (family: CompetenceBoardFamily) => {
    const ticket = (sequence.current[family] ?? 0) + 1
    sequence.current[family] = ticket
    setBoards((prev) => ({ ...prev, [family]: { status: 'loading' } }))
    try {
      const response = await competenceBoardApi.getBoard(family)
      if (sequence.current[family] !== ticket) return
      setBoards((prev) => ({
        ...prev,
        [family]: { status: 'ready', data: normaliseBoard(response.data, family) },
      }))
    } catch (error) {
      if (sequence.current[family] !== ticket) return
      const status = apiErrorStatus(error)
      setBoards((prev) => ({
        ...prev,
        [family]:
          status === 404
            ? { status: 'unavailable', message: getApiErrorMessage(error, DISABLED_FALLBACK) }
            : { status: 'error', message: getApiErrorMessage(error, LOAD_FAILED_FALLBACK) },
      }))
    }
  }, [])

  useEffect(() => {
    if (requested.current.has(activeFamily)) return
    requested.current.add(activeFamily)
    void load(activeFamily)
  }, [activeFamily, load])

  const startAssessment = async (mode: CompetenceBindMode, evidence: CompetencePlantEvidence) => {
    if (!startTarget) return
    setStarting(true)
    try {
      const response = await competenceStartApi.start({
        engineer_id: startTarget.engineerId,
        characteristic_key: startTarget.column.key,
        mode,
        // Blank boxes are sent as absent rather than as empty strings, so an
        // untouched form does not record "the serial is ''" as a fact.
        plant_evidence: normaliseEvidence(evidence),
      })
      setStartTarget(null)
      // The run is created and not yet carried out. Landing anywhere other than
      // its execution shell would leave a started assessment nobody is looking
      // at, so this goes straight there rather than reloading the board.
      navigate(competenceAssessmentExecutePath(response.data.run_id))
    } catch (error) {
      // The assessor gate, the flag and the 1:1 bind rule are all the server's
      // to state. Show its sentence; never soften a refusal into a retry.
      toast.error(getApiErrorMessage(error, 'The assessment could not be started.'))
    } finally {
      setStarting(false)
    }
  }

  const onTabChange = (value: string) => {
    // A half-filled start form belongs to a Plant cell; leaving it open behind
    // the People tab would let it be submitted against a cell nobody can see.
    setStartTarget(null)
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        next.set('tab', value)
        return next
      },
      { replace: true },
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Competence</h1>
        <p className="text-muted-foreground mt-1">
          Plant competencies are issued in PAMS and statutory training is held in Atlas. QGP shows
          both, records the assessments that demonstrate them, and writes to neither system.
        </p>
      </div>

      <Tabs value={activeTab} onValueChange={onTabChange}>
        <TabsList>
          <TabsTrigger value="plant" data-testid="competence-tab-plant">
            Plant
          </TabsTrigger>
          <TabsTrigger value="people" data-testid="competence-tab-people">
            People
          </TabsTrigger>
        </TabsList>

        <TabsContent value="plant">
          <Card>
            <CardHeader>
              <h2 className="text-lg font-semibold text-foreground">Plant — issued in PAMS</h2>
              <p className="text-sm text-muted-foreground">
                Columns are PAMS characteristics. A square that is only outlined means PAMS holds no
                record for that person and characteristic; it is not a failure and not a gap QGP has
                measured. Activate a square to start a demonstration where a family template is
                bound and PAMS has issued that characteristic to you.
              </p>
            </CardHeader>
            <CardContent className="space-y-4">
              {startTarget ? (
                <StartPanel
                  target={startTarget}
                  submitting={starting}
                  onCancel={() => setStartTarget(null)}
                  onSubmit={(mode, evidence) => void startAssessment(mode, evidence)}
                />
              ) : null}
              <BoardPanel
                family="pams"
                state={boards.pams}
                today={today}
                onRetry={() => void load('pams')}
                onStart={setStartTarget}
                footnote="Issued competencies are a read-only snapshot of PAMS. A square you can activate starts a demonstration bound to that characteristic; a pass records it here and changes nothing in PAMS."
              />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="people">
          <Card>
            <CardHeader>
              <h2 className="text-lg font-semibold text-foreground">People — held in Atlas</h2>
              <p className="text-sm text-muted-foreground">
                Everyone in the Atlas import appears, including office and management, and including
                anyone with no QGP employee record.
              </p>
            </CardHeader>
            <CardContent>
              <BoardPanel
                family="atlas"
                state={boards.atlas}
                today={today}
                onRetry={() => void load('atlas')}
                // Atlas courses are issued by a course pass, so there is no
                // characteristic to bind and nothing here is startable.
                onStart={() => undefined}
                footnote="Names come from the Atlas training matrix import and are never matched by name. A row with no QGP employee record stays on the board unlinked — QGP creates no user account from it."
              />
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
