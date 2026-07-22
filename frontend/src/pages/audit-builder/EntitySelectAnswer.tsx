import { useEffect, useRef, useState } from 'react'
import { AlertCircle, Loader2, Search, User, X } from 'lucide-react'
import { getApiErrorMessage, lookupsApi, usersApi, type UserSearchResult } from '../../api/client'
import { safetyAssetsApi, type SafetyLocation } from '../../api/safetyAssetsClient'
import { toCustomerSelectOptions, type CustomerLookupOption } from '../admin/customersCatalog'

export type EntitySelectKind = 'user' | 'location' | 'customer'

export interface EntitySelectAnswerProps {
  kind: EntitySelectKind
  /** Stable id string: user id, location id, or customer code. */
  value: string
  onChange: (value: string, label?: string) => void
  /** Best-effort label snapshot from response_json, used to prefill the search box. */
  label?: string
  className?: string
  variant?: 'desktop' | 'mobile'
  disabled?: boolean
}

const DESKTOP_FIELD_CLASS =
  'w-full px-4 py-3 bg-secondary border border-border rounded-xl text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-ring'
const MOBILE_FIELD_CLASS =
  'w-full px-4 py-4 bg-slate-800 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-purple-500 text-lg'

const LOCATION_PAGE_SIZE = 200

function fieldClass(variant: 'desktop' | 'mobile', extra?: string): string {
  const base = variant === 'mobile' ? MOBILE_FIELD_CLASS : DESKTOP_FIELD_CLASS
  return extra ? `${base} ${extra}` : base
}

function mutedTextClass(variant: 'desktop' | 'mobile'): string {
  return variant === 'mobile' ? 'text-slate-400' : 'text-muted-foreground'
}

function errorTextClass(variant: 'desktop' | 'mobile'): string {
  return variant === 'mobile' ? 'text-red-400' : 'text-destructive'
}

