/**
 * NotificationCenter - Real-time notification dropdown
 *
 * Features:
 * - Fetches real notifications from the API
 * - Unread badge count
 * - Mark as read on click
 * - Quick actions per notification
 */

import React, { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
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
  Loader2,
} from "lucide-react";
import { notificationsApi } from "../../api/client";

interface Notification {
  id: number;
  type: string;
  priority: "critical" | "high" | "medium" | "low";
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

const NotificationCenter: React.FC<NotificationCenterProps> = ({
  className = "",
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  const fetchNotifications = useCallback(async () => {
    try {
      setLoading(true);
      const [listRes, countRes] = await Promise.allSettled([
        notificationsApi.list({ page: 1, page_size: 20 }),
        notificationsApi.getUnreadCount(),
      ]);

      if (listRes.status === "fulfilled") {
        const items = listRes.value.data.items || [];
        setNotifications(
          items.map((n) => ({
            id: n.id,
            type: n.type || "info",
            priority: (n.priority || "medium") as Notification["priority"],
            title: n.title || "Notification",
            message: n.message || "",
            entity_type: n.entity_type,
            entity_id: n.entity_id,
            action_url: n.action_url,
            sender_name: n.sender_name,
            is_read: n.is_read ?? false,
            created_at: n.created_at || new Date().toISOString(),
          })),
        );
      }

      if (countRes.status === "fulfilled") {
        setUnreadCount(countRes.value.data.unread_count || 0);
      }
    } catch (err) {
      console.error("Failed to fetch notifications:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchNotifications();
    const interval = setInterval(fetchNotifications, 30000);
    return () => clearInterval(interval);
  }, [fetchNotifications]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const getNotificationIcon = (type: string, priority: string) => {
    const iconClass =
      priority === "critical"
        ? "text-red-500 animate-pulse"
        : priority === "high"
          ? "text-orange-500"
          : "text-muted-foreground";

    switch (type) {
      case "sos_alert":
        return <Siren className={`w-5 h-5 ${iconClass}`} />;
      case "riddor_incident":
        return <AlertTriangle className={`w-5 h-5 ${iconClass}`} />;
      case "mention":
        return <MessageSquare className={`w-5 h-5 ${iconClass}`} />;
      case "assignment":
        return <ClipboardList className={`w-5 h-5 ${iconClass}`} />;
      case "action_due_soon":
      case "action_overdue":
        return <Calendar className={`w-5 h-5 ${iconClass}`} />;
      case "audit_completed":
        return <Shield className={`w-5 h-5 ${iconClass}`} />;
      case "approval_requested":
        return <FileText className={`w-5 h-5 ${iconClass}`} />;
      default:
        return <Bell className={`w-5 h-5 ${iconClass}`} />;
    }
  };

  const formatTimeAgo = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const seconds = Math.floor((now.getTime() - date.getTime()) / 1000);

    if (seconds < 60) return "Just now";
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    if (seconds < 172800) return "Yesterday";
    return date.toLocaleDateString();
  };

  const handleNotificationClick = async (notification: Notification) => {
    if (!notification.is_read) {
      try {
        await notificationsApi.markRead(notification.id);
        setNotifications((prev) =>
          prev.map((n) =>
            n.id === notification.id ? { ...n, is_read: true } : n,
          ),
        );
        setUnreadCount((prev) => Math.max(0, prev - 1));
      } catch (err) {
        console.error("Failed to mark notification as read:", err);
      }
    }

    if (notification.action_url) {
      navigate(notification.action_url);
      setIsOpen(false);
    }
  };

  const markAllAsRead = async () => {
    try {
      await notificationsApi.markAllRead();
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
      setUnreadCount(0);
    } catch (err) {
      console.error("Failed to mark all as read:", err);
    }
  };

  const deleteNotification = async (id: number, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await notificationsApi.delete(id);
      const notification = notifications.find((n) => n.id === id);
      setNotifications((prev) => prev.filter((n) => n.id !== id));
      if (notification && !notification.is_read) {
        setUnreadCount((prev) => Math.max(0, prev - 1));
      }
    } catch (err) {
      console.error("Failed to delete notification:", err);
    }
  };

  const getPriorityBorder = (priority: string) => {
    switch (priority) {
      case "critical":
        return "border-l-4 border-l-destructive";
      case "high":
        return "border-l-4 border-l-warning";
      case "medium":
        return "border-l-4 border-l-info";
      default:
        return "border-l-4 border-l-border";
    }
  };

  return (
    <div className={`relative ${className}`} ref={dropdownRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="relative p-2 text-muted-foreground hover:text-foreground hover:bg-surface rounded-lg transition-all duration-200"
        aria-label="Notifications"
      >
        <Bell className="w-5 h-5" />
        {unreadCount > 0 && (
          <span className="absolute -top-1 -right-1 flex items-center justify-center min-w-[18px] h-[18px] text-xs font-bold text-destructive-foreground bg-destructive rounded-full px-1 animate-pulse">
            {unreadCount > 99 ? "99+" : unreadCount}
          </span>
        )}
      </button>

      {isOpen && (
        <div className="absolute right-0 mt-2 w-96 max-h-[70vh] bg-card border border-border rounded-xl shadow-2xl overflow-hidden z-50 animate-fade-in">
          <div className="flex items-center justify-between px-4 py-3 bg-background border-b border-border">
            <h3 className="text-lg font-semibold text-foreground flex items-center gap-2">
              <Bell className="w-5 h-5 text-primary" />
              Notifications
              {unreadCount > 0 && (
                <span className="text-xs bg-primary text-primary-foreground px-2 py-0.5 rounded-full">
                  {unreadCount} new
                </span>
              )}
            </h3>
            <div className="flex items-center gap-2">
              {unreadCount > 0 && (
                <button
                  onClick={markAllAsRead}
                  className="text-xs text-primary hover:text-primary/80 flex items-center gap-1"
                  title="Mark all as read"
                >
                  <CheckCheck className="w-4 h-4" />
                </button>
              )}
              <button
                onClick={() => navigate("/settings/notifications")}
                className="text-muted-foreground hover:text-foreground"
                title="Notification settings"
              >
                <Settings className="w-4 h-4" />
              </button>
            </div>
          </div>

          <div className="overflow-y-auto max-h-[calc(70vh-120px)]">
            {loading && notifications.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                <Loader2 className="w-8 h-8 mb-3 animate-spin" />
                <p className="text-sm">Loading notifications...</p>
              </div>
            ) : notifications.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                <Bell className="w-12 h-12 mb-3 opacity-50" />
                <p className="text-sm">No notifications yet</p>
              </div>
            ) : (
              <div className="divide-y divide-border/50">
                {notifications.map((notification) => (
                  <div
                    key={notification.id}
                    onClick={() => handleNotificationClick(notification)}
                    className={`
                      p-4 cursor-pointer transition-all duration-200 
                      hover:bg-surface group
                      ${!notification.is_read ? "bg-primary/5" : ""}
                      ${getPriorityBorder(notification.priority)}
                    `}
                  >
                    <div className="flex items-start gap-3">
                      <div className="flex-shrink-0 mt-0.5">
                        {getNotificationIcon(
                          notification.type,
                          notification.priority,
                        )}
                      </div>

                      <div className="flex-grow min-w-0">
                        <div className="flex items-start justify-between gap-2">
                          <h4
                            className={`text-sm font-medium truncate ${!notification.is_read ? "text-foreground" : "text-muted-foreground"}`}
                          >
                            {notification.title}
                          </h4>
                          <span className="text-xs text-muted-foreground whitespace-nowrap">
                            {formatTimeAgo(notification.created_at)}
                          </span>
                        </div>
                        <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
                          {notification.message}
                        </p>
                        {notification.sender_name && (
                          <p className="text-xs text-muted-foreground mt-1 flex items-center gap-1">
                            <User className="w-3 h-3" />
                            {notification.sender_name}
                          </p>
                        )}
                      </div>

                      <div className="flex-shrink-0 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                        {!notification.is_read && (
                          <div
                            className="w-2 h-2 bg-primary rounded-full"
                            title="Unread"
                          />
                        )}
                        <button
                          onClick={(e) =>
                            deleteNotification(notification.id, e)
                          }
                          className="p-1 text-muted-foreground hover:text-destructive rounded"
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

          <div className="px-4 py-3 bg-background border-t border-border">
            <button
              onClick={() => {
                navigate("/notifications");
                setIsOpen(false);
              }}
              className="w-full text-center text-sm text-primary hover:text-primary/80 flex items-center justify-center gap-1"
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
