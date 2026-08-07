import { useEffect, useId, useMemo, useRef, useState } from 'react'
import { Loader2, Search, Users, X } from 'lucide-react'
import { workforceApi, type EngineerProfile } from '../api/client'
import {
  ACTIVE_EMPLOYEES_LIST_PARAMS,
  employeePickerOptionLabel,
  employeePrimaryLabel,
  sortEmployeesForPicker,
} from '../pages/workforce/employeePickerUtils'
import { cn } from '../helpers/utils'
import { IconButton } from './ui/IconButton'
import { Input } from './ui/Input'
import { Label } from './ui/Label'
import {
  formatPersonNameCopy,
  personNameFieldCopy,
  type PersonNameFieldCopy,
} from './personNameFieldI18n'

/** Controlled value for person name surfaces (witnesses, named roles, etc.). */
export type PersonNameValue = {
  displayName: string
  engineerId?: number | null
}

export type PersonNameFieldMode = 'hybrid' | 'employeesOnly'

export type PersonNameFieldProps = {
  value?: PersonNameValue | null
  onChange: (value: PersonNameValue | null) => void
  /** `hybrid` allows free-text when no employee is selected; `employeesOnly` requires a roster pick. */
  mode?: PersonNameFieldMode
  label?: string
  placeholder?: string
  required?: boolean
  disabled?: boolean
  className?: string
  id?: string
  testId?: string
  /** Language for chunked copy (`en` / `cy`). Defaults to English. */
  lang?: string
  copy?: Partial<PersonNameFieldCopy>
}

/**
 * Hybrid employee smart-lookup with optional free-text fallback.
 * Reuses the active Engineers roster + picker label helpers from EngineerPeoplePicker.
 */