function UserEntitySelect({
  value,
  onChange,
  label,
  className,
  variant,
  disabled,
}: {
  value: string
  onChange: (value: string, label?: string) => void
  label?: string
  className?: string
  variant: 'desktop' | 'mobile'
  disabled?: boolean
}) {
  const [query, setQuery] = useState(label ?? '')
  const [results, setResults] = useState<UserSearchResult[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showDropdown, setShowDropdown] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const debounceRef = useRef<ReturnType<typeof setTimeout>>()
  const searchSeqRef = useRef(0)

  useEffect(() => {
    if (label !== undefined) setQuery(label)
  }, [label])

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setShowDropdown(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [])

  const runSearch = async (search: string) => {
    const seq = ++searchSeqRef.current
    if (search.trim().length < 2) {
      if (seq === searchSeqRef.current) {
        setResults([])
        setLoading(false)
      }
      return
    }
    setLoading(true)
    setError(null)
    try {
      const response = await usersApi.search(search.trim())
      if (seq !== searchSeqRef.current) return
      setResults(response.data || [])
    } catch (err) {
      if (seq !== searchSeqRef.current) return
      setError(getApiErrorMessage(err, 'Could not search users.'))
      setResults([])
    } finally {
      if (seq === searchSeqRef.current) setLoading(false)
    }
  }

  const handleInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const next = event.target.value
    setQuery(next)
    setShowDropdown(true)
    // Typing after a selection must clear the stale user id until a new pick.
    if (value) onChange('', undefined)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      void runSearch(next)
    }, 300)
  }

  const handleSelect = (user: UserSearchResult) => {
    const display = user.display_name || user.full_name || user.email
    setQuery(display)
    onChange(String(user.id), display)
    setShowDropdown(false)
    setResults([])
  }

  const handleClear = () => {
    setQuery('')
    setResults([])
    setError(null)
    onChange('', undefined)
  }

  return (
    <div ref={containerRef} className={`relative ${className ?? ''}`}>
      <div className="relative">
        <Search
          className={`absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 pointer-events-none ${mutedTextClass(variant)}`}
        />
        <input
          type="text"
          value={query}
          onChange={handleInputChange}
          onFocus={() => query.trim().length >= 2 && setShowDropdown(true)}
          placeholder="Search by name or email…"
          disabled={disabled}
          aria-label="Search for a user"
          className={fieldClass(variant, 'pl-10 pr-9')}
        />
        {loading && (
          <Loader2
            className={`absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 animate-spin ${mutedTextClass(variant)}`}
          />
        )}
        {!loading && (query || value) && !disabled && (
          <button
            type="button"
            onClick={handleClear}
            aria-label="Clear selected user"
            className={`absolute right-3 top-1/2 -translate-y-1/2 hover:opacity-80 ${mutedTextClass(variant)}`}
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      {error && (
        <p className={`mt-1 flex items-center gap-1 text-xs ${errorTextClass(variant)}`}>
          <AlertCircle className="w-3 h-3 shrink-0" />
          {error}
        </p>
      )}

      {!error && value && !query && (
        <p className={`mt-1 text-xs ${mutedTextClass(variant)}`}>Selected user ID: {value}</p>
      )}

      {showDropdown && !error && query.trim().length >= 2 && (
        <div className="absolute z-50 mt-1 w-full rounded-xl border border-border bg-card shadow-xl max-h-60 overflow-y-auto">
          {loading ? (
            <div className="flex items-center gap-2 px-3 py-2 text-sm text-muted-foreground">
              <Loader2 className="w-4 h-4 animate-spin" />
              Searching…
            </div>
          ) : results.length === 0 ? (
            <p className="px-3 py-2 text-sm text-muted-foreground">No users found.</p>
          ) : (
            results.map((user) => (
              <button
                key={user.id}
                type="button"
                onClick={() => handleSelect(user)}
                className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-muted transition-colors"
              >
                <User className="w-4 h-4 text-primary shrink-0" />
                <span className="min-w-0 flex-1 truncate">
                  <span className="font-medium text-foreground">
                    {user.display_name || user.full_name}
                  </span>
                  <span className="ml-1.5 text-xs text-muted-foreground">{user.email}</span>
                </span>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  )
}

async function loadAllLocations(): Promise<SafetyLocation[]> {
  const all: SafetyLocation[] = []
  let page = 1
  // Cap pages so a runaway total cannot hang the picker.
  for (let i = 0; i < 25; i += 1) {
    const response = await safetyAssetsApi.listLocations({
      page,
      page_size: LOCATION_PAGE_SIZE,
      is_active: true,
    })
    const items = response.data.items || []
    all.push(...items)
    const total = response.data.total ?? all.length
    if (items.length < LOCATION_PAGE_SIZE || all.length >= total) break
    page += 1
  }
  return all
}

function LocationEntitySelect({
  value,
  onChange,
  className,
  variant,
  disabled,
}: {
  value: string
  onChange: (value: string, label?: string) => void
  className?: string
  variant: 'desktop' | 'mobile'
  disabled?: boolean
}) {
  const [locations, setLocations] = useState<SafetyLocation[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState('')

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    loadAllLocations()
      .then((items) => {
        if (!cancelled) setLocations(items)
      })
      .catch((err) => {
        if (!cancelled) setError(getApiErrorMessage(err, 'Could not load locations.'))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  if (loading) {
    return (
      <div className={`flex items-center gap-2 text-sm ${mutedTextClass(variant)} ${className ?? ''}`}>
        <Loader2 className="w-4 h-4 animate-spin" />
        Loading locations…
      </div>
    )
  }

  if (error) {
    return (
      <p className={`flex items-center gap-1.5 text-sm ${errorTextClass(variant)} ${className ?? ''}`}>
        <AlertCircle className="w-4 h-4 shrink-0" />
        {error}
      </p>
    )
  }

  if (locations.length === 0) {
    return (
      <p className={`text-sm ${mutedTextClass(variant)} ${className ?? ''}`}>
        No locations configured yet — add one in the Safety Asset Register.
      </p>
    )
  }

  const needle = filter.trim().toLowerCase()
  const selected = value
    ? locations.find((location) => String(location.id) === value)
    : undefined
  const filtered = needle
    ? locations.filter((location) => location.name.toLowerCase().includes(needle))
    : locations
  // Keep the current selection visible even when the filter would hide it.
  const visible =
    selected && !filtered.some((location) => location.id === selected.id)
      ? [selected, ...filtered]
      : filtered

  return (
    <div className={`space-y-2 ${className ?? ''}`}>
      {locations.length > 20 && (
        <input
          type="search"
          value={filter}
          onChange={(event) => setFilter(event.target.value)}
          placeholder="Filter locations…"
          disabled={disabled}
          aria-label="Filter locations"
          className={fieldClass(variant)}
        />
      )}
      <select
        value={value}
        onChange={(event) => {
          const id = event.target.value
          const match = locations.find((location) => String(location.id) === id)
          onChange(id, match?.name)
        }}
        disabled={disabled}
        aria-label="Select a location"
        className={fieldClass(variant)}
      >
        <option value="">Select a location…</option>
        {visible.map((location) => (
          <option key={location.id} value={String(location.id)}>
            {location.name}
          </option>
        ))}
      </select>
      {needle && filtered.length === 0 && !selected && (
        <p className={`text-xs ${mutedTextClass(variant)}`}>No locations match “{filter}”.</p>
      )}
    </div>
  )
}

function CustomerEntitySelect({
  value,
  onChange,
  className,
  variant,
  disabled,
}: {
  value: string
  onChange: (value: string, label?: string) => void
  className?: string
  variant: 'desktop' | 'mobile'
  disabled?: boolean
}) {
  const [options, setOptions] = useState<CustomerLookupOption[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    lookupsApi
      .list('customers', true)
      .then((data) => {
        if (!cancelled) setOptions(toCustomerSelectOptions(data.items || []))
      })
      .catch((err) => {
        if (!cancelled) setError(getApiErrorMessage(err, 'Could not load customers.'))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  if (loading) {
    return (
      <div className={`flex items-center gap-2 text-sm ${mutedTextClass(variant)} ${className ?? ''}`}>
        <Loader2 className="w-4 h-4 animate-spin" />
        Loading customers…
      </div>
    )
  }

  if (error) {
    return (
      <p className={`flex items-center gap-1.5 text-sm ${errorTextClass(variant)} ${className ?? ''}`}>
        <AlertCircle className="w-4 h-4 shrink-0" />
        {error}
      </p>
    )
  }

  if (options.length === 0) {
    return (
      <p className={`text-sm ${mutedTextClass(variant)} ${className ?? ''}`}>
        No customers configured yet — add one in Admin → Lookup Tables.
      </p>
    )
  }

  return (
    <select
      value={value}
      onChange={(event) => {
        const code = event.target.value
        const match = options.find((option) => option.value === code)
        onChange(code, match?.label)
      }}
      disabled={disabled}
      aria-label="Select a customer"
      className={fieldClass(variant, className)}
    >
      <option value="">Select a customer…</option>
      {options.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  )
}

/** Executable answer widget for the user_select / location_select / customer_select question types. */
export default function EntitySelectAnswer({
  kind,
  value,
  onChange,
  label,
  className,
  variant = 'desktop',
  disabled = false,
}: EntitySelectAnswerProps) {
  if (kind === 'user') {
    return (
      <UserEntitySelect
        value={value}
        onChange={onChange}
        label={label}
        className={className}
        variant={variant}
        disabled={disabled}
      />
    )
  }
  if (kind === 'location') {
    return (
      <LocationEntitySelect
        value={value}
        onChange={onChange}
        className={className}
        variant={variant}
        disabled={disabled}
      />
    )
  }
  return (
    <CustomerEntitySelect
      value={value}
      onChange={onChange}
      className={className}
      variant={variant}
      disabled={disabled}
    />
  )
}
