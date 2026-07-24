import { useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Loader2, MessageSquare, Send, ShieldAlert, Sparkles, X } from 'lucide-react'
import { auditChallengeApi } from '../../api/client'
import type { AuditChallengeProposal, AuditChallengeSession } from '../../api/auditChallengeClient'
import ProposalDiffCard from './ProposalDiffCard'

interface CheckChallengeCoachProps {
  /** Section snapshot (wizard-generated or builder-local) — sent as-is to the coach. */
  sections: unknown[]
  brief?: Record<string, unknown>
  templateId?: number
  onClose: () => void
  /** Called with the merged section snapshot after "Apply accepted" — caller maps fields back. */
  onApplySections: (sections: Array<Record<string, unknown>>) => void
}

const FALLBACK_CHIPS = [
  { id: 'iso_closer', label: 'Closer ISO match', prompt: '' },
  { id: 'oem_manufacturer', label: 'Manufacturer / OEM standards', prompt: '' },
  { id: 'rebalance_scoring', label: 'Rebalance scoring', prompt: '' },
  { id: 'field_assessor', label: 'Field assessor lens', prompt: '' },
  { id: 'tighten_focus', label: 'Tighten focus', prompt: '' },
  { id: 'evidence_clarity', label: 'Evidence clarity', prompt: '' },
  { id: 'format_consistency', label: 'Format consistency', prompt: '' },
]

const ACTIVE_STATUSES = new Set(['queued', 'running'])

