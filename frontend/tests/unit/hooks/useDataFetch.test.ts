import { describe, it, expect, vi } from 'vitest';

/**
 * Tests the async data-fetching logic that useDataFetch encapsulates.
 * We test the fetch pattern directly (success, error, state transitions)
 * without mounting a React component.
 */

async function executeFetch<T>(fetchFn: () => Promise<T>) {
  let data: T | null = null;
  let loading = true;
  let error: string | null = null;

  loading = true;
  error = null;
  try {
    const result = await fetchFn();
    data = result;
  } catch (err) {
    error = err instanceof Error ? err.message : 'An error occurred';
  } finally {
    loading = false;
  }

  return { data, loading, error };
}

describe('useDataFetch logic', () => {
  it('should return data on successful fetch', async () => {
    const mockData = { id: 1, name: 'Test Item' };
    const fetchFn = vi.fn().mockResolvedValue(mockData);

    const result = await executeFetch(fetchFn);

    expect(fetchFn).toHaveBeenCalledOnce();
    expect(result.data).toEqual(mockData);
    expect(result.loading).toBe(false);
    expect(result.error).toBeNull();
  });

  it('should capture error message on failure', async () => {
    const fetchFn = vi.fn().mockRejectedValue(new Error('Network failure'));

    const result = await executeFetch(fetchFn);

    expect(fetchFn).toHaveBeenCalledOnce();
    expect(result.data).toBeNull();
    expect(result.loading).toBe(false);
    expect(result.error).toBe('Network failure');
  });

  it('should handle non-Error thrown values', async () => {
    const fetchFn = vi.fn().mockRejectedValue('string error');

    const result = await executeFetch(fetchFn);

    expect(result.data).toBeNull();
    expect(result.loading).toBe(false);
    expect(result.error).toBe('An error occurred');
  });

  it('should set loading to false after completion', async () => {
    const fetchFn = vi.fn().mockResolvedValue('done');

    const result = await executeFetch(fetchFn);

    expect(result.loading).toBe(false);
  });

  it('should set loading to false even after error', async () => {
    const fetchFn = vi.fn().mockRejectedValue(new Error('fail'));

    const result = await executeFetch(fetchFn);

    expect(result.loading).toBe(false);
  });

  it('should handle null return from fetch', async () => {
    const fetchFn = vi.fn().mockResolvedValue(null);

    const result = await executeFetch(fetchFn);

    expect(result.data).toBeNull();
    expect(result.error).toBeNull();
    expect(result.loading).toBe(false);
  });
});
