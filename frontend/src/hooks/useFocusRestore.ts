import { useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";

/**
 * Hook that saves focus position before route change
 * and restores it when navigating back
 *
 * This improves accessibility by maintaining focus context
 * when users navigate between pages using browser back/forward buttons.
 *
 * @example
 * ```tsx
 * function MyComponent() {
 *   useFocusRestore();
 *   return <div>Content</div>;
 * }
 * ```
 */
export function useFocusRestore() {
  const location = useLocation();
  const previousLocationRef = useRef<string | null>(null);
  const savedFocusRef = useRef<HTMLElement | null>(null);
  const focusKeyRef = useRef<string | null>(null);

  useEffect(() => {
    const currentPath = location.pathname;
    const previousPath = previousLocationRef.current;

    // Save current focus before navigation
    if (previousPath && previousPath !== currentPath) {
      const activeElement = document.activeElement as HTMLElement;
      if (activeElement && activeElement !== document.body) {
        savedFocusRef.current = activeElement;
        focusKeyRef.current = previousPath;
      }
    }

    // Restore focus if navigating back to a previously visited page
    if (focusKeyRef.current === currentPath && savedFocusRef.current) {
      // Use requestAnimationFrame to ensure DOM is ready
      requestAnimationFrame(() => {
        if (savedFocusRef.current) {
          try {
            savedFocusRef.current.focus();
            // If the element is no longer in the DOM, try to find it by ID or data attribute
            if (document.activeElement !== savedFocusRef.current) {
              const elementId = savedFocusRef.current.id;
              if (elementId) {
                const element = document.getElementById(elementId);
                element?.focus();
              }
            }
          } catch (error) {
            // Element may no longer exist, focus main content instead
            const mainContent = document.getElementById("main-content");
            if (mainContent) {
              mainContent.focus();
            }
          }
        }
      });
    } else {
      // For new pages, focus the main content area
      requestAnimationFrame(() => {
        const mainContent = document.getElementById("main-content");
        if (mainContent && !document.activeElement?.closest("main")) {
          mainContent.focus();
        }
      });
    }

    // Update previous location
    previousLocationRef.current = currentPath;
  }, [location.pathname]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      savedFocusRef.current = null;
      focusKeyRef.current = null;
    };
  }, []);
}
