import { describe, it, expect, vi } from 'vitest';
import { cn, formatDate, formatDateTime, truncate, getInitials, sleep, debounce } from '../../../src/helpers/utils';

describe('cn', () => {
  it('merges class names', () => {
    expect(cn('foo', 'bar')).toBe('foo bar');
  });

  it('handles conditional classes', () => {
    expect(cn('base', false && 'hidden', 'visible')).toBe('base visible');
  });

  it('deduplicates tailwind classes', () => {
    const result = cn('px-2', 'px-4');
    expect(result).toBe('px-4');
  });
});

describe('formatDate', () => {
  it('formats a date string', () => {
    const result = formatDate('2026-01-15T10:30:00Z');
    expect(result).toContain('15');
    expect(result).toContain('Jan');
    expect(result).toContain('2026');
  });

  it('formats a Date object', () => {
    const result = formatDate(new Date('2026-06-20'));
    expect(result).toContain('2026');
  });
});

describe('formatDateTime', () => {
  it('includes time in the output', () => {
    const result = formatDateTime('2026-01-15T14:30:00Z');
    expect(result).toContain('15');
    expect(result).toContain('Jan');
  });
});

describe('truncate', () => {
  it('returns the full string when shorter than limit', () => {
    expect(truncate('hello', 10)).toBe('hello');
  });

  it('truncates and adds ellipsis when longer', () => {
    expect(truncate('hello world', 5)).toBe('hello...');
  });

  it('handles exact length', () => {
    expect(truncate('hello', 5)).toBe('hello');
  });
});

describe('getInitials', () => {
  it('returns initials for a two-word name', () => {
    expect(getInitials('John Doe')).toBe('JD');
  });

  it('limits to 2 characters', () => {
    expect(getInitials('John Michael Doe')).toBe('JM');
  });

  it('handles single-word names', () => {
    expect(getInitials('Admin')).toBe('A');
  });
});

describe('sleep', () => {
  it('resolves after the specified duration', async () => {
    vi.useFakeTimers();
    const promise = sleep(100);
    vi.advanceTimersByTime(100);
    await expect(promise).resolves.toBeUndefined();
    vi.useRealTimers();
  });
});

describe('debounce', () => {
  it('delays execution', () => {
    vi.useFakeTimers();
    const fn = vi.fn();
    const debounced = debounce(fn, 200);

    debounced();
    expect(fn).not.toHaveBeenCalled();

    vi.advanceTimersByTime(200);
    expect(fn).toHaveBeenCalledOnce();
    vi.useRealTimers();
  });

  it('resets timer on subsequent calls', () => {
    vi.useFakeTimers();
    const fn = vi.fn();
    const debounced = debounce(fn, 200);

    debounced();
    vi.advanceTimersByTime(100);
    debounced();
    vi.advanceTimersByTime(100);
    expect(fn).not.toHaveBeenCalled();

    vi.advanceTimersByTime(100);
    expect(fn).toHaveBeenCalledOnce();
    vi.useRealTimers();
  });
});
