import { useState } from 'react';
import {
  Calendar,
  ChevronLeft,
  ChevronRight,
  Plus,
  Clock,
  MapPin,
  Users,
  AlertTriangle,
  CheckCircle2,
  Filter,
  List,
  Grid3X3,
  Bell,
  FileText
} from 'lucide-react';

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
  const [currentDate, setCurrentDate] = useState(new Date(2024, 0, 19)); // Jan 19, 2024
  const [viewMode, setViewMode] = useState<'month' | 'week' | 'list'>('month');
  const [selectedDate, setSelectedDate] = useState<Date | null>(null);
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

  const eventTypeColors: Record<string, { bg: string; text: string; border: string }> = {
    audit: { bg: 'bg-purple-500/20', text: 'text-purple-400', border: 'border-purple-500' },
    review: { bg: 'bg-blue-500/20', text: 'text-blue-400', border: 'border-blue-500' },
    deadline: { bg: 'bg-red-500/20', text: 'text-red-400', border: 'border-red-500' },
    meeting: { bg: 'bg-emerald-500/20', text: 'text-emerald-400', border: 'border-emerald-500' },
    training: { bg: 'bg-amber-500/20', text: 'text-amber-400', border: 'border-amber-500' }
  };

  const statusColors: Record<string, { bg: string; text: string }> = {
    upcoming: { bg: 'bg-blue-500/20', text: 'text-blue-400' },
    today: { bg: 'bg-violet-500/20', text: 'text-violet-400' },
    overdue: { bg: 'bg-red-500/20', text: 'text-red-400' },
    completed: { bg: 'bg-emerald-500/20', text: 'text-emerald-400' }
  };

  const getDaysInMonth = (date: Date) => {
    const year = date.getFullYear();
    const month = date.getMonth();
    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);
    const daysInMonth = lastDay.getDate();
    const startingDay = firstDay.getDay();
    
    const days: (number | null)[] = [];
    
    // Add empty days for the start of the month
    for (let i = 0; i < startingDay; i++) {
      days.push(null);
    }
    
    // Add all days in the month
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
    const today = new Date(2024, 0, 19); // Jan 19, 2024
    return day === today.getDate() && 
           currentDate.getMonth() === today.getMonth() && 
           currentDate.getFullYear() === today.getFullYear();
  };

  const upcomingEvents = events
    .filter(e => e.status !== 'completed')
    .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
    .slice(0, 5);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-white flex items-center gap-3">
            <div className="p-2 bg-gradient-to-br from-rose-500 to-pink-600 rounded-xl">
              <Calendar className="w-8 h-8" />
            </div>
            Calendar
          </h1>
          <p className="text-slate-400 mt-1">Audits, reviews, deadlines and events</p>
        </div>
        
        <div className="flex items-center gap-3">
          {/* View Mode Toggle */}
          <div className="flex bg-slate-800/50 rounded-lg p-1">
            <button
              onClick={() => setViewMode('month')}
              className={`p-2 rounded-md transition-all ${
                viewMode === 'month' ? 'bg-violet-600 text-white' : 'text-slate-400 hover:text-white'
              }`}
              title="Month View"
            >
              <Grid3X3 className="w-5 h-5" />
            </button>
            <button
              onClick={() => setViewMode('list')}
              className={`p-2 rounded-md transition-all ${
                viewMode === 'list' ? 'bg-violet-600 text-white' : 'text-slate-400 hover:text-white'
              }`}
              title="List View"
            >
              <List className="w-5 h-5" />
            </button>
          </div>
          
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={`p-2 rounded-lg transition-all ${
              showFilters ? 'bg-violet-500 text-white' : 'bg-slate-800/50 text-slate-400 hover:text-white'
            }`}
          >
            <Filter className="w-5 h-5" />
          </button>
          
          <button className="px-4 py-2 bg-gradient-to-r from-violet-600 to-purple-600 text-white font-medium rounded-xl hover:from-violet-500 hover:to-purple-500 transition-all flex items-center gap-2">
            <Plus className="w-5 h-5" />
            Add Event
          </button>
        </div>
      </div>

      {/* Filters */}
      {showFilters && (
        <div className="bg-slate-800/50 backdrop-blur-sm rounded-xl border border-slate-700/50 p-4">
          <div className="flex flex-wrap gap-2">
            {Object.entries(eventTypeColors).map(([type, colors]) => (
              <button
                key={type}
                onClick={() => {
                  setSelectedTypes(prev => 
                    prev.includes(type) ? prev.filter(t => t !== type) : [...prev, type]
                  );
                }}
                className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
                  selectedTypes.includes(type) || selectedTypes.length === 0
                    ? `${colors.bg} ${colors.text} border ${colors.border}`
                    : 'bg-slate-700/50 text-slate-400'
                }`}
              >
                {type.charAt(0).toUpperCase() + type.slice(1)}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Calendar Grid */}
        <div className="lg:col-span-3 bg-slate-800/50 backdrop-blur-sm rounded-xl border border-slate-700/50 p-6">
          {/* Month Navigation */}
          <div className="flex items-center justify-between mb-6">
            <button
              onClick={() => navigateMonth('prev')}
              className="p-2 text-slate-400 hover:text-white hover:bg-slate-700/50 rounded-lg transition-all"
            >
              <ChevronLeft className="w-5 h-5" />
            </button>
            
            <h2 className="text-xl font-semibold text-white">
              {monthNames[currentDate.getMonth()]} {currentDate.getFullYear()}
            </h2>
            
            <button
              onClick={() => navigateMonth('next')}
              className="p-2 text-slate-400 hover:text-white hover:bg-slate-700/50 rounded-lg transition-all"
            >
              <ChevronRight className="w-5 h-5" />
            </button>
          </div>

          {viewMode === 'month' && (
            <>
              {/* Day Names */}
              <div className="grid grid-cols-7 gap-1 mb-2">
                {dayNames.map((day) => (
                  <div key={day} className="text-center text-sm font-medium text-slate-500 py-2">
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
                      className={`min-h-[100px] p-2 rounded-lg transition-all ${
                        day ? 'bg-slate-900/30 hover:bg-slate-700/30 cursor-pointer' : ''
                      } ${today ? 'ring-2 ring-violet-500' : ''}`}
                      onClick={() => day && setSelectedDate(new Date(currentDate.getFullYear(), currentDate.getMonth(), day))}
                    >
                      {day && (
                        <>
                          <span className={`text-sm font-medium ${today ? 'text-violet-400' : 'text-slate-400'}`}>
                            {day}
                          </span>
                          <div className="mt-1 space-y-1">
                            {dayEvents.slice(0, 3).map((event) => (
                              <div
                                key={event.id}
                                className={`text-xs px-1.5 py-0.5 rounded truncate ${eventTypeColors[event.type].bg} ${eventTypeColors[event.type].text}`}
                              >
                                {event.title}
                              </div>
                            ))}
                            {dayEvents.length > 3 && (
                              <div className="text-xs text-slate-500 pl-1">
                                +{dayEvents.length - 3} more
                              </div>
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
                <div
                  key={event.id}
                  className={`p-4 rounded-xl border-l-4 ${eventTypeColors[event.type].border} bg-slate-900/30 hover:bg-slate-700/30 transition-all cursor-pointer`}
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1">
                      <div className="flex items-center gap-3 mb-2">
                        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${eventTypeColors[event.type].bg} ${eventTypeColors[event.type].text}`}>
                          {event.type}
                        </span>
                        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${statusColors[event.status].bg} ${statusColors[event.status].text}`}>
                          {event.status}
                        </span>
                        {event.priority === 'high' && (
                          <AlertTriangle className="w-4 h-4 text-amber-400" />
                        )}
                      </div>
                      
                      <h3 className="font-semibold text-white mb-1">{event.title}</h3>
                      
                      <div className="flex flex-wrap items-center gap-4 text-sm text-slate-400">
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
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Sidebar - Upcoming Events */}
        <div className="bg-slate-800/50 backdrop-blur-sm rounded-xl border border-slate-700/50 p-6">
          <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <Bell className="w-5 h-5 text-violet-400" />
            Upcoming
          </h3>
          
          <div className="space-y-4">
            {upcomingEvents.map((event) => (
              <div
                key={event.id}
                className="p-3 bg-slate-900/30 rounded-lg hover:bg-slate-700/30 transition-all cursor-pointer"
              >
                <div className="flex items-start gap-3">
                  <div className={`w-2 h-2 rounded-full mt-2 ${
                    event.status === 'overdue' ? 'bg-red-500' :
                    event.status === 'today' ? 'bg-violet-500 animate-pulse' :
                    'bg-blue-500'
                  }`} />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-white truncate">{event.title}</p>
                    <div className="flex items-center gap-2 mt-1 text-xs text-slate-500">
                      <Calendar className="w-3 h-3" />
                      <span>{event.date}</span>
                      {event.time && (
                        <>
                          <Clock className="w-3 h-3 ml-1" />
                          <span>{event.time}</span>
                        </>
                      )}
                    </div>
                    <span className={`inline-block mt-2 px-2 py-0.5 rounded text-xs ${eventTypeColors[event.type].bg} ${eventTypeColors[event.type].text}`}>
                      {event.type}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Legend */}
          <div className="mt-6 pt-4 border-t border-slate-700/50">
            <h4 className="text-sm font-medium text-slate-400 mb-3">Event Types</h4>
            <div className="space-y-2">
              {Object.entries(eventTypeColors).map(([type, colors]) => (
                <div key={type} className="flex items-center gap-2 text-sm">
                  <span className={`w-3 h-3 rounded-full ${colors.bg} ${colors.border} border`} />
                  <span className="text-slate-300 capitalize">{type}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
