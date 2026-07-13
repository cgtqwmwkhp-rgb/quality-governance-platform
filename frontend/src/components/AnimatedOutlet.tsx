import { useLocation, useOutlet } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'

/**
 * Animated route outlet.
 *
 * IMPORTANT: render `useOutlet()` (frozen element), not live `<Outlet />`.
 * With `<Outlet />` inside AnimatePresence, the exiting frame re-reads the
 * router location and can show the *next* page body while the URL/nav already
 * changed (Audit Builder ↔ Documents content desync).
 */
export function AnimatedOutlet() {
  const location = useLocation()
  const outlet = useOutlet()

  return (
    <AnimatePresence mode="wait" initial={false}>
      <motion.div
        key={location.pathname}
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -8 }}
        transition={{ duration: 0.15, ease: 'easeInOut' }}
      >
        {outlet}
      </motion.div>
    </AnimatePresence>
  )
}
