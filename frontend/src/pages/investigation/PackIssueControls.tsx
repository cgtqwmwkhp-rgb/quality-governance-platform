/**
 * Issue and redaction-review controls on a generated pack (INV-C17).
 *
 * Presentational: owns the dialog drafts only. Parent calls the API and passes
 * the list back down so a failed request cannot leave an optimistic issued
 * stamp on screen.
 *
 * Copy is plain English rather than i18n keys: this component only ever loads
 * on the lazy InvestigationDetail chunk (INV-C10's 212 kB gzip ceiling).
 */

import { useState } from 'react'
import { Loader2 } from 'lucide-react'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Textarea } from '../../components/ui/Textarea'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/Dialog'
import type { CustomerPackSummary } from '../../api/investigationsClient'
import {
  externalIssueBlockers,
  issueBlockedSentence,
  packIssueSummary,
} from './packIssueCopy'

export interface PackIssueControlsProps {
  pack: CustomerPackSummary
  investigationStatus: string | undefined
  canIssue: boolean
  busy: boolean
  onReview: (cleared: boolean, note?: string) => Promise<void>
  onIssue: (recipient: string, recipientEmail?: string, note?: string) => Promise<void>
}

export default function PackIssueControls({
  pack,
  investigationStatus,
  canIssue,
  busy,
  onReview,
  onIssue,
}: PackIssueControlsProps) {
  const [reviewOpen, setReviewOpen] = useState(false)
  const [issueOpen, setIssueOpen] = useState(false)
  const [reviewNote, setReviewNote] = useState('')
  const [recipient, setRecipient] = useState('')
  const [recipientEmail, setRecipientEmail] = useState('')
  const [issueNote, setIssueNote] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const blockers = externalIssueBlockers(pack, investigationStatus)
  const blockedSentence = issueBlockedSentence(blockers)
  const issueDisabled = busy || submitting || !canIssue || blockers.length > 0

  async function submitReview(cleared: boolean) {
    setSubmitting(true)
    try {
      await onReview(cleared, reviewNote.trim() || undefined)
      setReviewOpen(false)
      setReviewNote('')
    } finally {
      setSubmitting(false)
    }
  }

  async function submitIssue() {
    const named = recipient.trim()
    if (!named) return
    setSubmitting(true)
    try {
      await onIssue(named, recipientEmail.trim() || undefined, issueNote.trim() || undefined)
      setIssueOpen(false)
      setRecipient('')
      setRecipientEmail('')
      setIssueNote('')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="mt-3 space-y-2 border-t border-border pt-3" data-testid={`pack-issue-controls-${pack.id}`}>
      <p className="text-sm text-foreground" data-testid={`pack-issue-summary-${pack.id}`}>
        {packIssueSummary(pack)}
      </p>
      {blockedSentence ? (
        <p className="text-sm text-muted-foreground" data-testid={`pack-issue-blockers-${pack.id}`}>
          {blockedSentence}
        </p>
      ) : null}
      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={busy || submitting}
          data-testid={`pack-review-${pack.id}`}
          onClick={() => setReviewOpen(true)}
        >
          Record redaction review
        </Button>
        <Button
          type="button"
          size="sm"
          disabled={issueDisabled}
          data-testid={`pack-issue-${pack.id}`}
          onClick={() => setIssueOpen(true)}
        >
          Issue this pack
        </Button>
      </div>

      <Dialog open={reviewOpen} onOpenChange={setReviewOpen}>
        <DialogContent data-testid={`pack-review-dialog-${pack.id}`}>
          <DialogHeader>
            <DialogTitle>Redaction review</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            The pack already states the identity fields it redacted. Narrative text is reproduced as
            written. Say whether this copy is safe to issue to a customer.
          </p>
          <label className="block text-sm font-medium text-foreground" htmlFor={`pack-review-note-${pack.id}`}>
            What you checked, or what still needs redacting
          </label>
          <Textarea
            id={`pack-review-note-${pack.id}`}
            value={reviewNote}
            onChange={(event) => setReviewNote(event.target.value)}
            rows={3}
            data-testid={`pack-review-note-${pack.id}`}
          />
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              disabled={submitting}
              data-testid={`pack-review-needs-changes-${pack.id}`}
              onClick={() => void submitReview(false)}
            >
              {submitting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
              Needs changes
            </Button>
            <Button
              type="button"
              disabled={submitting}
              data-testid={`pack-review-clear-${pack.id}`}
              onClick={() => void submitReview(true)}
            >
              {submitting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
              Clear for issue
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={issueOpen} onOpenChange={setIssueOpen}>
        <DialogContent data-testid={`pack-issue-dialog-${pack.id}`}>
          <DialogHeader>
            <DialogTitle>Issue this pack</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Issuing renders the PDF once, keeps those bytes, and records who received them. A later
            download of this pack returns that copy.
          </p>
          <label className="block text-sm font-medium text-foreground" htmlFor={`pack-issue-recipient-${pack.id}`}>
            Who is receiving it
          </label>
          <Input
            id={`pack-issue-recipient-${pack.id}`}
            value={recipient}
            onChange={(event) => setRecipient(event.target.value)}
            data-testid={`pack-issue-recipient-${pack.id}`}
          />
          <label
            className="block text-sm font-medium text-foreground"
            htmlFor={`pack-issue-email-${pack.id}`}
          >
            Address, if there was one
          </label>
          <Input
            id={`pack-issue-email-${pack.id}`}
            type="email"
            value={recipientEmail}
            onChange={(event) => setRecipientEmail(event.target.value)}
            data-testid={`pack-issue-email-${pack.id}`}
          />
          <label className="block text-sm font-medium text-foreground" htmlFor={`pack-issue-note-${pack.id}`}>
            Why it is being issued
          </label>
          <Textarea
            id={`pack-issue-note-${pack.id}`}
            value={issueNote}
            onChange={(event) => setIssueNote(event.target.value)}
            rows={2}
            data-testid={`pack-issue-note-${pack.id}`}
          />
          <DialogFooter>
            <Button
              type="button"
              disabled={submitting || !recipient.trim()}
              data-testid={`pack-issue-confirm-${pack.id}`}
              onClick={() => void submitIssue()}
            >
              {submitting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
              Issue
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
