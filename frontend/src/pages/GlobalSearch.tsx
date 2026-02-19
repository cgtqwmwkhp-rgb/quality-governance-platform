import { useState, useEffect, useRef, useCallback } from 'react';
import {
  Search,
  X,
  Filter,
  FileText,
  AlertTriangle,
  Car,
  MessageSquare,
  Shield,
  ClipboardCheck,
  Zap,
  Clock,
  ChevronRight,
  History,
  Sparkles,
  Command,
  ArrowRight,
  Tag,
  Calendar
} from 'lucide-react';
import { cn } from "../helpers/utils";
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Card, CardContent } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { searchApi } from '../api/client';

interface SearchResult {
  id: string;
  type: 'incident' | 'rta' | 'complaint' | 'risk' | 'audit' | 'action' | 'document';
  title: string;
  description: string;
  module: string;
  status: string;
  date: string;
  relevance: number;
  highlights: string[];
}

interface SearchFilter {
  modules: string[];
  status: string[];
  dateRange: string;
}

export default function GlobalSearch() {
  const [query, setQuery] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const [results, setResults] = useState<SearchResult[]>([]);
  const [showFilters, setShowFilters] = useState(false);
  const [filters, setFilters] = useState<SearchFilter>({
    modules: [],
    status: [],
    dateRange: 'all'
  });
  const [searchHistory, setSearchHistory] = useState<string[]>([
    'safety incident report',
    'overdue actions',
    'ISO 9001 audit',
    'vehicle collision',
    'customer complaint'
  ]);
  const inputRef = useRef<HTMLInputElement>(null);

  const mockResults: SearchResult[] = [
    {
      id: 'INC-2024-0847',
      type: 'incident',
      title: 'Workplace Safety Incident - Warehouse Zone B',
      description: 'Employee reported slip hazard near loading dock area. Immediate action required.',
      module: 'Incidents',
      status: 'Open',
      date: '2024-01-15',
      relevance: 98,
      highlights: ['safety', 'incident', 'warehouse']
    },
    {
      id: 'RTA-2024-0234',
      type: 'rta',
      title: 'Vehicle Collision - Fleet Vehicle PLT-001',
      description: 'Minor collision reported at customer site. No injuries. Vehicle damage assessment pending.',
      module: 'RTAs',
      status: 'Under Investigation',
      date: '2024-01-14',
      relevance: 92,
      highlights: ['vehicle', 'collision', 'fleet']
    },
    {
      id: 'CMP-2024-0456',
      type: 'complaint',
      title: 'Customer Service Response Time',
      description: 'Customer complained about delayed response to service request. SLA breach identified.',
      module: 'Complaints',
      status: 'In Progress',
      date: '2024-01-13',
      relevance: 85,
      highlights: ['customer', 'service', 'response']
    },
    {
      id: 'RSK-2024-0089',
      type: 'risk',
      title: 'Supply Chain Disruption Risk',
      description: 'High risk identified for Q2 supply chain delays. Mitigation measures being implemented.',
      module: 'Risks',
      status: 'Monitoring',
      date: '2024-01-12',
      relevance: 78,
      highlights: ['supply', 'chain', 'risk']
    },
    {
      id: 'AUD-2024-0156',
      type: 'audit',
      title: 'ISO 9001:2015 Internal Audit',
      description: 'Scheduled internal audit for quality management system compliance verification.',
      module: 'Audits',
      status: 'Scheduled',
      date: '2024-01-20',
      relevance: 72,
      highlights: ['ISO', 'audit', 'quality']
    },
    {
      id: 'ACT-2024-0523',
      type: 'action',
      title: 'Update Emergency Procedures',
      description: 'Action item to update emergency evacuation procedures following safety review.',
      module: 'Actions',
      status: 'Overdue',
      date: '2024-01-10',
      relevance: 65,
      highlights: ['emergency', 'procedures', 'safety']
    }
  ];

  const moduleIcons: Record<string, React.ReactNode> = {
    'Incidents': <AlertTriangle className="w-5 h-5" />,
    'RTAs': <Car className="w-5 h-5" />,
    'Complaints': <MessageSquare className="w-5 h-5" />,
    'Risks': <Shield className="w-5 h-5" />,
    'Audits': <ClipboardCheck className="w-5 h-5" />,
    'Actions': <Zap className="w-5 h-5" />,
    'Documents': <FileText className="w-5 h-5" />
  };

  const moduleColors: Record<string, string> = {
    'Incidents': 'text-destructive bg-destructive/20',
    'RTAs': 'text-warning bg-warning/20',
    'Complaints': 'text-primary bg-primary/20',
    'Risks': 'text-destructive bg-destructive/20',
    'Audits': 'text-success bg-success/20',
    'Actions': 'text-info bg-info/20',
    'Documents': 'text-info bg-info/20'
  };

  const statusVariants: Record<string, 'warning' | 'info' | 'acknowledged' | 'default' | 'destructive' | 'resolved'> = {
    'Open': 'warning',
    'In Progress': 'info',
    'Under Investigation': 'acknowledged',
    'Monitoring': 'info',
    'Scheduled': 'default',
    'Overdue': 'destructive',
    'Closed': 'resolved'
  };

  const handleSearch = useCallback(async () => {
    if (!query.trim()) return;

    setIsSearching(true);

    if (!searchHistory.includes(query)) {
      setSearchHistory(prev => [query, ...prev.slice(0, 4)]);
    }

    try {
      const resp = await searchApi.search(query, {
        module: filters.modules.length === 1 ? filters.modules[0] : undefined,
      });
      const data = resp as { results?: SearchResult[]; total?: number };
      const items = Array.isArray(data?.results) ? data.results : [];
      setResults(items.map(r => ({
        id: r.id || '',
        type: (r.type || 'document') as SearchResult['type'],
        title: r.title || '',
        description: r.description || '',
        module: r.module || '',
        status: r.status || '',
        date: r.date || '',
        relevance: r.relevance || 0,
        highlights: Array.isArray(r.highlights) ? r.highlights : [],
      })));
    } catch (err) {
      console.error('Search failed, falling back to local results', err);
      setResults(mockResults.filter(r =>
        r.title.toLowerCase().includes(query.toLowerCase()) ||
        r.description.toLowerCase().includes(query.toLowerCase()) ||
        r.module.toLowerCase().includes(query.toLowerCase())
      ));
    } finally {
      setIsSearching(false);
    }
  }, [query, filters.modules]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSearch();
    }
  };

  const clearSearch = () => {
    setQuery('');
    setResults([]);
    inputRef.current?.focus();
  };

  const applyFilter = (type: keyof SearchFilter, value: string) => {
    setFilters(prev => {
      if (type === 'dateRange') {
        return { ...prev, dateRange: value };
      }
      const arr = prev[type] as string[];
      if (arr.includes(value)) {
        return { ...prev, [type]: arr.filter(v => v !== value) };
      }
      return { ...prev, [type]: [...arr, value] };
    });
  };

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

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
              <Button variant="ghost" size="sm" onClick={clearSearch}>
                <X className="w-5 h-5" />
              </Button>
            )}
            
            <Button
              variant={showFilters ? 'default' : 'ghost'}
              size="sm"
              onClick={() => setShowFilters(!showFilters)}
            >
              <Filter className="w-5 h-5" />
            </Button>
            
            <Button onClick={handleSearch}>
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
                          "px-3 py-1.5 rounded-lg text-sm font-medium transition-all",
                          filters.modules.includes(module)
                            ? 'bg-primary text-primary-foreground'
                            : 'bg-muted text-muted-foreground hover:text-foreground'
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
                          "px-3 py-1.5 rounded-lg text-sm font-medium transition-all",
                          filters.status.includes(status)
                            ? 'bg-primary text-primary-foreground'
                            : 'bg-muted text-muted-foreground hover:text-foreground'
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
                      { label: 'This Month', value: 'month' }
                    ].map((option) => (
                      <button
                        key={option.value}
                        onClick={() => applyFilter('dateRange', option.value)}
                        className={cn(
                          "px-3 py-1.5 rounded-lg text-sm font-medium transition-all",
                          filters.dateRange === option.value
                            ? 'bg-primary text-primary-foreground'
                            : 'bg-muted text-muted-foreground hover:text-foreground'
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
          <div className="flex items-center gap-2 text-muted-foreground mb-4">
            <History className="w-5 h-5" />
            <span className="font-medium">Recent Searches</span>
          </div>
          <div className="flex flex-wrap gap-3">
            {searchHistory.map((term, i) => (
              <button
                key={i}
                onClick={() => {
                  setQuery(term);
                  handleSearch();
                }}
                className="px-4 py-2 bg-card border border-border rounded-lg text-foreground hover:bg-muted hover:text-foreground transition-all flex items-center gap-2"
              >
                <Clock className="w-4 h-4 text-muted-foreground" />
                {term}
              </button>
            ))}
          </div>
          
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
                'Unresolved customer complaints'
              ].map((suggestion, i) => (
                <button
                  key={i}
                  onClick={() => setQuery(suggestion)}
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
              Found <span className="text-foreground font-medium">{results.length}</span> results for "{query}"
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
                    <div className={cn("p-3 rounded-xl", moduleColors[result.module])}>
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
                          <Badge variant={statusVariants[result.status] || 'default'}>
                            {result.status}
                          </Badge>
                          <span className="text-xs text-muted-foreground">{result.date}</span>
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
                          {result.relevance}% match
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
          <p className="text-muted-foreground">
            Try different keywords or adjust your filters
          </p>
        </div>
      )}
    </div>
  );
}
