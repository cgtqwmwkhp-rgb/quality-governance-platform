import { useEffect, useRef, useState } from 'react'
import { Search, Package, Loader2, X } from 'lucide-react'
import api from '../api/client'
import { trackError } from '../utils/errorTracker'
import { Input } from './ui/Input'

export interface AssetPickerOption {
  id: number
  asset_number: string
  name: string
  status?: string
}

interface AssetPickerProps {
  value: number | null | undefined
  onChange: (assetId: number | null, asset?: AssetPickerOption) => void
  label?: string
  placeholder?: string
  disabled?: boolean
}

interface AssetListResponse {
  items: AssetPickerOption[]
  total: number
}

export function AssetPicker({
  value,
  onChange,
  label = 'Linked asset',
  placeholder = 'Search assets by number or name...',
  disabled = false,
}: AssetPickerProps) {
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState<AssetPickerOption | null>(null)
  const [results, setResults] = useState<AssetPickerOption[]>([])
  const [loading, setLoading] = useState(false)
  const [showDropdown, setShowDropdown] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const debounceRef = useRef<ReturnType<typeof setTimeout>>()

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setShowDropdown(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  useEffect(() => {
    if (!value) {
      setSelected(null)
      setQuery('')
      return
    }
    if (selected?.id === value) return
    let cancelled = false
    ;(async () => {
      try {
        const response = await api.get<AssetPickerOption>(`/api/v1/assets/${value}`)
        if (!cancelled) {
          setSelected(response.data)
          setQuery(`${response.data.asset_number} — ${response.data.name}`)
        }
      } catch (err) {
        trackError(err, { component: 'AssetPicker', action: 'loadSelected' })
        if (!cancelled) {
          setQuery(`Asset #${value}`)
        }
      }
    })()
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reload only when value changes
  }, [value])

  const searchAssets = async (searchQuery: string) => {
    if (searchQuery.trim().length < 1) {
      setResults([])
      return
    }
    setLoading(true)
    try {
      const response = await api.get<AssetListResponse>('/api/v1/assets/', {
        params: { search: searchQuery.trim(), page: 1, page_size: 20 },
      })
      setResults(response.data.items || [])
    } catch (err) {
      trackError(err, { component: 'AssetPicker', action: 'searchAssets' })
      setResults([])
    } finally {
      setLoading(false)
    }
  }

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const next = e.target.value
    setQuery(next)
    setSelected(null)
    onChange(null)
    setShowDropdown(true)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => searchAssets(next), 300)
  }

  const handleSelect = (asset: AssetPickerOption) => {
    setSelected(asset)
    setQuery(`${asset.asset_number} — ${asset.name}`)
    onChange(asset.id, asset)
    setShowDropdown(false)
    setResults([])
  }

  const handleClear = () => {
    setQuery('')
    setSelected(null)
    onChange(null)
    setResults([])
  }

  return (
    <div ref={containerRef} className="relative">
      {label && <label className="block text-sm font-medium text-muted-foreground mb-1">{label}</label>}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
        <Input
          type="text"
          value={query}
          onChange={handleInputChange}
          onFocus={() => query.length >= 1 && setShowDropdown(true)}
          placeholder={placeholder}
          disabled={disabled}
          className="pl-9 pr-8"
          data-testid="asset-picker-input"
        />
        {(query || selected) && !disabled && (
          <button
            type="button"
            onClick={handleClear}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            aria-label="Clear asset"
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>
      {showDropdown && (loading || results.length > 0) && (
        <div className="absolute z-50 mt-1 w-full rounded-md border bg-popover shadow-md max-h-60 overflow-auto">
          {loading ? (
            <div className="flex items-center gap-2 px-3 py-2 text-sm text-muted-foreground">
              <Loader2 className="w-4 h-4 animate-spin" />
              Searching...
            </div>
          ) : (
            results.map((asset) => (
              <button
                key={asset.id}
                type="button"
                className="flex w-full items-start gap-2 px-3 py-2 text-left text-sm hover:bg-accent"
                onClick={() => handleSelect(asset)}
              >
                <Package className="w-4 h-4 mt-0.5 text-muted-foreground shrink-0" />
                <span>
                  <span className="font-medium">{asset.asset_number}</span>
                  <span className="text-muted-foreground"> — {asset.name}</span>
                </span>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  )
}
