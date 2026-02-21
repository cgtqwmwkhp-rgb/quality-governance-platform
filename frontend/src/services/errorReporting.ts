interface ErrorReport {
  message: string;
  stack?: string;
  componentStack?: string;
  url: string;
  timestamp: string;
  userAgent: string;
  userId?: number;
}

class ErrorReportingService {
  private queue: ErrorReport[] = [];
  private flushInterval: ReturnType<typeof setInterval> | null = null;

  init() {
    window.addEventListener('error', (event) => {
      this.report({
        message: event.message,
        stack: event.error?.stack,
        url: window.location.href,
        timestamp: new Date().toISOString(),
        userAgent: navigator.userAgent,
      });
    });

    window.addEventListener('unhandledrejection', (event) => {
      this.report({
        message: String(event.reason),
        stack: event.reason?.stack,
        url: window.location.href,
        timestamp: new Date().toISOString(),
        userAgent: navigator.userAgent,
      });
    });

    this.flushInterval = setInterval(() => this.flush(), 30000);
  }

  report(error: ErrorReport) {
    this.queue.push(error);
    if (this.queue.length >= 10) {
      this.flush();
    }
  }

  private async flush() {
    if (this.queue.length === 0) return;
    const batch = this.queue.splice(0);
    try {
      await fetch('/api/v1/telemetry/errors', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ errors: batch }),
      });
    } catch {
      this.queue.unshift(...batch);
    }
  }

  destroy() {
    if (this.flushInterval) clearInterval(this.flushInterval);
  }
}

export const errorReporting = new ErrorReportingService();
