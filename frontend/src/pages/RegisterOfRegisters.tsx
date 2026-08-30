import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Badge } from '../components/ui/Badge'
import { Input } from '../components/ui/Input'
import { useFeatureFlag } from '../hooks/useFeatureFlag'
import {
  REGISTER_CATALOGUE,
  type RegisterBand,
  type RegisterEntry,
} from '../data/registerCatalogue'
import {
  BAND_LABEL,
  hubOpenKind,
  registerHref,
} from '../components/register/registerCatalogueHonesty'
import NotFound from './NotFound'

const BAND_FILTERS: Array<{ id: 'all' | RegisterBand; label: string }> = [
  { id: 'all', label: 'All' },
  { id: 'live', label: 'LIVE' },
  { id: 'caption', label: 'Caption' },
  { id: 'document', label: 'Document' },
  { id: 'absent', label: 'Not captured' },
  { id: 'hub', label: 'This hub' },
]

const SCHEDULE_OFF_LABEL = 'Schedule module is off in this deployment'

/** Function clusters over existing spines. Not a second catalogue field. */
type HubCluster =
  | 'cases'
  | 'assets'
  | 'clocks'
  | 'people'
  | 'audit'
  | 'fleet'
  | 'information'
  | 'filed'
  | 'this-hub'

const CLUSTER_ORDER: readonly HubCluster[] = [
  'cases',
  'assets',
  'clocks',
  'people',
  'audit',
  'fleet',
  'information',
  'filed',
  'this-hub',
]

const CLUSTER_LABEL: Record<HubCluster, string> = {
  cases: 'Cases',
  assets: 'Assets',
  clocks: 'Clocks',
  people: 'People',
  audit: 'Audit',
  fleet: 'Fleet',
  information: 'Information',
  filed: 'Filed',
  'this-hub': 'This hub',
}

/**
 * EMPTY is a catalogue fact (absent band or note), never a counted zero.
 * Dual-SoR is externalSor. Do not treat “module may be off” as empty.
 */
const EMPTY_NOTE_RE =
  /\b(no tenant |no premises |no dedicated |may still be empty|not a qgp spine|privacy stub|inventory locked)/i

function clusterOf(entry: RegisterEntry): HubCluster {
  if (entry.band === 'hub') return 'this-hub'
  if (entry.band === 'document') return 'filed'
  switch (entry.to) {
    case '/incidents':
    case '/complaints':
    case '/risk-register':
    case '/actions':
      return 'cases'
    case '/safety-assets':
      return 'assets'
    case '/compliance-schedule':
    case '/compliance':
      return 'clocks'
    case '/workforce/training':
    case '/my-reading':
      return 'people'
    case '/audits':
    case '/audit-templates':
      return 'audit'
    case '/vehicle-checklists':
    case '/planet-mark':
      return 'fleet'
    case '/ims':
      return 'information'
    case '/registers':
      return 'this-hub'
    default:
      break
  }
  if (entry.docRef.startsWith('PEL-IT-') || entry.docRef === 'PEL-DP-5008') {
    return 'information'
  }
  if (entry.docRef === 'PEL-HSEQ-5008' || entry.docRef === 'PEL-HSEQ-5036') {
    return 'clocks'
  }
  if (
    entry.docRef === 'PEL-HSEQ-5026' ||
    entry.docRef === 'PEL-HSEQ-5028' ||
    entry.docRef === 'PEL-HSEQ-5043'
  ) {
    return 'people'
  }
  if (entry.ownerRole === 'Procurement') return 'cases'
  return 'cases'
}

function isEmptyOccurrence(entry: RegisterEntry): boolean {
  if (entry.band === 'hub') return false
  if (entry.band === 'absent') return true
  return Boolean(entry.note && EMPTY_NOTE_RE.test(entry.note))
}

