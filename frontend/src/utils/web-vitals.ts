import type { Metric } from 'web-vitals';

function reportMetric(metric: Metric) {
  const isProd = import.meta.env.PROD;

  if (!isProd) {
    console.debug(`[Web Vitals] ${metric.name}: ${metric.value.toFixed(2)} (${metric.rating})`);
    return;
  }

  // Report to telemetry endpoint in production
  const body = JSON.stringify({
    name: metric.name,
    value: metric.value,
    rating: metric.rating,
    delta: metric.delta,
    id: metric.id,
    navigationType: metric.navigationType,
  });

  // Use sendBeacon for reliable delivery during page unload
  if (navigator.sendBeacon) {
    navigator.sendBeacon('/api/telemetry/web-vitals', body);
  } else {
    fetch('/api/telemetry/web-vitals', {
      method: 'POST',
      body,
      headers: { 'Content-Type': 'application/json' },
      keepalive: true,
    }).catch(() => {});
  }
}

export function initWebVitals() {
  import('web-vitals').then(({ onCLS, onINP, onLCP, onFCP, onTTFB }) => {
    onCLS(reportMetric);
    onINP(reportMetric);
    onLCP(reportMetric);
    onFCP(reportMetric);
    onTTFB(reportMetric);
  });
}
