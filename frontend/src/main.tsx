import React from 'react'
import ReactDOM from 'react-dom/client'
import './i18n/i18n'
import App from './App'
import { ThemeProvider } from './contexts/ThemeContext'
import { ToastProvider } from './contexts/ToastContext'
import { LiveAnnouncerProvider } from './components/ui/LiveAnnouncer'
import { TooltipProvider } from './components/ui/Tooltip'
import { initErrorTracking } from './services/errorTracker'
import { reportWebVitals } from './lib/webVitals'
import './styles/design-tokens.css'
import './index.css'

// Build version stamp for deployment verification
const BUILD_SHA = import.meta.env.VITE_BUILD_SHA || 'dev'
const BUILD_TIME = import.meta.env.VITE_BUILD_TIME || new Date().toISOString()

// Expose for debugging (no secrets)
;(window as any).__BUILD_SHA__ = BUILD_SHA
;(window as any).__BUILD_TIME__ = BUILD_TIME

// Log once on startup for deployment verification
console.log(`[QGP] Build: ${BUILD_SHA} @ ${BUILD_TIME}`)

initErrorTracking()
reportWebVitals()

// Register the service worker only in production builds (SWA / deployed).
// Skip in local Vite/dev to avoid stale-cache interference during development.
// Do not attach controllerchange → location.reload() (reload loops).
if (import.meta.env.PROD && 'serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').then(
      (registration) => {
        console.log('SW registered:', registration.scope)
      },
      (error) => {
        console.log('SW registration failed:', error)
      },
    )
  })
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ThemeProvider>
      <LiveAnnouncerProvider>
        <TooltipProvider>
          <ToastProvider>
            <App />
          </ToastProvider>
        </TooltipProvider>
      </LiveAnnouncerProvider>
    </ThemeProvider>
  </React.StrictMode>,
)
