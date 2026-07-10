import { Loader2 } from 'lucide-react'
import type { ExternalAuditImportJob } from '../../api/client'
import { Button } from '../ui/Button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/Card'

type ImportReviewProcessingPanelsProps = {
  job: ExternalAuditImportJob | null
  isProcessing: boolean
  isQueueing: boolean
  onRetryQueue: () => void
}

export function ImportReviewProcessingPanels({
  job,
  isProcessing,
  isQueueing,
  onRetryQueue,
}: ImportReviewProcessingPanelsProps) {
  return (
    <>
      {isProcessing ? (
        <Card className="border-primary/30 bg-primary/5" aria-busy="true" role="status">
          <CardContent className="flex items-center gap-4 p-6">
            <Loader2 size={24} className="animate-spin text-primary" />
            <div>
              <p className="font-medium text-foreground">Processing import&hellip;</p>
              <p className="text-sm text-muted-foreground">
                Extracting text, running dual AI analysis (Mistral + Gemini), and generating draft
                findings. This may take up to five minutes for large documents.
              </p>
            </div>
          </CardContent>
        </Card>
      ) : null}

      {job &&
      !isProcessing &&
      (job.status === 'pending' ||
        job.status === 'queued' ||
        job.error_code === 'QUEUE_DISPATCH_FAILED') ? (
        <Card className="border-warning/30 bg-warning/5">
          <CardHeader>
            <CardTitle className="text-base">Processing queue</CardTitle>
            <CardDescription>
              This intake exists, but OCR and analysis are not currently running.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-foreground">
              {job.error_code === 'QUEUE_DISPATCH_FAILED'
                ? job.error_detail || 'Background processing could not be started automatically.'
                : 'Retry queueing this import to continue OCR, schema mapping, and reviewer draft generation.'}
            </p>
            <Button onClick={onRetryQueue} disabled={isQueueing || isProcessing}>
              {isQueueing ? <Loader2 size={16} className="animate-spin" /> : null}
              Retry Queue
            </Button>
          </CardContent>
        </Card>
      ) : null}

      {job?.processing_warnings_json?.length ? (
        <Card className="border-warning/30 bg-warning/5">
          <CardHeader>
            <CardTitle className="text-base">Reviewer warnings</CardTitle>
            <CardDescription>
              {job.processing_warnings_json.length} item(s) should be checked before promotion.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {job.processing_warnings_json.map((warning, index) => {
              const text =
                typeof warning === 'string'
                  ? warning
                  : String((warning as Record<string, unknown>)?.text ?? warning)
              const isVisual = text.startsWith('Visual:')
              const isScore = text.toLowerCase().includes('score')
              const isOutcome =
                text.toLowerCase().includes('outcome') ||
                text.toLowerCase().includes('disagreement')
              return (
                <div
                  key={`warning-${index}`}
                  className={`flex items-start gap-2 rounded px-3 py-2 text-sm ${
                    isOutcome
                      ? 'bg-red-50 border-l-2 border-red-400 text-red-800'
                      : isScore
                        ? 'bg-amber-50 border-l-2 border-amber-400 text-amber-800'
                        : isVisual
                          ? 'bg-blue-50 border-l-2 border-blue-400 text-blue-800'
                          : 'text-foreground'
                  }`}
                >
                  <span className="mt-0.5 text-xs">
                    {isOutcome ? '!' : isScore ? '#' : isVisual ? '\u25CB' : '\u2022'}
                  </span>
                  <span>{text}</span>
                </div>
              )
            })}
          </CardContent>
        </Card>
      ) : null}

      {job?.status === 'failed' ? (
        <Card className="border-destructive/30 bg-destructive/5">
          <CardHeader>
            <CardTitle className="text-base">Import failed</CardTitle>
            <CardDescription>The import did not reach reviewer-ready status.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-destructive">
            <p>{job.error_code || 'IMPORT_FAILED'}</p>
            <p>{job.error_detail || 'Review logs and retry the import job.'}</p>
          </CardContent>
        </Card>
      ) : null}
    </>
  )
}
