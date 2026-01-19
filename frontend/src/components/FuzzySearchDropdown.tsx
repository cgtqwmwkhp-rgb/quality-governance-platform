import { useState, useRef, useEffect } from 'react';
import { Search, Check, ChevronDown, X } from 'lucide-react';

interface Option {
  value: string;
  label: string;
  sublabel?: string;
  icon?: React.ReactNode;
}

interface FuzzySearchDropdownProps {
  options: Option[];
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  label?: string;
  required?: boolean;
  allowCustom?: boolean;
  disabled?: boolean;
}

export default function FuzzySearchDropdown({
  options,
  value,
  onChange,
  placeholder = 'Search or select...',
  label,
  required,
  allowCustom = false,
  disabled = false,
}: FuzzySearchDropdownProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [search, setSearch] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Fuzzy search implementation
  const fuzzyMatch = (text: string, pattern: string): boolean => {
    const lowerText = text.toLowerCase();
    const lowerPattern = pattern.toLowerCase();
    
    // Simple fuzzy: check if all characters exist in order
    let patternIdx = 0;
    for (let i = 0; i < lowerText.length && patternIdx < lowerPattern.length; i++) {
      if (lowerText[i] === lowerPattern[patternIdx]) {
        patternIdx++;
      }
    }
    return patternIdx === lowerPattern.length;
  };

  const filteredOptions = options.filter(
    (opt) =>
      fuzzyMatch(opt.label, search) ||
      (opt.sublabel && fuzzyMatch(opt.sublabel, search)) ||
      fuzzyMatch(opt.value, search)
  );

  const selectedOption = options.find((opt) => opt.value === value);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
        setSearch('');
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isOpen]);

  const handleSelect = (optionValue: string) => {
    onChange(optionValue);
    setIsOpen(false);
    setSearch('');
  };

  const handleClear = (e: React.MouseEvent) => {
    e.stopPropagation();
    onChange('');
    setSearch('');
  };

  return (
    <div className="w-full" ref={containerRef}>
      {label && (
        <label className="block text-sm font-medium text-gray-300 mb-2">
          {label}
          {required && <span className="text-red-400 ml-1">*</span>}
        </label>
      )}
      
      <div className="relative">
        {/* Selected value display / Trigger */}
        <button
          type="button"
          onClick={() => !disabled && setIsOpen(!isOpen)}
          disabled={disabled}
          className={`
            w-full flex items-center justify-between gap-2 px-4 py-3.5
            bg-white/5 border border-white/20 rounded-xl text-left
            transition-all duration-200
            ${disabled ? 'opacity-50 cursor-not-allowed' : 'hover:bg-white/10 hover:border-white/30'}
            ${isOpen ? 'border-purple-500 ring-2 ring-purple-500/20' : ''}
          `}
        >
          <div className="flex items-center gap-3 flex-1 min-w-0">
            {selectedOption?.icon}
            <div className="flex-1 min-w-0">
              {selectedOption ? (
                <div>
                  <div className="text-white font-medium truncate">{selectedOption.label}</div>
                  {selectedOption.sublabel && (
                    <div className="text-gray-400 text-xs truncate">{selectedOption.sublabel}</div>
                  )}
                </div>
              ) : (
                <span className="text-gray-500">{placeholder}</span>
              )}
            </div>
          </div>
          
          <div className="flex items-center gap-2">
            {value && !disabled && (
              <button
                type="button"
                onClick={handleClear}
                className="p-1 hover:bg-white/10 rounded-full transition-colors"
              >
                <X className="w-4 h-4 text-gray-400" />
              </button>
            )}
            <ChevronDown className={`w-5 h-5 text-gray-400 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
          </div>
        </button>

        {/* Dropdown panel */}
        {isOpen && (
          <div className="absolute z-50 w-full mt-2 bg-slate-800 border border-white/20 rounded-xl shadow-2xl overflow-hidden">
            {/* Search input */}
            <div className="p-2 border-b border-white/10">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <input
                  ref={inputRef}
                  type="text"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Type to search..."
                  className="w-full pl-10 pr-4 py-2.5 bg-white/5 border border-white/10 rounded-lg
                           text-white placeholder-gray-500 text-sm
                           focus:outline-none focus:border-purple-500"
                />
              </div>
            </div>

            {/* Options list */}
            <div className="max-h-64 overflow-y-auto overscroll-contain">
              {filteredOptions.length > 0 ? (
                filteredOptions.map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => handleSelect(option.value)}
                    className={`
                      w-full flex items-center gap-3 px-4 py-3 text-left
                      transition-colors
                      ${value === option.value ? 'bg-purple-500/20' : 'hover:bg-white/5'}
                    `}
                  >
                    {option.icon && <div className="flex-shrink-0">{option.icon}</div>}
                    <div className="flex-1 min-w-0">
                      <div className="text-white font-medium truncate">{option.label}</div>
                      {option.sublabel && (
                        <div className="text-gray-400 text-xs truncate">{option.sublabel}</div>
                      )}
                    </div>
                    {value === option.value && (
                      <Check className="w-5 h-5 text-purple-400 flex-shrink-0" />
                    )}
                  </button>
                ))
              ) : (
                <div className="px-4 py-8 text-center text-gray-500">
                  {allowCustom ? (
                    <button
                      type="button"
                      onClick={() => handleSelect(search)}
                      className="text-purple-400 hover:text-purple-300"
                    >
                      Use "{search}"
                    </button>
                  ) : (
                    'No matches found'
                  )}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
