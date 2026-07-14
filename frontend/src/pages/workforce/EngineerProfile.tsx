import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Pencil, Plus } from 'lucide-react'
import { trackError } from '../../utils/errorTracker'
import {
  workforceApi,
  getApiErrorMessage,
  type EngineerProfile as EngineerProfileType,
  type CompetencyRecord,
  type CompetencyRequirement,
  type TrainingTicket,
  type TicketVerifyState,
} from '../../api/client'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Label } from '../../components/ui/Label'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/Dialog'

const COMPETENCY_STATES = ['active', 'due', 'expired', 'failed', 'not_assessed'] as const

const stateColors: Record<string, string> = {
  active: 'bg-success/10 text-success',
  due: 'bg-warning/10 text-warning',
  expired: 'bg-destructive/10 text-destructive',
  failed: 'bg-destructive/10 text-destructive',
  not_assessed: 'bg-muted text-muted-foreground',
}

const VERIFY_STATES: TicketVerifyState[] = [
  'unverified',
  'pending',
  'verified',
  'rejected',
  'expired',
]

const verifyColors: Record<string, string> = {
  verified: 'bg-success/10 text-success',
  pending: 'bg-warning/10 text-warning',
  unverified: 'bg-muted text-muted-foreground',
  rejected: 'bg-destructive/10 text-destructive',
  expired: 'bg-destructive/10 text-destructive',
}

export type RequirementsMatch = {
  mandatoryTotal: number
  mandatoryMet: number
  /** Integer 0–100 when total > 0; null when there are no mandatory requirements. */
  percent: number | null
}

/** Mandatory met / mandatory total — a requirement is met when the engineer has an active record for its asset type. */
export function computeRequirementsMatch(
  requirements: CompetencyRequirement[],
  competencies: CompetencyRecord[],
  engineer?: Pick<EngineerProfileType, 'site' | 'job_title'> | null,
): RequirementsMatch {
  const activeAssetTypes = new Set(
    competencies.filter((c) => c.state === 'active').map((c) => c.asset_type_id),
  )

  const applicable = requirements.filter((req) => {
    if (!req.is_mandatory) return false
    if (req.site && engineer?.site && req.site !== engineer.site) return false
    if (req.role_key && engineer?.job_title && req.role_key !== engineer.job_title) return false
    return true
  })

  const mandatoryTotal = applicable.length
  if (mandatoryTotal === 0) {
    return { mandatoryTotal: 0, mandatoryMet: 0, percent: null }
  }

  const mandatoryMet = applicable.filter((req) => activeAssetTypes.has(req.asset_type_id)).length
  return {
    mandatoryTotal,
    mandatoryMet,
    percent: Math.round((mandatoryMet / mandatoryTotal) * 100),
  }
}

export function competenceGapsEngineerHref(engineerId: number): string {
  return `/workforce/competence-gaps?engineer_id=${engineerId}`
}

type TicketFormState = {
  scheme: string
  ticket_number: string
  issuer: string
  issued_at: string
  expires_at: string
  verify_state: TicketVerifyState | string
  evidence_id: string
  notes: string
}

const emptyTicketForm = (): TicketFormState => ({
  scheme: '',
  ticket_number: '',
  issuer: '',
  issued_at: '',
  expires_at: '',
  verify_state: 'unverified',
  evidence_id: '',
  notes: '',
})

function ticketToForm(ticket: TrainingTicket): TicketFormState {
  return {
    scheme: ticket.scheme ?? '',
    ticket_number: ticket.ticket_number ?? '',
    issuer: ticket.issuer ?? '',
    issued_at: ticket.issued_at ? ticket.issued_at.slice(0, 10) : '',
    expires_at: ticket.expires_at ? ticket.expires_at.slice(0, 10) : '',
    verify_state: ticket.verify_state || 'unverified',
    evidence_id: ticket.evidence_id != null ? String(ticket.evidence_id) : '',
    notes: ticket.notes ?? '',
  }
}

