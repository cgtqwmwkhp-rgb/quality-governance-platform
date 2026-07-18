import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { ChevronDown, Loader2, MessageSquare, Send } from 'lucide-react'
import {
  documentCampaignApi,
  getApiErrorMessage,
  type QuestionInboxThread,
} from '../../api/client'
import { toast } from '../../contexts/ToastContext'
import { Button } from '../../components/ui/Button'
import { Card, CardContent, CardHeader } from '../../components/ui/Card'
import { Textarea } from '../../components/ui/Textarea'
import { Badge } from '../../components/ui/Badge'
import { cn } from '../../helpers/utils'

export default function HsecQuestionInbox() {
  const { t } = useTranslation()
  const [threads, setThreads] = useState<QuestionInboxThread[]>([])
  const [loading, setLoading] = useState(true)
  const [expandedId, setExpandedId] = useState<number | null>(null)
  const [replyBodies, setReplyBodies] = useState<Record<number, string>>({})
  const [replyingId, setReplyingId] = useState<number | null>(null)
  const [resolvingId, setResolvingId] = useState<number | null>(null)

  const loadInbox = useCallback(async () => {
    setLoading(true)
    try {
      const response = await documentCampaignApi.listQuestionInbox()
      setThreads(response.data.items ?? [])
    } catch (err) {
      toast.error(getApiErrorMessage(err, t('admin.hsec_inbox.load_error')))
      setThreads([])
    } finally {
      setLoading(false)
    }
  }, [t])

  useEffect(() => {
    void loadInbox()
  }, [loadInbox])

  const handleReply = async (thread: QuestionInboxThread) => {
    const body = replyBodies[thread.thread_id]?.trim()
    if (!body) {
      toast.error(t('admin.hsec_inbox.reply_required'))
      return
    }
    setReplyingId(thread.thread_id)
    try {
      await documentCampaignApi.replyQuestion(thread.thread_id, { body })
      toast.success(t('admin.hsec_inbox.reply_sent'))
      setReplyBodies((prev) => ({ ...prev, [thread.thread_id]: '' }))
      await loadInbox()
    } catch (err) {
      toast.error(getApiErrorMessage(err, t('admin.hsec_inbox.reply_error')))
    } finally {
      setReplyingId(null)
    }
  }

  const handleResolve = async (threadId: number) => {
    setResolvingId(threadId)
    try {
      await documentCampaignApi.resolveQuestion(threadId)
      toast.success(t('admin.hsec_inbox.resolved'))
      if (expandedId === threadId) setExpandedId(null)
      await loadInbox()
    } catch (err) {
      toast.error(getApiErrorMessage(err, t('admin.hsec_inbox.resolve_error')))
    } finally {
      setResolvingId(null)
    }
  }

  const openThreads = threads.filter((thread) => thread.status !== 'resolved')

  return (
    <div className="space-y-6" data-testid="hsec-question-inbox-page">
      <div>
        <h1 className="text-2xl font-bold">{t('admin.hsec_inbox.title')}</h1>
        <p className="text-muted-foreground mt-1">{t('admin.hsec_inbox.subtitle')}</p>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <MessageSquare className="w-5 h-5 text-primary" />
            <h2 className="text-lg font-semibold">{t('admin.hsec_inbox.open_questions')}</h2>
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex justify-center py-8">
              <Loader2 className="w-6 h-6 animate-spin text-primary" />
            </div>
          ) : openThreads.length === 0 ? (
            <p className="text-sm text-muted-foreground">{t('admin.hsec_inbox.empty')}</p>
          ) : (
            <div className="space-y-3">
              {openThreads.map((thread) => {
                const expanded = expandedId === thread.thread_id
                return (
                  <div
                    key={thread.thread_id}
                    className="rounded-lg border border-border"
                    data-testid={`hsec-thread-${thread.thread_id}`}
                  >
                    <button
                      type="button"
                      className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left"
                      onClick={() =>
                        setExpandedId((prev) => (prev === thread.thread_id ? null : thread.thread_id))
                      }
                      aria-expanded={expanded}
                    >
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2 mb-1">
                          <Badge variant="secondary">{thread.status}</Badge>
                          <span className="text-xs text-muted-foreground">
                            {new Date(thread.created_at).toLocaleString()}
                          </span>
                        </div>
                        <p className="font-medium text-foreground truncate">
                          {thread.thread_title || thread.title || t('admin.hsec_inbox.untitled')}
                        </p>
                        <p className="text-sm text-muted-foreground truncate">{thread.document_title}</p>
                      </div>
                      <ChevronDown
                        className={cn(
                          'w-5 h-5 text-muted-foreground transition-transform',
                          expanded && 'rotate-180',
                        )}
                      />
                    </button>

                    {expanded ? (
                      <div className="border-t border-border px-4 py-4 space-y-4">
                        {thread.latest_message_preview || thread.latest_message?.body ? (
                          <div className="rounded-lg bg-muted/50 px-3 py-2 text-sm">
                            <p className="text-xs text-muted-foreground mb-1">
                              {t('admin.hsec_inbox.latest_message')}
                            </p>
                            <p className="whitespace-pre-wrap">
                              {thread.latest_message_preview || thread.latest_message?.body}
                            </p>
                          </div>
                        ) : (
                          <p className="text-sm text-muted-foreground">
                            {t('admin.hsec_inbox.no_messages')}
                          </p>
                        )}

                        <div className="space-y-2">
                          <label
                            className="text-sm font-medium"
                            htmlFor={`hsec-reply-${thread.thread_id}`}
                          >
                            {t('admin.hsec_inbox.reply_label')}
                          </label>
                          <Textarea
                            id={`hsec-reply-${thread.thread_id}`}
                            value={replyBodies[thread.thread_id] ?? ''}
                            onChange={(event) =>
                              setReplyBodies((prev) => ({
                                ...prev,
                                [thread.thread_id]: event.target.value,
                              }))
                            }
                            placeholder={t('admin.hsec_inbox.reply_placeholder')}
                          />
                        </div>

                        <div className="flex flex-wrap gap-2">
                          <Button
                            size="sm"
                            onClick={() => void handleReply(thread)}
                            disabled={replyingId === thread.thread_id}
                          >
                            {replyingId === thread.thread_id ? (
                              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                            ) : (
                              <Send className="w-4 h-4 mr-2" />
                            )}
                            {t('admin.hsec_inbox.send_reply')}
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => void handleResolve(thread.thread_id)}
                            disabled={resolvingId === thread.thread_id}
                          >
                            {resolvingId === thread.thread_id && (
                              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                            )}
                            {t('admin.hsec_inbox.resolve')}
                          </Button>
                        </div>
                      </div>
                    ) : null}
                  </div>
                )
              })}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
