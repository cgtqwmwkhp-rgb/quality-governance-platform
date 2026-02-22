import type { Metric } from "web-vitals";
import { API_BASE_URL } from "../config/apiBase";

interface ErrorReport {
  message: string;
  stack?: string;
  componentStack?: string;
  url: string;
  timestamp: string;
  userAgent: string;
  userId?: number;
  sessionId?: string;
  sessionStartTime?: string;
  traceId?: string;
}

interface PerformanceReport {
  name: string;
  value: number;
  rating: string;
  navigationType: string;
  timestamp: string;
  sessionId?: string;
}

const DEDUP_WINDOW_MS = 60_000;

class ErrorReportingService {
  private queue: ErrorReport[] = [];
  private perfQueue: PerformanceReport[] = [];
  private flushInterval: ReturnType<typeof setInterval> | null = null;
  private recentErrors = new Map<string, number>();
  private sessionId: string = "";
  private sessionStartTime: string = "";
  private userId?: number;

  init() {
    this.sessionId =
      crypto.randomUUID?.() ?? Math.random().toString(36).slice(2);
    this.sessionStartTime = new Date().toISOString();

    window.addEventListener("error", (event) => {
      this.report({
        message: event.message,
        stack: event.error?.stack,
        url: window.location.href,
        timestamp: new Date().toISOString(),
        userAgent: navigator.userAgent,
      });
    });

    window.addEventListener("unhandledrejection", (event) => {
      this.report({
        message: String(event.reason),
        stack: event.reason?.stack,
        url: window.location.href,
        timestamp: new Date().toISOString(),
        userAgent: navigator.userAgent,
      });
    });

    this.initWebVitals();
    this.flushInterval = setInterval(() => this.flush(), 30000);
  }

  setUserId(userId: number) {
    this.userId = userId;
  }

  report(error: ErrorReport) {
    const key = `${error.message}::${error.stack ?? ""}`;
    const now = Date.now();
    const lastSeen = this.recentErrors.get(key);
    if (lastSeen && now - lastSeen < DEDUP_WINDOW_MS) {
      return;
    }
    this.recentErrors.set(key, now);

    // Prune old entries periodically
    if (this.recentErrors.size > 500) {
      for (const [k, ts] of this.recentErrors) {
        if (now - ts > DEDUP_WINDOW_MS) this.recentErrors.delete(k);
      }
    }

    error.sessionId = this.sessionId;
    error.sessionStartTime = this.sessionStartTime;
    if (this.userId) error.userId = this.userId;

    this.queue.push(error);
    if (this.queue.length >= 10) {
      this.flush();
    }
  }

  private initWebVitals() {
    import("web-vitals")
      .then(({ onCLS, onLCP, onFCP, onTTFB, onINP }) => {
        const handle = (metric: Metric) => {
          this.perfQueue.push({
            name: metric.name,
            value: metric.value,
            rating: metric.rating,
            navigationType: metric.navigationType,
            timestamp: new Date().toISOString(),
            sessionId: this.sessionId,
          });
        };
        onCLS(handle);
        onLCP(handle);
        onFCP(handle);
        onTTFB(handle);
        onINP(handle);
      })
      .catch(() => {
        // web-vitals not available
      });
  }

  private isValidBaseUrl(): boolean {
    return !!(
      API_BASE_URL &&
      API_BASE_URL !== "/" &&
      API_BASE_URL.startsWith("http")
    );
  }

  private async flush() {
    if (!this.isValidBaseUrl()) return;

    if (this.queue.length > 0) {
      const batch = this.queue.splice(0);
      try {
        await fetch(`${API_BASE_URL}/api/v1/telemetry/errors`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ errors: batch }),
        });
      } catch {
        this.queue.unshift(...batch);
      }
    }

    if (this.perfQueue.length > 0) {
      const perfBatch = this.perfQueue.splice(0);
      try {
        await fetch(`${API_BASE_URL}/api/v1/telemetry/performance`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ metrics: perfBatch }),
        });
      } catch {
        this.perfQueue.unshift(...perfBatch);
      }
    }
  }

  destroy() {
    if (this.flushInterval) clearInterval(this.flushInterval);
    this.flush();
  }
}

export const errorReporting = new ErrorReportingService();
