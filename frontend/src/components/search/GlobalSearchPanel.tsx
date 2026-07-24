import { type ReactNode } from 'react'
import {
  AlertTriangle,
  ArrowRight,
  Calendar,
  Car,
  ChevronRight,
  ClipboardCheck,
  Clock,
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
import { useTranslation } from 'react-i18next'

import type { GlobalSearchResultRecord } from '../../api/client'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { Card, CardContent } from '../ui/Card'
import { Input } from '../ui/Input'
import { cn } from '../../helpers/utils'
import { getSuggestedSearches } from './suggestedSearches'
import type { useGlobalSearch } from './useGlobalSearch'

type SearchController = ReturnType<typeof useGlobalSearch>

interface GlobalSearchPanelProps {
  search: SearchController
  /** Compact layout for dialog palette */
  compact?: boolean
  showHeader?: boolean
}

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

export default function GlobalSearchPanel({
  search,
  compact = false,
  showHeader = true,
}: GlobalSearchPanelProps) {
  const { t } = useTranslation()
  const suggestions = getSuggestedSearches()
  const {
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
  } = search

  const interpretedLabel =
    interpreted && interpreted.source !== 'keyword'
      ? interpreted.label ||
        [interpreted.module, interpreted.status, interpreted.q].filter(Boolean).join(' · ')
      : null

  return (
    <div className={cn('space-y-4', !compact && 'space-y-6')}>
      {showHeader && !compact && (
        <div className="text-center mb-4">
          <h1 className="text-3xl font-bold text-foreground mb-2 flex items-center justify-center gap-3">
            <Search className="w-8 h-8 text-primary" />
            {t('search.global_title', 'Global Search')}
          </h1>
          <p className="text-muted-foreground">
            {t('search.global_subtitle', 'Search across all modules instantly')}
          </p>
        </div>
      )}

      <div className={cn(!compact && 'max-w-4xl mx-auto')}>
        <div className="relative">
          <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
            {isSearching ? (
              <div className="animate-spin w-5 h-5 border-2 border-primary border-t-transparent rounded-full" />
            ) : (
              <Search className="w-5 h-5 text-muted-foreground" />
            )}
          </div>

          <Input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={t(
              'search.placeholder',
              'Search incidents, RTAs, complaints, risks, audits, actions, documents...',
            )}
            aria-label={t('search', 'Search')}
            className={cn('w-full pl-12 pr-28', compact ? 'py-3 text-base' : 'py-5 text-lg rounded-2xl')}
          />

          <div className="absolute inset-y-0 right-0 flex items-center gap-1 pr-2">
            {query && (
              <Button variant="ghost" size="sm" onClick={clearSearch} aria-label={t('search.clear', 'Clear search')}>
                <X className="w-4 h-4" />
              </Button>
            )}
            <Button
              aria-label={t('search.toggle_filters', 'Toggle filters')}
              variant={showFilters ? 'default' : 'ghost'}
              size="sm"
              onClick={() => setShowFilters(!showFilters)}
            >
              <Filter className="w-4 h-4" />
            </Button>
            <Button size="sm" onClick={() => void handleSearch()}>
              {t('search', 'Search')}
              <ArrowRight className="w-4 h-4" />
            </Button>
          </div>
        </div>

        {interpretedLabel && (
          <div className="mt-2 flex items-center gap-2 text-sm text-muted-foreground">
            {interpreted?.source === 'gemini' ? (
              <Sparkles className="w-4 h-4 text-primary" aria-hidden />
            ) : null}
            <span>
              {t('search.interpreted_as', 'Interpreted as')}{' '}
              <span className="text-foreground font-medium">{interpretedLabel}</span>
            </span>
          </div>
        )}

        {showFilters && (
          <Card className="mt-3">
            <CardContent className="p-4">
              <div className={cn('grid gap-4', compact ? 'grid-cols-1' : 'grid-cols-1 md:grid-cols-3')}>
                <div>
                  <h3 className="text-sm font-medium text-muted-foreground mb-2 flex items-center gap-2">
                    <Tag className="w-4 h-4" /> {t('search.modules', 'Modules')}
                  </h3>
                  <div className="flex flex-wrap gap-2">
                    {Object.keys(moduleIcons).map((module) => (
                      <button
                        key={module}
                        type="button"
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
                <div>
                  <h3 className="text-sm font-medium text-muted-foreground mb-2 flex items-center gap-2">
                    <Clock className="w-4 h-4" /> {t('search.status', 'Status')}
                  </h3>
                  <div className="flex flex-wrap gap-2">
                    {['Open', 'In Progress', 'Closed', 'Overdue'].map((status) => (
                      <button
                        key={status}
                        type="button"
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
                <div>
                  <h3 className="text-sm font-medium text-muted-foreground mb-2 flex items-center gap-2">
                    <Calendar className="w-4 h-4" /> {t('search.date_range', 'Date Range')}
                  </h3>
                  <div className="flex flex-wrap gap-2">
                    {[
                      { label: t('search.date_all', 'All Time'), value: 'all' },
                      { label: t('search.date_today', 'Today'), value: 'today' },
                      { label: t('search.date_week', 'This Week'), value: 'week' },
                      { label: t('search.date_month', 'This Month'), value: 'month' },
                    ].map((option) => (
                      <button
                        key={option.value}
                        type="button"
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

      {!results.length && !query && (
        <div className={cn(!compact && 'max-w-4xl mx-auto')}>
          {searchHistory.length > 0 && (
            <>
              <div className="flex items-center gap-2 text-muted-foreground mb-3">
                <History className="w-4 h-4" />
                <span className="font-medium text-sm">{t('search.recent', 'Recent Searches')}</span>
              </div>
              <div className="flex flex-wrap gap-2 mb-4">
                {searchHistory.map((term) => (
                  <button
                    key={term}
                    type="button"
                    onClick={() => void handleSearch(term)}
                    className="px-3 py-1.5 bg-card border border-border rounded-lg text-sm text-foreground hover:bg-muted transition-all flex items-center gap-2"
                  >
                    <Clock className="w-3.5 h-3.5 text-muted-foreground" />
                    {term}
                  </button>
                ))}
              </div>
            </>
          )}

          <div className="p-4 bg-muted/40 border border-border rounded-xl">
            <div className="flex items-center gap-2 mb-3">
              <Search className="w-5 h-5 text-primary" />
              <span className="font-semibold text-foreground">
                {t('search.suggested_searches', 'Suggested searches')}
              </span>
            </div>
            <div className={cn('grid gap-2', compact ? 'grid-cols-1' : 'grid-cols-1 md:grid-cols-2')}>
              {suggestions.map((suggestion) => (
                <button
                  key={suggestion.id}
                  type="button"
                  onClick={() => void runSuggested(suggestion)}
                  className="p-3 bg-card rounded-lg text-left text-foreground hover:bg-primary/10 transition-all flex items-center justify-between group border border-border"
                >
                  <span>
                    {t(suggestion.labelKey, suggestion.defaultLabel)}
                  </span>
                  <ChevronRight className="w-4 h-4 opacity-0 group-hover:opacity-100 transition-opacity" />
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {results.length > 0 && (
        <div className={cn(!compact && 'max-w-4xl mx-auto')}>
          <p className="text-sm text-muted-foreground mb-3">
            {t('search.showing_results', 'Showing')}{' '}
            <span className="text-foreground font-medium">{results.length}</span> {t('search.of', 'of')}{' '}
            <span className="text-foreground font-medium">{totalResults}</span>{' '}
            {t('search.results_for', 'results for')} &quot;{query}&quot;
          </p>

          <div className="space-y-2" role="list">
            {results.map((result: GlobalSearchResultRecord) => (
              <Card
                key={result.id}
                role="listitem"
                className={cn(
                  'transition-all group',
                  result.path ? 'cursor-pointer hover:border-primary/50' : 'opacity-80',
                )}
                onClick={() => selectResult(result)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    selectResult(result)
                  }
                }}
                tabIndex={result.path ? 0 : -1}
              >
                <CardContent className="p-4">
                  <div className="flex items-start gap-3">
                    <div className={cn('p-2 rounded-xl', moduleColors[result.module])}>
                      {moduleIcons[result.module]}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <h3 className="font-semibold text-foreground group-hover:text-primary transition-colors">
                            {result.title}
                          </h3>
                          <p className="text-xs text-muted-foreground mt-0.5">{result.id}</p>
                        </div>
                        <div className="flex items-center gap-2 shrink-0">
                          <Badge variant={statusVariants[result.status.toLowerCase()] || 'default'}>
                            {result.status.replace(/_/g, ' ')}
                          </Badge>
                          <span className="text-xs text-muted-foreground">
                            {result.date ? new Date(result.date).toLocaleDateString() : ''}
                          </span>
                        </div>
                      </div>
                      <p className="text-muted-foreground mt-1 text-sm line-clamp-2">{result.description}</p>
                      <div className="flex items-center gap-3 mt-2 text-xs text-muted-foreground">
                        <span>{result.module}</span>
                        <span className="ml-auto">{Math.round(result.relevance)}% match</span>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}

      {query && !isSearching && results.length === 0 && (
        <div className={cn('text-center py-8', !compact && 'max-w-4xl mx-auto')}>
          <Search className="w-10 h-10 text-muted-foreground mx-auto mb-3" />
          <h3 className="text-lg font-semibold text-foreground mb-1">
            {t('search.no_results', 'No results found')}
          </h3>
          <p className="text-sm text-muted-foreground">
            {t('search.no_results_hint', 'Try different keywords or adjust your filters')}
          </p>
        </div>
      )}
    </div>
  )
}