function bandVariant(band: RegisterBand): 'success' | 'info' | 'secondary' | 'outline' | 'warning' {
  if (band === 'live') return 'success'
  if (band === 'hub') return 'info'
  if (band === 'caption') return 'warning'
  if (band === 'document') return 'secondary'
  return 'outline'
}

function systemOfRecord(entry: RegisterEntry): string {
  if (entry.externalSor && entry.band !== 'live') {
    return entry.externalSor
  }
  if (entry.externalSor) {
    return `QGP and ${entry.externalSor}`
  }
  if (entry.band === 'absent') return 'Not captured'
  if (entry.band === 'document') return 'Library document'
  return 'Quality Governance Platform'
}

function HubOpenCell({
  entry,
  scheduleEnabled,
  openLabel,
  scheduleOffLabel,
  noLinkLabel,
}: {
  entry: RegisterEntry
  scheduleEnabled: boolean
  openLabel: string
  scheduleOffLabel: string
  noLinkLabel: string
}) {
  const open = hubOpenKind(entry, { compliance_schedule: scheduleEnabled })
  if (open === 'link' && entry.to) {
    return (
      <Link to={registerHref(entry)} className="text-primary underline-offset-2 hover:underline">
        {openLabel}
      </Link>
    )
  }
  if (open === 'schedule-off') {
    return (
      <span className="text-muted-foreground" data-testid={`register-schedule-off-${entry.docRef}`}>
        {scheduleOffLabel}
      </span>
    )
  }
  return <span className="text-muted-foreground">{noLinkLabel}</span>
}

function OccupancyChips({ entry }: { entry: RegisterEntry }) {
  const empty = isEmptyOccurrence(entry)
  const dual = Boolean(entry.externalSor)
  if (!empty && !dual) return null
  return (
    <span className="inline-flex flex-wrap gap-1 mt-1">
      {empty ? (
        <Badge variant="outline" data-testid={`register-empty-${entry.docRef}`}>
          EMPTY
        </Badge>
      ) : null}
      {dual ? (
        <Badge variant="info" data-testid={`register-dual-${entry.docRef}`}>
          DUAL
        </Badge>
      ) : null}
    </span>
  )
}

