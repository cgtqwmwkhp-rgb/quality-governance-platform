import { describe, expect, it } from 'vitest'

import {
  BUILDER_SAVE_CONCURRENCY,
  BUILDER_SAVE_REQUEST_CONFIG,
  BUILDER_SAVE_TIMEOUT_MS,
  formatQuestionProgress,
  runWithConcurrency,
} from '../saveConcurrency'

describe('runWithConcurrency', () => {
  it('runs every item and never exceeds the limit in flight', async () => {
    const items = Array.from({ length: 19 }, (_, i) => i)
    const done: number[] = []
    let inFlight = 0
    let peak = 0

    const failure = await runWithConcurrency(items, 3, async (item) => {
      inFlight += 1
      peak = Math.max(peak, inFlight)
      await Promise.resolve()
      done.push(item)
      inFlight -= 1
    })

    expect(failure).toBeNull()
    expect(done).toHaveLength(19)
    expect(new Set(done).size).toBe(19)
    expect(peak).toBeLessThanOrEqual(3)
    expect(peak).toBeGreaterThan(1)
  })

  it('stops scheduling new work after a failure', async () => {
    const items = Array.from({ length: 20 }, (_, i) => i)
    const started: number[] = []

    const failure = await runWithConcurrency(items, 3, async (item) => {
      started.push(item)
      await Promise.resolve()
      if (item === 4) throw new Error('boom')
    })

    expect(failure).not.toBeNull()
    expect(failure?.item).toBe(4)
    expect(failure?.index).toBe(4)
    expect((failure?.error as Error).message).toBe('boom')
    // Some tasks after the failing one may already be in flight, but the run
    // must stop well short of the full list.
    expect(started.length).toBeLessThan(items.length)
    expect(started.length).toBeLessThanOrEqual(4 + 3)
  })

  it('lets in-flight work finish so its side effects are not lost', async () => {
    const finished: number[] = []

    const failure = await runWithConcurrency([0, 1, 2], 3, async (item) => {
      if (item === 0) {
        await Promise.resolve()
        throw new Error('first fails')
      }
      await Promise.resolve()
      await Promise.resolve()
      finished.push(item)
    })

    expect(failure?.index).toBe(0)
    expect(finished).toEqual([1, 2])
  })

  it('reports the lowest-index failure when several fail', async () => {
    const failure = await runWithConcurrency([0, 1, 2, 3], 4, async (item) => {
      if (item === 1 || item === 3) throw new Error(`fail-${item}`)
    })
    expect(failure?.index).toBe(1)
  })

  it('handles an empty list and a nonsense limit', async () => {
    expect(await runWithConcurrency([], 3, async () => {})).toBeNull()

    const seen: number[] = []
    const failure = await runWithConcurrency([1, 2], 0, async (item) => {
      seen.push(item)
    })
    expect(failure).toBeNull()
    expect(seen).toEqual([1, 2])
  })
})

describe('builder save request settings', () => {
  it('raises the write timeout above the 45s default without touching other callers', () => {
    expect(BUILDER_SAVE_TIMEOUT_MS).toBeGreaterThan(45000)
    expect(BUILDER_SAVE_REQUEST_CONFIG).toEqual({ timeout: BUILDER_SAVE_TIMEOUT_MS })
    expect(BUILDER_SAVE_CONCURRENCY).toBeGreaterThan(1)
  })

  it('formats question progress honestly', () => {
    expect(formatQuestionProgress(0, 19)).toBe('0 of 19 questions saved')
    expect(formatQuestionProgress(6, 19)).toBe('6 of 19 questions saved')
    expect(formatQuestionProgress(1, 1)).toBe('1 of 1 question saved')
  })
})
