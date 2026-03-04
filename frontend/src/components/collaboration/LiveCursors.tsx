/**
 * Live Cursors Component
 * 
 * Shows real-time cursor positions of other users editing the same document.
 */

import React, { useEffect, useState } from 'react';

interface CursorPosition {
  userId: string;
  userName: string;
  userColor: string;
  userAvatar?: string;
  position: { x: number; y: number };
  field?: string;
  isTyping?: boolean;
  lastUpdate: number;
}

interface LiveCursorsProps {
  documentId: string;
  containerRef: React.RefObject<HTMLElement>;
}

export function LiveCursors({ documentId, containerRef: _containerRef }: LiveCursorsProps) {
  const [cursors, setCursors] = useState<CursorPosition[]>([]);

  useEffect(() => {
    // In production, this would connect to WebSocket for real-time updates
    // For now, we simulate with mock data
    const mockCursors: CursorPosition[] = [
      {
        userId: '1',
        userName: 'Sarah Johnson',
        userColor: '#3B82F6',
        position: { x: 200, y: 150 },
        isTyping: true,
        lastUpdate: Date.now(),
      },
      {
        userId: '2',
        userName: 'Mike Chen',
        userColor: '#10B981',
        position: { x: 450, y: 320 },
        lastUpdate: Date.now(),
      },
    ];

    // Simulate cursor movement
    const interval = setInterval(() => {
      setCursors(prev => prev.map(c => ({
        ...c,
        position: {
          x: c.position.x + (Math.random() - 0.5) * 10,
          y: c.position.y + (Math.random() - 0.5) * 10,
        },
        lastUpdate: Date.now(),
      })));
    }, 100);

    setCursors(mockCursors);

    return () => clearInterval(interval);
  }, [documentId]);

  return (
    <>
      {cursors.map(cursor => (
        <div
          key={cursor.userId}
          className="pointer-events-none absolute z-50 transition-all duration-75"
          style={{
            left: cursor.position.x,
            top: cursor.position.y,
            transform: 'translate(-2px, -2px)',
          }}
        >
          {/* Cursor arrow */}
          <svg
            width="24"
            height="24"
            viewBox="0 0 24 24"
            fill="none"
            style={{ filter: 'drop-shadow(0 1px 2px rgba(0,0,0,0.3))' }}
          >
            <path
              d="M5.5 3.5L18.5 12L12 13.5L8.5 20.5L5.5 3.5Z"
              fill={cursor.userColor}
              stroke="white"
              strokeWidth="1.5"
            />
          </svg>

          {/* User name label */}
          <div
            className="absolute left-4 top-4 whitespace-nowrap rounded px-2 py-0.5 text-xs font-medium text-white shadow-lg"
            style={{ backgroundColor: cursor.userColor }}
          >
            {cursor.userName}
            {cursor.isTyping && (
              <span className="ml-1 inline-flex gap-0.5">
                <span className="animate-bounce" style={{ animationDelay: '0ms' }}>.</span>
                <span className="animate-bounce" style={{ animationDelay: '150ms' }}>.</span>
                <span className="animate-bounce" style={{ animationDelay: '300ms' }}>.</span>
              </span>
            )}
          </div>
        </div>
      ))}
    </>
  );
}

// ============================================================================
// Presence Avatars
// ============================================================================

interface PresenceAvatarsProps {
  users: Array<{
    id: string;
    name: string;
    avatar?: string;
    color: string;
    isEditing?: boolean;
  }>;
  max?: number;
}

export function PresenceAvatars({ users, max = 5 }: PresenceAvatarsProps) {
  const visibleUsers = users.slice(0, max);
  const hiddenCount = users.length - max;

  return (
    <div className="flex items-center -space-x-2">
      {visibleUsers.map((user, index) => (
        <div
          key={user.id}
          className="relative"
          style={{ zIndex: visibleUsers.length - index }}
        >
          <div
            className={`
              flex h-8 w-8 items-center justify-center rounded-full border-2 border-slate-800 
              text-xs font-bold text-white shadow-lg
              ${user.isEditing ? 'ring-2 ring-white ring-offset-2 ring-offset-slate-800' : ''}
            `}
            style={{ backgroundColor: user.color }}
            title={user.name}
          >
            {user.avatar ? (
              <img src={user.avatar} alt={user.name} className="h-full w-full rounded-full object-cover" />
            ) : (
              user.name.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase()
            )}
          </div>
          
          {/* Online indicator */}
          <div className="absolute -bottom-0.5 -right-0.5 h-3 w-3 rounded-full border-2 border-slate-800 bg-emerald-500" />
        </div>
      ))}

      {hiddenCount > 0 && (
        <div className="flex h-8 w-8 items-center justify-center rounded-full border-2 border-slate-800 bg-slate-700 text-xs font-bold text-white shadow-lg">
          +{hiddenCount}
        </div>
      )}
    </div>
  );
}

// ============================================================================
// Typing Indicator
// ============================================================================

interface TypingIndicatorProps {
  users: Array<{ name: string; color: string }>;
}

export function TypingIndicator({ users }: TypingIndicatorProps) {
  if (users.length === 0) return null;

  const getMessage = () => {
    if (users.length === 1) {
      return `${users[0].name} is typing`;
    } else if (users.length === 2) {
      return `${users[0].name} and ${users[1].name} are typing`;
    } else {
      return `${users[0].name} and ${users.length - 1} others are typing`;
    }
  };

  return (
    <div className="flex items-center gap-2 text-sm text-slate-400">
      <div className="flex gap-1">
        {[0, 1, 2].map(i => (
          <div
            key={i}
            className="h-2 w-2 rounded-full bg-slate-400 animate-bounce"
            style={{
              animationDelay: `${i * 150}ms`,
              backgroundColor: users[0]?.color || '#64748b',
            }}
          />
        ))}
      </div>
      <span>{getMessage()}</span>
    </div>
  );
}

// ============================================================================
// Collaboration Banner
// ============================================================================

interface CollaborationBannerProps {
  users: Array<{
    id: string;
    name: string;
    avatar?: string;
    color: string;
    isEditing?: boolean;
    field?: string;
  }>;
  onStartCollaboration?: () => void;
}

export function CollaborationBanner({ users, onStartCollaboration }: CollaborationBannerProps) {
  const editingUsers = users.filter(u => u.isEditing);

  if (users.length === 0) {
    return (
      <div className="flex items-center justify-between rounded-lg bg-slate-800/50 p-3">
        <span className="text-sm text-slate-400">No one else is viewing this document</span>
        {onStartCollaboration && (
          <button
            onClick={onStartCollaboration}
            className="text-sm font-medium text-blue-400 hover:text-blue-300"
          >
            Invite collaborators
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="flex items-center justify-between rounded-lg bg-slate-800/50 p-3">
      <div className="flex items-center gap-3">
        <PresenceAvatars users={users} max={4} />
        <div>
          <p className="text-sm font-medium text-white">
            {users.length} {users.length === 1 ? 'person' : 'people'} viewing
          </p>
          {editingUsers.length > 0 && (
            <p className="text-xs text-slate-400">
              {editingUsers.map(u => u.name).join(', ')} {editingUsers.length === 1 ? 'is' : 'are'} editing
            </p>
          )}
        </div>
      </div>

      <div className="flex items-center gap-2">
        <span className="flex h-2 w-2 rounded-full bg-emerald-500">
          <span className="animate-ping h-full w-full rounded-full bg-emerald-400 opacity-75" />
        </span>
        <span className="text-xs text-emerald-400">Live</span>
      </div>
    </div>
  );
}