export default function RegisterOfRegisters() {
  const { t, i18n } = useTranslation()
  const useWelshCopy = i18n.language.toLowerCase().startsWith('cy')
  const copy = (key: string, english: string) => (useWelshCopy ? t(key, english) : english)
  const enabled = useFeatureFlag('register_catalogue')
  const scheduleEnabled = useFeatureFlag('compliance_schedule')
  const [query, setQuery] = useState('')
  const [band, setBand] = useState<(typeof BAND_FILTERS)[number]['id']>('all')

  const rows = useMemo(() => {
    const needle = query.trim().toLowerCase()
    return REGISTER_CATALOGUE.filter((entry) => {
      if (band !== 'all' && entry.band !== band) return false
      if (!needle) return true
      const hay = [
        entry.docRef,
        entry.title,
        entry.purpose,
        entry.ownerRole,
        CLUSTER_LABEL[clusterOf(entry)],
        ...entry.standardRefs,
        entry.note ?? '',
        entry.externalSor ?? '',
      ]
        .join(' ')
        .toLowerCase()
      return hay.includes(needle)
    })
  }, [band, query])

  const clustered = useMemo(() => {
    return CLUSTER_ORDER.map((id) => ({
      id,
      label: CLUSTER_LABEL[id],
      entries: rows.filter((entry) => clusterOf(entry) === id),
    })).filter((group) => group.entries.length > 0)
  }, [rows])

  if (!enabled) {
    return <NotFound />
  }

  return (
    <div className="space-y-6" data-testid="register-of-registers">
      <div>
        <h1 className="text-2xl font-bold text-foreground">
          {copy('registers.hub.title', 'Registers')}
        </h1>
        <p className="text-muted-foreground mt-1">
          {copy(
            'registers.hub.subtitle',
            'PEL-HSEQ-5062 Register of Registers. Caption of where each register lives — not a second copy of the rows.',
          )}
        </p>
      </div>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
        <div className="flex-1">
          <label
            htmlFor="register-catalogue-search"
            className="text-sm font-medium text-foreground"
          >
            {copy('registers.hub.search', 'Search')}
          </label>
          <Input
            id="register-catalogue-search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={copy('registers.hub.search_placeholder', 'PEL ref, title, standard…')}
            className="mt-1"
          />
        </div>
      </div>

      <div
        className="inline-flex flex-wrap rounded-md border border-border p-0.5 gap-0.5"
        role="tablist"
        aria-label={copy('registers.hub.filter', 'Filter by status')}
      >
        {BAND_FILTERS.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            aria-selected={band === item.id}
            className={
              band === item.id
                ? 'px-3 py-1.5 text-sm rounded-sm bg-primary text-primary-foreground'
                : 'px-3 py-1.5 text-sm rounded-sm text-muted-foreground hover:text-foreground'
            }
            onClick={() => setBand(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>

      <div className="overflow-x-auto border border-border rounded-lg">
        <table className="w-full text-sm">
          <caption className="sr-only">
            {copy('registers.hub.caption', 'Named registers and their system of record')}
          </caption>
          <thead>
            <tr className="border-b border-border bg-muted/30 text-left">
              <th scope="col" className="px-4 py-3 font-medium text-muted-foreground">
                {copy('registers.hub.col_ref', 'Reference')}
              </th>
              <th scope="col" className="px-4 py-3 font-medium text-muted-foreground">
                {copy('registers.hub.col_title', 'Register')}
              </th>
              <th scope="col" className="px-4 py-3 font-medium text-muted-foreground">
                {copy('registers.hub.col_status', 'Status')}
              </th>
              <th scope="col" className="px-4 py-3 font-medium text-muted-foreground">
                {copy('registers.hub.col_sor', 'System of record')}
              </th>
              <th scope="col" className="px-4 py-3 font-medium text-muted-foreground">
                {copy('registers.hub.col_open', 'Open')}
              </th>
            </tr>
          </thead>
          {clustered.map((group) => (
            <tbody key={group.id} data-testid={`register-cluster-${group.id}`}>
              <tr className="border-b border-border bg-muted/20">
                <th
                  scope="colgroup"
                  colSpan={5}
                  className="px-4 py-2 text-left text-sm font-semibold text-foreground"
                >
                  {group.label}
                </th>
              </tr>
              {group.entries.map((entry) => (
                <tr key={entry.docRef} className="border-b border-border">
                  <th scope="row" className="px-4 py-3 font-medium text-foreground whitespace-nowrap">
                    {entry.docRef}
                  </th>
                  <td className="px-4 py-3">
                    <div className="text-foreground">{entry.title}</div>
                    <div className="text-xs text-muted-foreground mt-0.5">{entry.purpose}</div>
                    <div className="text-xs text-muted-foreground mt-0.5">{entry.ownerRole}</div>
                    {isEmptyOccurrence(entry) && entry.note ? (
                      <div className="text-xs text-muted-foreground mt-0.5">{entry.note}</div>
                    ) : null}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-col items-start gap-1">
                      <Badge variant={bandVariant(entry.band)}>{BAND_LABEL[entry.band]}</Badge>
                      <OccupancyChips entry={entry} />
                    </div>
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">{systemOfRecord(entry)}</td>
                  <td className="px-4 py-3">
                    <HubOpenCell
                      entry={entry}
                      scheduleEnabled={scheduleEnabled}
                      openLabel={copy('registers.hub.open', 'Open')}
                      scheduleOffLabel={SCHEDULE_OFF_LABEL}
                      noLinkLabel={copy('registers.hub.no_link', 'No QGP list')}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          ))}
        </table>
      </div>
    </div>
  )
}
