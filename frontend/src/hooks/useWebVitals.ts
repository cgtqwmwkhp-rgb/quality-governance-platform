import { onCLS, onFID, onLCP, onFCP, onTTFB, onINP } from 'web-vitals'
import { useEffect } from 'react'

interface VitalMetric {
  name: string
  value: number
  rating: 'good' | 'needs-improvement' | 'poor'
  id: string
}

function reportVital(metric: VitalMetric) {
  if (process.env.NODE_ENV === 'development') {
    console.log(`[Web Vital] ${metric.name}: ${metric.value.toFixed(1)} (${metric.rating})`)
  }
  // Send to analytics endpoint when available
  const endpoint = (window as Window & { __VITALS_ENDPOINT__?: string }).__VITALS_ENDPOINT__
  if (endpoint) {
    navigator.sendBeacon(endpoint, JSON.stringify(metric))
  }
}

export function useWebVitals() {
  useEffect(() => {
    onCLS(reportVital)
    onFID(reportVital)
    onLCP(reportVital)
    onFCP(reportVital)
    onTTFB(reportVital)
    onINP(reportVital)
  }, [])
}
