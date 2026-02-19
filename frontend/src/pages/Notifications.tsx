import { useState, useEffect, useCallback } from 'react';
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
  Mail,
  MessageSquare,
  Smartphone,
  Volume2,
  Loader2
} from 'lucide-react';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Switch } from '../components/ui/Switch';
import { cn } from "../helpers/utils";
import { notificationsApi, NotificationEntry } from '../api/client';

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

const TYPE_MAP: Record<string, Notification['type']> = {
  mention: 'info',
  assignment: 'alert',
  sos_alert: 'alert',
  action_due_soon: 'warning',
  action_overdue: 'warning',
  system_announcement: 'info',
  audit_scheduled: 'reminder',
  risk_assessment: 'success',
};

function mapApiNotification(n: NotificationEntry): Notification {
  const mapped: Notification['type'] = TYPE_MAP[n.type] || (n.priority === 'high' ? 'alert' : 'info');
  const created = new Date(n.created_at);
  const diffMs = Date.now() - created.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  let timestamp: string;
  if (diffMin < 1) timestamp = 'Just now';
  else if (diffMin < 60) timestamp = `${diffMin} min ago`;
  else if (diffMin < 1440) timestamp = `${Math.floor(diffMin / 60)}h ago`;
  else timestamp = `${Math.floor(diffMin / 1440)}d ago`;

  return {
    id: String(n.id),
    type: mapped,
    title: n.title,
    message: n.message,
    timestamp,
    read: n.is_read,
    module: n.entity_type ? n.entity_type.charAt(0).toUpperCase() + n.entity_type.slice(1) + 's' : undefined,
    actionUrl: n.action_url || undefined,
    actionLabel: n.action_url ? 'View' : undefined,
  };
}

