import React from 'react'
import ReactDOM from 'react-dom/client'
import './i18n/i18n'
import App from './App'
import { ThemeProvider } from './contexts/ThemeContext'
import { LiveAnnouncerProvider } from './components/ui/LiveAnnouncer'
import { TooltipProvider } from './components/ui/Tooltip'
import './index.css'

// Build version stamp for deployment verification
const BUILD_SHA = import.meta.env.VITE_BUILD_SHA || 'dev'
const BUILD_TIME = import.meta.env.VITE_BUILD_TIME || new Date().toISOString()

// Expose for debugging (no secrets)
;(window as any).__BUILD_SHA__ = BUILD_SHA
;(window as any).__BUILD_TIME__ = BUILD_TIME

// Log once on startup for deployment verification
console.log(`[QGP] Build: ${BUILD_SHA} @ ${BUILD_TIME}`)

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ThemeProvider>
      <LiveAnnouncerProvider>
        <TooltipProvider>
          <App />
        </TooltipProvider>
      </LiveAnnouncerProvider>
    </ThemeProvider>
  </React.StrictMode>,
)
