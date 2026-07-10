/**
 * Web Vitals reporter — sends Core Web Vitals to the telemetry endpoint.
 *
 * Metrics collected: CLS, LCP, TTFB, INP (FID removed in web-vitals v5).
 * Uses the `web-vitals` library (already in package.json).
 *
 * Call `reportWebVitals()` once from the app entry point.
 */

import type { Metric } from 'web-vitals'
import { API_BASE_URL } from '../config/apiBase'

const TELEMETRY_ENDPOINT =
  import.meta.env.VITE_TELEMETRY_ENDPOINT || `${API_BASE_URL}/api/v1/telemetry/web-vitals`

const SEND_BEACON_SUPPORTED = typeof navigator.sendBeacon === 'function'

function sendMetric(metric: Metric): void {
  const payload = {
    name: metric.name,
    value: metric.value,
    delta: metric.delta,
    id: metric.id,
    rating: metric.rating,
    navigationType:
      metric.navigationType ??
      (performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming | undefined)
        ?.type,
    url: location.href,
    timestamp: new Date().toISOString(),
  }

  if (import.meta.env.DEV) {
    // eslint-disable-next-line no-console
    console.log(`[WebVital] ${metric.name}: ${metric.value} (${metric.rating})`)
  }

  const body = JSON.stringify(payload)

  if (SEND_BEACON_SUPPORTED) {
    const blob = new Blob([body], { type: 'application/json' })
    navigator.sendBeacon(TELEMETRY_ENDPOINT, blob)
  } else {
    fetch(TELEMETRY_ENDPOINT, {
      method: 'POST',
      body,
      headers: { 'Content-Type': 'application/json' },
      keepalive: true,
    }).catch(() => {
      /* non-blocking */
    })
  }
}

export function reportWebVitals(): void {
  // web-vitals v5 removed onFID; INP is the interaction metric replacement.
  import('web-vitals').then(({ onCLS, onFCP, onLCP, onTTFB, onINP }) => {
    onCLS(sendMetric)
    onFCP(sendMetric)
    onLCP(sendMetric)
    onTTFB(sendMetric)
    onINP(sendMetric)
  })
}
