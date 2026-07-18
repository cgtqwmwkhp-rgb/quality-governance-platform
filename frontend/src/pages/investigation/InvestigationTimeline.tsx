import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  Filter,
  RefreshCw,
  Loader2,
  History,
  MessageSquare,
  ListTodo,
  FileQuestion,
  Package,
  PenLine,
} from 'lucide-react'
import type {
  Action,
  CustomerPackSummary,
  EvidenceAsset,
  InvestigationComment,
  TimelineEvent,
} from '../../api/client'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Badge } from '../../components/ui/Badge'
import { Textarea } from '../../components/ui/Textarea'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../../components/ui/Select'
import { buildActivitySpine, filterActivitySpine, type ActivityKind } from './activitySpine'

/** Backend event_type values + spine kinds for GET .../timeline?event_type= / local filter. */
export const TIMELINE_FILTER_OPTIONS = [
  { value: 'all', labelKey: 'investigations.timeline.filter_all' },
  { value: 'CREATED', labelKey: 'investigations.timeline.filter_created' },
  { value: 'STATUS_CHANGED', labelKey: 'investigations.timeline.filter_status' },
  { value: 'DATA_UPDATED', labelKey: 'investigations.timeline.filter_data' },
  { value: 'COMMENT_ADDED', labelKey: 'investigations.timeline.filter_comment' },
  { value: 'CAPA', labelKey: 'investigations.timeline.filter_capa' },
  { value: 'EVIDENCE', labelKey: 'investigations.timeline.filter_evidence' },
  { value: 'PACK_GENERATED', labelKey: 'investigations.timeline.filter_pack' },
  { value: 'MANUAL_ENTRY', labelKey: 'investigations.timeline.filter_manual' },
  { value: 'APPROVED', labelKey: 'investigations.timeline.filter_approved' },
  { value: 'REJECTED', labelKey: 'investigations.timeline.filter_rejected' },
] as const

const KIND_ICON: Record<ActivityKind, typeof History> = {
  revision: History,
  comment: MessageSquare,
  capa: ListTodo,
  evidence: FileQuestion,
  pack: Package,
  manual: PenLine,
}

interface InvestigationTimelineProps {
  timeline: TimelineEvent[]
  comments: InvestigationComment[]
  actions: Action[]
  evidence: EvidenceAsset[]
  packs: CustomerPackSummary[]
  timelineLoading: boolean
  timelineFilter: string
  onTimelineFilterChange: (value: string) => void
  onRefresh: () => void
  onAddManualEntry: (content: string) => Promise<void>
  onJumpTab?: (tab: 'timeline' | 'evidence' | 'actions' | 'report' | 'rca' | 'summary') => void
  addingManual?: boolean
}

export default function InvestigationTimeline({
  timeline,
  comments,
  actions,
  evidence,
  packs,
  timelineLoading,
  timelineFilter,
  onTimelineFilterChange,
  onRefresh,
  onAddManualEntry,
  onJumpTab,
  addingManual = false,
}: InvestigationTimelineProps) {
  const { t } = useTranslation()
  const [manualText, setManualText] = useState('')

  const spine = useMemo(
    () =>
      filterActivitySpine(
        buildActivitySpine({ timeline, comments, actions, evidence, packs }),
        timelineFilter,
      ),
    [timeline, comments, actions, evidence, packs, timelineFilter],
  )

  const submitManual = async () => {
    if (!manualText.trim()) return
    await onAddManualEntry(manualText.trim())
    setManualText('')
  }

  return (
    <div className="space-y-4" data-testid="investigation-timeline-panel">
      <p className="text-sm text-muted-foreground" data-testid="investigation-timeline-hint">
        {t(
          'investigations.timeline.activity_spine_hint',
          'Unified activity spine — comments, CAPA, evidence, packs, and manual entries alongside the audit trail.',
        )}
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
                  {t(opt.labelKey, opt.value.replace(/_/g, ' '))}
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

      <Card className="p-4" data-testid="investigation-timeline-manual">
        <label htmlFor="inv-manual-timeline" className="block text-sm font-medium text-foreground mb-2">
          {t('investigations.timeline.add_manual', 'Add to timeline')}
        </label>
        <Textarea
          id="inv-manual-timeline"
          rows={2}
          value={manualText}
          onChange={(e) => setManualText(e.target.value)}
          placeholder={t(
            'investigations.timeline.manual_placeholder',
            'Site visit, customer call, decision note…',
          )}
          data-testid="investigation-timeline-manual-input"
        />
        <div className="mt-2 flex justify-end">
          <Button
            size="sm"
            onClick={() => void submitManual()}
            disabled={addingManual || !manualText.trim()}
            data-testid="investigation-timeline-manual-submit"
          >
            {addingManual ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <PenLine className="w-4 h-4 mr-2" />
            )}
            {t('investigations.timeline.add_manual', 'Add to timeline')}
          </Button>
        </div>
      </Card>

      {timelineLoading ? (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
        </div>
      ) : spine.length === 0 ? (
        <Card className="p-12 text-center">
          <History className="w-12 h-12 mx-auto mb-4 text-muted-foreground/50" />
          <h3 className="text-lg font-semibold text-foreground mb-2">
            {t('investigations.timeline.empty_title')}
          </h3>
          <p className="text-muted-foreground">{t('investigations.timeline.empty_body')}</p>
        </Card>
      ) : (
        <div className="space-y-4" data-testid="investigation-activity-spine">
          {spine.map((item) => {
            const Icon = KIND_ICON[item.kind] || History
            return (
              <Card
                key={item.id}
                className="p-4"
                data-testid={`timeline-activity-${item.id}`}
              >
                <div className="flex items-start gap-4">
                  <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0">
                    <Icon className="w-5 h-5 text-primary" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1 flex-wrap">
                      <span className="font-medium text-foreground">{item.title}</span>
                      <Badge variant="outline" className="text-xs capitalize">
                        {item.kind}
                      </Badge>
                      {item.actorId != null ? (
                        <span className="text-xs text-muted-foreground">
                          {t('investigations.timeline.actor', { id: item.actorId })}
                        </span>
                      ) : null}
                    </div>
                    {item.body ? (
                      <p className="text-sm text-muted-foreground line-clamp-3">{item.body}</p>
                    ) : null}
                    <div className="mt-2 flex items-center gap-3 flex-wrap">
                      <p className="text-xs text-muted-foreground">
                        {item.createdAt ? new Date(item.createdAt).toLocaleString() : '—'}
                      </p>
                      {item.hrefTab && onJumpTab ? (
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-7 px-2 text-xs"
                          onClick={() => onJumpTab(item.hrefTab!)}
                          data-testid={`timeline-jump-${item.kind}-${item.id}`}
                        >
                          {t('investigations.timeline.open_related', 'Open related')}
                        </Button>
                      ) : null}
                    </div>
                  </div>
                </div>
              </Card>
            )
          })}
        </div>
      )}
    </div>
  )
}
