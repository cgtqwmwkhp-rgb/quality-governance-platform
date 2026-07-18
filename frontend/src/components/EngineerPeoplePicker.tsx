import { useEffect, useMemo, useState } from 'react'
import { Search, Users, Loader2 } from 'lucide-react'
import { workforceApi, type EngineerProfile, type UserSearchResult } from '../api/client'
import {
  ACTIVE_EMPLOYEES_LIST_PARAMS,
  employeePickerOptionLabel,
  sortEmployeesForPicker,
} from '../pages/workforce/employeePickerUtils'
import { Input } from './ui/Input'
import { cn } from '../helpers/utils'

export type EngineerPeopleSelection = {
  engineerId: number
  label: string
  /** Present when the person has a QGP login — required for case/task assignment. */
  user?: UserSearchResult
  hasLogin: boolean
}

type Props = {
  valueLabel?: string
  onChange: (selection: EngineerPeopleSelection | null) => void
  /** When true, selection requires a linked user_id (case owners / action assignees). */
  requireLogin?: boolean
  placeholder?: string
  className?: string
  testId?: string
}

function toUserResult(eng: EngineerProfile): UserSearchResult | undefined {
  if (eng.user_id == null) return undefined
  return {
    id: eng.user_id,
    email: eng.linked_user?.email || `user-${eng.user_id}`,
    full_name: eng.linked_user?.full_name || eng.display_name || `User #${eng.user_id}`,
  }
}

/**
 * Best-in-class person picker: always lists active Engineers (PAMS roster),
 * even when they have no QGP login. Login-required surfaces disable unlinked rows.
 */
export function EngineerPeoplePicker({
  valueLabel = '',
  onChange,
  requireLogin = true,
  placeholder = 'Search employees…',
  className,
  testId = 'engineer-people-picker',
}: Props) {
  const [query, setQuery] = useState(valueLabel)
  const [engineers, setEngineers] = useState<EngineerProfile[]>([])
  const [loading, setLoading] = useState(true)
  const [open, setOpen] = useState(false)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    workforceApi
      .listEngineers({ ...ACTIVE_EMPLOYEES_LIST_PARAMS })
      .then((res) => {
        if (!cancelled) setEngineers(sortEmployeesForPicker(res.data.items || []))
      })
      .catch(() => {
        if (!cancelled) setEngineers([])
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    setQuery(valueLabel)
  }, [valueLabel])

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase()
    if (!needle) return engineers
    return engineers.filter((eng) => {
      const label = employeePickerOptionLabel(eng).toLowerCase()
      const email = (eng.linked_user?.email || '').toLowerCase()
      return label.includes(needle) || email.includes(needle)
    })
  }, [engineers, query])

  return (
    <div className={cn('relative min-w-[220px]', className)} data-testid={testId}>
      <div className="relative">
        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
        <Input
          value={query}
          onChange={(e) => {
            setQuery(e.target.value)
            setOpen(true)
            onChange(null)
          }}
          onFocus={() => setOpen(true)}
          placeholder={placeholder}
          className="pl-8 h-9"
          autoComplete="off"
        />
        {loading && (
          <Loader2 className="absolute right-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 animate-spin text-muted-foreground" />
        )}
      </div>
      {open && (
        <ul
          className="absolute z-50 mt-1 max-h-56 w-full overflow-auto rounded-md border border-border bg-card shadow-md"
          role="listbox"
        >
          {filtered.length === 0 ? (
            <li className="px-3 py-2 text-sm text-muted-foreground">No employees found</li>
          ) : (
            filtered.map((eng) => {
              const hasLogin = eng.user_id != null
              const disabled = requireLogin && !hasLogin
              const label = employeePickerOptionLabel(eng)
              return (
                <li key={eng.id}>
                  <button
                    type="button"
                    disabled={disabled}
                    className={cn(
                      'w-full flex items-start gap-2 px-3 py-2 text-left text-sm',
                      disabled
                        ? 'opacity-50 cursor-not-allowed'
                        : 'hover:bg-muted cursor-pointer',
                    )}
                    onClick={() => {
                      const user = toUserResult(eng)
                      setQuery(label)
                      setOpen(false)
                      onChange({
                        engineerId: eng.id,
                        label,
                        user,
                        hasLogin,
                      })
                    }}
                  >
                    <Users className="w-3.5 h-3.5 mt-0.5 text-primary shrink-0" />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-medium text-foreground">{label}</span>
                      <span className="block text-xs text-muted-foreground">
                        {hasLogin
                          ? eng.linked_user?.email || `User #${eng.user_id}`
                          : 'No login — link on Employees profile to assign'}
                      </span>
                    </span>
                  </button>
                </li>
              )
            })
          )}
        </ul>
      )}
    </div>
  )
}
