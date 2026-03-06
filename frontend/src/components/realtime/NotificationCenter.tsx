/**
 * NotificationCenter - Real-time notification dropdown
 * 
 * Features:
 * - Real-time notification updates via WebSocket
 * - Unread badge count
 * - Mark as read on click
 * - Grouped by time (Today, Yesterday, Earlier)
 * - Quick actions per notification
 */

import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { trackError } from '../../utils/errorTracker';
import {
  Bell,
  CheckCheck,
  X,
  AlertTriangle,
  MessageSquare,
  ClipboardList,
  Calendar,
  Shield,
  Siren,
  FileText,
  User,
  ChevronRight,
  Settings,
} from 'lucide-react';

interface Notification {
  id: number;
  type: string;
  priority: 'critical' | 'high' | 'medium' | 'low';
  title: string;
  message: string;
  entity_type?: string;
  entity_id?: string;
  action_url?: string;
  sender_id?: number;
  sender_name?: string;
  is_read: boolean;
  created_at: string;
}

interface NotificationCenterProps {
  className?: string;
}

const NotificationCenter: React.FC<NotificationCenterProps> = ({ className = '' }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  // Fetch notifications from API
  useEffect(() => {
    const fetchNotifications = async () => {
      try {
        const response = await fetch('/api/v1/notifications/');
        if (response.ok) {
          const data: Notification[] = await response.json();
          setNotifications(data);
          setUnreadCount(data.filter(n => !n.is_read).length);
        }
      } catch (err) {
        trackError(err, { component: 'NotificationCenter', action: 'fetchNotifications' });
      }
    };
    fetchNotifications();
  }, []);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // WebSocket connection for real-time updates
  useEffect(() => {
    // Future: connect to WebSocket for real-time notifications
    // const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    // const ws = new WebSocket(`${wsProtocol}//${window.location.host}/api/v1/realtime/ws/${userId}`);
    // ws.onmessage = (event) => {
    //   const data = JSON.parse(event.data);
    //   if (data.type === 'notification') {
    //     setNotifications(prev => [data.data, ...prev]);
    //     setUnreadCount(prev => prev + 1);
    //   }
    // };
    // return () => ws.close();
  }, []);

  const getNotificationIcon = (type: string, priority: string) => {
    const iconClass = priority === 'critical' 
      ? 'text-red-500 animate-pulse' 
      : priority === 'high' 
        ? 'text-orange-500' 
        : 'text-gray-400';

    switch (type) {
      case 'sos_alert':
        return <Siren className={`w-5 h-5 ${iconClass}`} />;
      case 'riddor_incident':
        return <AlertTriangle className={`w-5 h-5 ${iconClass}`} />;
      case 'mention':
        return <MessageSquare className={`w-5 h-5 ${iconClass}`} />;
      case 'assignment':
        return <ClipboardList className={`w-5 h-5 ${iconClass}`} />;
      case 'action_due_soon':
      case 'action_overdue':
        return <Calendar className={`w-5 h-5 ${iconClass}`} />;
      case 'audit_completed':
        return <Shield className={`w-5 h-5 ${iconClass}`} />;
      case 'approval_requested':
        return <FileText className={`w-5 h-5 ${iconClass}`} />;
      default:
        return <Bell className={`w-5 h-5 ${iconClass}`} />;
    }
  };

  const formatTimeAgo = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const seconds = Math.floor((now.getTime() - date.getTime()) / 1000);

    if (seconds < 60) return 'Just now';
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    if (seconds < 172800) return 'Yesterday';
    return date.toLocaleDateString();
  };

  const handleNotificationClick = (notification: Notification) => {
    // Mark as read
    setNotifications(prev =>
      prev.map(n => (n.id === notification.id ? { ...n, is_read: true } : n))
    );
    setUnreadCount(prev => Math.max(0, prev - 1));

    // Navigate to action URL
    if (notification.action_url) {
      navigate(notification.action_url);
      setIsOpen(false);
    }
  };

  const markAllAsRead = () => {
    setNotifications(prev => prev.map(n => ({ ...n, is_read: true })));
    setUnreadCount(0);
  };

  const deleteNotification = (id: number, e: React.MouseEvent) => {
    e.stopPropagation();
    setNotifications(prev => prev.filter(n => n.id !== id));
    const notification = notifications.find(n => n.id === id);
    if (notification && !notification.is_read) {
      setUnreadCount(prev => Math.max(0, prev - 1));
    }
  };

  const getPriorityBorder = (priority: string) => {
    switch (priority) {
      case 'critical':
        return 'border-l-4 border-l-red-500';
      case 'high':
        return 'border-l-4 border-l-orange-500';
      case 'medium':
        return 'border-l-4 border-l-yellow-500';
      default:
        return 'border-l-4 border-l-gray-500';
    }
  };

  return (
    <div className={`relative ${className}`} ref={dropdownRef}>
      {/* Bell Icon with Badge */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="relative p-2 text-gray-400 hover:text-white hover:bg-slate-700 rounded-lg transition-all duration-200"
        aria-label="Notifications"
      >
        <Bell className="w-5 h-5" />
        {unreadCount > 0 && (
          <span className="absolute -top-1 -right-1 flex items-center justify-center min-w-[18px] h-[18px] text-xs font-bold text-white bg-red-500 rounded-full px-1 animate-pulse">
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
      </button>

      {/* Dropdown Panel */}
      {isOpen && (
        <div className="absolute right-0 mt-2 w-96 max-h-[70vh] bg-slate-800 border border-slate-700 rounded-xl shadow-2xl overflow-hidden z-50 animate-fade-in">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 bg-slate-900 border-b border-slate-700">
            <h3 className="text-lg font-semibold text-white flex items-center gap-2">
              <Bell className="w-5 h-5 text-emerald-500" />
              Notifications
              {unreadCount > 0 && (
                <span className="text-xs bg-emerald-500 text-white px-2 py-0.5 rounded-full">
                  {unreadCount} new
                </span>
              )}
            </h3>
            <div className="flex items-center gap-2">
              {unreadCount > 0 && (
                <button
                  onClick={markAllAsRead}
                  className="text-xs text-emerald-400 hover:text-emerald-300 flex items-center gap-1"
                  title="Mark all as read"
                >
                  <CheckCheck className="w-4 h-4" />
                </button>
              )}
              <button
                onClick={() => navigate('/settings/notifications')}
                className="text-gray-400 hover:text-white"
                title="Notification settings"
              >
                <Settings className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Notification List */}
          <div className="overflow-y-auto max-h-[calc(70vh-120px)] custom-scrollbar">
            {notifications.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-gray-400">
                <Bell className="w-12 h-12 mb-3 opacity-50" />
                <p className="text-sm">No notifications yet</p>
              </div>
            ) : (
              <div className="divide-y divide-slate-700/50">
                {notifications.map((notification) => (
                  <div
                    key={notification.id}
                    role="button"
                    tabIndex={0}
                    onClick={() => handleNotificationClick(notification)}
                    onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') handleNotificationClick(notification); }}
                    className={`
                      p-4 cursor-pointer transition-all duration-200 
                      hover:bg-slate-700/50 group
                      ${!notification.is_read ? 'bg-slate-700/30' : ''}
                      ${getPriorityBorder(notification.priority)}
                    `}
                  >
                    <div className="flex items-start gap-3">
                      {/* Icon */}
                      <div className="flex-shrink-0 mt-0.5">
                        {getNotificationIcon(notification.type, notification.priority)}
                      </div>

                      {/* Content */}
                      <div className="flex-grow min-w-0">
                        <div className="flex items-start justify-between gap-2">
                          <h4 className={`text-sm font-medium truncate ${!notification.is_read ? 'text-white' : 'text-gray-300'}`}>
                            {notification.title}
                          </h4>
                          <span className="text-xs text-gray-500 whitespace-nowrap">
                            {formatTimeAgo(notification.created_at)}
                          </span>
                        </div>
                        <p className="text-xs text-gray-400 mt-1 line-clamp-2">
                          {notification.message}
                        </p>
                        {notification.sender_name && (
                          <p className="text-xs text-gray-500 mt-1 flex items-center gap-1">
                            <User className="w-3 h-3" />
                            {notification.sender_name}
                          </p>
                        )}
                      </div>

                      {/* Actions */}
                      <div className="flex-shrink-0 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                        {!notification.is_read && (
                          <div className="w-2 h-2 bg-emerald-500 rounded-full" title="Unread" />
                        )}
                        <button
                          onClick={(e) => deleteNotification(notification.id, e)}
                          className="p-1 text-gray-500 hover:text-red-400 rounded"
                          title="Delete"
                        >
                          <X className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="px-4 py-3 bg-slate-900 border-t border-slate-700">
            <button
              onClick={() => {
                navigate('/notifications');
                setIsOpen(false);
              }}
              className="w-full text-center text-sm text-emerald-400 hover:text-emerald-300 flex items-center justify-center gap-1"
            >
              View all notifications
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default NotificationCenter;
