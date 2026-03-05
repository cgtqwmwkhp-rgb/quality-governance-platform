import { useState, useEffect } from 'react'
import { useAppStore } from '../stores'

export default function OfflineIndicator() {
  const [browserOnline, setBrowserOnline] = useState(navigator.onLine)
  const [showBanner, setShowBanner] = useState(false)
  const connectionStatus = useAppStore((s) => s.connectionStatus)

  useEffect(() => {
    const handleOnline = () => { setBrowserOnline(true); setShowBanner(true); setTimeout(() => setShowBanner(false), 3000) }
    const handleOffline = () => { setBrowserOnline(false); setShowBanner(true) }

    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)

    return () => {
      window.removeEventListener('online', handleOnline)
      window.removeEventListener('offline', handleOffline)
    }
  }, [])

  const isDisconnected = !browserOnline || connectionStatus === 'disconnected'
  const isReconnecting = browserOnline && connectionStatus === 'reconnecting'
  const isBackOnline = browserOnline && connectionStatus === 'connected' && showBanner

  if (!showBanner && !isDisconnected && !isReconnecting) return null

  let message = ''
  let style = ''

  if (isDisconnected) {
    message = 'Offline — changes will sync when connected'
    style = 'bg-warning/10 text-warning border border-warning/30'
  } else if (isReconnecting) {
    message = 'Reconnecting...'
    style = 'bg-warning/10 text-warning border border-warning/30'
  } else if (isBackOnline) {
    message = 'Back online'
    style = 'bg-success/10 text-success border border-success/30'
  }

  if (!message) return null

  return (
    <div className={`fixed bottom-4 right-4 z-50 px-4 py-2 rounded-lg shadow-lg text-sm font-medium transition-all ${style}`}>
      {message}
    </div>
  )
}
