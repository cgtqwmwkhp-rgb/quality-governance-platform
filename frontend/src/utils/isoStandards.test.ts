import { describe, expect, it } from 'vitest'
import {
  ISO_STANDARDS,
  autoTagContent,
  getAllClauses,
  getClausesByStandard,
  searchClauses,
} from '../data/isoStandards'

describe('isoStandards data + helpers', () => {
  it('exposes ISO 9001/14001/45001 catalogues', () => {
    expect(ISO_STANDARDS.length).toBeGreaterThanOrEqual(3)
    const codes = ISO_STANDARDS.map((s) => s.code)
    expect(codes).toEqual(
      expect.arrayContaining(['ISO 9001:2015', 'ISO 14001:2015', 'ISO 45001:2018']),
    )
    for (const standard of ISO_STANDARDS) {
      expect(standard.clauses.length).toBeGreaterThan(0)
      expect(standard.clauses[0].clauseNumber).toBeTruthy()
    }
  })

  it('getAllClauses flattens every standard', () => {
    const all = getAllClauses()
    const expected = ISO_STANDARDS.reduce((n, s) => n + s.clauses.length, 0)
    expect(all).toHaveLength(expected)
  })

  it('getClausesByStandard filters by id', () => {
    const id = ISO_STANDARDS[0].id
    const clauses = getClausesByStandard(id)
    expect(clauses.length).toBe(ISO_STANDARDS[0].clauses.length)
    expect(getClausesByStandard('missing')).toEqual([])
  })

  it('searchClauses matches title/keywords', () => {
    const hits = searchClauses('context')
    expect(hits.length).toBeGreaterThan(0)
    expect(searchClauses('zzznomatchzzz')).toEqual([])
  })

  it('autoTagContent scores keyword and clause mentions', () => {
    const tagged = autoTagContent(
      'Understanding the organization and its context for ISO 9001 clause 4 quality management',
    )
    expect(tagged.length).toBeGreaterThan(0)
    expect(tagged[0].id).toBeTruthy()
    expect(autoTagContent('')).toEqual([])
  })
})
