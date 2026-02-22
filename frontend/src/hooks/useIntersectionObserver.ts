import { useEffect, useRef, useState, RefObject } from "react";

export interface UseIntersectionObserverOptions {
  /**
   * The root element for intersection checking. Defaults to viewport.
   */
  root?: Element | null;
  /**
   * Margin around the root. Can have values similar to the CSS margin property.
   * Defaults to "0px".
   */
  rootMargin?: string;
  /**
   * Either a single number or an array of numbers which indicate at what percentage
   * of the target's visibility the observer's callback should be executed.
   * Defaults to 0.1 (10% visible).
   */
  threshold?: number | number[];
  /**
   * Whether the observer is enabled. Defaults to true.
   */
  enabled?: boolean;
}

export interface UseIntersectionObserverReturn {
  /**
   * Ref to attach to the element you want to observe
   */
  ref: RefObject<HTMLElement>;
  /**
   * Whether the element is currently intersecting
   */
  isIntersecting: boolean;
  /**
   * The IntersectionObserverEntry if available
   */
  entry?: IntersectionObserverEntry;
}

/**
 * Hook for lazy loading images and infinite scroll
 *
 * Uses the Intersection Observer API to detect when an element enters
 * or leaves the viewport. Useful for:
 * - Lazy loading images
 * - Infinite scroll pagination
 * - Triggering animations when elements come into view
 * - Performance optimization by deferring non-critical content
 *
 * @param options - IntersectionObserver options
 * @returns Object with ref, isIntersecting flag, and entry
 *
 * @example
 * ```tsx
 * // Lazy load an image
 * function LazyImage({ src, alt }) {
 *   const { ref, isIntersecting } = useIntersectionObserver({
 *     threshold: 0.1,
 *   });
 *
 *   return (
 *     <div ref={ref}>
 *       {isIntersecting ? (
 *         <img src={src} alt={alt} />
 *       ) : (
 *         <div className="placeholder">Loading...</div>
 *       )}
 *     </div>
 *   );
 * }
 * ```
 *
 * @example
 * ```tsx
 * // Infinite scroll
 * function InfiniteScroll({ onLoadMore }) {
 *   const { ref, isIntersecting } = useIntersectionObserver({
 *     rootMargin: "100px",
 *   });
 *
 *   useEffect(() => {
 *     if (isIntersecting) {
 *       onLoadMore();
 *     }
 *   }, [isIntersecting, onLoadMore]);
 *
 *   return <div ref={ref}>Loading more...</div>;
 * }
 * ```
 */
export function useIntersectionObserver(
  options: UseIntersectionObserverOptions = {},
): UseIntersectionObserverReturn {
  const {
    root = null,
    rootMargin = "0px",
    threshold = 0.1,
    enabled = true,
  } = options;

  const [isIntersecting, setIsIntersecting] = useState(false);
  const [entry, setEntry] = useState<IntersectionObserverEntry>();
  const elementRef = useRef<HTMLElement>(null);
  const observerRef = useRef<IntersectionObserver | null>(null);

  useEffect(() => {
    const element = elementRef.current;
    if (!element || !enabled) {
      return;
    }

    // Check if IntersectionObserver is supported
    if (typeof IntersectionObserver === "undefined") {
      // Fallback: assume element is visible if IntersectionObserver is not supported
      setIsIntersecting(true);
      return;
    }

    // Create observer
    observerRef.current = new IntersectionObserver(
      (entries) => {
        const [entry] = entries;
        setIsIntersecting(entry.isIntersecting);
        setEntry(entry);
      },
      {
        root,
        rootMargin,
        threshold,
      },
    );

    // Start observing
    observerRef.current.observe(element);

    // Cleanup
    return () => {
      if (observerRef.current) {
        observerRef.current.disconnect();
        observerRef.current = null;
      }
    };
  }, [root, rootMargin, threshold, enabled]);

  return {
    ref: elementRef,
    isIntersecting,
    entry,
  };
}
