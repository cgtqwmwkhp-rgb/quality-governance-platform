/**
 * "Needs my decision" — the decisions outstanding for the signed-in user.
 *
 * Read-only on purpose. Every row links to the screen that owns the record, where
 * the decision is actually recorded, because a decision taken here would be a
 * decision recorded away from the register that has to evidence it.
 *
 * The three states that look alike and are not:
 *
 * - **items** — these are yours, soonest deadline first.
 * - **empty and every source answered** — you are clear. Safe to say so.
 * - **empty and a source could not be read** — we do not know whether you are
 *   clear, and the panel says exactly that. The surface this replaces reported an
 *   empty queue to every user forever, which is why the distinction is rendered
 *   rather than collapsed.
 *
 * A failed request is shown with a retry, not swallowed: silence on this panel
 * reads as "nothing to do".
 */
import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { AlertCircle, CheckCircle2, ChevronRight, Clock, Loader2 } from 'lucide-react'

import { approvalsApi } from '../api/client'
import {
  decisionsAreComplete,
  describeUnavailableDecisionSources,
  unattributedDecisionCount,
  unavailableSourceReasons,
  type MyDecisionsResponse,
  type PendingDecision,
} from '../api/approvalsClient'
import { Button } from './ui/Button'

/** What the date on a row is a record of, in the words the record supports. */
const BASIS_LABELS: Record<string, string> = {
  submitted: 'submitted',
  raised: 'raised',
  last_updated: 'last updated',
}

function formatDate(value: string | null | undefined): string | null {
  if (!value) return null
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return null
  return date.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
}

function isOverdue(dueAt: string | null | undefined): boolean {
  if (!dueAt) return false
  const due = new Date(dueAt)
  return !Number.isNaN(due.getTime()) && due.getTime() < Date.now()
}

function DecisionRow({ item }: { item: PendingDecision }) {
  const { t } = useTranslation()
  const due = formatDate(item.due_at)
  const requested = formatDate(item.requested_at)
  const basis = item.requested_at_basis ? BASIS_LABELS[item.requested_at_basis] : null
  const overdue = isOverdue(item.due_at)

  const body = (
    <>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-baseline gap-x-2">
          <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {item.decision}
          </span>
          <span className="truncate font-medium text-foreground">{item.title}</span>
          {item.reference ? (
            <span className="text-xs text-muted-foreground">{item.reference}</span>
          ) : null}
        </div>
        <div className="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
          <span>{item.source_label}</span>
          {due ? (
            <span
              className={overdue ? 'font-semibold text-destructive' : undefined}
              data-testid={`decision-due-${item.key}`}
            >
              <Clock className="mr-1 inline h-3 w-3" aria-hidden="true" />
              {overdue
                ? t('approvals.my_decisions.overdue', 'Overdue — was due {{date}}', { date: due })
                : t('approvals.my_decisions.due', 'Due {{date}}', { date: due })}
            </span>
          ) : (
            <span>{t('approvals.my_decisions.no_deadline', 'No deadline')}</span>
          )}
          {/*
            The date is labelled with what it records. `last_updated` means the
            domain never timestamped the moment this landed on the user, and
            captioning it "requested" would invent a fact about the record.
          */}
          {requested && basis ? (
            <span data-testid={`decision-basis-${item.key}`}>{`${basis} ${requested}`}</span>
          ) : null}
        </div>
      </div>
      {item.deep_link ? (
        <ChevronRight className="mt-1 h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
      ) : null}
    </>
  )

  if (!item.deep_link) {
    return (
      <li
        className="flex items-start gap-3 border-t border-border px-4 py-3 first:border-t-0"
        data-testid={`decision-${item.key}`}
      >
        {body}
        {/*
          No route to send them to. `/signatures` renders a hardcoded empty list
          and never calls the signatures API, so a link there would tell someone
          holding real work that they have none. Saying so is the honest option.
        */}
        <span
          className="shrink-0 self-center text-xs text-muted-foreground"
          data-testid={`decision-no-screen-${item.key}`}
        >
          {t('approvals.my_decisions.no_screen', 'No screen for this yet')}
        </span>
      </li>
    )
  }

  return (
    <li className="border-t border-border first:border-t-0" data-testid={`decision-${item.key}`}>
      <Link
        to={item.deep_link}
        className="flex items-start gap-3 px-4 py-3 hover:bg-muted/50 focus-visible:bg-muted/50 focus-visible:outline-none"
      >
        {body}
      </Link>
    </li>
  )
}

