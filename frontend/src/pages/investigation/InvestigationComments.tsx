import { useTranslation } from 'react-i18next'
import { Loader2, Send } from 'lucide-react'
import type { InvestigationComment } from '../../api/client'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Textarea } from '../../components/ui/Textarea'

interface InvestigationCommentsProps {
  comments: InvestigationComment[]
  commentsLoading: boolean
  newComment: string
  onNewCommentChange: (value: string) => void
  addingComment: boolean
  onAddComment: () => void
}

export default function InvestigationComments({
  comments,
  commentsLoading,
  newComment,
  onNewCommentChange,
  addingComment,
  onAddComment,
}: InvestigationCommentsProps) {
  const { t } = useTranslation()

  return (
    <>
      {/* Recent Notes Preview */}
      <Card className="p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-foreground">
            {t('investigations.recent_notes')}
          </h3>
          <span className="text-sm text-muted-foreground">{comments.length} total</span>
        </div>
        {commentsLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
          </div>
        ) : comments.length === 0 ? (
          <p className="text-muted-foreground text-center py-4">No notes yet.</p>
        ) : (
          <div className="space-y-3">
            {comments.slice(0, 3).map((comment) => (
              <div key={comment.id} className="p-3 bg-surface rounded-lg">
                <p className="text-sm text-foreground whitespace-pre-wrap">{comment.content}</p>
                <div className="flex items-center justify-between mt-2 text-xs text-muted-foreground">
                  <span>User #{comment.author_id}</span>
                  <span>{new Date(comment.created_at).toLocaleString()}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Add Comment Form */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold text-foreground mb-4">
          {t('investigations.add_note')}
        </h3>
        <div className="flex gap-4">
          <Textarea
            value={newComment}
            onChange={(e) => onNewCommentChange(e.target.value)}
            placeholder="Add a note to this investigation..."
            rows={2}
            className="flex-1"
          />
          <Button onClick={onAddComment} disabled={addingComment || !newComment.trim()}>
            {addingComment ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Send className="w-4 h-4" />
            )}
          </Button>
        </div>
      </Card>
    </>
  )
}