export function PersonNameField({
  value = null,
  onChange,
  mode = 'hybrid',
  label,
  placeholder,
  required = false,
  disabled = false,
  className,
  id,
  testId = 'person-name-field',
  lang,
  copy: copyOverrides,
}: PersonNameFieldProps) {
  const baseCopy = personNameFieldCopy(lang)
  const copy = { ...baseCopy, ...copyOverrides }
  const generatedId = useId()
  const inputId = id ?? generatedId
  const listboxId = `${inputId}-listbox`

  const [query, setQuery] = useState(value?.displayName ?? '')
  const [engineers, setEngineers] = useState<EngineerProfile[]>([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setLoadError(false)
    workforceApi
      .listEngineers({ ...ACTIVE_EMPLOYEES_LIST_PARAMS })
      .then((res) => {
        if (!cancelled) {
          setEngineers(sortEmployeesForPicker(res.data.items || []))
          setLoadError(false)
        }
      })
      .catch(() => {
        if (!cancelled) {
          setEngineers([])
          setLoadError(true)
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    setQuery(value?.displayName ?? '')
  }, [value?.displayName])

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase()
    if (!needle) return engineers
    return engineers.filter((eng) => {
      const optionLabel = employeePickerOptionLabel(eng).toLowerCase()
      const email = (eng.linked_user?.email || '').toLowerCase()
      return optionLabel.includes(needle) || email.includes(needle)
    })
  }, [engineers, query])

  const trimmedQuery = query.trim()
  const exactEmployeeMatch = useMemo(() => {
    if (!trimmedQuery) return null
    return (
      engineers.find(
        (eng) => employeePrimaryLabel(eng).toLowerCase() === trimmedQuery.toLowerCase(),
      ) ?? null
    )
  }, [engineers, trimmedQuery])

  const showFreeTextOption =
    mode === 'hybrid' &&
    trimmedQuery.length > 0 &&
    value?.engineerId == null &&
    !exactEmployeeMatch

  const selectEmployee = (eng: EngineerProfile) => {
    const displayName = employeePrimaryLabel(eng)
    setQuery(displayName)
    setOpen(false)
    onChange({ displayName, engineerId: eng.id })
  }

  const selectFreeText = (name: string) => {
    const displayName = name.trim()
    if (!displayName) {
      setQuery('')
      setOpen(false)
      onChange(null)
      return
    }
    setQuery(displayName)
    setOpen(false)
    onChange({ displayName, engineerId: null })
  }

  const handleInputChange = (next: string) => {
    setQuery(next)
    setOpen(true)
    const trimmed = next.trim()
    if (!trimmed) {
      onChange(null)
      return
    }
    if (mode === 'hybrid') {
      onChange({ displayName: next, engineerId: null })
    } else {
      onChange(null)
    }
  }

  const handleClear = () => {
    setQuery('')
    setOpen(false)
    onChange(null)
  }

  const resolvedPlaceholder = placeholder ?? copy.placeholder
  const clearLabel = label ? `${copy.clear} ${label}` : copy.clear

  return (
    <div
      ref={containerRef}
      className={cn('relative min-w-[220px]', className)}
      data-testid={testId}
    >
      {label ? (
        <Label htmlFor={inputId} required={required} className="mb-1 block text-foreground">
          {label}
        </Label>
      ) : null}

      <div className="relative">
        <Search
          aria-hidden="true"
          className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground"
        />
        <Input
          id={inputId}
          role="combobox"
          value={query}
          disabled={disabled}
          required={required}
          autoComplete="off"
          placeholder={resolvedPlaceholder}
          aria-label={label ? undefined : resolvedPlaceholder}
          aria-expanded={open}
          aria-controls={listboxId}
          aria-haspopup="listbox"
          aria-autocomplete="list"
          aria-busy={loading || undefined}
          aria-invalid={loadError || undefined}
          className="h-9 pl-8 pr-16"
          onChange={(e) => handleInputChange(e.target.value)}
          onFocus={() => setOpen(true)}
          onKeyDown={(e) => {
            if (e.key === 'Escape') {
              setOpen(false)
            }
            if (e.key === 'Enter' && mode === 'hybrid' && showFreeTextOption) {
              e.preventDefault()
              selectFreeText(query)
            }
          }}
        />
        {loading ? (
          <Loader2
            aria-hidden="true"
            className="absolute right-8 top-1/2 h-3.5 w-3.5 -translate-y-1/2 animate-spin text-muted-foreground"
          />
        ) : null}
        {query && !disabled ? (
          <IconButton
            label={clearLabel}
            onClick={handleClear}
            className="absolute right-2 top-1/2 h-auto w-auto -translate-y-1/2 rounded p-1 hover:bg-muted"
          >
            <X className="h-3.5 w-3.5 text-muted-foreground" aria-hidden="true" />
          </IconButton>
        ) : null}
      </div>

      {value?.engineerId != null ? (
        <p className="mt-1 text-xs text-muted-foreground" data-testid={`${testId}-linked`}>
          {copy.selectedEmployee}
        </p>
      ) : value?.displayName?.trim() && mode === 'hybrid' ? (
        <p className="mt-1 text-xs text-muted-foreground" data-testid={`${testId}-free-text`}>
          {copy.freeTextHint}
        </p>
      ) : null}

      {open && !disabled ? (
        <ul
          id={listboxId}
          role="listbox"
          className="absolute z-50 mt-1 max-h-56 w-full overflow-auto rounded-md border border-border bg-card shadow-md"
          data-testid={`${testId}-listbox`}
        >
          {loading ? (
            <li className="px-3 py-2 text-sm text-muted-foreground" role="presentation">
              {copy.loading}
            </li>
          ) : null}

          {!loading && loadError ? (
            <li className="px-3 py-2 text-sm text-destructive" role="presentation">
              {copy.loadFailed}
            </li>
          ) : null}

          {!loading &&
            filtered.map((eng) => {
              const optionLabel = employeePickerOptionLabel(eng)
              const selected = value?.engineerId === eng.id
              return (
                <li key={eng.id} role="presentation">
                  <button
                    type="button"
                    role="option"
                    aria-selected={selected}
                    className={cn(
                      'flex w-full cursor-pointer items-start gap-2 px-3 py-2 text-left text-sm hover:bg-muted',
                      selected && 'bg-muted',
                    )}
                    onClick={() => selectEmployee(eng)}
                  >
                    <Users
                      className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary"
                      aria-hidden="true"
                    />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-medium text-foreground">
                        {optionLabel}
                      </span>
                      {eng.linked_user?.email ? (
                        <span className="block text-xs text-muted-foreground">
                          {eng.linked_user.email}
                        </span>
                      ) : null}
                    </span>
                  </button>
                </li>
              )
            })}

          {!loading && filtered.length === 0 && !showFreeTextOption ? (
            <li className="px-3 py-2 text-sm text-muted-foreground" role="presentation">
              {copy.noEmployees}
            </li>
          ) : null}

          {showFreeTextOption ? (
            <li role="presentation" className="border-t border-border">
              <button
                type="button"
                role="option"
                aria-selected={false}
                className="w-full cursor-pointer px-3 py-2 text-left text-sm text-foreground hover:bg-muted"
                data-testid={`${testId}-use-free-text`}
                onClick={() => selectFreeText(query)}
              >
                {formatPersonNameCopy(copy.useFreeText, trimmedQuery)}
              </button>
            </li>
          ) : null}
        </ul>
      ) : null}
    </div>
  )
}
