import { useState, useEffect } from 'react'

export default function OfflineIndicator() {
  const [online, setOnline] = useState(navigator.onLine)
  const [showBanner, setShowBanner] = useState(false)

  useEffect(() => {
    const handleOnline = () => { setOnline(true); setShowBanner(true); setTimeout(() => setShowBanner(false), 3000) }
    const handleOffline = () => { setOnline(false); setShowBanner(true) }

    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)

    return () => {
      window.removeEventListener('online', handleOnline)
      window.removeEventListener('offline', handleOffline)
    }
  }, [])

  if (!showBanner && online) return null

  return (
    <div className={`fixed bottom-4 right-4 z-50 px-4 py-2 rounded-lg shadow-lg text-sm font-medium transition-all ${
      online
        ? 'bg-success/10 text-success border border-success/30'
        : 'bg-warning/10 text-warning border border-warning/30'
    }`}>
      {online ? '✓ Back online — syncing data...' : '⚡ Offline — changes will sync when connected'}
    </div>
  )
}
