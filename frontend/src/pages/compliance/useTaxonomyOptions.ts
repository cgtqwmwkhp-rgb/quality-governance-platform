import { useCallback, useEffect, useState } from 'react'
import api from '../../api/client'

export interface TaxonomyOption {
  /** The value stored on the requirement, e.g. "03.01". */
  taxonomyId: string
  /** Leaf name, e.g. "Fire Risk Assessment". */
  name: string
  /** Parent section name, shown so two similarly named leaves stay distinguishable. */
  sectionName: string
}

interface CategoryNode {
  taxonomy_id?: string
  name?: string
  active?: boolean
  children?: CategoryNode[]
}

/**
 * Flatten the category tree to the level the schedule actually stores.
 *
 * Every catalogue template carries a two-part code (`03.01`, `04.13`), which is
 * a *child* of a section, so offering sections would produce a value the rest of
 * the product does not use. Inactive categories are dropped: the taxonomy seed
 * deliberately deactivates branches the organisation does not operate, and
 * offering those invites obligations nobody intends to hold.
 */
export function flattenTaxonomy(sections: CategoryNode[]): TaxonomyOption[] {
  const options: TaxonomyOption[] = []
  for (const section of sections) {
    const sectionName = section.name ?? ''
    for (const child of section.children ?? []) {
      if (child.active === false) continue
      if (!child.taxonomy_id) continue
      options.push({
        taxonomyId: child.taxonomy_id,
        name: child.name ?? child.taxonomy_id,
        sectionName,
      })
    }
  }
  return options.sort((a, b) => a.taxonomyId.localeCompare(b.taxonomyId))
}

export interface TaxonomyOptionsState {
  options: TaxonomyOption[]
  loading: boolean
  /** True when the list could not be read. Distinct from a genuinely empty list. */
  failed: boolean
  reload: () => void
}

/**
 * Load the closed list of taxonomy codes a requirement may be filed under.
 *
 * Fetched once when the form opens rather than on mount, because the register
 * page renders far more often than the form does.
 */
export function useTaxonomyOptions(enabled: boolean): TaxonomyOptionsState {
  const [options, setOptions] = useState<TaxonomyOption[]>([])
  const [loading, setLoading] = useState(false)
  const [failed, setFailed] = useState(false)
  const [attempt, setAttempt] = useState(0)

  const reload = useCallback(() => setAttempt((n) => n + 1), [])

  useEffect(() => {
    if (!enabled) return
    let cancelled = false
    setLoading(true)
    setFailed(false)
    void (async () => {
      try {
        const response = await api.get('/api/v1/document-categories/')
        if (cancelled) return
        setOptions(flattenTaxonomy(response.data?.sections ?? []))
      } catch {
        if (cancelled) return
        // Left empty rather than partially populated: a truncated list would let
        // someone file an obligation under the wrong code without knowing the
        // right one was missing.
        setOptions([])
        setFailed(true)
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [enabled, attempt])

  return { options, loading, failed, reload }
}
