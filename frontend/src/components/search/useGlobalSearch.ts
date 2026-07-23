import { type KeyboardEvent, useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import {
  getApiErrorMessage,
  type GlobalSearchResultRecord,
  type SearchInterpretResponse,
  searchApi,
} from '../../api/client'
import { toast } from '../../contexts/ToastContext'
import { dateRangeToBounds, type SuggestedSearch } from './suggestedSearches'

export interface SearchFilter {
  modules: string[]
  status: string[]
  dateRange: string
}

export interface UseGlobalSearchOptions {
  /** Called after a result is selected (palette closes). */
  onNavigateAway?: () => void
  /** Autofocus input when panel mounts / opens. */
  autofocus?: boolean
  open?: boolean
}

export function useGlobalSearch(options: UseGlobalSearchOptions = {}) {
  const { onNavigateAway, autofocus = true, open = true } = options
  const navigate = useNavigate()

  const [query, setQuery] = useState('')
  const [isSearching, setIsSearching] = useState(false)
  const [results, setResults] = useState<GlobalSearchResultRecord[]>([])
  const [showFilters, setShowFilters] = useState(false)
  const [filters, setFilters] = useState<SearchFilter>({
    modules: [],
    status: [],
    dateRange: 'all',
  })
  const [searchHistory, setSearchHistory] = useState<string[]>([])
  const [totalResults, setTotalResults] = useState(0)
  const [interpreted, setInterpreted] = useState<SearchInterpretResponse | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (autofocus && open) {
      // Defer so Dialog focus trap has mounted
      const id = window.setTimeout(() => inputRef.current?.focus(), 50)
      return () => window.clearTimeout(id)
    }
  }, [autofocus, open])

  const runSearch = useCallback(
    async (params: {
      q: string
      module?: string
      status?: string
      date_from?: string
      date_to?: string
    }) => {
      const activeQuery = params.q.trim()
      if (!activeQuery) return

      setIsSearching(true)
      setQuery(activeQuery)
      setSearchHistory((prev) =>
        prev.includes(activeQuery)
          ? prev
          : [activeQuery, ...prev.filter((term) => term !== activeQuery)].slice(0, 5),
      )

      try {
        // API accepts a single module; multi-select is applied client-side after FTS.
        const moduleParam =
          params.module || (filters.modules.length === 1 ? filters.modules[0] : undefined)
        const statusParam =
          params.status ||
          (filters.status.length > 0
            ? filters.status.map((s) => s.toLowerCase().replace(/\s+/g, '_')).join(',')
            : undefined)
        const dates = {
          ...dateRangeToBounds(filters.dateRange),
          ...(params.date_from ? { date_from: params.date_from } : {}),
          ...(params.date_to ? { date_to: params.date_to } : {}),
        }

        const response = await searchApi.search({
          q: activeQuery,
          module: moduleParam,
          status: statusParam,
          ...dates,
          page: 1,
          page_size: 100,
        })
        let items = response.data.results
        if (!params.module && filters.modules.length > 1) {
          items = items.filter((item) => filters.modules.includes(item.module))
        }
        setResults(items)
        setTotalResults(items.length)
      } catch (error) {
        setResults([])
        setTotalResults(0)
        toast.error(getApiErrorMessage(error))
      } finally {
        setIsSearching(false)
      }
    },
    [filters.dateRange, filters.modules, filters.status],
  )

  // Re-run FTS when filter chips change while a query is active.
  useEffect(() => {
    const active = query.trim()
    if (!active) return
    void runSearch({ q: active })
    // Intentionally depend on filter values + query, not runSearch identity.
    // eslint-disable-next-line react-hooks/exhaustive-deps -- filter-driven refresh
  }, [filters.modules, filters.status, filters.dateRange])

  const handleSearch = useCallback(
    async (overrideQuery?: string) => {
      const activeQuery = (overrideQuery ?? query).trim()
      if (!activeQuery) return

      try {
        const intent = await searchApi.interpret(activeQuery)
        setInterpreted(intent.data)

        if (intent.data.navigate) {
          onNavigateAway?.()
          navigate(intent.data.navigate)
          return
        }

        await runSearch({
          q: intent.data.q || activeQuery,
          module: intent.data.module ?? undefined,
          status: intent.data.status ?? undefined,
          date_from: intent.data.date_from ?? undefined,
          date_to: intent.data.date_to ?? undefined,
        })
      } catch {
        setInterpreted(null)
        await runSearch({ q: activeQuery })
      }
    },
    [navigate, onNavigateAway, query, runSearch],
  )

  const runSuggested = useCallback(
    async (suggestion: SuggestedSearch) => {
      setInterpreted({
        q: suggestion.params.q,
        module: suggestion.params.module ?? null,
        status: suggestion.params.status ?? null,
        date_from: suggestion.params.date_from ?? null,
        date_to: suggestion.params.date_to ?? null,
        navigate: suggestion.navigate ?? null,
        label: suggestion.defaultLabel,
        source: 'suggestion',
      })
      if (suggestion.navigate) {
        onNavigateAway?.()
        navigate(suggestion.navigate)
        return
      }
      await runSearch(suggestion.params)
    },
    [navigate, onNavigateAway, runSearch],
  )

  const selectResult = useCallback(
    (result: GlobalSearchResultRecord) => {
      if (!result.path) return
      onNavigateAway?.()
      navigate(result.path)
    },
    [navigate, onNavigateAway],
  )

  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Enter') {
      void handleSearch()
    }
  }

  const clearSearch = () => {
    setQuery('')
    setResults([])
    setTotalResults(0)
    setInterpreted(null)
    inputRef.current?.focus()
  }

  const applyFilter = (type: keyof SearchFilter, value: string) => {
    setFilters((prev) => {
      if (type === 'dateRange') {
        return { ...prev, dateRange: value }
      }
      const arr = prev[type] as string[]
      if (arr.includes(value)) {
        return { ...prev, [type]: arr.filter((v) => v !== value) }
      }
      return { ...prev, [type]: [...arr, value] }
    })
  }

  return {
    query,
    setQuery,
    isSearching,
    results,
    showFilters,
    setShowFilters,
    filters,
    searchHistory,
    totalResults,
    interpreted,
    inputRef,
    handleSearch,
    handleKeyDown,
    clearSearch,
    applyFilter,
    runSuggested,
    selectResult,
    runSearch,
  }
}
