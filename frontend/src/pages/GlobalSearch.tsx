import { type KeyboardEvent, type ReactNode, useEffect, useRef, useState } from 'react'
import {
  AlertTriangle,
  ArrowRight,
  Calendar,
  Car,
  ChevronRight,
  ClipboardCheck,
  Clock,
  Command,
  FileText,
  Filter,
  History,
  MessageSquare,
  Search,
  Shield,
  Sparkles,
  Tag,
  X,
  Zap,
} from 'lucide-react'

import { getApiErrorMessage, type GlobalSearchResultRecord, searchApi } from '../api/client'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { Card, CardContent } from '../components/ui/Card'
import { Input } from '../components/ui/Input'
import { toast } from '../contexts/ToastContext'
import { cn } from '../helpers/utils'

interface SearchFilter {
  modules: string[]
  status: string[]
  dateRange: string
}

export default function GlobalSearch() {
  const [query, setQuery] = useState('')
  const [isSearching, setIsSearching] = useState(false)
  const [rawResults, setRawResults] = useState<GlobalSearchResultRecord[]>([])
  const [results, setResults] = useState<GlobalSearchResultRecord[]>([])
  const [showFilters, setShowFilters] = useState(false)
  const [filters, setFilters] = useState<SearchFilter>({
    modules: [],
    status: [],
    dateRange: 'all',
  })
  const [searchHistory, setSearchHistory] = useState<string[]>([])
  const [totalResults, setTotalResults] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)

  const moduleIcons: Record<string, ReactNode> = {
    Incidents: <AlertTriangle className="w-5 h-5" />,
    RTAs: <Car className="w-5 h-5" />,
    Complaints: <MessageSquare className="w-5 h-5" />,
    Risks: <Shield className="w-5 h-5" />,
    Audits: <ClipboardCheck className="w-5 h-5" />,
    Actions: <Zap className="w-5 h-5" />,
    Documents: <FileText className="w-5 h-5" />,
  }

  const moduleColors: Record<string, string> = {
    Incidents: 'text-destructive bg-destructive/20',
    RTAs: 'text-warning bg-warning/20',
    Complaints: 'text-primary bg-primary/20',
    Risks: 'text-destructive bg-destructive/20',
    Audits: 'text-success bg-success/20',
    Actions: 'text-info bg-info/20',
    Documents: 'text-info bg-info/20',
  }

  const statusVariants: Record<
    string,
    'warning' | 'info' | 'acknowledged' | 'default' | 'destructive' | 'resolved'
  > = {
    open: 'warning',
    in_progress: 'info',
    under_investigation: 'acknowledged',
    monitoring: 'info',
    scheduled: 'default',
    overdue: 'destructive',
    closed: 'resolved',
    completed: 'resolved',
  }

  const applyClientFilters = (
    items: GlobalSearchResultRecord[],
    activeFilters: SearchFilter,
  ): GlobalSearchResultRecord[] => {
    const now = new Date()
    return items.filter((item) => {
      if (activeFilters.modules.length > 0 && !activeFilters.modules.includes(item.module)) {
        return false
      }

      if (
        activeFilters.status.length > 0 &&
        !activeFilters.status.some((status) => item.status.toLowerCase() === status.toLowerCase().replace(/\s+/g, '_'))
      ) {
        return false
      }

      if (activeFilters.dateRange !== 'all') {
        const itemDate = new Date(item.date)
        if (Number.isNaN(itemDate.getTime())) return false

        if (activeFilters.dateRange === 'today') {
          if (itemDate.toDateString() !== now.toDateString()) return false
        }

        if (activeFilters.dateRange === 'week') {
          const weekAgo = new Date(now)
          weekAgo.setDate(now.getDate() - 7)
          if (itemDate < weekAgo) return false
        }

        if (activeFilters.dateRange === 'month') {
          const monthAgo = new Date(now)
          monthAgo.setMonth(now.getMonth() - 1)
          if (itemDate < monthAgo) return false
        }
      }

      return true
    })
  }

  const handleSearch = async (overrideQuery?: string) => {
    const activeQuery = (overrideQuery ?? query).trim()
    if (!activeQuery) return

    setIsSearching(true)

    if (!searchHistory.includes(activeQuery)) {
      setSearchHistory([activeQuery, ...searchHistory.filter((term) => term !== activeQuery).slice(0, 4)])
    }

    try {
      const response = await searchApi.search({
        q: activeQuery,
        page: 1,
        page_size: 100,
      })
      const filtered = applyClientFilters(response.data.results, filters)
      setRawResults(response.data.results)
      setResults(filtered)
      setTotalResults(response.data.total)
    } catch (error) {
      setRawResults([])
      setResults([])
      setTotalResults(0)
      toast.error(getApiErrorMessage(error))
    } finally {
      setIsSearching(false)
    }
  }

  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSearch()
    }
  }

  const clearSearch = () => {
    setQuery('')
    setRawResults([])
    setResults([])
    setTotalResults(0)
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

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  useEffect(() => {
    setResults(applyClientFilters(rawResults, filters))
  }, [filters, rawResults])

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="text-center mb-8">
        <h1 className="text-4xl font-bold text-foreground mb-3 flex items-center justify-center gap-3">
          <Search className="w-10 h-10 text-primary" />
          Global Search
        </h1>
        <p className="text-muted-foreground text-lg">Search across all modules instantly</p>
        <p className="text-sm text-muted-foreground mt-2 flex items-center justify-center gap-2">
          <Command className="w-4 h-4" /> + K to open from anywhere
        </p>
      </div>

      {/* Search Bar */}
      <div className="max-w-4xl mx-auto">
        <div className="relative">
          <div className="absolute inset-y-0 left-0 pl-5 flex items-center pointer-events-none">
            {isSearching ? (
              <div className="animate-spin w-6 h-6 border-2 border-primary border-t-transparent rounded-full" />
            ) : (
              <Search className="w-6 h-6 text-muted-foreground" />
            )}
          </div>

          <Input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Search incidents, RTAs, complaints, risks, audits, actions, documents..."
            className="w-full pl-14 pr-32 py-5 text-lg rounded-2xl"
          />

          <div className="absolute inset-y-0 right-0 flex items-center gap-2 pr-4">
            {query && (
              <Button variant="ghost" size="sm" onClick={clearSearch} aria-label="Clear search">
                <X className="w-5 h-5" />
              </Button>
            )}

            <Button
              aria-label="Toggle filters"
              variant={showFilters ? 'default' : 'ghost'}
              size="sm"
              onClick={() => setShowFilters(!showFilters)}
            >
              <Filter className="w-5 h-5" />
            </Button>

            <Button onClick={() => void handleSearch()}>
              Search
              <ArrowRight className="w-4 h-4" />
            </Button>
          </div>
        </div>

        {/* Filters */}
        {showFilters && (
          <Card className="mt-4 animate-in slide-in-from-top duration-200">
            <CardContent className="p-4">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {/* Module Filters */}
                <div>
                  <h3 className="text-sm font-medium text-muted-foreground mb-3 flex items-center gap-2">
                    <Tag className="w-4 h-4" /> Modules
                  </h3>
                  <div className="flex flex-wrap gap-2">
                    {Object.keys(moduleIcons).map((module) => (
                      <button
                        key={module}
                        onClick={() => applyFilter('modules', module)}
                        className={cn(
                          'px-3 py-1.5 rounded-lg text-sm font-medium transition-all',
                          filters.modules.includes(module)
                            ? 'bg-primary text-primary-foreground'
                            : 'bg-muted text-muted-foreground hover:text-foreground',
                        )}
                      >
                        {module}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Status Filters */}
                <div>
                  <h3 className="text-sm font-medium text-muted-foreground mb-3 flex items-center gap-2">
                    <Clock className="w-4 h-4" /> Status
                  </h3>
                  <div className="flex flex-wrap gap-2">
                    {['Open', 'In Progress', 'Closed', 'Overdue'].map((status) => (
                      <button
                        key={status}
                        onClick={() => applyFilter('status', status)}
                        className={cn(
                          'px-3 py-1.5 rounded-lg text-sm font-medium transition-all',
                          filters.status.includes(status)
                            ? 'bg-primary text-primary-foreground'
                            : 'bg-muted text-muted-foreground hover:text-foreground',
                        )}
                      >
                        {status}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Date Range */}
                <div>
                  <h3 className="text-sm font-medium text-muted-foreground mb-3 flex items-center gap-2">
                    <Calendar className="w-4 h-4" /> Date Range
                  </h3>
                  <div className="flex flex-wrap gap-2">
                    {[
                      { label: 'All Time', value: 'all' },
                      { label: 'Today', value: 'today' },
                      { label: 'This Week', value: 'week' },
                      { label: 'This Month', value: 'month' },
                    ].map((option) => (
                      <button
                        key={option.value}
                        onClick={() => applyFilter('dateRange', option.value)}
                        className={cn(
                          'px-3 py-1.5 rounded-lg text-sm font-medium transition-all',
                          filters.dateRange === option.value
                            ? 'bg-primary text-primary-foreground'
                            : 'bg-muted text-muted-foreground hover:text-foreground',
                        )}
                      >
                        {option.label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Search History / Suggestions */}
      {!results.length && !query && (
        <div className="max-w-4xl mx-auto">
          {searchHistory.length > 0 && (
            <>
              <div className="flex items-center gap-2 text-muted-foreground mb-4">
                <History className="w-5 h-5" />
                <span className="font-medium">Recent Searches</span>
              </div>
              <div className="flex flex-wrap gap-3">
                {searchHistory.map((term, i) => (
                  <button
                    key={i}
                    onClick={() => {
                      setQuery(term)
                      void handleSearch(term)
                    }}
                    className="px-4 py-2 bg-card border border-border rounded-lg text-foreground hover:bg-muted hover:text-foreground transition-all flex items-center gap-2"
                  >
                    <Clock className="w-4 h-4 text-muted-foreground" />
                    {term}
                  </button>
                ))}
              </div>
            </>
          )}

          {/* AI Suggestions */}
          <div className="mt-8 p-6 bg-gradient-to-r from-primary/10 to-primary/5 border border-primary/30 rounded-xl">
            <div className="flex items-center gap-3 mb-4">
              <Sparkles className="w-6 h-6 text-primary" />
              <span className="font-semibold text-foreground">AI-Powered Suggestions</span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {[
                'Show all overdue actions',
                'Recent high-priority incidents',
                'Pending ISO audits this month',
                'Unresolved customer complaints',
              ].map((suggestion, i) => (
                <button
                  key={i}
                  onClick={() => {
                    setQuery(suggestion)
                    void handleSearch(suggestion)
                  }}
                  className="p-3 bg-card rounded-lg text-left text-foreground hover:bg-primary/20 transition-all flex items-center justify-between group"
                >
                  <span>{suggestion}</span>
                  <ChevronRight className="w-4 h-4 opacity-0 group-hover:opacity-100 transition-opacity" />
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Search Results */}
      {results.length > 0 && (
        <div className="max-w-4xl mx-auto">
          <div className="flex items-center justify-between mb-4">
            <p className="text-muted-foreground">
              Showing <span className="text-foreground font-medium">{results.length}</span> of{' '}
              <span className="text-foreground font-medium">{totalResults}</span> results
              for "{query}"
            </p>
          </div>

          <div className="space-y-4">
            {results.map((result) => (
              <Card
                key={result.id}
                className="hover:border-primary/50 transition-all group cursor-pointer"
              >
                <CardContent className="p-5">
                  <div className="flex items-start gap-4">
                    <div className={cn('p-3 rounded-xl', moduleColors[result.module])}>
                      {moduleIcons[result.module]}
                    </div>

                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <h3 className="font-semibold text-foreground group-hover:text-primary transition-colors">
                            {result.title}
                          </h3>
                          <p className="text-sm text-muted-foreground mt-0.5">{result.id}</p>
                        </div>

                        <div className="flex items-center gap-2">
                          <Badge variant={statusVariants[result.status.toLowerCase()] || 'default'}>
                            {result.status.replace(/_/g, ' ')}
                          </Badge>
                          <span className="text-xs text-muted-foreground">
                            {new Date(result.date).toLocaleDateString()}
                          </span>
                        </div>
                      </div>

                      <p className="text-muted-foreground mt-2 text-sm line-clamp-2">
                        {result.description}
                      </p>

                      <div className="flex items-center gap-4 mt-3">
                        <span className="text-xs text-muted-foreground">{result.module}</span>
                        <div className="flex items-center gap-1">
                          {result.highlights.map((tag, i) => (
                            <span
                              key={i}
                              className="px-2 py-0.5 bg-primary/20 text-primary rounded text-xs"
                            >
                              {tag}
                            </span>
                          ))}
                        </div>
                        <div className="ml-auto flex items-center gap-1 text-xs text-muted-foreground">
                          <Sparkles className="w-3 h-3 text-primary" />
                          {Math.round(result.relevance)}% match
                        </div>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}

      {/* No Results */}
      {query && !isSearching && results.length === 0 && (
        <div className="max-w-4xl mx-auto text-center py-12">
          <div className="w-20 h-20 bg-muted rounded-full flex items-center justify-center mx-auto mb-4">
            <Search className="w-10 h-10 text-muted-foreground" />
          </div>
          <h3 className="text-xl font-semibold text-foreground mb-2">No results found</h3>
          <p className="text-muted-foreground">Try different keywords or adjust your filters</p>
        </div>
      )}
    </div>
  )
}
