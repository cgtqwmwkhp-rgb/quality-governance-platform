import { describe, expect, it } from 'vitest'
import { flattenTaxonomy } from '../useTaxonomyOptions'

describe('flattenTaxonomy', () => {
  it('returns the level-2 children, which is the level the schedule stores', () => {
    const options = flattenTaxonomy([
      {
        taxonomy_id: '03',
        name: 'Fire Safety',
        children: [
          { taxonomy_id: '03.01', name: 'Fire Risk Assessment', active: true },
          { taxonomy_id: '03.02', name: 'FRA Site Visit', active: true },
        ],
      },
    ])

    expect(options).toEqual([
      { taxonomyId: '03.01', name: 'Fire Risk Assessment', sectionName: 'Fire Safety' },
      { taxonomyId: '03.02', name: 'FRA Site Visit', sectionName: 'Fire Safety' },
    ])
  })

  it('never offers a section itself, only its children', () => {
    const options = flattenTaxonomy([
      { taxonomy_id: '03', name: 'Fire Safety', children: [{ taxonomy_id: '03.01', name: 'FRA' }] },
    ])

    expect(options.map((o) => o.taxonomyId)).not.toContain('03')
  })

  it('drops categories the taxonomy seed deactivated', () => {
    const options = flattenTaxonomy([
      {
        taxonomy_id: '06',
        name: 'Transport',
        children: [
          { taxonomy_id: '06.03', name: 'Fleet', active: true },
          { taxonomy_id: '06.04', name: 'O-Licence & Tachograph', active: false },
        ],
      },
    ])

    expect(options.map((o) => o.taxonomyId)).toEqual(['06.03'])
  })

  it('keeps a child whose active flag is absent, rather than silently hiding it', () => {
    const options = flattenTaxonomy([
      { taxonomy_id: '01', name: 'Governance', children: [{ taxonomy_id: '01.01', name: 'Policy' }] },
    ])

    expect(options.map((o) => o.taxonomyId)).toEqual(['01.01'])
  })

  it('skips a child with no taxonomy id, which could not be stored anyway', () => {
    const options = flattenTaxonomy([
      {
        taxonomy_id: '01',
        name: 'Governance',
        children: [{ name: 'Broken' }, { taxonomy_id: '01.02', name: 'Register' }],
      },
    ])

    expect(options.map((o) => o.taxonomyId)).toEqual(['01.02'])
  })

  it('orders by code across sections so the list reads predictably', () => {
    const options = flattenTaxonomy([
      { taxonomy_id: '04', name: 'Plant', children: [{ taxonomy_id: '04.13', name: 'LOLER' }] },
      { taxonomy_id: '03', name: 'Fire', children: [{ taxonomy_id: '03.01', name: 'FRA' }] },
    ])

    expect(options.map((o) => o.taxonomyId)).toEqual(['03.01', '04.13'])
  })

  it('survives a section with no children key at all', () => {
    expect(flattenTaxonomy([{ taxonomy_id: '09', name: 'Empty' }])).toEqual([])
  })

  it('falls back to the code when a child has no name', () => {
    const options = flattenTaxonomy([
      { taxonomy_id: '07', name: 'HR', children: [{ taxonomy_id: '07.02' }] },
    ])

    expect(options[0]).toEqual({ taxonomyId: '07.02', name: '07.02', sectionName: 'HR' })
  })
})
