import { useState } from 'react';
import {
  Calendar,
  ChevronLeft,
  ChevronRight,
  Plus,
  Clock,
  MapPin,
  AlertTriangle,
  Filter,
  List,
  Grid3X3,
  Bell
} from 'lucide-react';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { cn } from '../lib/utils';

interface CalendarEvent {
  id: string;
  title: string;
  type: 'audit' | 'review' | 'deadline' | 'meeting' | 'training';
  date: string;
  time?: string;
  endTime?: string;
  location?: string;
  attendees?: string[];
  description?: string;
  status: 'upcoming' | 'today' | 'overdue' | 'completed';
  priority?: 'high' | 'medium' | 'low';
  relatedModule?: string;
  relatedId?: string;
}

export default function CalendarView() {
  const [currentDate, setCurrentDate] = useState(new Date(2024, 0, 19));
  const [viewMode, setViewMode] = useState<'month' | 'list'>('month');
  const [, setSelectedDate] = useState<Date | null>(null);
  const [showFilters, setShowFilters] = useState(false);
  const [selectedTypes, setSelectedTypes] = useState<string[]>([]);

  const events: CalendarEvent[] = [
    {
      id: 'EVT001',
      title: 'ISO 9001:2015 Internal Audit',
      type: 'audit',
      date: '2024-01-22',
      time: '09:00',
      endTime: '17:00',
      location: 'Main Office - Conference Room A',
      attendees: ['John Smith', 'Sarah Johnson', 'External Auditor'],
      description: 'Annual internal audit for quality management system',
      status: 'upcoming',
      priority: 'high',
      relatedModule: 'Audits',
      relatedId: 'AUD-2024-0156'
    },
    {
      id: 'EVT002',
      title: 'Risk Register Review',
      type: 'review',
      date: '2024-01-19',
      time: '14:00',
      endTime: '15:30',
      location: 'Virtual - Teams Meeting',
      attendees: ['Sarah Johnson', 'Mike Chen'],
      description: 'Quarterly review of risk register',
      status: 'today',
      priority: 'medium',
      relatedModule: 'Risks'
    },
    {
      id: 'EVT003',
      title: 'Action Item Deadline - Update Emergency Procedures',
      type: 'deadline',
      date: '2024-01-15',
      description: 'Deadline for completing emergency procedure updates',
      status: 'overdue',
      priority: 'high',
      relatedModule: 'Actions',
      relatedId: 'ACT-2024-0523'
    },
    {
      id: 'EVT004',
      title: 'Health & Safety Training',
      type: 'training',
      date: '2024-01-25',
      time: '10:00',
      endTime: '12:00',
      location: 'Training Room B',
      attendees: ['All Staff'],
      description: 'Mandatory annual health and safety training',
      status: 'upcoming',
      priority: 'medium'
    },
    {
      id: 'EVT005',
      title: 'Management Review Meeting',
      type: 'meeting',
      date: '2024-01-26',
      time: '09:00',
      endTime: '11:00',
      location: 'Board Room',
      attendees: ['Executive Team', 'Department Heads'],
      description: 'Monthly management review of IMS performance',
      status: 'upcoming',
      priority: 'high'
    },
    {
      id: 'EVT006',
      title: 'Complaint Resolution Deadline',
      type: 'deadline',
      date: '2024-01-20',
      description: 'SLA deadline for CMP-2024-0456',
      status: 'upcoming',
      priority: 'high',
      relatedModule: 'Complaints',
      relatedId: 'CMP-2024-0456'
    }
  ];

  const eventTypeStyles: Record<string, { variant: string }> = {
    audit: { variant: 'info' },
    review: { variant: 'info' },
    deadline: { variant: 'destructive' },
    meeting: { variant: 'success' },
    training: { variant: 'warning' }
  };

  const getDaysInMonth = (date: Date) => {
    const year = date.getFullYear();
    const month = date.getMonth();
    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);
    const daysInMonth = lastDay.getDate();
    const startingDay = firstDay.getDay();
    
    const days: (number | null)[] = [];
    for (let i = 0; i < startingDay; i++) {
      days.push(null);
    }
    for (let i = 1; i <= daysInMonth; i++) {
      days.push(i);
    }
    return days;
  };

  const getEventsForDate = (day: number) => {
    const dateStr = `${currentDate.getFullYear()}-${String(currentDate.getMonth() + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
    return events.filter(e => e.date === dateStr);
  };

  const navigateMonth = (direction: 'prev' | 'next') => {
    setCurrentDate(prev => {
      const newDate = new Date(prev);
      if (direction === 'prev') {
        newDate.setMonth(newDate.getMonth() - 1);
      } else {
        newDate.setMonth(newDate.getMonth() + 1);
      }
      return newDate;
    });
  };

  const monthNames = ['January', 'February', 'March', 'April', 'May', 'June',
                      'July', 'August', 'September', 'October', 'November', 'December'];
  const dayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

  const isToday = (day: number) => {
    const today = new Date(2024, 0, 19);
    return day === today.getDate() && 
           currentDate.getMonth() === today.getMonth() && 
           currentDate.getFullYear() === today.getFullYear();
  };

  const upcomingEvents = events
    .filter(e => e.status !== 'completed')
    .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
    .slice(0, 5);

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-foreground flex items-center gap-3">
            <div className="p-2 bg-primary/10 rounded-xl">
              <Calendar className="w-8 h-8 text-primary" />
            </div>
            Calendar
          </h1>
          <p className="text-muted-foreground mt-1">Audits, reviews, deadlines and events</p>
        </div>
        
        <div className="flex items-center gap-3">
          <div className="flex bg-surface rounded-lg p-1 border border-border">
            <button
              onClick={() => setViewMode('month')}
              className={cn(
                "p-2 rounded-md transition-all",
                viewMode === 'month' ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground'
              )}
              title="Month View"
            >
              <Grid3X3 className="w-5 h-5" />
            </button>
            <button
              onClick={() => setViewMode('list')}
              className={cn(
                "p-2 rounded-md transition-all",
                viewMode === 'list' ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground'
              )}
              title="List View"
            >
              <List className="w-5 h-5" />
            </button>
          </div>
          
          <Button
            variant={showFilters ? 'default' : 'outline'}
            size="sm"
            onClick={() => setShowFilters(!showFilters)}
          >
            <Filter className="w-5 h-5" />
          </Button>
          
          <Button>
            <Plus className="w-5 h-5" />
            Add Event
          </Button>
        </div>
      </div>

      {/* Filters */}
      {showFilters && (
        <Card className="p-4">
          <div className="flex flex-wrap gap-2">
            {Object.entries(eventTypeStyles).map(([type]) => (
              <Button
                key={type}
                variant={selectedTypes.includes(type) || selectedTypes.length === 0 ? 'default' : 'outline'}
                size="sm"
                onClick={() => {
                  setSelectedTypes(prev => 
                    prev.includes(type) ? prev.filter(t => t !== type) : [...prev, type]
                  );
                }}
              >
                {type.charAt(0).toUpperCase() + type.slice(1)}
              </Button>
            ))}
          </div>
        </Card>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Calendar Grid */}
        <Card className="lg:col-span-3 p-6">
          {/* Month Navigation */}
          <div className="flex items-center justify-between mb-6">
            <Button variant="ghost" size="sm" onClick={() => navigateMonth('prev')}>
              <ChevronLeft className="w-5 h-5" />
            </Button>
            
            <h2 className="text-xl font-semibold text-foreground">
              {monthNames[currentDate.getMonth()]} {currentDate.getFullYear()}
            </h2>
            
            <Button variant="ghost" size="sm" onClick={() => navigateMonth('next')}>
              <ChevronRight className="w-5 h-5" />
            </Button>
          </div>

          {viewMode === 'month' && (
            <>
              {/* Day Names */}
              <div className="grid grid-cols-7 gap-1 mb-2">
                {dayNames.map((day) => (
                  <div key={day} className="text-center text-sm font-medium text-muted-foreground py-2">
                    {day}
                  </div>
                ))}
              </div>

              {/* Calendar Grid */}
              <div className="grid grid-cols-7 gap-1">
                {getDaysInMonth(currentDate).map((day, index) => {
                  const dayEvents = day ? getEventsForDate(day) : [];
                  const today = isToday(day || 0);
                  
                  return (
                    <div
                      key={index}
                      className={cn(
                        "min-h-[100px] p-2 rounded-lg transition-all",
                        day && "bg-surface hover:bg-surface-hover cursor-pointer",
                        today && "ring-2 ring-primary"
                      )}
                      onClick={() => day && setSelectedDate(new Date(currentDate.getFullYear(), currentDate.getMonth(), day))}
                    >
                      {day && (
                        <>
                          <span className={cn(
                            "text-sm font-medium",
                            today ? 'text-primary' : 'text-muted-foreground'
                          )}>
                            {day}
                          </span>
                          <div className="mt-1 space-y-1">
                            {dayEvents.slice(0, 3).map((event) => (
                              <Badge
                                key={event.id}
                                variant={eventTypeStyles[event.type].variant as any}
                                className="text-[10px] truncate w-full justify-start"
                              >
                                {event.title}
                              </Badge>
                            ))}
                            {dayEvents.length > 3 && (
                              <span className="text-xs text-muted-foreground pl-1">
                                +{dayEvents.length - 3} more
                              </span>
                            )}
                          </div>
                        </>
                      )}
                    </div>
                  );
                })}
              </div>
            </>
          )}

          {viewMode === 'list' && (
            <div className="space-y-4">
              {events.map((event) => (
                <Card
                  key={event.id}
                  hoverable
                  className={cn(
                    "p-4 border-l-4",
                    event.type === 'audit' && "border-l-info",
                    event.type === 'review' && "border-l-info",
                    event.type === 'deadline' && "border-l-destructive",
                    event.type === 'meeting' && "border-l-success",
                    event.type === 'training' && "border-l-warning",
                  )}
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1">
                      <div className="flex items-center gap-3 mb-2 flex-wrap">
                        <Badge variant={eventTypeStyles[event.type].variant as any}>
                          {event.type}
                        </Badge>
                        <Badge variant={
                          event.status === 'overdue' ? 'destructive' :
                          event.status === 'today' ? 'info' : 'secondary'
                        }>
                          {event.status}
                        </Badge>
                        {event.priority === 'high' && (
                          <AlertTriangle className="w-4 h-4 text-warning" />
                        )}
                      </div>
                      
                      <h3 className="font-semibold text-foreground mb-1">{event.title}</h3>
                      
                      <div className="flex flex-wrap items-center gap-4 text-sm text-muted-foreground">
                        <span className="flex items-center gap-1">
                          <Calendar className="w-4 h-4" />
                          {event.date}
                        </span>
                        {event.time && (
                          <span className="flex items-center gap-1">
                            <Clock className="w-4 h-4" />
                            {event.time} - {event.endTime}
                          </span>
                        )}
                        {event.location && (
                          <span className="flex items-center gap-1">
                            <MapPin className="w-4 h-4" />
                            {event.location}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </Card>

        {/* Sidebar - Upcoming Events */}
        <Card className="p-6">
          <h3 className="text-lg font-semibold text-foreground mb-4 flex items-center gap-2">
            <Bell className="w-5 h-5 text-primary" />
            Upcoming
          </h3>
          
          <div className="space-y-4">
            {upcomingEvents.map((event) => (
              <div
                key={event.id}
                className="p-3 bg-surface rounded-lg hover:bg-surface-hover transition-colors cursor-pointer"
              >
                <div className="flex items-start gap-3">
                  <div className={cn(
                    "w-2 h-2 rounded-full mt-2",
                    event.status === 'overdue' && 'bg-destructive',
                    event.status === 'today' && 'bg-primary animate-pulse',
                    event.status === 'upcoming' && 'bg-info'
                  )} />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-foreground truncate">{event.title}</p>
                    <div className="flex items-center gap-2 mt-1 text-xs text-muted-foreground">
                      <Calendar className="w-3 h-3" />
                      <span>{event.date}</span>
                      {event.time && (
                        <>
                          <Clock className="w-3 h-3 ml-1" />
                          <span>{event.time}</span>
                        </>
                      )}
                    </div>
                    <Badge variant={eventTypeStyles[event.type].variant as any} className="mt-2 text-[10px]">
                      {event.type}
                    </Badge>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Legend */}
          <div className="mt-6 pt-4 border-t border-border">
            <h4 className="text-sm font-medium text-muted-foreground mb-3">Event Types</h4>
            <div className="space-y-2">
              {Object.entries(eventTypeStyles).map(([type, styles]) => (
                <div key={type} className="flex items-center gap-2 text-sm">
                  <Badge variant={styles.variant as any} className="w-3 h-3 p-0 rounded-full" />
                  <span className="text-foreground capitalize">{type}</span>
                </div>
              ))}
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}
