import { useTranslation } from 'react-i18next'
import { Filter, RefreshCw, Loader2, History } from 'lucide-react'
import type { TimelineEvent } from '../../api/client'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Badge } from '../../components/ui/Badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../../components/ui/Select'

/** Backend event_type values (exact match for GET .../timeline?event_type=). */
export const TIMELINE_FILTER_OPTIONS = [
  { value: 'all', labelKey: 'investigations.timeline.filter_all' },
  { value: 'CREATED', labelKey: 'investigations.timeline.filter_created' },
  { value: 'STATUS_CHANGED', labelKey: 'investigations.timeline.filter_status' },
  { value: 'DATA_UPDATED', labelKey: 'investigations.timeline.filter_data' },
  { value: 'COMMENT_ADDED', labelKey: 'investigations.timeline.filter_comment' },
  { value: 'PACK_GENERATED', labelKey: 'investigations.timeline.filter_pack' },
  { value: 'APPROVED', labelKey: 'investigations.timeline.filter_approved' },
  { value: 'REJECTED', labelKey: 'investigations.timeline.filter_rejected' },
] as const

interface InvestigationTimelineProps {
  timeline: TimelineEvent[]
  timelineLoading: boolean
  timelineFilter: string
  onTimelineFilterChange: (value: string) => void
  onRefresh: () => void
}

export default function InvestigationTimeline({
  timeline,
  timelineLoading,
  timelineFilter,
  onTimelineFilterChange,
  onRefresh,
}: InvestigationTimelineProps) {
  const { t } = useTranslation()

  return (
    <div className="space-y-4" data-testid="investigation-timeline-panel">
      <p className="text-sm text-muted-foreground" data-testid="investigation-timeline-hint">
        {t('investigations.timeline.audit_hint')}
      </p>
      <div className="flex items-center gap-4 flex-wrap">
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-muted-foreground" />
          <Select value={timelineFilter} onValueChange={onTimelineFilterChange}>
            <SelectTrigger className="w-56" data-testid="investigation-timeline-filter">
              <SelectValue placeholder={t('investigations.timeline.filter_all')} />
            </SelectTrigger>
            <SelectContent>
              {TIMELINE_FILTER_OPTIONS.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  {t(opt.labelKey)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={onRefresh}
          data-testid="investigation-timeline-refresh"
        >
          <RefreshCw className="w-4 h-4 mr-2" />
          {t('investigations.timeline.refresh')}
        </Button>
      </div>

      {timelineLoading ? (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
        </div>
      ) : timeline.length === 0 ? (
        <Card className="p-12 text-center">
          <History className="w-12 h-12 mx-auto mb-4 text-muted-foreground/50" />
          <h3 className="text-lg font-semibold text-foreground mb-2">
            {t('investigations.timeline.empty_title')}
          </h3>
          <p className="text-muted-foreground">{t('investigations.timeline.empty_body')}</p>
        </Card>
      ) : (
        <div className="space-y-4">
          {timeline.map((event) => (
            <Card key={event.id} className="p-4" data-testid={`timeline-event-${event.id}`}>
              <div className="flex items-start gap-4">
                <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0">
                  <History className="w-5 h-5 text-primary" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1 flex-wrap">
                    <span className="font-medium text-foreground">
                      {event.event_type.replace(/_/g, ' ')}
                    </span>
                    <Badge variant="outline" className="text-xs">
                      {event.field_path || t('investigations.timeline.system')}
                    </Badge>
                    {event.actor_id != null ? (
                      <span className="text-xs text-muted-foreground">
                        {t('investigations.timeline.actor', { id: event.actor_id })}
                      </span>
                    ) : null}
                  </div>
                  {event.old_value && event.new_value && (
                    <p className="text-sm text-muted-foreground">
                      Changed from &quot;{event.old_value}&quot; to &quot;
                      {event.new_value}&quot;
                    </p>
                  )}
                  {!event.old_value && event.new_value ? (
                    <p className="text-sm text-muted-foreground line-clamp-2">{event.new_value}</p>
                  ) : null}
                  <p className="text-xs text-muted-foreground mt-1">
                    {new Date(event.created_at).toLocaleString()}
                  </p>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
