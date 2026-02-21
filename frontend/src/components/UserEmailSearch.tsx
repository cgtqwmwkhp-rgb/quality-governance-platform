import { useState, useEffect, useRef } from "react";
import { Search, User, Loader2, X } from "lucide-react";
import { Input } from "./ui/Input";
import { usersApi, UserSearchResult } from "../api/client";

interface UserEmailSearchProps {
  value: string;
  onChange: (email: string, user?: UserSearchResult) => void;
  placeholder?: string;
  label?: string;
  required?: boolean;
}

export function UserEmailSearch({
  value,
  onChange,
  placeholder = "Search by email...",
  label,
  required = false,
}: UserEmailSearchProps) {
  const [query, setQuery] = useState(value);
  const [results, setResults] = useState<UserSearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [showDropdown, setShowDropdown] = useState(false);
  const [selectedUser, setSelectedUser] = useState<UserSearchResult | null>(
    null,
  );
  const containerRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();

  useEffect(() => {
    setQuery(value);
  }, [value]);

  useEffect(() => {
    // Close dropdown when clicking outside
    const handleClickOutside = (e: MouseEvent) => {
      if (
        containerRef.current &&
        !containerRef.current.contains(e.target as Node)
      ) {
        setShowDropdown(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const searchUsers = async (searchQuery: string) => {
    if (searchQuery.length < 2) {
      setResults([]);
      return;
    }

    setLoading(true);
    try {
      const response = await usersApi.search(searchQuery);
      setResults(response.data || []);
    } catch (err) {
      console.error("Failed to search users:", err);
      // Fallback: try to list users and filter
      try {
        const listResponse = await usersApi.list(1, 50);
        const filtered = (listResponse.data.items || []).filter(
          (u) =>
            u.email.toLowerCase().includes(searchQuery.toLowerCase()) ||
            u.full_name.toLowerCase().includes(searchQuery.toLowerCase()),
        );
        setResults(filtered);
      } catch {
        setResults([]);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newValue = e.target.value;
    setQuery(newValue);
    setSelectedUser(null);
    onChange(newValue, undefined);
    setShowDropdown(true);

    // Debounce search
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
    }
    debounceRef.current = setTimeout(() => {
      searchUsers(newValue);
    }, 300);
  };

  const handleSelectUser = (user: UserSearchResult) => {
    setQuery(user.email);
    setSelectedUser(user);
    onChange(user.email, user);
    setShowDropdown(false);
    setResults([]);
  };

  const handleClear = () => {
    setQuery("");
    setSelectedUser(null);
    onChange("", undefined);
    setResults([]);
  };

  return (
    <div ref={containerRef} className="relative">
      {label && (
        <label className="block text-sm font-medium text-foreground mb-1">
          {label} {required && <span className="text-destructive">*</span>}
        </label>
      )}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
        <Input
          type="email"
          value={query}
          onChange={handleInputChange}
          onFocus={() => query.length >= 2 && setShowDropdown(true)}
          placeholder={placeholder}
          className="pl-9 pr-8"
          required={required}
        />
        {loading && (
          <Loader2 className="absolute right-8 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground animate-spin" />
        )}
        {query && (
          <button
            type="button"
            onClick={handleClear}
            className="absolute right-2 top-1/2 -translate-y-1/2 p-1 hover:bg-muted rounded"
          >
            <X className="w-4 h-4 text-muted-foreground" />
          </button>
        )}
      </div>

      {/* Selected user indicator */}
      {selectedUser && (
        <div className="mt-1 flex items-center gap-2 text-xs text-success">
          <User className="w-3 h-3" />
          <span>{selectedUser.full_name}</span>
          {selectedUser.department && (
            <span className="text-muted-foreground">
              ({selectedUser.department})
            </span>
          )}
        </div>
      )}

      {/* Dropdown results */}
      {showDropdown && results.length > 0 && (
        <div className="absolute z-50 w-full mt-1 bg-background border border-border rounded-lg shadow-lg max-h-60 overflow-y-auto">
          {results.map((user) => (
            <button
              key={user.id}
              type="button"
              onClick={() => handleSelectUser(user)}
              className="w-full px-3 py-2 text-left hover:bg-muted flex items-center gap-3 transition-colors"
            >
              <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0">
                <User className="w-4 h-4 text-primary" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="font-medium text-foreground truncate">
                  {user.full_name}
                </p>
                <p className="text-sm text-muted-foreground truncate">
                  {user.email}
                </p>
              </div>
              {user.department && (
                <span className="text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded">
                  {user.department}
                </span>
              )}
            </button>
          ))}
        </div>
      )}

      {/* No results message */}
      {showDropdown &&
        query.length >= 2 &&
        !loading &&
        results.length === 0 && (
          <div className="absolute z-50 w-full mt-1 bg-background border border-border rounded-lg shadow-lg p-3 text-center text-sm text-muted-foreground">
            No users found. Enter a valid email address.
          </div>
        )}
    </div>
  );
}