function formToPayload(form: TicketFormState, engineerId: number) {
  const evidenceRaw = form.evidence_id.trim()
  const evidence_id = evidenceRaw === '' ? undefined : Number(evidenceRaw)
  return {
    engineer_id: engineerId,
    scheme: form.scheme.trim(),
    ticket_number: form.ticket_number.trim(),
    issuer: form.issuer.trim() || undefined,
    issued_at: form.issued_at || undefined,
    expires_at: form.expires_at || undefined,
    verify_state: form.verify_state,
    evidence_id: Number.isFinite(evidence_id) ? evidence_id : undefined,
    notes: form.notes.trim() || undefined,
  }
}

export default function EngineerProfile() {
  const { t } = useTranslation()
  const { id } = useParams<{ id: string }>()
  const [engineer, setEngineer] = useState<EngineerProfileType | null>(null)
  const [competencies, setCompetencies] = useState<CompetencyRecord[]>([])
  const [tickets, setTickets] = useState<TrainingTicket[]>([])
  const [requirements, setRequirements] = useState<CompetencyRequirement[]>([])
  const [assetTypeMap, setAssetTypeMap] = useState<Record<number, string>>({})
  const [assetTypeMapError, setAssetTypeMapError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [ticketsError, setTicketsError] = useState<string | null>(null)
  const [requirementsError, setRequirementsError] = useState<string | null>(null)
  const [ticketsLoading, setTicketsLoading] = useState(false)

  const [ticketDialogOpen, setTicketDialogOpen] = useState(false)
  const [editingTicket, setEditingTicket] = useState<TrainingTicket | null>(null)
  const [ticketForm, setTicketForm] = useState<TicketFormState>(emptyTicketForm)
  const [ticketSaving, setTicketSaving] = useState(false)
  const [ticketFormError, setTicketFormError] = useState<string | null>(null)

  useEffect(() => {
    workforceApi
      .listAssetTypes()
      .then((res) => {
        const map: Record<number, string> = {}
        for (const at of res.data?.items || []) map[at.id] = at.name
        setAssetTypeMap(map)
        setAssetTypeMapError(null)
      })
      .catch((err) => {
        trackError(err, { component: 'EngineerProfile', action: 'listAssetTypes' })
        setAssetTypeMap({})
        setAssetTypeMapError(getApiErrorMessage(err))
      })
  }, [])

  const loadTickets = useCallback(async (engineerId: number) => {
    setTicketsLoading(true)
    setTicketsError(null)
    try {
      const res = await workforceApi.trainingTickets.list({
        engineer_id: engineerId,
        page: 1,
        page_size: 100,
      })
      setTickets(res.data?.items || [])
    } catch (err) {
      trackError(err, { component: 'EngineerProfile', action: 'listTickets' })
      setTickets([])
      setTicketsError(getApiErrorMessage(err))
    } finally {
      setTicketsLoading(false)
    }
  }, [])

  const loadRequirements = useCallback(async () => {
    setRequirementsError(null)
    try {
      const res = await workforceApi.competencyRequirements.list({
        is_mandatory: true,
        page: 1,
        page_size: 200,
      })
      setRequirements(res.data?.items || [])
    } catch (err) {
      trackError(err, { component: 'EngineerProfile', action: 'listRequirements' })
      setRequirements([])
      setRequirementsError(getApiErrorMessage(err))
    }
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
        await Promise.all([loadTickets(numId), loadRequirements()])
      } catch (err) {
        trackError(err, { component: 'EngineerProfile', action: 'load' })
        setError(getApiErrorMessage(err))
        setEngineer(null)
      } finally {
        setLoading(false)
      }
    }
    void load()
  }, [id, t, loadTickets, loadRequirements])

  const match = useMemo(
    () => computeRequirementsMatch(requirements, competencies, engineer),
    [requirements, competencies, engineer],
  )

  const stateCounts = useMemo(() => {
    const counts: Record<string, number> = Object.fromEntries(
      COMPETENCY_STATES.map((s) => [s, 0]),
    )
    for (const c of competencies) {
      if (c.state in counts) counts[c.state] += 1
      else counts.not_assessed += 1
    }
    return counts
  }, [competencies])

  const openCreateTicket = () => {
    setEditingTicket(null)
    setTicketForm(emptyTicketForm())
    setTicketFormError(null)
    setTicketDialogOpen(true)
  }

  const openEditTicket = (ticket: TrainingTicket) => {
    setEditingTicket(ticket)
    setTicketForm(ticketToForm(ticket))
    setTicketFormError(null)
    setTicketDialogOpen(true)
  }

  const saveTicket = async () => {
    if (!engineer) return
    if (!ticketForm.scheme.trim() || !ticketForm.ticket_number.trim()) {
      setTicketFormError(t('workforce.engineers.tickets.form_required'))
      return
    }
    setTicketSaving(true)
    setTicketFormError(null)
    try {
      const payload = formToPayload(ticketForm, engineer.id)
      if (editingTicket) {
        const { engineer_id: _omit, ...update } = payload
        await workforceApi.trainingTickets.update(editingTicket.id, update)
      } else {
        await workforceApi.trainingTickets.create(payload)
      }
      setTicketDialogOpen(false)
      await loadTickets(engineer.id)
    } catch (err) {
      trackError(err, {
        component: 'EngineerProfile',
        action: editingTicket ? 'updateTicket' : 'createTicket',
      })
      setTicketFormError(getApiErrorMessage(err))
    } finally {
      setTicketSaving(false)
    }
  }

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

  const assetTypeLabel = (assetTypeId: number) =>
    assetTypeMap[assetTypeId] ??
    (assetTypeMapError
      ? t('workforce.engineers.asset_type_unavailable', { id: assetTypeId })
      : `Asset Type #${assetTypeId}`)

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <Link to="/workforce/engineers" className="text-muted-foreground hover:text-foreground">
          &larr; {t('workforce.engineers.title')}
        </Link>
        <Link
          to={competenceGapsEngineerHref(engineer.id)}
          className="text-sm text-primary hover:underline"
          data-testid="engineer-competence-gaps-link"
        >
          {t('workforce.engineers.view_competence_gaps')}
        </Link>
      </div>

      {/* Identity */}
      <div className="bg-card border border-border rounded-xl p-6" data-testid="engineer-identity">
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
              {engineer.external_id ? `${engineer.external_id.slice(0, 8)}…` : '—'}
            </p>
          </div>
        </div>
      </div>

      {assetTypeMapError && (
        <div
          className="p-3 rounded-lg bg-warning/10 text-warning text-sm"
          data-testid="asset-type-map-error"
          role="alert"
        >
          {t('workforce.engineers.asset_types_load_error')}: {assetTypeMapError}
        </div>
      )}

      {/* Competency state KPIs — full lifecycle set */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4" data-testid="competency-state-kpis">
        {COMPETENCY_STATES.map((state) => (
          <div key={state} className="bg-card border border-border rounded-xl p-5">
            <p className="text-sm text-muted-foreground">
              {t(`workforce.engineers.competency_state.${state}`)}
            </p>
            <p
              className={`text-3xl font-bold mt-1 ${
                state === 'active'
                  ? 'text-success'
                  : state === 'due'
                    ? 'text-warning'
                    : state === 'expired' || state === 'failed'
                      ? 'text-destructive'
                      : 'text-muted-foreground'
              }`}
            >
              {stateCounts[state]}
            </p>
          </div>
        ))}
      </div>

      {/* Requirements coverage % match */}
      <div
        className="bg-card border border-border rounded-xl p-6"
        data-testid="requirements-coverage"
      >
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h2 className="text-lg font-semibold text-foreground">
              {t('workforce.engineers.requirements.title')}
            </h2>
            <p className="text-sm text-muted-foreground mt-1">
              {t('workforce.engineers.requirements.subtitle')}
            </p>
          </div>
          {requirementsError ? (
            <p className="text-sm text-destructive" data-testid="requirements-match-error" role="alert">
              {t('workforce.engineers.requirements.load_error')}: {requirementsError}
            </p>
          ) : match.percent === null ? (
            <p className="text-sm text-muted-foreground" data-testid="requirements-match-empty">
              {t('workforce.engineers.requirements.empty')}
            </p>
          ) : (
            <div className="text-right" data-testid="requirements-match-percent">
              <p className="text-3xl font-bold text-foreground">{match.percent}%</p>
              <p className="text-sm text-muted-foreground">
                {t('workforce.engineers.requirements.match_detail', {
                  met: match.mandatoryMet,
                  total: match.mandatoryTotal,
                })}
              </p>
            </div>
          )}
        </div>
        {!requirementsError && match.mandatoryTotal > 0 && (
          <ul className="mt-4 divide-y divide-border" data-testid="requirements-list">
            {requirements
              .filter((req) => req.is_mandatory)
              .map((req) => {
                const met = competencies.some(
                  (c) => c.asset_type_id === req.asset_type_id && c.state === 'active',
                )
                return (
                  <li key={req.id} className="py-3 flex items-center justify-between gap-3 text-sm">
                    <div>
                      <p className="font-medium text-foreground">{req.name}</p>
                      <p className="text-muted-foreground">{assetTypeLabel(req.asset_type_id)}</p>
                    </div>
                    <span
                      className={`px-2 py-0.5 rounded-full text-xs font-medium ${met ? 'bg-success/10 text-success' : 'bg-destructive/10 text-destructive'}`}
                    >
                      {met
                        ? t('workforce.engineers.requirements.met')
                        : t('workforce.engineers.requirements.gap')}
                    </span>
                  </li>
                )
              })}
          </ul>
        )}
      </div>

      {/* Training tickets */}
      <div
        className="bg-card border border-border rounded-xl overflow-hidden"
        data-testid="training-tickets"
      >
        <div className="px-6 py-4 border-b border-border flex items-center justify-between gap-3 flex-wrap">
          <div>
            <h2 className="text-lg font-semibold text-foreground">
              {t('workforce.engineers.tickets.title')}
            </h2>
            <p className="text-sm text-muted-foreground mt-1">
              {t('workforce.engineers.tickets.subtitle')}
            </p>
          </div>
          <Button type="button" size="sm" onClick={openCreateTicket} data-testid="ticket-create">
            <Plus className="w-4 h-4" />
            {t('workforce.engineers.tickets.add')}
          </Button>
        </div>
        {ticketsError ? (
          <div className="px-6 py-8 text-destructive text-sm" role="alert" data-testid="tickets-error">
            {t('workforce.engineers.tickets.load_error')}: {ticketsError}
          </div>
        ) : ticketsLoading ? (
          <div className="px-6 py-12 flex justify-center">
            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary" />
          </div>
        ) : tickets.length === 0 ? (
          <div
            className="px-6 py-12 text-center text-muted-foreground"
            data-testid="tickets-empty"
          >
            {t('workforce.engineers.tickets.empty')}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm" data-testid="tickets-table">
              <thead>
                <tr className="border-b border-border bg-muted/30">
                  <th className="px-4 py-3 text-left font-medium text-muted-foreground">
                    {t('workforce.engineers.tickets.scheme')}
                  </th>
                  <th className="px-4 py-3 text-left font-medium text-muted-foreground">
                    {t('workforce.engineers.tickets.number')}
                  </th>
                  <th className="px-4 py-3 text-left font-medium text-muted-foreground">
                    {t('workforce.engineers.tickets.expiry')}
                  </th>
                  <th className="px-4 py-3 text-left font-medium text-muted-foreground">
                    {t('workforce.engineers.tickets.verify_state')}
                  </th>
                  <th className="px-4 py-3 text-left font-medium text-muted-foreground">
                    {t('workforce.engineers.tickets.evidence')}
                  </th>
                  <th className="px-4 py-3 text-right font-medium text-muted-foreground">
                    {t('workforce.engineers.tickets.actions')}
                  </th>
                </tr>
              </thead>
              <tbody>
                {tickets.map((ticket) => (
                  <tr
                    key={ticket.id}
                    className="border-b border-border hover:bg-muted/20 transition-colors"
                    data-testid={`ticket-row-${ticket.id}`}
                  >
                    <td className="px-4 py-3 text-foreground">{ticket.scheme}</td>
                    <td className="px-4 py-3 font-mono text-foreground">{ticket.ticket_number}</td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {ticket.expires_at
                        ? new Date(ticket.expires_at).toLocaleDateString()
                        : '—'}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`px-2 py-0.5 rounded-full text-xs font-medium ${verifyColors[ticket.verify_state] || verifyColors.unverified}`}
                      >
                        {String(ticket.verify_state).replace(/_/g, ' ')}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {ticket.evidence_id != null
                        ? t('workforce.engineers.tickets.evidence_id', {
                            id: ticket.evidence_id,
                          })
                        : '—'}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon-sm"
                        onClick={() => openEditTicket(ticket)}
                        aria-label={t('workforce.engineers.tickets.edit')}
                        data-testid={`ticket-edit-${ticket.id}`}
                      >
                        <Pencil className="w-3.5 h-3.5" />
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Competency Records Table */}
      <div className="bg-card border border-border rounded-xl overflow-hidden">
        <div className="px-6 py-4 border-b border-border">
          <h2 className="text-lg font-semibold text-foreground">
            {t('workforce.engineers.competency_records')}
          </h2>
        </div>
        {competencies.length === 0 ? (
          <div className="px-6 py-12 text-center text-muted-foreground">
            {t('workforce.engineers.competency_records_empty')}
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
                      {assetTypeLabel(rec.asset_type_id)}
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

      <Dialog open={ticketDialogOpen} onOpenChange={setTicketDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {editingTicket
                ? t('workforce.engineers.tickets.edit_title')
                : t('workforce.engineers.tickets.create_title')}
            </DialogTitle>
          </DialogHeader>
          <div className="grid gap-3 py-2">
            {ticketFormError && (
              <p className="text-sm text-destructive" role="alert">
                {ticketFormError}
              </p>
            )}
            <div className="grid gap-1.5">
              <Label htmlFor="ticket-scheme" required>
                {t('workforce.engineers.tickets.scheme')}
              </Label>
              <Input
                id="ticket-scheme"
                value={ticketForm.scheme}
                onChange={(e) => setTicketForm((f) => ({ ...f, scheme: e.target.value }))}
                data-testid="ticket-form-scheme"
              />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="ticket-number" required>
                {t('workforce.engineers.tickets.number')}
              </Label>
              <Input
                id="ticket-number"
                value={ticketForm.ticket_number}
                onChange={(e) => setTicketForm((f) => ({ ...f, ticket_number: e.target.value }))}
                data-testid="ticket-form-number"
              />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="ticket-issuer">{t('workforce.engineers.tickets.issuer')}</Label>
              <Input
                id="ticket-issuer"
                value={ticketForm.issuer}
                onChange={(e) => setTicketForm((f) => ({ ...f, issuer: e.target.value }))}
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="grid gap-1.5">
                <Label htmlFor="ticket-issued">{t('workforce.engineers.tickets.issued')}</Label>
                <Input
                  id="ticket-issued"
                  type="date"
                  value={ticketForm.issued_at}
                  onChange={(e) => setTicketForm((f) => ({ ...f, issued_at: e.target.value }))}
                />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="ticket-expires">{t('workforce.engineers.tickets.expiry')}</Label>
                <Input
                  id="ticket-expires"
                  type="date"
                  value={ticketForm.expires_at}
                  onChange={(e) => setTicketForm((f) => ({ ...f, expires_at: e.target.value }))}
                />
              </div>
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="ticket-verify">{t('workforce.engineers.tickets.verify_state')}</Label>
              <select
                id="ticket-verify"
                className="flex h-9 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
                value={ticketForm.verify_state}
                onChange={(e) =>
                  setTicketForm((f) => ({ ...f, verify_state: e.target.value }))
                }
                data-testid="ticket-form-verify"
              >
                {VERIFY_STATES.map((s) => (
                  <option key={s} value={s}>
                    {s.replace(/_/g, ' ')}
                  </option>
                ))}
              </select>
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="ticket-evidence">{t('workforce.engineers.tickets.evidence')}</Label>
              <Input
                id="ticket-evidence"
                type="number"
                value={ticketForm.evidence_id}
                onChange={(e) => setTicketForm((f) => ({ ...f, evidence_id: e.target.value }))}
                placeholder={t('workforce.engineers.tickets.evidence_placeholder')}
                data-testid="ticket-form-evidence"
              />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="ticket-notes">{t('workforce.engineers.tickets.notes')}</Label>
              <Input
                id="ticket-notes"
                value={ticketForm.notes}
                onChange={(e) => setTicketForm((f) => ({ ...f, notes: e.target.value }))}
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setTicketDialogOpen(false)}
              disabled={ticketSaving}
            >
              {t('common.cancel')}
            </Button>
            <Button
              type="button"
              onClick={() => void saveTicket()}
              disabled={ticketSaving}
              data-testid="ticket-form-save"
            >
              {ticketSaving
                ? t('workforce.engineers.tickets.saving')
                : t('workforce.engineers.tickets.save')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
