import { useState } from 'react';
import {
  Bell,
  BellOff,
  Check,
  CheckCheck,
  Trash2,
  Settings,
  AlertTriangle,
  Info,
  CheckCircle2,
  Clock,
  X,
  Filter,
  ChevronDown,
  Mail,
  MessageSquare,
  Smartphone,
  Volume2,
  VolumeX
} from 'lucide-react';

interface Notification {
  id: string;
  type: 'alert' | 'info' | 'success' | 'warning' | 'reminder';
  title: string;
  message: string;
  timestamp: string;
  read: boolean;
  module?: string;
  actionUrl?: string;
  actionLabel?: string;
}

interface NotificationPreference {
  id: string;
  label: string;
  description: string;
  email: boolean;
  push: boolean;
  inApp: boolean;
}

export default function Notifications() {
  const [activeTab, setActiveTab] = useState<'notifications' | 'settings'>('notifications');
  const [filter, setFilter] = useState<'all' | 'unread' | 'alerts'>('all');
  const [notifications, setNotifications] = useState<Notification[]>([
    {
      id: 'NOT001',
      type: 'alert',
      title: 'High Priority Incident Reported',
      message: 'A new high-priority incident (INC-2024-0847) has been reported and requires immediate attention.',
      timestamp: '5 minutes ago',
      read: false,
      module: 'Incidents',
      actionUrl: '/incidents/INC-2024-0847',
      actionLabel: 'View Incident'
    },
    {
      id: 'NOT002',
      type: 'warning',
      title: 'Action Item Overdue',
      message: 'Action ACT-2024-0523 "Update Emergency Procedures" is now 4 days overdue.',
      timestamp: '1 hour ago',
      read: false,
      module: 'Actions',
      actionUrl: '/actions/ACT-2024-0523',
      actionLabel: 'View Action'
    },
    {
      id: 'NOT003',
      type: 'reminder',
      title: 'Upcoming Audit Reminder',
      message: 'ISO 9001:2015 Internal Audit is scheduled for January 22, 2024. Prepare documentation.',
      timestamp: '2 hours ago',
      read: false,
      module: 'Audits',
      actionUrl: '/audits/AUD-2024-0156',
      actionLabel: 'View Audit'
    },
    {
      id: 'NOT004',
      type: 'success',
      title: 'Risk Assessment Approved',
      message: 'Risk RSK-2024-0089 has been reviewed and approved by Sarah Johnson.',
      timestamp: '3 hours ago',
      read: true,
      module: 'Risks'
    },
    {
      id: 'NOT005',
      type: 'info',
      title: 'New Document Uploaded',
      message: 'A new document "Safety Protocol v2.1" has been uploaded to the Document Library.',
      timestamp: 'Yesterday',
      read: true,
      module: 'Documents'
    },
    {
      id: 'NOT006',
      type: 'info',
      title: 'Weekly Summary Available',
      message: 'Your weekly IMS summary report is now available for review.',
      timestamp: 'Yesterday',
      read: true,
      actionUrl: '/reports',
      actionLabel: 'View Report'
    }
  ]);

  const [preferences, setPreferences] = useState<NotificationPreference[]>([
    {
      id: 'PREF001',
      label: 'High Priority Alerts',
      description: 'Critical incidents, severe risks, and urgent actions',
      email: true,
      push: true,
      inApp: true
    },
    {
      id: 'PREF002',
      label: 'Action Reminders',
      description: 'Due dates and overdue action items',
      email: true,
      push: true,
      inApp: true
    },
    {
      id: 'PREF003',
      label: 'Audit Notifications',
      description: 'Upcoming audits, findings, and results',
      email: true,
      push: false,
      inApp: true
    },
    {
      id: 'PREF004',
      label: 'Document Updates',
      description: 'New documents, version changes, and reviews',
      email: false,
      push: false,
      inApp: true
    },
    {
      id: 'PREF005',
      label: 'Weekly Summaries',
      description: 'Weekly digest of IMS activities',
      email: true,
      push: false,
      inApp: false
    },
    {
      id: 'PREF006',
      label: 'Assignment Notifications',
      description: 'When tasks or items are assigned to you',
      email: true,
      push: true,
      inApp: true
    }
  ]);

  const typeIcons: Record<string, { icon: React.ReactNode; color: string; bg: string }> = {
    alert: { icon: <AlertTriangle className="w-5 h-5" />, color: 'text-red-400', bg: 'bg-red-500/20' },
    warning: { icon: <Clock className="w-5 h-5" />, color: 'text-amber-400', bg: 'bg-amber-500/20' },
    success: { icon: <CheckCircle2 className="w-5 h-5" />, color: 'text-emerald-400', bg: 'bg-emerald-500/20' },
    info: { icon: <Info className="w-5 h-5" />, color: 'text-blue-400', bg: 'bg-blue-500/20' },
    reminder: { icon: <Bell className="w-5 h-5" />, color: 'text-violet-400', bg: 'bg-violet-500/20' }
  };

  const unreadCount = notifications.filter(n => !n.read).length;

  const filteredNotifications = notifications.filter(n => {
    if (filter === 'unread') return !n.read;
    if (filter === 'alerts') return n.type === 'alert' || n.type === 'warning';
    return true;
  });

  const markAsRead = (id: string) => {
    setNotifications(prev => 
      prev.map(n => n.id === id ? { ...n, read: true } : n)
    );
  };

  const markAllAsRead = () => {
    setNotifications(prev => prev.map(n => ({ ...n, read: true })));
  };

  const deleteNotification = (id: string) => {
    setNotifications(prev => prev.filter(n => n.id !== id));
  };

  const clearAll = () => {
    setNotifications([]);
  };

  const togglePreference = (id: string, channel: 'email' | 'push' | 'inApp') => {
    setPreferences(prev => 
      prev.map(p => p.id === id ? { ...p, [channel]: !p[channel] } : p)
    );
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-white flex items-center gap-3">
            <div className="p-2 bg-gradient-to-br from-amber-500 to-orange-600 rounded-xl relative">
              <Bell className="w-8 h-8" />
              {unreadCount > 0 && (
                <span className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 text-white text-xs font-bold rounded-full flex items-center justify-center">
                  {unreadCount}
                </span>
              )}
            </div>
            Notifications
          </h1>
          <p className="text-slate-400 mt-1">Stay updated with important alerts and reminders</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-slate-700/50">
        <button
          onClick={() => setActiveTab('notifications')}
          className={`px-6 py-3 font-medium transition-all border-b-2 ${
            activeTab === 'notifications'
              ? 'text-violet-400 border-violet-400'
              : 'text-slate-400 border-transparent hover:text-white'
          }`}
        >
          <span className="flex items-center gap-2">
            <Bell className="w-5 h-5" />
            Notifications
            {unreadCount > 0 && (
              <span className="px-2 py-0.5 bg-red-500/20 text-red-400 rounded-full text-sm">
                {unreadCount}
              </span>
            )}
          </span>
        </button>
        <button
          onClick={() => setActiveTab('settings')}
          className={`px-6 py-3 font-medium transition-all border-b-2 ${
            activeTab === 'settings'
              ? 'text-violet-400 border-violet-400'
              : 'text-slate-400 border-transparent hover:text-white'
          }`}
        >
          <span className="flex items-center gap-2">
            <Settings className="w-5 h-5" />
            Preferences
          </span>
        </button>
      </div>

      {/* Notifications Tab */}
      {activeTab === 'notifications' && (
        <>
          {/* Actions Bar */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              <button
                onClick={() => setFilter('all')}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                  filter === 'all'
                    ? 'bg-violet-600 text-white'
                    : 'bg-slate-800/50 text-slate-400 hover:text-white'
                }`}
              >
                All
              </button>
              <button
                onClick={() => setFilter('unread')}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                  filter === 'unread'
                    ? 'bg-violet-600 text-white'
                    : 'bg-slate-800/50 text-slate-400 hover:text-white'
                }`}
              >
                Unread ({unreadCount})
              </button>
              <button
                onClick={() => setFilter('alerts')}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                  filter === 'alerts'
                    ? 'bg-violet-600 text-white'
                    : 'bg-slate-800/50 text-slate-400 hover:text-white'
                }`}
              >
                Alerts
              </button>
            </div>
            
            <div className="flex items-center gap-2">
              <button
                onClick={markAllAsRead}
                className="px-4 py-2 bg-slate-800/50 text-slate-400 hover:text-white rounded-lg text-sm font-medium transition-all flex items-center gap-2"
                disabled={unreadCount === 0}
              >
                <CheckCheck className="w-4 h-4" />
                Mark All Read
              </button>
              <button
                onClick={clearAll}
                className="px-4 py-2 bg-slate-800/50 text-slate-400 hover:text-red-400 rounded-lg text-sm font-medium transition-all flex items-center gap-2"
              >
                <Trash2 className="w-4 h-4" />
                Clear All
              </button>
            </div>
          </div>

          {/* Notifications List */}
          <div className="space-y-3">
            {filteredNotifications.map((notification) => (
              <div
                key={notification.id}
                className={`bg-slate-800/50 backdrop-blur-sm rounded-xl border transition-all ${
                  notification.read
                    ? 'border-slate-700/50'
                    : 'border-violet-500/50 bg-violet-500/5'
                }`}
              >
                <div className="p-4">
                  <div className="flex items-start gap-4">
                    <div className={`p-2.5 rounded-xl ${typeIcons[notification.type].bg}`}>
                      <div className={typeIcons[notification.type].color}>
                        {typeIcons[notification.type].icon}
                      </div>
                    </div>
                    
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <h3 className={`font-semibold ${notification.read ? 'text-slate-300' : 'text-white'}`}>
                            {notification.title}
                          </h3>
                          {notification.module && (
                            <span className="text-xs text-slate-500 mt-0.5 block">
                              {notification.module}
                            </span>
                          )}
                        </div>
                        
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-slate-500 whitespace-nowrap">
                            {notification.timestamp}
                          </span>
                          {!notification.read && (
                            <span className="w-2 h-2 bg-violet-500 rounded-full" />
                          )}
                        </div>
                      </div>
                      
                      <p className="text-slate-400 mt-2 text-sm">
                        {notification.message}
                      </p>
                      
                      <div className="flex items-center gap-3 mt-3">
                        {notification.actionUrl && (
                          <a
                            href={notification.actionUrl}
                            className="text-sm text-violet-400 hover:text-violet-300 font-medium transition-colors"
                          >
                            {notification.actionLabel} →
                          </a>
                        )}
                        
                        <div className="flex items-center gap-2 ml-auto">
                          {!notification.read && (
                            <button
                              onClick={() => markAsRead(notification.id)}
                              className="p-1.5 text-slate-500 hover:text-emerald-400 transition-colors"
                              title="Mark as read"
                            >
                              <Check className="w-4 h-4" />
                            </button>
                          )}
                          <button
                            onClick={() => deleteNotification(notification.id)}
                            className="p-1.5 text-slate-500 hover:text-red-400 transition-colors"
                            title="Delete"
                          >
                            <X className="w-4 h-4" />
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Empty State */}
          {filteredNotifications.length === 0 && (
            <div className="text-center py-12">
              <div className="w-20 h-20 bg-slate-800/50 rounded-full flex items-center justify-center mx-auto mb-4">
                <BellOff className="w-10 h-10 text-slate-600" />
              </div>
              <h3 className="text-xl font-semibold text-white mb-2">No notifications</h3>
              <p className="text-slate-400">
                {filter === 'unread' ? "You're all caught up!" : "Nothing to show here"}
              </p>
            </div>
          )}
        </>
      )}

      {/* Settings Tab */}
      {activeTab === 'settings' && (
        <div className="bg-slate-800/50 backdrop-blur-sm rounded-xl border border-slate-700/50 overflow-hidden">
          <div className="p-6 border-b border-slate-700/50">
            <h2 className="text-lg font-semibold text-white">Notification Preferences</h2>
            <p className="text-sm text-slate-400 mt-1">
              Choose how and when you want to be notified
            </p>
          </div>
          
          {/* Channel Headers */}
          <div className="grid grid-cols-[1fr,80px,80px,80px] gap-4 px-6 py-3 bg-slate-900/50 border-b border-slate-700/50">
            <div className="text-sm font-medium text-slate-400">Notification Type</div>
            <div className="text-sm font-medium text-slate-400 text-center flex items-center justify-center gap-1">
              <Mail className="w-4 h-4" />
              Email
            </div>
            <div className="text-sm font-medium text-slate-400 text-center flex items-center justify-center gap-1">
              <Smartphone className="w-4 h-4" />
              Push
            </div>
            <div className="text-sm font-medium text-slate-400 text-center flex items-center justify-center gap-1">
              <MessageSquare className="w-4 h-4" />
              In-App
            </div>
          </div>
          
          {/* Preference Rows */}
          {preferences.map((pref) => (
            <div
              key={pref.id}
              className="grid grid-cols-[1fr,80px,80px,80px] gap-4 px-6 py-4 border-b border-slate-700/30 hover:bg-slate-700/10 transition-colors"
            >
              <div>
                <p className="font-medium text-white">{pref.label}</p>
                <p className="text-sm text-slate-500 mt-0.5">{pref.description}</p>
              </div>
              
              <div className="flex items-center justify-center">
                <button
                  onClick={() => togglePreference(pref.id, 'email')}
                  className={`w-10 h-6 rounded-full transition-all ${
                    pref.email ? 'bg-violet-600' : 'bg-slate-700'
                  }`}
                >
                  <div className={`w-4 h-4 bg-white rounded-full transition-transform mx-1 ${
                    pref.email ? 'translate-x-4' : ''
                  }`} />
                </button>
              </div>
              
              <div className="flex items-center justify-center">
                <button
                  onClick={() => togglePreference(pref.id, 'push')}
                  className={`w-10 h-6 rounded-full transition-all ${
                    pref.push ? 'bg-violet-600' : 'bg-slate-700'
                  }`}
                >
                  <div className={`w-4 h-4 bg-white rounded-full transition-transform mx-1 ${
                    pref.push ? 'translate-x-4' : ''
                  }`} />
                </button>
              </div>
              
              <div className="flex items-center justify-center">
                <button
                  onClick={() => togglePreference(pref.id, 'inApp')}
                  className={`w-10 h-6 rounded-full transition-all ${
                    pref.inApp ? 'bg-violet-600' : 'bg-slate-700'
                  }`}
                >
                  <div className={`w-4 h-4 bg-white rounded-full transition-transform mx-1 ${
                    pref.inApp ? 'translate-x-4' : ''
                  }`} />
                </button>
              </div>
            </div>
          ))}
          
          {/* Sound Settings */}
          <div className="p-6 border-t border-slate-700/50">
            <h3 className="text-lg font-semibold text-white mb-4">Sound & Alerts</h3>
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Volume2 className="w-5 h-5 text-slate-400" />
                  <div>
                    <p className="font-medium text-white">Notification Sounds</p>
                    <p className="text-sm text-slate-500">Play sound for in-app notifications</p>
                  </div>
                </div>
                <button className="w-10 h-6 rounded-full bg-violet-600 transition-all">
                  <div className="w-4 h-4 bg-white rounded-full translate-x-4 mx-1" />
                </button>
              </div>
              
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Bell className="w-5 h-5 text-slate-400" />
                  <div>
                    <p className="font-medium text-white">Desktop Notifications</p>
                    <p className="text-sm text-slate-500">Show browser notifications</p>
                  </div>
                </div>
                <button className="w-10 h-6 rounded-full bg-slate-700 transition-all">
                  <div className="w-4 h-4 bg-white rounded-full mx-1" />
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
