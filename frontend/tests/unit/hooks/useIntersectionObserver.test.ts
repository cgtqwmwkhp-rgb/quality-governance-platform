import { renderHook } from '@testing-library/react';
import { useIntersectionObserver } from '@/hooks/useIntersectionObserver';

describe('useIntersectionObserver', () => {
  it('returns a ref', () => {
    const { result } = renderHook(() => useIntersectionObserver());
    expect(result.current.ref).toBeDefined();
  });

  it('returns isIntersecting state', () => {
    const { result } = renderHook(() => useIntersectionObserver());
    expect(typeof result.current.isIntersecting).toBe('boolean');
  });
});
