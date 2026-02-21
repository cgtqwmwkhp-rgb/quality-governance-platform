/**
 * useCollaboration - React hook for real-time collaborative editing
 *
 * Features:
 * - Yjs-based conflict-free collaborative editing
 * - Awareness (cursor positions, user presence)
 * - Undo/redo support
 * - WebSocket sync provider
 */

import { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { API_BASE_URL } from "../config/apiBase";

// Types for collaborative editing
interface CollaboratorInfo {
  id: string;
  name: string;
  color: string;
  cursor?: { index: number; length: number };
  lastActive: Date;
}

interface CollaborationState {
  isConnected: boolean;
  isSynced: boolean;
  collaborators: CollaboratorInfo[];
  localUser: CollaboratorInfo | null;
}

interface UseCollaborationOptions {
  documentId: string;
  userId: string;
  userName: string;
  userColor?: string;
  onSync?: () => void;
  onUpdate?: (update: Uint8Array) => void;
  autoConnect?: boolean;
}

interface UseCollaborationReturn {
  state: CollaborationState;
  connect: () => void;
  disconnect: () => void;
  applyUpdate: (update: Uint8Array) => void;
  getState: () => unknown;
  undo: () => void;
  redo: () => void;
  canUndo: boolean;
  canRedo: boolean;
  updateCursor: (index: number, length: number) => void;
}

// Generate a random color for user
const generateUserColor = (): string => {
  const colors = [
    "#10B981", // emerald
    "#3B82F6", // blue
    "#8B5CF6", // violet
    "#EC4899", // pink
    "#F59E0B", // amber
    "#EF4444", // red
    "#06B6D4", // cyan
    "#84CC16", // lime
  ];
  return colors[Math.floor(Math.random() * colors.length)]!;
};

/**
 * Hook for real-time collaborative editing using Yjs
 *
 * NOTE: This is a simplified implementation for demonstration.
 * For production, install and integrate:
 * - yjs: Core CRDT library
 * - y-websocket: WebSocket sync provider
 * - y-indexeddb: Offline persistence
 */
const useCollaboration = (
  options: UseCollaborationOptions,
): UseCollaborationReturn => {
  const {
    documentId,
    userId,
    userName,
    userColor = generateUserColor(),
    onSync,
    onUpdate,
    autoConnect = true,
  } = options;

  const [state, setState] = useState<CollaborationState>({
    isConnected: false,
    isSynced: false,
    collaborators: [],
    localUser: null,
  });

  const [canUndo, setCanUndo] = useState(false);
  const [canRedo, setCanRedo] = useState(false);

  // Document state (simulated)
  const documentRef = useRef<Record<string, unknown> | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const undoStackRef = useRef<Uint8Array[]>([]);
  const redoStackRef = useRef<Uint8Array[]>([]);

  // Local user info
  const localUser = useMemo<CollaboratorInfo>(
    () => ({
      id: userId,
      name: userName,
      color: userColor,
      lastActive: new Date(),
    }),
    [userId, userName, userColor],
  );

  // Connect to collaboration server
  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = API_BASE_URL.replace(/^https?:\/\//, "");
    const wsUrl = `${protocol}//${host}/api/v1/realtime/collab/${documentId}?userId=${userId}`;

    console.log(`[Collaboration] Connecting to ${wsUrl}`);

    try {
      const ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        console.log("[Collaboration] Connected");
        setState((prev) => ({
          ...prev,
          isConnected: true,
          localUser,
        }));

        // Send awareness info
        ws.send(
          JSON.stringify({
            type: "awareness",
            user: localUser,
          }),
        );
      };

      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          handleMessage(message);
        } catch (error) {
          console.error("[Collaboration] Failed to parse message:", error);
        }
      };

      ws.onclose = () => {
        console.log("[Collaboration] Disconnected");
        setState((prev) => ({
          ...prev,
          isConnected: false,
          isSynced: false,
        }));
      };

      ws.onerror = (error) => {
        console.error("[Collaboration] Error:", error);
      };

      wsRef.current = ws;
    } catch (error) {
      console.error("[Collaboration] Failed to connect:", error);
    }
  }, [documentId, userId, localUser]);

  // Disconnect from collaboration server
  const disconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setState((prev) => ({
      ...prev,
      isConnected: false,
      isSynced: false,
    }));
  }, []);

  // Handle incoming messages
  const handleMessage = useCallback(
    (message: Record<string, unknown>) => {
      switch (message["type"]) {
        case "sync":
          setState((prev) => ({ ...prev, isSynced: true }));
          onSync?.();
          break;

        case "update":
          if (message["update"]) {
            const update = new Uint8Array(
              message["update"] as ArrayBuffer | ArrayLike<number>,
            );
            onUpdate?.(update);
          }
          break;

        case "awareness":
          if (message["users"]) {
            const users = message["users"] as CollaboratorInfo[];
            const collaborators = users
              .filter((u) => u.id !== userId)
              .map((u) => ({
                ...u,
                lastActive: new Date(u.lastActive),
              }));
            setState((prev) => ({ ...prev, collaborators }));
          }
          break;

        case "cursor": {
          const cursorUserId = message["userId"] as string;
          const cursor = message["cursor"] as CollaboratorInfo["cursor"];
          setState((prev) => ({
            ...prev,
            collaborators: prev.collaborators.map((c) =>
              c.id === cursorUserId ? { ...c, cursor } : c,
            ),
          }));
          break;
        }

        default:
          console.log("[Collaboration] Unknown message type:", message["type"]);
      }
    },
    [userId, onSync, onUpdate],
  );

  // Apply a local update
  const applyUpdate = useCallback((update: Uint8Array) => {
    // Store in undo stack
    undoStackRef.current.push(update);
    redoStackRef.current = [];
    setCanUndo(true);
    setCanRedo(false);

    // Broadcast to other collaborators
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(
        JSON.stringify({
          type: "update",
          update: Array.from(update),
        }),
      );
    }
  }, []);

  // Get current document state
  const getState = useCallback(() => {
    return documentRef.current;
  }, []);

  // Undo last change
  const undo = useCallback(() => {
    if (undoStackRef.current.length === 0) return;

    const update = undoStackRef.current.pop();
    if (update) {
      redoStackRef.current.push(update);
      setCanUndo(undoStackRef.current.length > 0);
      setCanRedo(true);

      // TODO: Apply inverse of update
      console.log("[Collaboration] Undo");
    }
  }, []);

  // Redo last undone change
  const redo = useCallback(() => {
    if (redoStackRef.current.length === 0) return;

    const update = redoStackRef.current.pop();
    if (update) {
      undoStackRef.current.push(update);
      setCanUndo(true);
      setCanRedo(redoStackRef.current.length > 0);

      // TODO: Re-apply update
      console.log("[Collaboration] Redo");
    }
  }, []);

  // Update cursor position
  const updateCursor = useCallback((index: number, length: number) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(
        JSON.stringify({
          type: "cursor",
          cursor: { index, length },
        }),
      );
    }
  }, []);

  // Auto-connect on mount
  useEffect(() => {
    if (autoConnect) {
      connect();
    }

    return () => {
      disconnect();
    };
  }, [autoConnect]); // eslint-disable-line react-hooks/exhaustive-deps

  return {
    state,
    connect,
    disconnect,
    applyUpdate,
    getState,
    undo,
    redo,
    canUndo,
    canRedo,
    updateCursor,
  };
};

export default useCollaboration;
