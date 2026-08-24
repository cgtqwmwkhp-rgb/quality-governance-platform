/**
 * Save-path plumbing for the Audit Template Builder.
 *
 * A multi-section template still saves over one HTTP request per section and per
 * question (no bulk endpoint yet), so a 6-section / 19-question template makes 26
 * sequential round trips and blows the 45s default write timeout. Until the bulk
 * upsert lands, the builder save path gets a longer per-request timeout and runs
 * the question writes for a section a few at a time.
 */
import type { AxiosRequestConfig } from 'axios'

/**
 * Per-request timeout for builder save calls only. `resolveRequestTimeout` in
 * `api/client.ts` preserves any override that is not one of its own defaults.
 */
export const BUILDER_SAVE_TIMEOUT_MS = 90000

/** Per-request config applied to every write the builder's save path makes. */
export const BUILDER_SAVE_REQUEST_CONFIG: AxiosRequestConfig = {
  timeout: BUILDER_SAVE_TIMEOUT_MS,
}

/** How many question create/update calls may be in flight at once. */
export const BUILDER_SAVE_CONCURRENCY = 3

export interface ConcurrentTaskFailure<T> {
  item: T
  index: number
  error: unknown
}

/**
 * Run `worker` over `items` with at most `limit` in flight.
 *
 * Stops scheduling new work as soon as any task fails, waits for the tasks
 * already in flight (so their results are not orphaned — a created question's id
 * still reaches the caller's id map), and returns the failure with the lowest
 * index so the reported error is deterministic. Returns null when all succeeded.
 */
export async function runWithConcurrency<T>(
  items: readonly T[],
  limit: number,
  worker: (item: T, index: number) => Promise<void>,
): Promise<ConcurrentTaskFailure<T> | null> {
  if (items.length === 0) return null

  let nextIndex = 0
  const failures: ConcurrentTaskFailure<T>[] = []

  const runLane = async (): Promise<void> => {
    for (;;) {
      if (failures.length > 0) return
      const index = nextIndex
      nextIndex += 1
      if (index >= items.length) return
      try {
        await worker(items[index], index)
      } catch (error) {
        failures.push({ item: items[index], index, error })
        return
      }
    }
  }

  const lanes = Math.max(1, Math.min(Math.floor(limit) || 1, items.length))
  await Promise.all(Array.from({ length: lanes }, () => runLane()))
  if (failures.length === 0) return null
  return failures.reduce((lowest, f) => (f.index < lowest.index ? f : lowest))
}

/** "6 of 19 questions saved" — progress wording shared by the banner and the header. */
export function formatQuestionProgress(saved: number, total: number): string {
  return `${saved} of ${total} question${total === 1 ? '' : 's'} saved`
}