export function NeedsMyDecisionPanel() {
  const { t } = useTranslation()
  const [data, setData] = useState<MyDecisionsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [failed, setFailed] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setFailed(false)
    try {
      const response = await approvalsApi.myDecisions()
      setData(response.data)
    } catch {
      // The body is not surfaced: this endpoint's failures are transport or
      // authorisation, and neither has anything a user can act on beyond retrying.
      setData(null)
      setFailed(true)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  if (loading && !data) {
    return (
      <div
        className="flex items-center gap-2 rounded-xl border border-border p-4 text-sm text-muted-foreground"
        role="status"
        data-testid="needs-my-decision-loading"
      >
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
        <span>{t('approvals.my_decisions.loading', 'Checking what needs your decision…')}</span>
      </div>
    )
  }

  if (failed || !data) {
    return (
      <div
        className="flex flex-col gap-3 rounded-xl border border-destructive/30 bg-destructive/5 p-4 sm:flex-row sm:items-center sm:justify-between"
        role="alert"
        data-testid="needs-my-decision-error"
      >
        <p className="text-sm text-foreground">
          {t(
            'approvals.my_decisions.failed',
            'Could not check what needs your decision. This is not a report that nothing does.',
          )}
        </p>
        <Button onClick={() => void load()} variant="outline" size="sm">
          {t('approvals.my_decisions.retry', 'Try again')}
        </Button>
      </div>
    )
  }

  const complete = decisionsAreComplete(data)
  const unreadable = describeUnavailableDecisionSources(data)
  const reasons = unavailableSourceReasons(data)
  const unattributed = unattributedDecisionCount(data)
  const truncated = (data.sources ?? []).some((source) => source.truncated)

  if (data.items.length === 0) {
    // Two different answers, and only one of them is "you are clear".
    if (!complete) {
      return (
        <div
          className="rounded-xl border border-amber-300 bg-amber-50 p-4 text-amber-950 dark:border-amber-700 dark:bg-amber-950/30 dark:text-amber-100"
          role="status"
          data-testid="needs-my-decision-unknown"
        >
          <div className="flex items-start gap-3">
            <AlertCircle className="mt-0.5 h-5 w-5 shrink-0" aria-hidden="true" />
            <div>
              <p className="font-semibold">
                {t(
                  'approvals.my_decisions.unknown_title',
                  'Cannot confirm whether anything needs your decision',
                )}
              </p>
              <p className="mt-1 text-sm">
                <strong className="font-semibold">{unreadable}</strong>{' '}
                {t(
                  'approvals.my_decisions.unknown_body',
                  'could not be read, so this is not a report that you are clear.',
                )}
              </p>
              {reasons.map((reason) => (
                <p key={reason} className="mt-1 text-xs opacity-90">
                  {reason}
                </p>
              ))}
            </div>
          </div>
        </div>
      )
    }

    return (
      <div
        className="flex items-center gap-2 rounded-xl border border-border p-4 text-sm text-muted-foreground"
        role="status"
        data-testid="needs-my-decision-clear"
      >
        <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" aria-hidden="true" />
        <span>
          {t('approvals.my_decisions.clear', 'Nothing needs your decision. Every source answered:')}{' '}
          {(data.sources ?? []).map((source) => source.label).join(', ')}
        </span>
      </div>
    )
  }

  return (
    <section
      className="overflow-hidden rounded-xl border border-border"
      aria-labelledby="needs-my-decision-heading"
      data-testid="needs-my-decision"
    >
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border bg-muted/40 px-4 py-3">
        <h2 id="needs-my-decision-heading" className="text-sm font-semibold text-foreground">
          {t('approvals.my_decisions.title', 'Needs my decision')}
        </h2>
        <span className="text-xs text-muted-foreground" data-testid="needs-my-decision-count">
          {/*
            "at least" whenever a source was unreadable or capped, because `total`
            counts the rows we got rather than the rows that exist.
          */}
          {complete && !truncated
            ? data.total
            : t('approvals.my_decisions.at_least', 'at least {{count}}', { count: data.total })}
        </span>
      </div>

      {!complete ? (
        <p
          className="flex items-start gap-2 border-b border-amber-300 bg-amber-50 px-4 py-2 text-xs text-amber-950 dark:border-amber-700 dark:bg-amber-950/30 dark:text-amber-100"
          role="status"
          data-testid="needs-my-decision-partial"
        >
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <span>
            <strong className="font-semibold">{unreadable}</strong>{' '}
            {t(
              'approvals.my_decisions.partial',
              'could not be read, so there may be more decisions than these.',
            )}
          </span>
        </p>
      ) : null}

      <ul>
        {data.items.map((item) => (
          <DecisionRow key={item.key} item={item} />
        ))}
      </ul>

      {unattributed > 0 ? (
        <p
          className="border-t border-border px-4 py-2 text-xs text-muted-foreground"
          data-testid="needs-my-decision-unattributed"
        >
          {t(
            'approvals.my_decisions.unattributed',
            '{{count}} pending approval(s) name nobody as approver, so they are in no one\u2019s queue and need a workflow fix.',
            { count: unattributed },
          )}
        </p>
      ) : null}
    </section>
  )
}

export default NeedsMyDecisionPanel
