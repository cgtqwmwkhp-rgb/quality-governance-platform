import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Check, X, Pencil, ExternalLink } from 'lucide-react'
import type { AuditChallengeProposal } from '../../api/auditChallengeClient'

const DIMENSION_LABELS: Record<string, string> = {
  scoring: 'Scoring',
  focus: 'Focus',
  format: 'Format',
  evidence: 'Evidence',
  iso: 'ISO',
  oem: 'OEM',
  field_usability: 'Field usability',
  duplication: 'Duplication',
}

interface ProposalDiffCardProps {
  proposal: AuditChallengeProposal
  busy?: boolean
  onDecide: (decision: 'accept' | 'reject' | 'edit', editedAfter?: Record<string, unknown>) => void
}

function fieldValue(obj: Record<string, unknown> | null | undefined, key: string): string {
  const v = obj?.[key]
  if (v === null || v === undefined) return ''
  return String(v)
}

export default function ProposalDiffCard({ proposal, busy, onDecide }: ProposalDiffCardProps) {
  const { t } = useTranslation()
  const [editing, setEditing] = useState(false)
  const [editedText, setEditedText] = useState(fieldValue(proposal.after, 'text'))
  const [editedGuidance, setEditedGuidance] = useState(fieldValue(proposal.after, 'guidance'))

  const decided = proposal.decision !== 'pending'
  const beforeText = fieldValue(proposal.before, 'text')
  const afterText = fieldValue(proposal.after, 'text')
  const beforeGuidance = fieldValue(proposal.before, 'guidance')
  const afterGuidance = fieldValue(proposal.after, 'guidance')

  const saveEdit = () => {
    onDecide('edit', {
      ...(proposal.after || {}),
      text: editedText,
      guidance: editedGuidance,
    })
    setEditing(false)
  }

  return (
    <div
      className={`rounded-xl border p-3 space-y-2 text-sm ${
        proposal.decision === 'accepted' || proposal.decision === 'edited'
          ? 'border-success/50 bg-success/5'
          : proposal.decision === 'rejected'
            ? 'border-border bg-secondary/40 opacity-60'
            : 'border-border bg-card'
      }`}
      data-testid="challenge-proposal-card"
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 flex-wrap">
          {proposal.dimension && (
            <span className="px-2 py-0.5 rounded-full text-xs bg-primary/10 text-primary">
              {DIMENSION_LABELS[proposal.dimension] || proposal.dimension}
            </span>
          )}
          {proposal.decision !== 'pending' && (
            <span className="px-2 py-0.5 rounded-full text-xs bg-secondary text-muted-foreground capitalize">
              {proposal.decision}
            </span>
          )}
        </div>
      </div>

      {proposal.assessor_failure_mode && (
        <p className="text-xs text-muted-foreground">{proposal.assessor_failure_mode}</p>
      )}

      {editing ? (
        <div className="space-y-2">
          <label className="block text-xs">
            <span className="text-muted-foreground">
              {t('auditChallenge.questionText', { defaultValue: 'Question text' })}
            </span>
            <textarea
              value={editedText}
              onChange={(e) => setEditedText(e.target.value)}
              rows={2}
              className="mt-1 w-full px-2 py-1.5 rounded-lg bg-secondary border border-border text-sm resize-none"
            />
          </label>
          <label className="block text-xs">
            <span className="text-muted-foreground">
              {t('auditChallenge.guidance', { defaultValue: 'Assessor guidance' })}
            </span>
            <textarea
              value={editedGuidance}
              onChange={(e) => setEditedGuidance(e.target.value)}
              rows={2}
              className="mt-1 w-full px-2 py-1.5 rounded-lg bg-secondary border border-border text-sm resize-none"
            />
          </label>
        </div>
      ) : (
        <div className="grid gap-1.5 sm:grid-cols-2">
          <div className="rounded-lg bg-destructive/5 border border-destructive/20 p-2">
            <p className="text-[10px] uppercase tracking-wide text-muted-foreground mb-1">
              {t('auditChallenge.before', { defaultValue: 'Before' })}
            </p>
            <p className="text-xs">{beforeText || t('auditChallenge.noText', { defaultValue: '(no text)' })}</p>
            {beforeGuidance && <p className="text-[11px] text-muted-foreground mt-1">{beforeGuidance}</p>}
          </div>
          <div className="rounded-lg bg-success/5 border border-success/20 p-2">
            <p className="text-[10px] uppercase tracking-wide text-muted-foreground mb-1">
              {t('auditChallenge.after', { defaultValue: 'Proposed' })}
            </p>
            <p className="text-xs">{afterText || beforeText}</p>
            {afterGuidance && <p className="text-[11px] text-muted-foreground mt-1">{afterGuidance}</p>}
          </div>
        </div>
      )}

      {proposal.rationale && <p className="text-xs italic text-muted-foreground">{proposal.rationale}</p>}

      {proposal.citations.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {proposal.citations.map((c) => (
            <a
              key={`${c.scheme}-${c.refId}`}
              href={c.url || undefined}
              target={c.url ? '_blank' : undefined}
              rel={c.url ? 'noreferrer' : undefined}
              className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] border border-border ${
                c.url ? 'text-primary hover:underline' : 'text-muted-foreground'
              }`}
            >
              {c.url && <ExternalLink className="w-3 h-3" />}
              {c.scheme}: {c.label}
            </a>
          ))}
        </div>
      )}

      {!decided && (
        <div className="flex gap-2 pt-1">
          {editing ? (
            <>
              <button
                type="button"
                disabled={busy}
                onClick={saveEdit}
                className="px-3 py-1.5 rounded-lg bg-primary text-primary-foreground text-xs inline-flex items-center gap-1 disabled:opacity-50"
              >
                <Check className="w-3.5 h-3.5" />
                {t('auditChallenge.saveAccept', { defaultValue: 'Save & accept' })}
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => setEditing(false)}
                className="px-3 py-1.5 rounded-lg bg-secondary text-xs"
              >
                {t('common.cancel', { defaultValue: 'Cancel' })}
              </button>
            </>
          ) : (
            <>
              <button
                type="button"
                disabled={busy}
                onClick={() => onDecide('accept')}
                className="px-3 py-1.5 rounded-lg bg-success/15 text-success text-xs inline-flex items-center gap-1 disabled:opacity-50"
                data-testid="challenge-proposal-accept"
              >
                <Check className="w-3.5 h-3.5" />
                {t('auditChallenge.accept', { defaultValue: 'Accept' })}
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => setEditing(true)}
                className="px-3 py-1.5 rounded-lg bg-secondary text-xs inline-flex items-center gap-1 disabled:opacity-50"
              >
                <Pencil className="w-3.5 h-3.5" />
                {t('auditChallenge.edit', { defaultValue: 'Edit' })}
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => onDecide('reject')}
                className="px-3 py-1.5 rounded-lg bg-destructive/10 text-destructive text-xs inline-flex items-center gap-1 disabled:opacity-50"
                data-testid="challenge-proposal-reject"
              >
                <X className="w-3.5 h-3.5" />
                {t('auditChallenge.reject', { defaultValue: 'Reject' })}
              </button>
            </>
          )}
        </div>
      )}
    </div>
  )
}
