import type { Metric } from "web-vitals";
import { API_BASE_URL } from "../config/apiBase";

function getWebVitalsUrl(): string {
  const base = API_BASE_URL || "";
  if (!base || base === "/" || !base.startsWith("http")) {
    return "";
  }
  return `${base}/api/v1/telemetry/web-vitals`;
}

function reportMetric(metric: Metric) {
  const isProd = import.meta.env.PROD;

  if (!isProd) {
    console.debug(
      `[Web Vitals] ${metric.name}: ${metric.value.toFixed(2)} (${metric.rating})`,
    );
    return;
  }

  const url = getWebVitalsUrl();
  if (!url) return;

  const body = JSON.stringify({
    name: metric.name,
    value: metric.value,
    rating: metric.rating,
    delta: metric.delta,
    id: metric.id,
    navigationType: metric.navigationType,
  });

  try {
    if (navigator.sendBeacon) {
      const blob = new Blob([body], { type: "application/json" });
      navigator.sendBeacon(url, blob);
    } else {
      fetch(url, {
        method: "POST",
        body,
        headers: { "Content-Type": "application/json" },
        keepalive: true,
      }).catch(() => {});
    }
  } catch {
    // Silently ignore telemetry failures
  }
}

export function initWebVitals() {
  import("web-vitals").then(({ onCLS, onINP, onLCP, onFCP, onTTFB }) => {
    onCLS(reportMetric);
    onINP(reportMetric);
    onLCP(reportMetric);
    onFCP(reportMetric);
    onTTFB(reportMetric);
  });
}
