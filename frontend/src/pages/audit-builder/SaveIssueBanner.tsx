import { AlertTriangle } from 'lucide-react'
import type { SaveIssue } from './saveErrorModel'

export interface SaveIssueBannerProps {
  summary: string
  issues: SaveIssue[]
  onShowQuestion?: (questionId: string) => void
}

export default function SaveIssueBanner({ summary, issues, onShowQuestion }: SaveIssueBannerProps) {
  if (!issues.length && !summary) return null

  return (
    <div
      role="alert"
      aria-live="assertive"
      data-testid="save-issue-banner"
      className="rounded-2xl border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive"
    >
      <div className="flex items-start gap-3">
        <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" aria-hidden="true" />
        <div className="min-w-0 flex-1 space-y-3">
          <p className="font-semibold text-destructive" data-testid="save-issue-summary">
            {summary}
          </p>
          {issues.length > 0 && (
            <ol className="list-decimal space-y-3 pl-5 text-destructive/95">
              {issues.map((issue, index) => (
                <li key={issue.id} data-testid={`save-issue-${index}`}>
                  <div className="space-y-1">
                    <p className="font-medium text-foreground">
                      {issue.label}
                      {issue.context ? (
                        <span className="font-normal text-muted-foreground"> — {issue.context}</span>
                      ) : null}
                    </p>
                    <p data-testid={`save-issue-action-${index}`}>{issue.action}</p>
                    {issue.questionId && onShowQuestion ? (
                      <button
                        type="button"
                        className="mt-1 text-xs font-medium text-primary underline-offset-2 hover:underline"
                        data-testid={`save-issue-show-${index}`}
                        onClick={() => onShowQuestion(issue.questionId!)}
                      >
                        Show question
                      </button>
                    ) : null}
                  </div>
                </li>
              ))}
            </ol>
          )}
        </div>
      </div>
    </div>
  )
}
