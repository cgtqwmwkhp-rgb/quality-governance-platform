/**
 * ISO Tag Selector Component
 * 
 * Reusable component for tagging any content with ISO clause references.
 * Can be embedded in any form across the platform (documents, audits, incidents, etc.)
 * 
 * Features:
 * - Manual clause selection with search
 * - AI auto-tagging from content
 * - Multi-standard support (9001, 14001, 45001)
 * - Visual clause badges
 */

import React, { useState, useMemo } from 'react';
import {
  Award,
  Leaf,
  HardHat,
  Search,
  X,
  ChevronDown,
  Plus,
  Sparkles,
  CheckCircle2,
  AlertCircle,
} from 'lucide-react';
import { ISO_STANDARDS, ISOClause, getAllClauses, autoTagContent, searchClauses } from '../data/isoStandards';

interface ISOTagSelectorProps {
  selectedClauses: string[];
  onChange: (clauses: string[]) => void;
  contentForAutoTag?: string;
  compact?: boolean;
  label?: string;
  showAutoTag?: boolean;
}

const standardIcons: Record<string, React.ElementType> = {
  iso9001: Award,
  iso14001: Leaf,
  iso45001: HardHat,
};

const standardColors: Record<string, { bg: string; text: string; border: string }> = {
  iso9001: { bg: 'bg-blue-500/20', text: 'text-blue-400', border: 'border-blue-500' },
  iso14001: { bg: 'bg-green-500/20', text: 'text-green-400', border: 'border-green-500' },
  iso45001: { bg: 'bg-orange-500/20', text: 'text-orange-400', border: 'border-orange-500' },
};

