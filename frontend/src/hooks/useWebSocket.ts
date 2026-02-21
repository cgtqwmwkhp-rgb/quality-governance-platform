/**
 * useWebSocket - React hook for WebSocket connection management
 * 
 * Features:
 * - Auto-connect on mount
 * - Auto-reconnect with exponential backoff
 * - Heartbeat/ping-pong
 * - Channel subscriptions
 * - Notification handling
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { API_BASE_URL } from '../config/apiBase';

interface WebSocketMessage {
  type: string;
  data?: Record<string, unknown>;
  timestamp?: string;
}

interface Notification {
  id: number;
  type: string;
  priority: string;
  title: string;
  message: string;
  entity_type?: string;
  entity_id?: string;
  action_url?: string;
  is_read: boolean;
  created_at: string;
}

interface UseWebSocketOptions {
  userId?: number;
  autoConnect?: boolean;
  reconnectAttempts?: number;
  reconnectInterval?: number;
  heartbeatInterval?: number;
  onNotification?: (notification: Notification) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: Event) => void;
}

interface UseWebSocketReturn {
  isConnected: boolean;
  isConnecting: boolean;
  lastMessage: WebSocketMessage | null;
  notifications: Notification[];
  unreadCount: number;
  connect: () => void;
  disconnect: () => void;
  subscribe: (channel: string) => void;
  unsubscribe: (channel: string) => void;
  send: (message: Record<string, unknown>) => void;
  clearNotifications: () => void;
  markAsRead: (notificationId: number) => void;
}

const useWebSocket = (options: UseWebSocketOptions = {}): UseWebSocketReturn => {
  const {
    userId,
    autoConnect = true,
    reconnectAttempts = 5,
    reconnectInterval = 3000,
    heartbeatInterval = 30000,
    onNotification,
    onConnect,
    onDisconnect,
    onError,
  } = options;

  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const heartbeatIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Get WebSocket URL
  const getWsUrl = useCallback(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = API_BASE_URL.replace(/^https?:\/\//, '');
    return `${protocol}//${host}/api/v1/realtime/ws/${userId || 0}`;
  }, [userId]);

  // Send heartbeat
  const sendHeartbeat = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'ping' }));
    }
  }, []);

  // Start heartbeat interval
  const startHeartbeat = useCallback(() => {
    if (heartbeatIntervalRef.current) {
      clearInterval(heartbeatIntervalRef.current);
    }
    heartbeatIntervalRef.current = setInterval(sendHeartbeat, heartbeatInterval);
  }, [sendHeartbeat, heartbeatInterval]);

  // Stop heartbeat interval
  const stopHeartbeat = useCallback(() => {
    if (heartbeatIntervalRef.current) {
      clearInterval(heartbeatIntervalRef.current);
      heartbeatIntervalRef.current = null;
    }
  }, []);

  // Handle incoming message
  const handleMessage = useCallback((event: MessageEvent) => {
    try {
      const message: WebSocketMessage = JSON.parse(event.data);
      setLastMessage(message);

      switch (message.type) {
        case 'notification':
          const notification = message.data as unknown as Notification;
          setNotifications(prev => [notification, ...prev]);
          if (!notification.is_read) {
            setUnreadCount(prev => prev + 1);
          }
          onNotification?.(notification);
          
          // Show browser notification if permitted
          if (Notification.permission === 'granted') {
            new Notification(notification.title, {
              body: notification.message,
              icon: '/vite.svg',
              tag: `notification-${notification.id}`,
            });
          }
          break;

        case 'pong':
          // Heartbeat response - connection is alive
          break;

        case 'subscribed':
          console.log(`Subscribed to channel: ${message.data?.['channel']}`);
          break;

        case 'unsubscribed':
          console.log(`Unsubscribed from channel: ${message.data?.['channel']}`);
          break;

        case 'presence_update':
          // Handle presence update
          break;

        default:
          console.log('Unknown message type:', message.type);
      }
    } catch (error) {
      console.error('Failed to parse WebSocket message:', error);
    }
  }, [onNotification]);

  // Connect to WebSocket
  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN || isConnecting) {
      return;
    }

    setIsConnecting(true);
    const url = getWsUrl();
    console.log(`Connecting to WebSocket: ${url}`);

    try {
      const ws = new WebSocket(url);

      ws.onopen = () => {
        console.log('WebSocket connected');
        setIsConnected(true);
        setIsConnecting(false);
        reconnectAttemptsRef.current = 0;
        startHeartbeat();
        onConnect?.();
      };

      ws.onmessage = handleMessage;

      ws.onclose = (event) => {
        console.log('WebSocket disconnected:', event.code, event.reason);
        setIsConnected(false);
        setIsConnecting(false);
        stopHeartbeat();
        onDisconnect?.();

        // Attempt reconnection
        if (reconnectAttemptsRef.current < reconnectAttempts) {
          const delay = reconnectInterval * Math.pow(2, reconnectAttemptsRef.current);
          console.log(`Reconnecting in ${delay}ms (attempt ${reconnectAttemptsRef.current + 1}/${reconnectAttempts})`);
          
          reconnectTimeoutRef.current = setTimeout(() => {
            reconnectAttemptsRef.current++;
            connect();
          }, delay);
        }
      };

      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        onError?.(error);
      };

      wsRef.current = ws;
    } catch (error) {
      console.error('Failed to create WebSocket:', error);
      setIsConnecting(false);
    }
  }, [
    getWsUrl,
    isConnecting,
    handleMessage,
    startHeartbeat,
    stopHeartbeat,
    reconnectAttempts,
    reconnectInterval,
    onConnect,
    onDisconnect,
    onError,
  ]);

  // Disconnect from WebSocket
  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    
    stopHeartbeat();
    
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    
    setIsConnected(false);
    setIsConnecting(false);
  }, [stopHeartbeat]);

  // Subscribe to a channel
  const subscribe = useCallback((channel: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'subscribe', channel }));
    }
  }, []);

  // Unsubscribe from a channel
  const unsubscribe = useCallback((channel: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'unsubscribe', channel }));
    }
  }, []);

  // Send a message
  const send = useCallback((message: Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
    } else {
      console.warn('WebSocket not connected, message not sent');
    }
  }, []);

  // Clear all notifications
  const clearNotifications = useCallback(() => {
    setNotifications([]);
    setUnreadCount(0);
  }, []);

  // Mark notification as read
  const markAsRead = useCallback((notificationId: number) => {
    setNotifications(prev =>
      prev.map(n => (n.id === notificationId ? { ...n, is_read: true } : n))
    );
    setUnreadCount(prev => Math.max(0, prev - 1));
  }, []);

  // Auto-connect on mount
  useEffect(() => {
    if (autoConnect && userId) {
      // Request notification permission
      if ('Notification' in window && Notification.permission === 'default') {
        Notification.requestPermission();
      }
      
      connect();
    }

    return () => {
      disconnect();
    };
  }, [autoConnect, userId]); // eslint-disable-line react-hooks/exhaustive-deps

  return {
    isConnected,
    isConnecting,
    lastMessage,
    notifications,
    unreadCount,
    connect,
    disconnect,
    subscribe,
    unsubscribe,
    send,
    clearNotifications,
    markAsRead,
  };
};

export default useWebSocket;