export default function CheckChallengeCoach({
  sections,
  brief,
  templateId,
  onClose,
  onApplySections,
}: CheckChallengeCoachProps) {
  const { t } = useTranslation()
  const [session, setSession] = useState<AuditChallengeSession | null>(null)
  const [starting, setStarting] = useState(false)
  const [applying, setApplying] = useState(false)
  const [decidingId, setDecidingId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [selectedChip, setSelectedChip] = useState<string | null>(null)
  const [message, setMessage] = useState('')
  const scrollRef = useRef<HTMLDivElement>(null)

  const chips = session?.chips?.length ? session.chips : FALLBACK_CHIPS

  const isActive = !!session && ACTIVE_STATUSES.has(session.status)
  const activeSessionId = isActive ? (session?.id ?? null) : null

  useEffect(() => {
    if (activeSessionId == null) return
    const timer = window.setInterval(() => {
      void auditChallengeApi
        .getSession(activeSessionId)
        .then((res) => setSession(res.data))
        .catch(() => undefined)
    }, 2000)
    return () => window.clearInterval(timer)
  }, [activeSessionId])

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [session?.turns?.length])

  const startSession = async (chipId?: string, freeText?: string) => {
    setError(null)
    setStarting(true)
    try {
      const res = await auditChallengeApi.createSession({
        sections,
        brief,
        chip_id: chipId,
        message: freeText,
        template_id: templateId,
      })
      setSession(res.data)
      setMessage('')
    } catch (err) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        t('auditChallenge.startFailed', { defaultValue: 'Could not start the Check & Challenge coach.' })
      setError(String(detail))
    } finally {
      setStarting(false)
    }
  }

  const sendFollowUp = async () => {
    if (!session || !message.trim()) return
    setError(null)
    setStarting(true)
    try {
      const res = await auditChallengeApi.sendMessage(session.id, message.trim(), selectedChip || undefined)
      setSession(res.data)
      setMessage('')
      setSelectedChip(null)
    } catch {
      setError(t('auditChallenge.messageFailed', { defaultValue: 'Could not send that follow-up.' }))
    } finally {
      setStarting(false)
    }
  }

  const decide = async (proposal: AuditChallengeProposal, decision: 'accept' | 'reject' | 'edit', editedAfter?: Record<string, unknown>) => {
    if (!session) return
    setDecidingId(proposal.id)
    setError(null)
    try {
      const res = await auditChallengeApi.decideProposal(session.id, proposal.id, decision, editedAfter)
      setSession((prev) =>
        prev
          ? {
              ...prev,
              proposals: prev.proposals.map((p) => (p.id === proposal.id ? res.data : p)),
            }
          : prev,
      )
    } catch {
      setError(t('auditChallenge.decideFailed', { defaultValue: 'Could not record that decision.' }))
    } finally {
      setDecidingId(null)
    }
  }

  const applyAccepted = async () => {
    if (!session) return
    setApplying(true)
    setError(null)
    try {
      const res = await auditChallengeApi.applySession(session.id)
      onApplySections((res.data.sections || []) as Array<Record<string, unknown>>)
    } catch {
      setError(t('auditChallenge.applyFailed', { defaultValue: 'Could not apply accepted changes.' }))
    } finally {
      setApplying(false)
    }
  }

  const pendingCount = useMemo(
    () => session?.proposals.filter((p) => p.decision === 'pending').length || 0,
    [session],
  )
  const acceptedCount = useMemo(
    () => session?.proposals.filter((p) => p.decision === 'accepted' || p.decision === 'edited').length || 0,
    [session],
  )

  const modelsUsed = session?.models_used as
    | { critic?: string | null; author?: string | null; research?: string | null }
    | null
    | undefined

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
      <div
        className="absolute inset-0 bg-black/70 backdrop-blur-sm"
        role="button"
        tabIndex={0}
        onClick={onClose}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') onClose()
        }}
      />

      <div
        className="relative w-full max-w-4xl max-h-[92vh] bg-card border border-border rounded-2xl shadow-2xl flex flex-col overflow-hidden"
        data-testid="check-challenge-coach"
      >
        <div className="flex items-center justify-between p-5 border-b border-border">
          <div className="flex items-center gap-3">
            <div className="w-11 h-11 bg-primary rounded-xl flex items-center justify-center">
              <ShieldAlert className="w-5 h-5 text-primary-foreground" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-foreground">
                {t('auditChallenge.title', { defaultValue: 'Check & Challenge coach' })}
              </h2>
              <p className="text-sm text-muted-foreground">
                {t('auditChallenge.subtitle', {
                  defaultValue: 'A field assessor red-teams this template and proposes cited fixes.',
                })}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-secondary text-muted-foreground hover:text-foreground transition-colors"
            aria-label={t('common.close', { defaultValue: 'Close' })}
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-5 space-y-4" ref={scrollRef}>
          {error && <div className="text-destructive text-sm">{error}</div>}

          {!session && (
            <div className="space-y-4">
              <p className="text-sm text-muted-foreground">
                {t('auditChallenge.intro', {
                  defaultValue:
                    'Pick a challenge lens or describe what you want red-teamed. The coach cites Assist Map standards and, when relevant, manufacturer research.',
                })}
              </p>
              <div className="flex flex-wrap gap-2">
                {chips.map((chip) => (
                  <button
                    key={chip.id}
                    type="button"
                    disabled={starting}
                    onClick={() => void startSession(chip.id)}
                    className="px-3 py-1.5 rounded-lg text-xs border border-border bg-secondary hover:border-primary/40 disabled:opacity-50"
                  >
                    {chip.label}
                  </button>
                ))}
              </div>
              <div className="flex gap-2">
                <input
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  placeholder={t('auditChallenge.freeformPlaceholder', {
                    defaultValue: 'Or describe a specific concern…',
                  })}
                  className="flex-1 px-3 py-2 rounded-xl bg-secondary border border-border text-sm"
                />
                <button
                  type="button"
                  disabled={starting || !message.trim()}
                  onClick={() => void startSession(undefined, message.trim())}
                  className="px-4 py-2 bg-primary text-primary-foreground rounded-lg inline-flex items-center gap-2 disabled:opacity-50"
                >
                  {starting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                  {t('auditChallenge.run', { defaultValue: 'Run' })}
                </button>
              </div>
            </div>
          )}

          {session && (
            <div className="space-y-4">
              <div className="flex items-center gap-3 text-sm">
                {isActive ? (
                  <span className="inline-flex items-center gap-2 text-muted-foreground">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    {session.progress_message ||
                      t('auditChallenge.working', { defaultValue: 'Working…' })}{' '}
                    ({session.progress_pct}%)
                  </span>
                ) : session.status === 'failed' ? (
                  <span className="text-destructive">
                    {t('auditChallenge.failed', { defaultValue: 'Run failed' })}: {session.error_detail}
                  </span>
                ) : (
                  <span className="text-success">
                    {t('auditChallenge.ready', { defaultValue: 'Ready for review' })}
                  </span>
                )}
                {modelsUsed && (
                  <span className="text-xs text-muted-foreground">
                    {t('auditChallenge.modelsUsed', {
                      defaultValue: 'critic {{critic}} · author {{author}} · research {{research}}',
                      critic: modelsUsed.critic || 'heuristic',
                      author: modelsUsed.author || 'deterministic',
                      research: modelsUsed.research || 'offline',
                    })}
                  </span>
                )}
              </div>

              <div className="space-y-2">
                {session.turns
                  .filter((turn) => turn.role !== 'user')
                  .map((turn) => (
                    <div key={turn.id} className="rounded-xl border border-border bg-secondary/40 p-3 text-sm">
                      <div className="flex items-center gap-2 mb-1">
                        <MessageSquare className="w-3.5 h-3.5 text-muted-foreground" />
                        <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                          {turn.role}
                        </span>
                      </div>
                      <p className="whitespace-pre-line text-foreground/90">{turn.content}</p>
                    </div>
                  ))}
              </div>

              {session.proposals.length > 0 && (
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-medium">
                      {t('auditChallenge.proposals', {
                        defaultValue: 'Proposed changes ({{count}})',
                        count: session.proposals.length,
                      })}
                    </h3>
                    <span className="text-xs text-muted-foreground">
                      {t('auditChallenge.proposalsSummary', {
                        defaultValue: '{{accepted}} accepted · {{pending}} pending',
                        accepted: acceptedCount,
                        pending: pendingCount,
                      })}
                    </span>
                  </div>
                  {session.proposals.map((proposal) => (
                    <ProposalDiffCard
                      key={proposal.id}
                      proposal={proposal}
                      busy={decidingId === proposal.id}
                      onDecide={(decision, editedAfter) => void decide(proposal, decision, editedAfter)}
                    />
                  ))}
                </div>
              )}

              {!isActive && (
                <div className="flex gap-2 pt-1">
                  <input
                    value={message}
                    onChange={(e) => setMessage(e.target.value)}
                    placeholder={t('auditChallenge.followUpPlaceholder', {
                      defaultValue: 'Ask a follow-up or request another pass…',
                    })}
                    className="flex-1 px-3 py-2 rounded-xl bg-secondary border border-border text-sm"
                  />
                  <button
                    type="button"
                    disabled={starting || !message.trim()}
                    onClick={() => void sendFollowUp()}
                    className="px-3 py-2 bg-secondary rounded-lg inline-flex items-center gap-2 disabled:opacity-50"
                    aria-label={t('auditChallenge.send', { defaultValue: 'Send' })}
                  >
                    {starting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                  </button>
                </div>
              )}
            </div>
          )}
        </div>

        <div className="border-t border-border p-4 flex items-center justify-between bg-card gap-3">
          <button
            type="button"
            onClick={onClose}
            className="px-3 py-2 rounded-lg bg-secondary text-foreground"
          >
            {t('common.close', { defaultValue: 'Close' })}
          </button>
          {session && (
            <button
              type="button"
              disabled={applying || acceptedCount === 0}
              onClick={() => void applyAccepted()}
              className="px-4 py-2 bg-primary text-primary-foreground rounded-lg inline-flex items-center gap-2 disabled:opacity-50"
              data-testid="challenge-apply-accepted"
            >
              {applying ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
              {t('auditChallenge.applyAccepted', {
                defaultValue: 'Apply {{count}} accepted change(s)',
                count: acceptedCount,
              })}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
