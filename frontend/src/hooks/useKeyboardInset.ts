/**
 * Publish how much of the layout viewport the on-screen keyboard covers, as a
 * CSS custom property, so fixed field chrome can sit above it.
 *
 * This cannot be done in CSS. When the virtual keyboard opens, mobile Safari
 * does not shrink the layout viewport — it shrinks the *visual* viewport and
 * leaves `position: fixed; bottom: 0` pinned to a line that is now behind the
 * keyboard. `100dvh` does not rescue it either: `dvh` tracks the browser
 * toolbar, not the keyboard. The overlap is only observable via
 * `window.visualViewport`.
 *
 * Where an engine resizes the *layout* viewport for the keyboard instead,
 * `window.innerHeight` shrinks alongside `visualViewport.height`, so the
 * measured overlap is ~0 and this hook correctly moves nothing.
 */
import { useEffect } from 'react'

export const KEYBOARD_INSET_VAR = '--qgp-keyboard-inset'

/**
 * Overlap smaller than this is a collapsing browser toolbar, not a keyboard.
 * Acting on it would make the action bar jitter while the auditor scrolls.
 */
export const KEYBOARD_MIN_PX = 40

/** Never lift chrome by more than this share of the viewport. */
const MAX_INSET_RATIO = 0.6

type ViewportMetrics = Pick<VisualViewport, 'height' | 'offsetTop'>

/**
 * The keyboard overlap in CSS px, or 0 when there is nothing to clear.
 *
 * Split out from the hook because this is the part with edge cases worth
 * pinning: no visual viewport at all, a zero/NaN height from a detached
 * viewport mid-navigation, and a pinch-zoom that shrinks the visual viewport
 * without any keyboard being present.
 */
export function keyboardInsetFrom(
  layoutHeight: number,
  viewport: ViewportMetrics | null | undefined,
): number {
  if (!viewport) return 0
  if (!Number.isFinite(layoutHeight) || layoutHeight <= 0) return 0
  if (!Number.isFinite(viewport.height) || viewport.height <= 0) return 0
  const offsetTop = Number.isFinite(viewport.offsetTop) ? viewport.offsetTop : 0
  const overlap = layoutHeight - (viewport.height + offsetTop)
  if (!Number.isFinite(overlap) || overlap < KEYBOARD_MIN_PX) return 0
  // A pinch-zoom also shrinks the visual viewport, so clamp: the worst a zoom
  // can do is lift the action bar, never push it off the top of the screen.
  return Math.round(Math.min(overlap, layoutHeight * MAX_INSET_RATIO))
}

/**
 * Keep {@link KEYBOARD_INSET_VAR} on `<html>` in step with the keyboard while
 * mounted, and remove it on unmount so no other page inherits a stale lift.
 *
 * Returns nothing on purpose. The value is only ever consumed by CSS; holding
 * it in React state would re-render the whole execute page on every
 * pinch-scroll event, which is the opposite of what a field device needs.
 */
export function useKeyboardInset(enabled: boolean = true): void {
  useEffect(() => {
    if (!enabled) return
    if (typeof window === 'undefined') return
    const viewport = window.visualViewport
    // No measurement is possible, so the property stays unset and every
    // consumer falls back to its `0px` default rather than guessing.
    if (!viewport) return

    const root = document.documentElement
    const publish = () => {
      root.style.setProperty(
        KEYBOARD_INSET_VAR,
        `${keyboardInsetFrom(window.innerHeight, viewport)}px`,
      )
    }

    publish()
    viewport.addEventListener('resize', publish)
    viewport.addEventListener('scroll', publish)
    return () => {
      viewport.removeEventListener('resize', publish)
      viewport.removeEventListener('scroll', publish)
      root.style.removeProperty(KEYBOARD_INSET_VAR)
    }
  }, [enabled])
}