export default function Notifications() {
  const [activeTab, setActiveTab] = useState<'notifications' | 'settings'>('notifications');
  const [filter, setFilter] = useState<'all' | 'unread' | 'alerts'>('all');
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(true);

  const [preferences, setPreferences] = useState<NotificationPreference[]>([
    { id: 'PREF001', label: 'High Priority Alerts', description: 'Critical incidents, severe risks, and urgent actions', email: true, push: true, inApp: true },
    { id: 'PREF002', label: 'Action Reminders', description: 'Due dates and overdue action items', email: true, push: true, inApp: true },
    { id: 'PREF003', label: 'Audit Notifications', description: 'Upcoming audits, findings, and results', email: true, push: false, inApp: true },
    { id: 'PREF004', label: 'Document Updates', description: 'New documents, version changes, and reviews', email: false, push: false, inApp: true },
    { id: 'PREF005', label: 'Weekly Summaries', description: 'Weekly digest of IMS activities', email: true, push: false, inApp: false },
    { id: 'PREF006', label: 'Assignment Notifications', description: 'When tasks or items are assigned to you', email: true, push: true, inApp: true },
  ]);

  const loadNotifications = useCallback(async () => {
    try {
      setLoading(true);
      const resp = await notificationsApi.list({ page: 1, page_size: 50 });
      const data = resp as { items?: NotificationEntry[] };
      const items = Array.isArray(data?.items) ? data.items : [];
      setNotifications(items.map(mapApiNotification));
    } catch (err) {
      console.error('Failed to load notifications', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadNotifications();
  }, [loadNotifications]);

  const typeStyles: Record<string, { icon: React.ReactNode; variant: string }> = {
    alert: { icon: <AlertTriangle className="w-5 h-5" />, variant: 'destructive' },
    warning: { icon: <Clock className="w-5 h-5" />, variant: 'warning' },
    success: { icon: <CheckCircle2 className="w-5 h-5" />, variant: 'success' },
    info: { icon: <Info className="w-5 h-5" />, variant: 'info' },
    reminder: { icon: <Bell className="w-5 h-5" />, variant: 'primary' }
  };

  const unreadCount = notifications.filter(n => !n.read).length;

  const filteredNotifications = notifications.filter(n => {
    if (filter === 'unread') return !n.read;
    if (filter === 'alerts') return n.type === 'alert' || n.type === 'warning';
    return true;
  });

  const markAsRead = async (id: string) => {
    try {
      await notificationsApi.markRead(Number(id));
      setNotifications(prev => prev.map(n => n.id === id ? { ...n, read: true } : n));
    } catch (err) {
      console.error('Failed to mark notification as read', err);
    }
  };

  const markAllAsRead = async () => {
    try {
      await notificationsApi.markAllRead();
      setNotifications(prev => prev.map(n => ({ ...n, read: true })));
    } catch (err) {
      console.error('Failed to mark all as read', err);
    }
  };

  const deleteNotification = async (id: string) => {
    try {
      await notificationsApi.delete(Number(id));
      setNotifications(prev => prev.filter(n => n.id !== id));
    } catch (err) {
      console.error('Failed to delete notification', err);
    }
  };

  const clearAll = async () => {
    try {
      await notificationsApi.markAllRead();
      setNotifications([]);
    } catch (err) {
      console.error('Failed to clear notifications', err);
    }
  };

  const togglePreference = (id: string, channel: 'email' | 'push' | 'inApp') => {
    setPreferences(prev => prev.map(p => p.id === id ? { ...p, [channel]: !p[channel] } : p));
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-foreground flex items-center gap-3">
            <div className="p-2 bg-primary/10 rounded-xl relative">
              <Bell className="w-8 h-8 text-primary" />
              {unreadCount > 0 && (
                <span className="absolute -top-1 -right-1 w-5 h-5 bg-destructive text-destructive-foreground text-xs font-bold rounded-full flex items-center justify-center">
                  {unreadCount}
                </span>
              )}
            </div>
            Notifications
          </h1>
          <p className="text-muted-foreground mt-1">Stay updated with important alerts and reminders</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-border">
        <button
          onClick={() => setActiveTab('notifications')}
          className={cn(
            "px-6 py-3 font-medium transition-all border-b-2",
            activeTab === 'notifications'
              ? 'text-primary border-primary'
              : 'text-muted-foreground border-transparent hover:text-foreground'
          )}
        >
          <span className="flex items-center gap-2">
            <Bell className="w-5 h-5" />
            Notifications
            {unreadCount > 0 && (
              <Badge variant="destructive">{unreadCount}</Badge>
            )}
          </span>
        </button>
        <button
          onClick={() => setActiveTab('settings')}
          className={cn(
            "px-6 py-3 font-medium transition-all border-b-2",
            activeTab === 'settings'
              ? 'text-primary border-primary'
              : 'text-muted-foreground border-transparent hover:text-foreground'
          )}
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
              {['all', 'unread', 'alerts'].map((f) => (
                <Button
                  key={f}
                  variant={filter === f ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setFilter(f as any)}
                >
                  {f === 'unread' ? `Unread (${unreadCount})` : f.charAt(0).toUpperCase() + f.slice(1)}
                </Button>
              ))}
            </div>
            
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" onClick={markAllAsRead} disabled={unreadCount === 0}>
                <CheckCheck className="w-4 h-4" />
                Mark All Read
              </Button>
              <Button variant="ghost" size="sm" onClick={clearAll} className="text-destructive hover:text-destructive">
                <Trash2 className="w-4 h-4" />
                Clear All
              </Button>
            </div>
          </div>

          {/* Notifications List */}
          <div className="space-y-3">
            {filteredNotifications.map((notification) => (
              <Card
                key={notification.id}
                className={cn(
                  "p-4",
                  !notification.read && "border-primary/30 bg-primary/5"
                )}
              >
                <div className="flex items-start gap-4">
                  <div className={cn(
                    "p-2.5 rounded-xl",
                    typeStyles[notification.type].variant === 'destructive' && "bg-destructive/10 text-destructive",
                    typeStyles[notification.type].variant === 'warning' && "bg-warning/10 text-warning",
                    typeStyles[notification.type].variant === 'success' && "bg-success/10 text-success",
                    typeStyles[notification.type].variant === 'info' && "bg-info/10 text-info",
                    typeStyles[notification.type].variant === 'primary' && "bg-primary/10 text-primary",
                  )}>
                    {typeStyles[notification.type].icon}
                  </div>
                  
                  <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <h3 className={cn(
                          "font-semibold",
                          notification.read ? 'text-muted-foreground' : 'text-foreground'
                        )}>
                          {notification.title}
                        </h3>
                        {notification.module && (
                          <span className="text-xs text-muted-foreground mt-0.5 block">
                            {notification.module}
                          </span>
                        )}
                      </div>
                      
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-muted-foreground whitespace-nowrap">
                          {notification.timestamp}
                        </span>
                        {!notification.read && (
                          <span className="w-2 h-2 bg-primary rounded-full" />
                        )}
                      </div>
                    </div>
                    
                    <p className="text-muted-foreground mt-2 text-sm">
                      {notification.message}
                    </p>
                    
                    <div className="flex items-center gap-3 mt-3">
                      {notification.actionUrl && (
                        <a href={notification.actionUrl} className="text-sm text-primary hover:underline font-medium">
                          {notification.actionLabel} →
                        </a>
                      )}
                      
                      <div className="flex items-center gap-2 ml-auto">
                        {!notification.read && (
                          <Button variant="ghost" size="sm" onClick={() => markAsRead(notification.id)}>
                            <Check className="w-4 h-4" />
                          </Button>
                        )}
                        <Button variant="ghost" size="sm" onClick={() => deleteNotification(notification.id)} className="text-muted-foreground hover:text-destructive">
                          <X className="w-4 h-4" />
                        </Button>
                      </div>
                    </div>
                  </div>
                </div>
              </Card>
            ))}
          </div>

          {/* Empty State */}
          {filteredNotifications.length === 0 && (
            <div className="text-center py-12">
              <div className="w-20 h-20 bg-surface rounded-full flex items-center justify-center mx-auto mb-4">
                <BellOff className="w-10 h-10 text-muted-foreground" />
              </div>
              <h3 className="text-xl font-semibold text-foreground mb-2">No notifications</h3>
              <p className="text-muted-foreground">
                {filter === 'unread' ? "You're all caught up!" : "Nothing to show here"}
              </p>
            </div>
          )}
        </>
      )}

      {/* Settings Tab */}
      {activeTab === 'settings' && (
        <Card className="overflow-hidden">
          <div className="p-6 border-b border-border">
            <h2 className="text-lg font-semibold text-foreground">Notification Preferences</h2>
            <p className="text-sm text-muted-foreground mt-1">
              Choose how and when you want to be notified
            </p>
          </div>
          
          {/* Channel Headers */}
          <div className="grid grid-cols-[1fr,80px,80px,80px] gap-4 px-6 py-3 bg-surface border-b border-border">
            <div className="text-sm font-medium text-muted-foreground">Notification Type</div>
            <div className="text-sm font-medium text-muted-foreground text-center flex items-center justify-center gap-1">
              <Mail className="w-4 h-4" />
              Email
            </div>
            <div className="text-sm font-medium text-muted-foreground text-center flex items-center justify-center gap-1">
              <Smartphone className="w-4 h-4" />
              Push
            </div>
            <div className="text-sm font-medium text-muted-foreground text-center flex items-center justify-center gap-1">
              <MessageSquare className="w-4 h-4" />
              In-App
            </div>
          </div>
          
          {/* Preference Rows */}
          {preferences.map((pref) => (
            <div
              key={pref.id}
              className="grid grid-cols-[1fr,80px,80px,80px] gap-4 px-6 py-4 border-b border-border hover:bg-surface transition-colors"
            >
              <div>
                <p className="font-medium text-foreground">{pref.label}</p>
                <p className="text-sm text-muted-foreground mt-0.5">{pref.description}</p>
              </div>
              
              <div className="flex items-center justify-center">
                <Switch checked={pref.email} onCheckedChange={() => togglePreference(pref.id, 'email')} />
              </div>
              
              <div className="flex items-center justify-center">
                <Switch checked={pref.push} onCheckedChange={() => togglePreference(pref.id, 'push')} />
              </div>
              
              <div className="flex items-center justify-center">
                <Switch checked={pref.inApp} onCheckedChange={() => togglePreference(pref.id, 'inApp')} />
              </div>
            </div>
          ))}
          
          {/* Sound Settings */}
          <div className="p-6 border-t border-border">
            <h3 className="text-lg font-semibold text-foreground mb-4">Sound & Alerts</h3>
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Volume2 className="w-5 h-5 text-muted-foreground" />
                  <div>
                    <p className="font-medium text-foreground">Notification Sounds</p>
                    <p className="text-sm text-muted-foreground">Play sound for in-app notifications</p>
                  </div>
                </div>
                <Switch defaultChecked />
              </div>
              
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Bell className="w-5 h-5 text-muted-foreground" />
                  <div>
                    <p className="font-medium text-foreground">Desktop Notifications</p>
                    <p className="text-sm text-muted-foreground">Show browser notifications</p>
                  </div>
                </div>
                <Switch />
              </div>
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}
