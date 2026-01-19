import { useState, useEffect, useRef } from 'react';
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
  const [_suggestions] = useState<string[]>([]); void _suggestions;
  const inputRef = useRef<HTMLInputElement>(null);

  // Mock search results
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
    'Incidents': 'text-red-400 bg-red-500/20',
    'RTAs': 'text-amber-400 bg-amber-500/20',
    'Complaints': 'text-purple-400 bg-purple-500/20',
    'Risks': 'text-rose-400 bg-rose-500/20',
    'Audits': 'text-emerald-400 bg-emerald-500/20',
    'Actions': 'text-blue-400 bg-blue-500/20',
    'Documents': 'text-sky-400 bg-sky-500/20'
  };

  const statusColors: Record<string, string> = {
    'Open': 'text-amber-400 bg-amber-500/20',
    'In Progress': 'text-blue-400 bg-blue-500/20',
    'Under Investigation': 'text-purple-400 bg-purple-500/20',
    'Monitoring': 'text-cyan-400 bg-cyan-500/20',
    'Scheduled': 'text-indigo-400 bg-indigo-500/20',
    'Overdue': 'text-red-400 bg-red-500/20',
    'Closed': 'text-emerald-400 bg-emerald-500/20'
  };

  const handleSearch = () => {
    if (!query.trim()) return;
    
    setIsSearching(true);
    
    // Add to history
    if (!searchHistory.includes(query)) {
      setSearchHistory([query, ...searchHistory.slice(0, 4)]);
    }
    
    // Simulate search delay
    setTimeout(() => {
      setResults(mockResults.filter(r => 
        r.title.toLowerCase().includes(query.toLowerCase()) ||
        r.description.toLowerCase().includes(query.toLowerCase()) ||
        r.module.toLowerCase().includes(query.toLowerCase())
      ));
      setIsSearching(false);
    }, 500);
  };

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

  // Auto-focus on mount
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="text-center mb-8">
        <h1 className="text-4xl font-bold text-white mb-3 flex items-center justify-center gap-3">
          <Search className="w-10 h-10 text-violet-400" />
          Global Search
        </h1>
        <p className="text-slate-400 text-lg">Search across all modules instantly</p>
        <p className="text-sm text-slate-500 mt-2 flex items-center justify-center gap-2">
          <Command className="w-4 h-4" /> + K to open from anywhere
        </p>
      </div>

      {/* Search Bar */}
      <div className="max-w-4xl mx-auto">
        <div className="relative">
          <div className="absolute inset-y-0 left-0 pl-5 flex items-center pointer-events-none">
            {isSearching ? (
              <div className="animate-spin w-6 h-6 border-2 border-violet-400 border-t-transparent rounded-full" />
            ) : (
              <Search className="w-6 h-6 text-slate-400" />
            )}
          </div>
          
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Search incidents, RTAs, complaints, risks, audits, actions, documents..."
            className="w-full pl-14 pr-32 py-5 bg-slate-800/80 backdrop-blur-sm border border-slate-700 rounded-2xl text-white text-lg placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-transparent transition-all"
          />
          
          <div className="absolute inset-y-0 right-0 flex items-center gap-2 pr-4">
            {query && (
              <button
                onClick={clearSearch}
                className="p-2 text-slate-400 hover:text-white transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            )}
            
            <button
              onClick={() => setShowFilters(!showFilters)}
              className={`p-2 rounded-lg transition-all ${
                showFilters ? 'bg-violet-500 text-white' : 'text-slate-400 hover:text-white'
              }`}
            >
              <Filter className="w-5 h-5" />
            </button>
            
            <button
              onClick={handleSearch}
              className="px-4 py-2 bg-gradient-to-r from-violet-600 to-purple-600 text-white font-medium rounded-xl hover:from-violet-500 hover:to-purple-500 transition-all flex items-center gap-2"
            >
              Search
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Filters */}
        {showFilters && (
          <div className="mt-4 p-4 bg-slate-800/80 backdrop-blur-sm border border-slate-700 rounded-xl animate-in slide-in-from-top duration-200">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {/* Module Filters */}
              <div>
                <h3 className="text-sm font-medium text-slate-400 mb-3 flex items-center gap-2">
                  <Tag className="w-4 h-4" /> Modules
                </h3>
                <div className="flex flex-wrap gap-2">
                  {Object.keys(moduleIcons).map((module) => (
                    <button
                      key={module}
                      onClick={() => applyFilter('modules', module)}
                      className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
                        filters.modules.includes(module)
                          ? 'bg-violet-500 text-white'
                          : 'bg-slate-700/50 text-slate-400 hover:text-white'
                      }`}
                    >
                      {module}
                    </button>
                  ))}
                </div>
              </div>

              {/* Status Filters */}
              <div>
                <h3 className="text-sm font-medium text-slate-400 mb-3 flex items-center gap-2">
                  <Clock className="w-4 h-4" /> Status
                </h3>
                <div className="flex flex-wrap gap-2">
                  {['Open', 'In Progress', 'Closed', 'Overdue'].map((status) => (
                    <button
                      key={status}
                      onClick={() => applyFilter('status', status)}
                      className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
                        filters.status.includes(status)
                          ? 'bg-violet-500 text-white'
                          : 'bg-slate-700/50 text-slate-400 hover:text-white'
                      }`}
                    >
                      {status}
                    </button>
                  ))}
                </div>
              </div>

              {/* Date Range */}
              <div>
                <h3 className="text-sm font-medium text-slate-400 mb-3 flex items-center gap-2">
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
                      className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
                        filters.dateRange === option.value
                          ? 'bg-violet-500 text-white'
                          : 'bg-slate-700/50 text-slate-400 hover:text-white'
                      }`}
                    >
                      {option.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Search History / Suggestions */}
      {!results.length && !query && (
        <div className="max-w-4xl mx-auto">
          <div className="flex items-center gap-2 text-slate-400 mb-4">
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
                className="px-4 py-2 bg-slate-800/50 border border-slate-700/50 rounded-lg text-slate-300 hover:bg-slate-700/50 hover:text-white transition-all flex items-center gap-2"
              >
                <Clock className="w-4 h-4 text-slate-500" />
                {term}
              </button>
            ))}
          </div>
          
          {/* AI Suggestions */}
          <div className="mt-8 p-6 bg-gradient-to-r from-violet-500/10 to-purple-500/10 border border-violet-500/30 rounded-xl">
            <div className="flex items-center gap-3 mb-4">
              <Sparkles className="w-6 h-6 text-violet-400" />
              <span className="font-semibold text-white">AI-Powered Suggestions</span>
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
                  className="p-3 bg-slate-800/50 rounded-lg text-left text-slate-300 hover:bg-violet-500/20 hover:text-white transition-all flex items-center justify-between group"
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
            <p className="text-slate-400">
              Found <span className="text-white font-medium">{results.length}</span> results for "{query}"
            </p>
          </div>
          
          <div className="space-y-4">
            {results.map((result) => (
              <div
                key={result.id}
                className="bg-slate-800/50 backdrop-blur-sm border border-slate-700/50 rounded-xl p-5 hover:border-violet-500/50 transition-all group cursor-pointer"
              >
                <div className="flex items-start gap-4">
                  <div className={`p-3 rounded-xl ${moduleColors[result.module]}`}>
                    {moduleIcons[result.module]}
                  </div>
                  
                  <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <h3 className="font-semibold text-white group-hover:text-violet-400 transition-colors">
                          {result.title}
                        </h3>
                        <p className="text-sm text-slate-500 mt-0.5">{result.id}</p>
                      </div>
                      
                      <div className="flex items-center gap-2">
                        <span className={`px-2 py-1 rounded-full text-xs font-medium ${statusColors[result.status]}`}>
                          {result.status}
                        </span>
                        <span className="text-xs text-slate-500">{result.date}</span>
                      </div>
                    </div>
                    
                    <p className="text-slate-400 mt-2 text-sm line-clamp-2">
                      {result.description}
                    </p>
                    
                    <div className="flex items-center gap-4 mt-3">
                      <span className="text-xs text-slate-500">{result.module}</span>
                      <div className="flex items-center gap-1">
                        {result.highlights.map((tag, i) => (
                          <span
                            key={i}
                            className="px-2 py-0.5 bg-violet-500/20 text-violet-400 rounded text-xs"
                          >
                            {tag}
                          </span>
                        ))}
                      </div>
                      <div className="ml-auto flex items-center gap-1 text-xs text-slate-500">
                        <Sparkles className="w-3 h-3 text-violet-400" />
                        {result.relevance}% match
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* No Results */}
      {query && !isSearching && results.length === 0 && (
        <div className="max-w-4xl mx-auto text-center py-12">
          <div className="w-20 h-20 bg-slate-800/50 rounded-full flex items-center justify-center mx-auto mb-4">
            <Search className="w-10 h-10 text-slate-600" />
          </div>
          <h3 className="text-xl font-semibold text-white mb-2">No results found</h3>
          <p className="text-slate-400">
            Try different keywords or adjust your filters
          </p>
        </div>
      )}
    </div>
  );
}
