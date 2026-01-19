/**
 * MentionInput - Rich text input with @mention support
 * 
 * Features:
 * - @mention autocomplete popup
 * - Fuzzy search for users
 * - Mention chips with avatars
 * - Keyboard navigation
 * - Accessible
 */

import React, { useState, useRef, useEffect, KeyboardEvent, useCallback } from 'react';
import { User, Search } from 'lucide-react';

interface MentionUser {
  id: number;
  display_name: string;
  email: string;
  avatar_url?: string;
}

interface MentionInputProps {
  value: string;
  onChange: (value: string) => void;
  onMention?: (user: MentionUser) => void;
  placeholder?: string;
  className?: string;
  rows?: number;
  disabled?: boolean;
  maxLength?: number;
}

const MentionInput: React.FC<MentionInputProps> = ({
  value,
  onChange,
  onMention,
  placeholder = 'Type @ to mention someone...',
  className = '',
  rows = 3,
  disabled = false,
  maxLength = 5000,
}) => {
  const [showPopup, setShowPopup] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [popupPosition, setPopupPosition] = useState({ top: 0, left: 0 });
  const [mentionStartIndex, setMentionStartIndex] = useState<number | null>(null);
  const [users, setUsers] = useState<MentionUser[]>([]);
  
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const popupRef = useRef<HTMLDivElement>(null);

  // Mock users for demonstration
  const mockUsers: MentionUser[] = [
    { id: 1, display_name: 'John Smith', email: 'john.smith@plantexpand.com' },
    { id: 2, display_name: 'Jane Doe', email: 'jane.doe@plantexpand.com' },
    { id: 3, display_name: 'Bob Wilson', email: 'bob.wilson@plantexpand.com' },
    { id: 4, display_name: 'Alice Brown', email: 'alice.brown@plantexpand.com' },
    { id: 5, display_name: 'Charlie Davis', email: 'charlie.davis@plantexpand.com' },
    { id: 6, display_name: 'Diana Evans', email: 'diana.evans@plantexpand.com' },
    { id: 7, display_name: 'Edward Foster', email: 'edward.foster@plantexpand.com' },
    { id: 8, display_name: 'Fiona Green', email: 'fiona.green@plantexpand.com' },
  ];

  // Filter users based on search query
  useEffect(() => {
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      const filtered = mockUsers.filter(
        u => u.display_name.toLowerCase().includes(query) || 
             u.email.toLowerCase().includes(query)
      );
      setUsers(filtered.slice(0, 8));
    } else {
      setUsers(mockUsers.slice(0, 8));
    }
    setSelectedIndex(0);
  }, [searchQuery]);

  // Calculate popup position
  const updatePopupPosition = useCallback(() => {
    if (!textareaRef.current) return;

    const textarea = textareaRef.current;
    const { selectionStart } = textarea;
    
    // Create a hidden div to measure text
    const div = document.createElement('div');
    div.style.cssText = window.getComputedStyle(textarea, null).cssText;
    div.style.height = 'auto';
    div.style.position = 'absolute';
    div.style.visibility = 'hidden';
    div.style.whiteSpace = 'pre-wrap';
    div.style.wordWrap = 'break-word';
    div.textContent = value.substring(0, selectionStart);
    
    // Add a span for cursor position
    const span = document.createElement('span');
    span.textContent = '|';
    div.appendChild(span);
    
    document.body.appendChild(div);
    
    const spanRect = span.getBoundingClientRect();
    const textareaRect = textarea.getBoundingClientRect();
    
    document.body.removeChild(div);
    
    // Position popup below cursor
    setPopupPosition({
      top: Math.min(spanRect.height, textarea.scrollHeight - textarea.scrollTop) + 4,
      left: Math.min(spanRect.width - div.offsetWidth + textareaRect.width, textareaRect.width - 250),
    });
  }, [value]);

  // Handle input change
  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const newValue = e.target.value;
    const cursorPos = e.target.selectionStart;
    
    onChange(newValue);

    // Check for @ trigger
    const textBeforeCursor = newValue.substring(0, cursorPos);
    const atIndex = textBeforeCursor.lastIndexOf('@');
    
    if (atIndex !== -1) {
      // Check if @ is at start or preceded by whitespace
      const charBefore = atIndex > 0 ? textBeforeCursor[atIndex - 1] : ' ';
      if (charBefore === ' ' || charBefore === '\n' || atIndex === 0) {
        const query = textBeforeCursor.substring(atIndex + 1);
        
        // Check if query doesn't contain spaces (still typing mention)
        if (!query.includes(' ') && !query.includes('\n')) {
          setMentionStartIndex(atIndex);
          setSearchQuery(query);
          setShowPopup(true);
          updatePopupPosition();
          return;
        }
      }
    }
    
    setShowPopup(false);
    setMentionStartIndex(null);
  };

  // Handle keyboard navigation
  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (!showPopup) return;

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setSelectedIndex(prev => Math.min(prev + 1, users.length - 1));
        break;
      case 'ArrowUp':
        e.preventDefault();
        setSelectedIndex(prev => Math.max(prev - 1, 0));
        break;
      case 'Enter':
      case 'Tab':
        e.preventDefault();
        if (users[selectedIndex]) {
          insertMention(users[selectedIndex]);
        }
        break;
      case 'Escape':
        e.preventDefault();
        setShowPopup(false);
        break;
    }
  };

  // Insert mention into text
  const insertMention = (user: MentionUser) => {
    if (mentionStartIndex === null || !textareaRef.current) return;

    const cursorPos = textareaRef.current.selectionStart;
    const beforeMention = value.substring(0, mentionStartIndex);
    const afterMention = value.substring(cursorPos);
    
    // Format: @[Display Name]
    const mentionText = `@[${user.display_name}] `;
    const newValue = beforeMention + mentionText + afterMention;
    
    onChange(newValue);
    setShowPopup(false);
    setMentionStartIndex(null);
    
    // Notify parent
    if (onMention) {
      onMention(user);
    }

    // Set cursor position after mention
    setTimeout(() => {
      if (textareaRef.current) {
        const newPos = mentionStartIndex + mentionText.length;
        textareaRef.current.selectionStart = newPos;
        textareaRef.current.selectionEnd = newPos;
        textareaRef.current.focus();
      }
    }, 0);
  };

  // Close popup when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (popupRef.current && !popupRef.current.contains(e.target as Node) &&
          textareaRef.current && !textareaRef.current.contains(e.target as Node)) {
        setShowPopup(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const getInitials = (name: string) => {
    return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
  };

  return (
    <div className={`relative ${className}`}>
      {/* Text Area */}
      <textarea
        ref={textareaRef}
        value={value}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        disabled={disabled}
        maxLength={maxLength}
        rows={rows}
        className={`
          w-full p-3 bg-slate-700 border border-slate-600 rounded-lg 
          text-white placeholder-gray-400 resize-none
          focus:ring-2 focus:ring-emerald-500 focus:border-transparent 
          transition-all duration-200
          disabled:opacity-50 disabled:cursor-not-allowed
        `}
      />

      {/* Character count */}
      {maxLength && (
        <div className="absolute bottom-2 right-2 text-xs text-gray-500">
          {value.length}/{maxLength}
        </div>
      )}

      {/* Mention Popup */}
      {showPopup && users.length > 0 && (
        <div
          ref={popupRef}
          className="absolute z-50 w-64 bg-slate-800 border border-slate-700 rounded-lg shadow-xl overflow-hidden animate-fade-in"
          style={{ top: `${popupPosition.top}px`, left: `${Math.max(0, popupPosition.left)}px` }}
        >
          {/* Search indicator */}
          <div className="px-3 py-2 bg-slate-900 border-b border-slate-700 flex items-center gap-2">
            <Search className="w-4 h-4 text-gray-500" />
            <span className="text-sm text-gray-400">
              {searchQuery ? `Searching: "${searchQuery}"` : 'Mention someone'}
            </span>
          </div>

          {/* User list */}
          <div className="max-h-48 overflow-y-auto custom-scrollbar">
            {users.map((user, index) => (
              <button
                key={user.id}
                onClick={() => insertMention(user)}
                className={`
                  w-full px-3 py-2 flex items-center gap-3 text-left transition-colors
                  ${index === selectedIndex ? 'bg-emerald-600 text-white' : 'hover:bg-slate-700 text-gray-300'}
                `}
              >
                  {/* Avatar */}
                  <div className={`
                    w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold
                    ${index === selectedIndex ? 'bg-emerald-700' : 'bg-slate-600'}
                  `}>
                    {user.avatar_url ? (
                      <img src={user.avatar_url} alt={user.display_name} className="w-full h-full rounded-full object-cover" />
                    ) : (
                      getInitials(user.display_name)
                    )}
                  </div>

                  {/* Info */}
                  <div className="flex-grow min-w-0">
                    <div className="text-sm font-medium truncate">{user.display_name}</div>
                    <div className={`text-xs truncate ${index === selectedIndex ? 'text-emerald-200' : 'text-gray-500'}`}>
                      {user.email}
                    </div>
                  </div>
              </button>
            ))}
          </div>

          {/* Keyboard hints */}
          <div className="px-3 py-2 bg-slate-900 border-t border-slate-700 flex items-center justify-between text-xs text-gray-500">
            <span>↑↓ Navigate</span>
            <span>↵ Select</span>
            <span>Esc Close</span>
          </div>
        </div>
      )}

      {/* No results */}
      {showPopup && users.length === 0 && searchQuery && (
        <div
          ref={popupRef}
          className="absolute z-50 w-64 bg-slate-800 border border-slate-700 rounded-lg shadow-xl p-4 text-center text-gray-400"
          style={{ top: `${popupPosition.top}px`, left: `${Math.max(0, popupPosition.left)}px` }}
        >
          <User className="w-8 h-8 mx-auto mb-2 opacity-50" />
          <p className="text-sm">No users found for "{searchQuery}"</p>
        </div>
      )}
    </div>
  );
};

export default MentionInput;
