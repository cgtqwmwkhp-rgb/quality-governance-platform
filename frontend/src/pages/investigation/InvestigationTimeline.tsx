import { Filter, RefreshCw, Loader2, History } from "lucide-react";
import type { TimelineEvent } from "../../api/client";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Badge } from "../../components/ui/Badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../../components/ui/Select";

interface InvestigationTimelineProps {
  timeline: TimelineEvent[];
  timelineLoading: boolean;
  timelineFilter: string;
  onTimelineFilterChange: (value: string) => void;
  onRefresh: () => void;
}

export default function InvestigationTimeline({
  timeline,
  timelineLoading,
  timelineFilter,
  onTimelineFilterChange,
  onRefresh,
}: InvestigationTimelineProps) {
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-muted-foreground" />
          <Select value={timelineFilter} onValueChange={onTimelineFilterChange}>
            <SelectTrigger className="w-48">
              <SelectValue placeholder="Filter by type" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Events</SelectItem>
              <SelectItem value="status_change">Status Changes</SelectItem>
              <SelectItem value="field_update">Field Updates</SelectItem>
              <SelectItem value="comment">Comments</SelectItem>
              <SelectItem value="action">Actions</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <Button variant="outline" size="sm" onClick={onRefresh}>
          <RefreshCw className="w-4 h-4 mr-2" />
          Refresh
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
            No Timeline Events
          </h3>
          <p className="text-muted-foreground">
            Events will appear here as the investigation progresses.
          </p>
        </Card>
      ) : (
        <div className="space-y-4">
          {timeline.map((event) => (
            <Card key={event.id} className="p-4">
              <div className="flex items-start gap-4">
                <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0">
                  <History className="w-5 h-5 text-primary" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-medium text-foreground">
                      {event.event_type.replace(/_/g, " ")}
                    </span>
                    <Badge variant="outline" className="text-xs">
                      {event.field_path || "System"}
                    </Badge>
                  </div>
                  {event.old_value && event.new_value && (
                    <p className="text-sm text-muted-foreground">
                      Changed from &quot;{event.old_value}&quot; to &quot;
                      {event.new_value}&quot;
                    </p>
                  )}
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
  );
}