export default function ISOTagSelector({
  selectedClauses,
  onChange,
  contentForAutoTag,
  compact = false,
  label = 'ISO Clause Tags',
  showAutoTag = true,
}: ISOTagSelectorProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedStandard, setSelectedStandard] = useState<string>('all');
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [autoTagSuggestions, setAutoTagSuggestions] = useState<ISOClause[]>([]);

  // Get clause objects for selected IDs
  const selectedClauseObjects = useMemo(() => {
    return selectedClauses.map(id => getAllClauses().find(c => c.id === id)).filter(Boolean) as ISOClause[];
  }, [selectedClauses]);

  // Filter clauses based on search
  const filteredClauses = useMemo(() => {
    let clauses = searchQuery ? searchClauses(searchQuery) : getAllClauses().filter(c => c.level === 2);
    
    if (selectedStandard !== 'all') {
      clauses = clauses.filter(c => c.standard === selectedStandard);
    }

    return clauses.slice(0, 20);
  }, [searchQuery, selectedStandard]);

  // Handle auto-tagging
  const handleAutoTag = () => {
    if (contentForAutoTag) {
      const suggestions = autoTagContent(contentForAutoTag);
      setAutoTagSuggestions(suggestions);
      setShowSuggestions(true);
    }
  };

  // Toggle clause selection
  const toggleClause = (clauseId: string) => {
    if (selectedClauses.includes(clauseId)) {
      onChange(selectedClauses.filter(id => id !== clauseId));
    } else {
      onChange([...selectedClauses, clauseId]);
    }
  };

  // Apply all suggestions
  const applyAllSuggestions = () => {
    const newClauses = [...new Set([...selectedClauses, ...autoTagSuggestions.map(c => c.id)])];
    onChange(newClauses);
    setShowSuggestions(false);
  };

  // Render a clause badge
  const renderClauseBadge = (clause: ISOClause, removable = true) => {
    const Icon = standardIcons[clause.standard]!;
    const colors = standardColors[clause.standard]!;

    return (
      <span
        key={clause.id}
        className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-full text-xs font-medium ${colors.bg} ${colors.text} border ${colors.border}/30`}
      >
        <Icon className="w-3 h-3" />
        {clause.clauseNumber}
        {removable && (
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); toggleClause(clause.id); }}
            className="ml-1 hover:bg-white/20 rounded-full p-0.5"
          >
            <X className="w-3 h-3" />
          </button>
        )}
      </span>
    );
  };

  if (compact) {
    return (
      <div className="space-y-2">
        {label && <label className="block text-sm font-medium text-gray-300">{label}</label>}
        
        <div 
          onClick={() => setIsOpen(!isOpen)}
          className="p-3 bg-slate-700 border border-slate-600 rounded-lg cursor-pointer hover:border-slate-500 transition-all"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 flex-wrap">
              {selectedClauseObjects.length > 0 ? (
                selectedClauseObjects.slice(0, 3).map(clause => renderClauseBadge(clause))
              ) : (
                <span className="text-gray-400 text-sm">Click to add ISO tags...</span>
              )}
              {selectedClauseObjects.length > 3 && (
                <span className="text-xs text-gray-400">+{selectedClauseObjects.length - 3} more</span>
              )}
            </div>
            <ChevronDown className={`w-4 h-4 text-gray-400 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
          </div>
        </div>

        {isOpen && (
          <div className="bg-slate-800 border border-slate-700 rounded-lg p-3 space-y-3">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type="text"
                placeholder="Search clauses..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-9 pr-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm placeholder-gray-400 focus:ring-2 focus:ring-emerald-500"
              />
            </div>

            <div className="max-h-40 overflow-y-auto space-y-1">
              {filteredClauses.map(clause => {
                const isSelected = selectedClauses.includes(clause.id);
                const Icon = standardIcons[clause.standard]!;
                const colors = standardColors[clause.standard]!;

                return (
                  <div
                    key={clause.id}
                    onClick={() => toggleClause(clause.id)}
                    className={`flex items-center gap-2 p-2 rounded-lg cursor-pointer transition-all ${
                      isSelected ? 'bg-emerald-600/20 border border-emerald-500/50' : 'bg-slate-700/50 hover:bg-slate-700'
                    }`}
                  >
                    <Icon className={`w-4 h-4 ${colors.text}`} />
                    <span className="text-sm font-medium text-gray-400">{clause.clauseNumber}</span>
                    <span className="text-sm text-white truncate flex-grow">{clause.title}</span>
                    {isSelected && <CheckCircle2 className="w-4 h-4 text-emerald-400" />}
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    );
  }

  // Full version
  return (
    <div className="space-y-3">
      {label && (
        <div className="flex items-center justify-between">
          <label className="block text-sm font-medium text-gray-300">{label}</label>
          {showAutoTag && contentForAutoTag && (
            <button
              type="button"
              onClick={handleAutoTag}
              className="text-xs bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white px-3 py-1 rounded-full flex items-center gap-1"
            >
              <Sparkles className="w-3 h-3" />
              AI Auto-Tag
            </button>
          )}
        </div>
      )}

      {/* Selected Tags */}
      <div className="flex flex-wrap gap-2 min-h-[32px]">
        {selectedClauseObjects.map(clause => renderClauseBadge(clause))}
        <button
          type="button"
          onClick={() => setIsOpen(!isOpen)}
          className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-slate-700 text-gray-300 border border-dashed border-slate-600 hover:border-emerald-500 hover:text-emerald-400 transition-all"
        >
          <Plus className="w-3 h-3" />
          Add Tag
        </button>
      </div>

      {/* AI Suggestions */}
      {showSuggestions && autoTagSuggestions.length > 0 && (
        <div className="p-3 bg-purple-500/10 border border-purple-500/30 rounded-lg">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-purple-400 flex items-center gap-2">
              <Sparkles className="w-4 h-4" />
              AI Suggested Tags ({autoTagSuggestions.length})
            </span>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={applyAllSuggestions}
                className="text-xs bg-purple-600 hover:bg-purple-700 text-white px-2 py-1 rounded"
              >
                Apply All
              </button>
              <button
                type="button"
                onClick={() => setShowSuggestions(false)}
                className="text-xs text-gray-400 hover:text-white"
              >
                Dismiss
              </button>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            {autoTagSuggestions.map(clause => {
              const isAlreadySelected = selectedClauses.includes(clause.id);
              if (isAlreadySelected) return null;

              const Icon = standardIcons[clause.standard]!;
              const colors = standardColors[clause.standard]!;

              return (
                <button
                  key={clause.id}
                  type="button"
                  onClick={() => toggleClause(clause.id)}
                  className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-full text-xs font-medium ${colors.bg} ${colors.text} border ${colors.border}/30 hover:scale-105 transition-all`}
                >
                  <Icon className="w-3 h-3" />
                  {clause.clauseNumber}
                  <Plus className="w-3 h-3" />
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Tag Selector Dropdown */}
      {isOpen && (
        <div className="bg-slate-800 border border-slate-700 rounded-lg p-4 space-y-4">
          <div className="flex gap-3">
            {/* Search */}
            <div className="relative flex-grow">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type="text"
                placeholder="Search clauses by number, title, or keyword..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-10 pr-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-gray-400 focus:ring-2 focus:ring-emerald-500"
              />
            </div>

            {/* Standard Filter */}
            <select
              value={selectedStandard}
              onChange={(e) => setSelectedStandard(e.target.value)}
              className="px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white focus:ring-2 focus:ring-emerald-500"
            >
              <option value="all">All Standards</option>
              {ISO_STANDARDS.map(s => (
                <option key={s.id} value={s.id}>{s.code}</option>
              ))}
            </select>
          </div>

          {/* Clause List */}
          <div className="max-h-60 overflow-y-auto space-y-2 custom-scrollbar">
            {filteredClauses.length > 0 ? (
              filteredClauses.map(clause => {
                const isSelected = selectedClauses.includes(clause.id);
                const Icon = standardIcons[clause.standard]!;
                const colors = standardColors[clause.standard]!;

                return (
                  <div
                    key={clause.id}
                    onClick={() => toggleClause(clause.id)}
                    className={`flex items-start gap-3 p-3 rounded-lg cursor-pointer transition-all ${
                      isSelected 
                        ? 'bg-emerald-600/20 border border-emerald-500/50' 
                        : 'bg-slate-700/50 hover:bg-slate-700 border border-transparent'
                    }`}
                  >
                    <div className={`p-1.5 rounded ${colors.bg}`}>
                      <Icon className={`w-4 h-4 ${colors.text}`} />
                    </div>
                    <div className="flex-grow">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-gray-400">{clause.clauseNumber}</span>
                        <span className="text-sm text-white">{clause.title}</span>
                      </div>
                      <p className="text-xs text-gray-500 mt-1">{clause.description}</p>
                      <div className="flex flex-wrap gap-1 mt-2">
                        {clause.keywords.slice(0, 4).map((keyword, i) => (
                          <span key={i} className="text-xs bg-slate-600 text-gray-400 px-1.5 py-0.5 rounded">
                            {keyword}
                          </span>
                        ))}
                      </div>
                    </div>
                    {isSelected && <CheckCircle2 className="w-5 h-5 text-emerald-400 flex-shrink-0" />}
                  </div>
                );
              })
            ) : (
              <div className="text-center py-8 text-gray-400">
                <AlertCircle className="w-8 h-8 mx-auto mb-2 opacity-50" />
                <p>No clauses found matching "{searchQuery}"</p>
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="flex justify-between items-center pt-3 border-t border-slate-700">
            <span className="text-xs text-gray-400">
              {selectedClauses.length} clause(s) selected
            </span>
            <button
              type="button"
              onClick={() => setIsOpen(false)}
              className="text-sm bg-emerald-600 hover:bg-emerald-700 text-white px-4 py-1.5 rounded-lg"
            >
              Done
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
