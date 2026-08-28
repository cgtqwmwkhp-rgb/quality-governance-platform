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
import { BAND_LABEL, hubOpenKind, registerHref } from '../components/register/registerCatalogueHonesty'
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
      <Link
        to={registerHref(entry)}
        className="text-primary underline-offset-2 hover:underline"
      >
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

export default function RegisterOfRegisters() {
  const { t } = useTranslation()
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
        ...entry.standardRefs,
        entry.note ?? '',
        entry.externalSor ?? '',
      ]
        .join(' ')
        .toLowerCase()
      return hay.includes(needle)
    })
  }, [band, query])

  if (!enabled) {
    return <NotFound />
  }

  return (
    <div className="space-y-6" data-testid="register-of-registers">
      <div>
        <h1 className="text-2xl font-bold text-foreground">
          {t('registers.hub.title', 'Registers')}
        </h1>
        <p className="text-muted-foreground mt-1">
          {t(
            'registers.hub.subtitle',
            'PEL-HSEQ-5062 Register of Registers. Caption of where each register lives — not a second copy of the rows.',
          )}
        </p>
      </div>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
        <div className="flex-1">
          <label htmlFor="register-catalogue-search" className="text-sm font-medium text-foreground">
            {t('registers.hub.search', 'Search')}
          </label>
          <Input
            id="register-catalogue-search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={t('registers.hub.search_placeholder', 'PEL ref, title, standard…')}
            className="mt-1"
          />
        </div>
      </div>

      <div
        className="inline-flex flex-wrap rounded-md border border-border p-0.5 gap-0.5"
        role="tablist"
        aria-label={t('registers.hub.filter', 'Filter by status')}
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
            {t('registers.hub.caption', 'Named registers and their system of record')}
          </caption>
          <thead>
            <tr className="border-b border-border bg-muted/30 text-left">
              <th scope="col" className="px-4 py-3 font-medium text-muted-foreground">
                {t('registers.hub.col_ref', 'Reference')}
              </th>
              <th scope="col" className="px-4 py-3 font-medium text-muted-foreground">
                {t('registers.hub.col_title', 'Register')}
              </th>
              <th scope="col" className="px-4 py-3 font-medium text-muted-foreground">
                {t('registers.hub.col_status', 'Status')}
              </th>
              <th scope="col" className="px-4 py-3 font-medium text-muted-foreground">
                {t('registers.hub.col_sor', 'System of record')}
              </th>
              <th scope="col" className="px-4 py-3 font-medium text-muted-foreground">
                {t('registers.hub.col_open', 'Open')}
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((entry) => (
              <tr key={entry.docRef} className="border-b border-border">
                <th scope="row" className="px-4 py-3 font-medium text-foreground whitespace-nowrap">
                  {entry.docRef}
                </th>
                <td className="px-4 py-3">
                  <div className="text-foreground">{entry.title}</div>
                  <div className="text-xs text-muted-foreground mt-0.5">{entry.purpose}</div>
                </td>
                <td className="px-4 py-3">
                  <Badge variant={bandVariant(entry.band)}>{BAND_LABEL[entry.band]}</Badge>
                </td>
                <td className="px-4 py-3 text-muted-foreground">{systemOfRecord(entry)}</td>
                <td className="px-4 py-3">
                  <HubOpenCell
                    entry={entry}
                    scheduleEnabled={scheduleEnabled}
                    openLabel={t('registers.hub.open', 'Open')}
                    scheduleOffLabel={SCHEDULE_OFF_LABEL}
                    noLinkLabel={t('registers.hub.no_link', 'No QGP list')}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
