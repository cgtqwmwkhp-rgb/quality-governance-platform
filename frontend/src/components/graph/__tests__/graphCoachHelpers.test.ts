/**
 * GraphCoach helpers + orientation primitive (X-2).
 */
import { describe, expect, it, beforeEach } from 'vitest'
import {
  clampCoachStepIndex,
  coachDismissStorageKey,
  coachStepProgress,
  dismissCoach,
  isCoachDismissed,
  resetCoach,
  shouldRenderCoachPanel,
  shouldShowGraphCoach,
} from '../graphCoachHelpers'
import {
  DEFAULT_GRAPH_ORIENTATION,
  graphOrientationLabel,
  parseStoredGraphOrientation,
  resolveGraphOrientation,
  toggleGraphOrientation,
  writeStoredGraphOrientation,
  readStoredGraphOrientation,
} from '../graphOrientation'
import { getCoachSteps, getCoachSurfaceDefinition, GRAPH_COACH_SURFACES } from '../coachSteps'
import { buildRelationshipMapModel } from '../relationshipsMapHelpers'
import type { DocumentEdge } from '../../../api/documentGraphClient'

function memoryStorage(initial: Record<string, string> = {}): Storage {
  const data = { ...initial }
  return {
    get length() {
      return Object.keys(data).length
    },
    clear() {
      for (const key of Object.keys(data)) delete data[key]
    },
    getItem(key: string) {
      return Object.prototype.hasOwnProperty.call(data, key) ? data[key] : null
    },
    key(index: number) {
      return Object.keys(data)[index] ?? null
    },
    removeItem(key: string) {
      delete data[key]
    },
    setItem(key: string, value: string) {
      data[key] = String(value)
    },
  }
}

function edge(overrides: Partial<DocumentEdge> & { id: number }): DocumentEdge {
  return {
    tenant_id: 1,
    src_document_id: 10,
    dst_document_id: 20,
    edge_type: 'implements',
    is_primary_parent: false,
    status: 'confirmed',
    created_method: 'manual',
    created_at: '2026-08-01T10:00:00Z',
    updated_at: '2026-08-01T10:00:00Z',
    ...overrides,
  }
}

describe('graphCoachHelpers', () => {
  it('hides coach when graph_coach is off', () => {
    expect(shouldShowGraphCoach(false)).toBe(false)
    expect(shouldRenderCoachPanel(false, 'document_relationships')).toBe(false)
  })

  it('shows coach when graph_coach is on and not dismissed', () => {
    const storage = memoryStorage()
    expect(shouldShowGraphCoach(true)).toBe(true)
    expect(shouldRenderCoachPanel(true, 'document_relationships', storage)).toBe(true)
  })

  it('persists dismiss per surface', () => {
    const storage = memoryStorage()
    dismissCoach('document_relationships', storage)
    expect(isCoachDismissed('document_relationships', storage)).toBe(true)
    expect(shouldRenderCoachPanel(true, 'document_relationships', storage)).toBe(false)
    expect(storage.getItem(coachDismissStorageKey('document_relationships'))).toBe('1')
    expect(isCoachDismissed('job_lifecycle', storage)).toBe(false)
    resetCoach('document_relationships', storage)
    expect(isCoachDismissed('document_relationships', storage)).toBe(false)
  })

  it('clamps step index and reports progress', () => {
    expect(clampCoachStepIndex(-1, 5)).toBe(0)
    expect(clampCoachStepIndex(99, 5)).toBe(4)
    expect(clampCoachStepIndex(2, 0)).toBe(0)
    expect(coachStepProgress(0, 5)).toBe(20)
    expect(coachStepProgress(4, 5)).toBe(100)
  })
})

describe('coachSteps registry', () => {
  it('registers document_relationships, structure map, and job_lifecycle surfaces', () => {
    expect(GRAPH_COACH_SURFACES).toEqual([
      'document_relationships',
      'document_structure_map',
      'job_lifecycle',
    ])
    expect(getCoachSteps('document_relationships')).toHaveLength(5)
    expect(getCoachSteps('document_structure_map')).toHaveLength(5)
    expect(getCoachSteps('job_lifecycle')).toHaveLength(5)
    expect(getCoachSurfaceDefinition('document_relationships').heading).toMatch(/Document/i)
    expect(getCoachSurfaceDefinition('document_structure_map').heading).toMatch(/Structure/i)
  })

  it('never calls Doc Graph the golden thread', () => {
    for (const surface of GRAPH_COACH_SURFACES) {
      const blob = JSON.stringify(getCoachSurfaceDefinition(surface)).toLowerCase()
      expect(blob).not.toContain('golden thread')
    }
  })
})

describe('graphOrientation', () => {
  it('resolves and toggles orientation', () => {
    expect(resolveGraphOrientation('vertical')).toBe('vertical')
    expect(resolveGraphOrientation('nope')).toBe(DEFAULT_GRAPH_ORIENTATION)
    expect(toggleGraphOrientation('horizontal')).toBe('vertical')
    expect(toggleGraphOrientation('vertical')).toBe('horizontal')
    expect(graphOrientationLabel('vertical')).toBe('Vertical')
  })

  it('parses and persists stored orientation', () => {
    const storage = memoryStorage()
    expect(parseStoredGraphOrientation('horizontal')).toBe('horizontal')
    expect(parseStoredGraphOrientation('sideways')).toBeNull()
    writeStoredGraphOrientation('document_relationships', 'vertical', storage)
    expect(readStoredGraphOrientation('document_relationships', storage)).toBe('vertical')
  })
})

describe('buildRelationshipMapModel orientation', () => {
  beforeEach(() => {
    // no-op — pure helper
  })

  it('keeps hub-fan layout for horizontal (default)', () => {
    const model = buildRelationshipMapModel(
      10,
      'Policy',
      'POL-10',
      [edge({ id: 1, src_document_id: 10, dst_document_id: 20 })],
      { 20: 'SOP' },
      { orientation: 'horizontal' },
    )
    const hub = model.nodes.find((n) => n.isHub)!
    const peer = model.nodes.find((n) => n.id === 20)!
    expect(hub.x).toBe(model.width / 2)
    expect(peer.y).not.toBe(hub.y)
  })

  it('stacks inbound above and outbound below for vertical spine', () => {
    const model = buildRelationshipMapModel(
      10,
      'Procedure',
      'PRO-10',
      [
        edge({ id: 1, src_document_id: 5, dst_document_id: 10 }), // inbound implements parent
        edge({ id: 2, src_document_id: 10, dst_document_id: 30 }), // outbound child
      ],
      { 5: 'Policy', 30: 'SOP' },
      { orientation: 'vertical', height: 400 },
    )
    const hub = model.nodes.find((n) => n.isHub)!
    const parent = model.nodes.find((n) => n.id === 5)!
    const child = model.nodes.find((n) => n.id === 30)!
    expect(parent.y).toBeLessThan(hub.y)
    expect(child.y).toBeGreaterThan(hub.y)
    expect(parent.x).toBe(hub.x)
    expect(child.x).toBe(hub.x)
  })
})
